"""Results store (memory + files under backend/out) and the human-review update."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from . import compare as cmp
from . import config
from .config import FIELDS
from .flybrain import FlyBrain
from .rules_extract import Extracted


class Store:
    def __init__(self, out_dir: Path | None = None) -> None:
        self.out = Path(out_dir) if out_dir else config.OUT_DIR
        self.results: dict[str, dict] = {}
        self.states: dict[str, Any] = {}      # RunState for retry (memory only)
        self._load()

    # -- persistence ---------------------------------------------------
    def _load(self) -> None:
        p = self.out / "results.json"
        if p.is_file():
            try:
                self.results = json.loads(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                self.results = {}
        rd = self.out / "reviewed"
        if rd.is_dir():
            for f in rd.glob("email_*.json"):
                try:
                    r = json.loads(f.read_text(encoding="utf-8"))
                    self.results[r["email_id"]] = r
                except Exception:  # noqa: BLE001
                    pass

    def put(self, result: dict, state: Any = None) -> None:
        self.results[result["email_id"]] = result
        if state is not None:
            self.states[result["email_id"]] = state

    def persist_review(self, result: dict) -> None:
        rd = self.out / "reviewed"
        rd.mkdir(parents=True, exist_ok=True)
        (rd / f"{result['email_id']}.json").write_text(json.dumps(result), encoding="utf-8")

    def get(self, email_id: str) -> dict | None:
        return self.results.get(email_id)

    # -- views -----------------------------------------------------------
    @staticmethod
    def summary(r: dict) -> dict:
        keep = ("email_id", "category", "status", "review_reason", "has_defect", "defect_fields", "headline",
                "classifier_confidence", "comparison_performed")
        s = {k: r.get(k) for k in keep}
        g = r.get("gate") or {}
        s["gate"] = {k: g.get(k) for k in ("suspicion", "threshold", "escalate", "decided_by")} if g else None
        s["escalation_open"] = bool((r.get("escalation") or {}).get("open"))
        s["engine"] = r.get("engine")
        return s

    def stats(self, n_total: int) -> dict:
        rs = list(self.results.values())
        cls: dict[str, int] = {}
        issues: dict[str, int] = {}
        comps = mism = needs = disc = 0
        for r in rs:
            cls[r["category"]] = cls.get(r["category"], 0) + 1
            if r["category"] == "BL_COMPARISON":
                if r.get("comparison_performed"):
                    comps += 1
                if r.get("status") == "MISMATCH":
                    mism += 1
                    disc += len(r.get("defect_fields") or [])
                    for f in r.get("defect_fields") or []:
                        issues[f"{f} mismatch"] = issues.get(f"{f} mismatch", 0) + 1
                elif r.get("status") == "NEEDS_REVIEW":
                    needs += 1
                    k = f"needs review: {(r.get('review_reason') or 'uncertain').replace('_', ' ')}"
                    issues[k] = issues.get(k, 0) + 1
        acc = None
        sp = self.out / "score.json"
        if sp.is_file():
            try:
                acc = round(float(json.loads(sp.read_text(encoding="utf-8"))["final_score"]), 4)
            except Exception:  # noqa: BLE001
                acc = None
        top = sorted(({"label": k, "count": v} for k, v in issues.items()), key=lambda d: -d["count"])[:8]
        return {"emails_total": n_total, "processed": len(rs), "classified": cls, "comparisons": comps,
                "mismatches": mism, "needs_review": needs, "discrepancies_found": disc,
                "accuracy_vs_labels": acc, "top_issues": top}


# ---------------------------------------------------------------------------
# human review
# ---------------------------------------------------------------------------
def apply_review(result: dict, body: dict, gate: FlyBrain, state_path: Path | None = None) -> dict:
    """Apply a human decision to a Result and teach the fly gate. Returns the updated Result."""
    r = json.loads(json.dumps(result))       # deep copy, results are JSON-safe
    decision = body.get("decision")
    field = body.get("field")
    if decision not in ("confirm_mismatch", "confirm_ok", "correct_field"):
        raise ValueError("decision must be confirm_mismatch | confirm_ok | correct_field")
    was_escalated = (r.get("status") == "NEEDS_REVIEW") or bool((r.get("gate") or {}).get("escalate"))
    before_status = r.get("status")
    fields = r.get("fields") or []

    if decision == "correct_field":
        if field not in FIELDS:
            raise ValueError("correct_field needs a valid `field`")
        if len(fields) != len(FIELDS):
            raise ValueError("no field-level comparison exists for this email (documents missing/unreadable); "
                             "use confirm_ok / confirm_mismatch or supply the documents")
        by = {f["field"]: f for f in fields}
        cur = by.get(field) or {"field": field}
        si_v = body.get("corrected_si") if body.get("corrected_si") not in (None, "") else cur.get("si_value")
        bl_v = body.get("corrected_bl") if body.get("corrected_bl") not in (None, "") else cur.get("bl_value")
        new = cmp.compare_field(
            field,
            Extracted(field=field, value=si_v, evidence=(cur.get("si_evidence") or "") + " [human-corrected]" if body.get("corrected_si") else cur.get("si_evidence"),
                      confidence=1.0, flags=["human_corrected"] if body.get("corrected_si") else []),
            Extracted(field=field, value=bl_v, evidence=(cur.get("bl_evidence") or "") + " [human-corrected]" if body.get("corrected_bl") else cur.get("bl_evidence"),
                      confidence=1.0, flags=["human_corrected"] if body.get("corrected_bl") else []),
        )
        new["note"] = "corrected by reviewer"
        new["confidence"] = 1.0
        fields = [new if f["field"] == field else f for f in fields]
        dec = cmp.decide(fields)
        r["fields"] = fields
        r.update({"status": dec["status"], "review_reason": dec["review_reason"], "has_defect": dec["has_defect"],
                  "defect_fields": dec["defect_fields"], "headline": dec["headline"] + " (reviewed)"})
    elif decision == "confirm_ok":
        r.update({"status": "OK", "review_reason": None, "has_defect": False, "defect_fields": [],
                  "headline": "No mismatch detected (confirmed by reviewer)"})
    else:  # confirm_mismatch
        dfs = list(r.get("suspected_defect_fields") or []) or [f["field"] for f in fields if f.get("state") == "mismatch"]
        if field and field in FIELDS and field not in dfs:
            dfs.append(field)
        if not dfs:
            raise ValueError("confirm_mismatch needs a mismatching field (pass `field`)")
        dfs = sorted(dfs)
        r.update({"status": "MISMATCH", "review_reason": None, "has_defect": True, "defect_fields": dfs,
                  "headline": cmp.headline("MISMATCH", dfs, fields, None) + " (confirmed by reviewer)"})

    if r.get("escalation"):
        r["escalation"]["open"] = False
        r["escalation"]["resolved"] = True

    # ---- fly gate learning ------------------------------------------------------
    # Only teach the gate when the GATE itself made the escalation call (`decided_by == "flynet"`).
    # A deterministic trigger (missing_attachment/wrong_doc_type/unreadable/missing_value) bypasses
    # the gate entirely - it never decided anything there, so "was this escalation correct?" has no
    # gate-connection to reinforce or depress. Learning from it anyway was also why the shipped demo
    # showed a visible no-op: every deterministic case starts from the exact same untouched weights,
    # so "escalation was correct" (LTP) on an already-near-ceiling weight barely moves (see
    # DEFAULT_INIT_W in flybrain.py for the other half of that fix). Gate-decided (flynet) escalations
    # still learn exactly as before - that is the gate's real, measurable job.
    gate_info = r.get("gate") or {}
    vec = gate_info.get("input_vector")
    gate_decided = gate_info.get("decided_by") == "flynet"
    verdict = body.get("escalation_verdict")
    if verdict is None and vec and gate_decided:
        if decision == "correct_field":
            verdict = "escalation_correct"
        elif was_escalated:
            verdict = "escalation_unneeded"
    elif verdict is None and vec and not was_escalated and decision == "correct_field":
        verdict = "escalation_correct"      # a report the human had to correct should have been escalated
        gate_decided = True                 # the gate stayed silent when it should have flagged this
    fly = None
    if verdict in ("escalation_correct", "escalation_unneeded") and vec and gate_decided:
        fly = gate.learn(vec, verdict, note=f"{r['email_id']}: {decision}")
        fly["simulated"] = False
        if state_path:
            gate.save(state_path)
    elif verdict in ("escalation_correct", "escalation_unneeded") and vec and not gate_decided:
        fly = {"skipped": True, "reason": "this escalation was a deterministic trigger, not a fly-gate "
               "decision - no weight update applied (the gate never decided anything here to reinforce)"}
    r["review"] = {"decision": decision, "field": field, "corrected_si": body.get("corrected_si"),
                   "corrected_bl": body.get("corrected_bl"), "escalation_verdict": verdict,
                   "previous_status": before_status, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "fly": fly}
    return r
