"""Held-out grey-zone evaluation for the fly-brain gate (reviews/developer.md / judge.md item #1).

WHY THIS FILE EXISTS
    The gate's ``calibrate()`` report in ``flybrain.py`` trains AND evaluates on synthetic 32-d
    vectors it also generates itself - a legitimate sanity check that the architecture works, but
    circular (same author, same input semantics, never touches a real document). On the real
    520-email set the gate almost never gets to decide anything on its own: every NEEDS_REVIEW case
    is a deterministic trigger (missing_attachment/wrong_doc_type/unreadable/missing_value), which
    bypasses the gate by design. That leaves the gate's OWN job unmeasured.

WHAT THIS SCRIPT DOES INSTEAD
    Builds real SI/BL document PAIRS from the bundle's own clean .txt attachments (the same 84
    OK/MISMATCH BL_COMPARISON txt pairs used for the classifier/layout perturbation checks),
    applies hand-written, realistic mutations that are genuinely ambiguous or genuinely NOT
    ambiguous, and reruns them through the REAL pipeline (parse -> extract -> compare -> gate) -
    not a synthetic vector. Only ``decided_by == "flynet"`` escalations count as "the gate did
    something"; deterministic triggers are excluded on purpose (they are not the gate's job).

    This is intentionally separate from ``python -m sdoc.run_all`` / ``score_cli.py``: it never
    touches ``ground_truth.json``, never feeds the official 520-email score, and is not run as
    part of the submission. It answers one question only: "does the gate correctly tell confident
    reports from genuinely uncertain ones, on data it never trained or calibrated on?"

BUCKETS (gold label = should a human be asked to double-check this, yes/no)
    clean            (gold: NO)  - unmodified real SI/BL pair.
    clean_defect     (gold: NO)  - one confident, unambiguous defect injected (weight +500kg).
                                   A confirmed real mismatch must be reported, not gated away.
    near_miss_typo   (gold: YES) - a one-letter typo in the BL consignee name (near-miss, not a
                                   confident value swap - could be a defect OR a typo).
    conflicting_line (gold: YES) - a look-alike second "weight" line added to the BL, so the
                                   extractor has two plausible candidate values.
    ambiguous_role   (gold: YES) - both attachments' title lines are stripped so doc-type
                                   detection cannot confidently tell SI from BL (role assignment
                                   falls back to file order) - the literal "ambiguous SI/BL role
                                   assignment" case named in reviews/judge.md item #1.

Run (from backend/):  python -m tools.grey_zone_eval
Writes backend/out/grey_zone_eval.json; numbers are summarised in backend/README.md.
"""
from __future__ import annotations

import asyncio
import json
import random
import re
import shutil
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sdoc.flybrain import FlyBrain  # noqa: E402
from sdoc.inbox import Inbox  # noqa: E402
from sdoc.pipeline import Pipeline  # noqa: E402

BUNDLE = BACKEND_DIR.parent / "work" / "bundle"
SCRATCH = BACKEND_DIR / "out" / "_grey_zone_scratch"
OUT_PATH = BACKEND_DIR / "out" / "grey_zone_eval.json"

_CONSIGNEE_RE = re.compile(r"(?m)^((?:Consignee[^:\n]*|CONSIGNEE|To the Order of):\s*)(.+)$")
_WEIGHT_RE = re.compile(r"(?m)^((?:Gross|GROSS)[^:\n]*:\s*)(\d[\d,]*)(.*)$")


def _eligible_pairs() -> list[dict]:
    """Real BL_COMPARISON emails whose SI+BL are both plain .txt (readable without any format
    quirk getting in the way) - the same population used for the classifier/layout checks."""
    inbox = Inbox()
    out = []
    for eid in inbox.ids():
        e = inbox.get(eid)
        atts = e.get("attachments", [])
        if len(atts) == 2 and all(a.endswith(".txt") for a in atts):
            out.append(e)
    return out


def _typo(bl: str) -> str:
    def rep(m: re.Match) -> str:
        v = m.group(2)
        j = len(v) // 2
        return m.group(1) + v[:j] + ("X" if v[j] != "X" else "Y") + v[j + 1:]
    return _CONSIGNEE_RE.sub(rep, bl, count=1)


def _conflicting_line(bl: str) -> str:
    lines = bl.split("\n")
    lines.insert(min(3, len(lines)), "Gross Weight of container: 2,000 KG")
    return "\n".join(lines)


def _confident_defect(bl: str) -> str:
    def rep(m: re.Match) -> str:
        n = int(m.group(2).replace(",", ""))
        return m.group(1) + f"{n + 500:,}" + m.group(3)
    return _WEIGHT_RE.sub(rep, bl, count=1)


def _strip_title(doc_text: str) -> str:
    """Remove the first non-blank line (the 'SHIPPING INSTRUCTION' / 'BILL OF LADING (DRAFT)'
    title) so doc-type detection loses its main signal - SI/BL role assignment then falls back
    to file order/hints instead of a confident title match."""
    lines = doc_text.split("\n")
    for i, l in enumerate(lines):
        if l.strip():
            lines[i] = ""
            break
    return "\n".join(lines)


MUTATIONS = {
    "clean": (lambda si, bl: (si, bl), False),
    "clean_defect": (lambda si, bl: (si, _confident_defect(bl)), False),
    "near_miss_typo": (lambda si, bl: (si, _typo(bl)), False),
    "conflicting_line": (lambda si, bl: (si, _conflicting_line(bl)), False),
    "ambiguous_role": (lambda si, bl: (_strip_title(si), _strip_title(bl)), True),
}
GOLD_ESCALATE = {"clean": False, "clean_defect": False, "near_miss_typo": True,
                  "conflicting_line": True, "ambiguous_role": True}


def _build(name: str, pairs: list[dict], mut, rename_generic: bool) -> tuple[Path, list[str]]:
    d = SCRATCH / name
    if d.exists():
        shutil.rmtree(d)
    (d / "inbox").mkdir(parents=True)
    (d / "attachments").mkdir()
    ids = []
    for e in pairs:
        si_path, bl_path = e["attachments"]
        si = (BUNDLE / si_path).read_text(encoding="utf-8")
        bl = (BUNDLE / bl_path).read_text(encoding="utf-8")
        si2, bl2 = mut(si, bl)
        e2 = dict(e)
        if rename_generic:
            # generic file names too, so the role-hint-from-filename fallback can't rescue it
            new_atts = [f"attachments/{e['email_id']}_doc1.txt", f"attachments/{e['email_id']}_doc2.txt"]
        else:
            new_atts = [si_path, bl_path]
        for path, text in zip(new_atts, (si2, bl2)):
            (d / path).write_text(text, encoding="utf-8")
        e2["attachments"] = new_atts
        (d / "inbox" / f"{e['email_id']}.json").write_text(json.dumps(e2), encoding="utf-8")
        ids.append(e["email_id"])
    return d, ids


async def _run_all(root: Path, ids: list[str]) -> dict[str, dict]:
    inbox = Inbox(root)
    pipe = Pipeline(inbox=inbox, gate=FlyBrain.load_or_calibrate(None), default_engine="rules")
    res: dict[str, dict] = {}
    sem = asyncio.Semaphore(8)

    async def one(eid: str) -> None:
        async with sem:
            r, _ = await pipe.run(eid)
            res[eid] = r
    await asyncio.gather(*[one(i) for i in ids])
    return res


def main(n_per_bucket: int = 40, seed: int = 20260921) -> dict:
    all_pairs = _eligible_pairs()
    rng = random.Random(seed)
    rng.shuffle(all_pairs)
    sample = all_pairs[:n_per_bucket]
    report: dict[str, dict] = {}
    confusion = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for name, (mut, rename_generic) in MUTATIONS.items():
        root, ids = _build(name, sample, mut, rename_generic)
        results = asyncio.run(_run_all(root, ids))
        gold = GOLD_ESCALATE[name]
        gate_escalated = 0
        deterministic = 0
        examples = []
        for eid in ids:
            r = results[eid]
            g = r.get("gate") or {}
            if g.get("decided_by") == "flynet" and g.get("escalate"):
                gate_escalated += 1
                if gold:
                    confusion["tp"] += 1
                else:
                    confusion["fp"] += 1
                if len(examples) < 3:
                    examples.append({"email_id": eid, "suspicion": g.get("suspicion"), "reason": g.get("reason")})
            else:
                if gold:
                    confusion["fn"] += 1
                else:
                    confusion["tn"] += 1
        report[name] = {
            "n": len(ids), "gold_escalate": gold,
            "gate_escalated_flynet": gate_escalated,
            "gate_escalation_rate": round(gate_escalated / len(ids), 3) if ids else None,
            "example_gate_decisions": examples,
        }
        shutil.rmtree(root, ignore_errors=True)
    tp, fp, tn, fn = confusion["tp"], confusion["fp"], confusion["tn"], confusion["fn"]
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall and (precision + recall) else None
    summary = {
        "method": "real SI/BL document pairs from the bundle's own clean .txt attachments, "
                  "hand-mutated, run through the full parse->extract->compare->gate pipeline "
                  "(not synthetic 32-d vectors) - independent of flybrain.py's own calibration report",
        "n_per_bucket": len(sample), "buckets": report, "confusion": confusion,
        "gate_precision_on_flagged": round(precision, 3) if precision is not None else None,
        "gate_recall_on_should_escalate": round(recall, 3) if recall is not None else None,
        "gate_f1": round(f1, 3) if f1 is not None else None,
        "note": "counts only decided_by=='flynet' escalations; deterministic triggers "
                "(missing_attachment/wrong_doc_type/unreadable/missing_value) are excluded by "
                "design - they bypass the gate and are not part of its measured job. This does "
                "NOT feed the official 520-email score.",
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    shutil.rmtree(SCRATCH, ignore_errors=True)
    return summary


if __name__ == "__main__":
    s = main()
    print(json.dumps({k: v for k, v in s.items() if k != "buckets"}, indent=2))
    for name, b in s["buckets"].items():
        print(f"  {name:18s} n={b['n']:3d} gold_escalate={str(b['gold_escalate']):5s} "
              f"gate_escalated={b['gate_escalated_flynet']:3d} rate={b['gate_escalation_rate']}")
