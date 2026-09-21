"""The pipeline: inbox -> classifier -> 7 parallel field agents -> aggregator -> compare (pure) -> fly gate -> report.

Every node is a real call and emits trace events (CONTRACT.md). Engines:
    classifier / field agents : 'gemini' if a key exists (or forced), else 'rules'.  A failing Gemini node
                                emits a visible error event, falls back to its rules twin (engine='rules')
                                and is listed in Result.errors so it can be retried.
    aggregator / compare      : 'pure'  (no LLM)
    gate                      : 'flynet'
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from . import compare as cmp
from . import config, intake
from .classifier import ClassResult, classify_rules
from .config import FIELDS
from .docparse import ParsedDoc, parse_document
from .flybrain import FlyBrain, build_input_vector
from .inbox import Inbox
from .rules_extract import Extracted, extract_field

FIELD_NODES = [f"field:{f}" for f in FIELDS]


@dataclass
class RunState:
    """Everything needed to re-run only failed nodes (retry)."""
    email_id: str
    docs: list[ParsedDoc] = field(default_factory=list)
    classification: ClassResult | None = None
    field_out: dict[str, tuple[Extracted, Extracted]] = field(default_factory=dict)
    field_engine: dict[str, str] = field(default_factory=dict)
    errors: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    gate_vector: list[float] | None = None
    engine: str = "rules"


class Pipeline:
    def __init__(self, inbox: Inbox | None = None, gate: FlyBrain | None = None, gemini: Any = None,
                 default_engine: str | None = None) -> None:
        self.inbox = inbox or Inbox()
        self.gate = gate or FlyBrain.load_or_calibrate(None)
        self._gemini = gemini
        self.default_engine = default_engine or config.default_engine()

    # ------------------------------------------------------------------
    def gemini_client(self):
        if self._gemini is None:
            from .llm import GeminiClient
            self._gemini = GeminiClient()
        return self._gemini

    def resolve_engine(self, force: str | None = None) -> str:
        eng = force or self.default_engine
        if eng == "gemini" and self._gemini is None and not config.gemini_key():
            return "rules"          # never pretend: no key, no injected client -> rules
        return eng if eng in ("rules", "gemini") else "rules"

    # ------------------------------------------------------------------
    async def run(self, email_id: str, *, force_engine: str | None = None, inject_fail: set[str] | None = None,
                  prior: RunState | None = None, on_event: Callable[[dict], None] | None = None
                  ) -> tuple[dict, RunState]:
        email = self.inbox.get(email_id)
        if email is None:
            raise KeyError(email_id)
        engine = self.resolve_engine(force_engine)
        retry = prior is not None
        st = prior or RunState(email_id=email_id)
        st.engine = engine
        inject = set(inject_fail or ())
        t0 = time.perf_counter()
        seq0 = (max((e["seq"] for e in st.events), default=-1) + 1) if retry else 0
        new_events: list[dict] = []

        def ev(node: str, state: str, eng: str | None, summary: str, payload: dict | None = None,
               dur: float | None = None) -> None:
            e = {"seq": seq0 + len(new_events), "t_ms": int((time.perf_counter() - t0) * 1000), "node": node,
                 "state": state, "engine": eng, "duration_ms": None if dur is None else int(dur * 1000),
                 "summary": summary, "payload": payload or {}}
            new_events.append(e)
            if on_event:
                on_event(e)

        failed_nodes = {e["node"] for e in st.errors} if retry else set()

        # ---- inbox / intake ------------------------------------------------
        if not retry or not st.docs:
            ev("inbox", "start", "pure", f"reading {email_id}")
            t = time.perf_counter()
            paths = [self.inbox.attachment_path(a) for a in email.get("attachments", [])]
            st.docs = await asyncio.gather(*[asyncio.to_thread(parse_document, p) for p in paths]) if paths else []
            st.docs = list(st.docs)
            ev("inbox", "done", "pure",
               f"{len(st.docs)} attachment(s) opened" if st.docs else "no attachments",
               {"email_id": email_id, "from": email.get("from"), "subject": email.get("subject"),
                "attachments": [d.to_dict() for d in st.docs]}, time.perf_counter() - t)

        # ---- classifier ----------------------------------------------------
        if st.classification is None or "classifier" in failed_nodes:
            st.errors = [e for e in st.errors if e["node"] != "classifier"]
            ev("classifier", "start", engine, "classifying")
            t = time.perf_counter()
            names = [d.name for d in st.docs]
            cls: ClassResult | None = None
            if engine == "gemini":
                try:
                    if "classifier" in inject:
                        raise RuntimeError("injected failure (demo)")
                    from .llm import classify_gemini
                    cls = await classify_gemini(self.gemini_client(), email, names)
                except Exception as e:  # noqa: BLE001
                    msg = f"{type(e).__name__}: {e}"
                    st.errors.append({"node": "classifier", "message": msg, "retriable": True, "fallback": "rules"})
                    ev("classifier", "error", "gemini", f"Gemini classifier failed: {msg[:160]}", {"error": msg},
                       time.perf_counter() - t)
            elif "classifier" in inject:
                msg = "injected failure (demo)"
                st.errors.append({"node": "classifier", "message": msg, "retriable": True, "fallback": None})
                ev("classifier", "error", "rules", msg, {"error": msg}, time.perf_counter() - t)
            if cls is None and not any(e["node"] == "classifier" and not e.get("fallback") for e in st.errors):
                cls = await asyncio.to_thread(classify_rules, email, names)
            if cls is not None:
                st.classification = cls
                ev("classifier", "done", cls.engine,
                   f"{cls.category} ({cls.confidence:.2f})", cls.to_payload(), time.perf_counter() - t)
        cls = st.classification
        if cls is None:      # classifier failed and no fallback allowed: report the failure visibly
            return self._finish_error(email, st, ev, new_events, "classifier failed"), st

        result = self._base_result(email, cls, st)

        # ---- non-comparison categories stop here ---------------------------------
        if cls.category != "BL_COMPARISON":
            result.update({"status": None, "headline": f"Classified as {cls.category} - no document comparison needed"})
            return self._finalize(result, st, ev, new_events), st

        # ---- intake / preflight ------------------------------------------------
        it = intake.assess(st.docs, email.get("body", ""))
        if it.no_docs_requested or it.reason:
            return await self._no_compare(email, cls, st, it, result, ev, new_events), st

        si, bl = it.si, it.bl
        assert si is not None and bl is not None

        # ---- 7 parallel field agents ----------------------------------------------
        todo = [f for f in FIELDS if f not in st.field_out or f"field:{f}" in failed_nodes]
        st.errors = [e for e in st.errors if e["node"] not in {f"field:{f}" for f in todo}]

        async def field_agent(f: str) -> None:
            node = f"field:{f}"
            ev(node, "start", engine, f"reading {f} in SI and BL")
            t = time.perf_counter()
            out: tuple[Extracted, Extracted] | None = None
            used = engine
            if engine == "gemini":
                try:
                    if node in inject:
                        raise RuntimeError("injected failure (demo)")
                    from .llm import extract_field_gemini
                    out = await extract_field_gemini(self.gemini_client(), f, si, bl)
                except Exception as e:  # noqa: BLE001
                    msg = f"{type(e).__name__}: {e}"
                    st.errors.append({"node": node, "message": msg, "retriable": True, "fallback": "rules"})
                    ev(node, "error", "gemini", f"Gemini failed: {msg[:160]}", {"error": msg}, time.perf_counter() - t)
                    used = "rules"
            elif node in inject:
                msg = "injected failure (demo)"
                st.errors.append({"node": node, "message": msg, "retriable": True, "fallback": None})
                ev(node, "error", "rules", msg, {"error": msg}, time.perf_counter() - t)
                return
            if out is None:
                try:
                    out = await asyncio.to_thread(lambda: (extract_field(si, f), extract_field(bl, f)))
                except Exception as e:  # noqa: BLE001
                    msg = f"{type(e).__name__}: {e}"
                    st.errors.append({"node": node, "message": msg, "retriable": True, "fallback": None})
                    ev(node, "error", "rules", msg, {"error": msg}, time.perf_counter() - t)
                    return
            s, b = out
            st.field_out[f] = (s, b)
            st.field_engine[f] = used
            ev(node, "done", used, f"{f}: SI {s.value!r} | BL {b.value!r}",
               {"field": f, "si_value": s.value, "bl_value": b.value, "si_evidence": s.evidence,
                "bl_evidence": b.evidence, "confidence": round(min(s.confidence, b.confidence), 3),
                "flags": sorted(set(s.flags + b.flags))}, time.perf_counter() - t)

        await asyncio.gather(*[field_agent(f) for f in todo])

        # ---- aggregator -----------------------------------------------------------
        ev("aggregator", "start", "pure", "collating field agent outputs")
        t = time.perf_counter()
        fields_raw: dict[str, tuple[Extracted, Extracted]] = st.field_out
        agent_fail = [f for f in FIELDS if f not in fields_raw]
        ev("aggregator", "done", "pure",
           f"{len(fields_raw)}/7 field agents reported" + (f"; failed: {', '.join(agent_fail)}" if agent_fail else ""),
           {"reported": sorted(fields_raw), "failed": agent_fail,
            "si_doc": si.name, "bl_doc": bl.name}, time.perf_counter() - t)

        # ---- compare (pure) -------------------------------------------------------
        ev("compare", "start", "pure", "comparing SI (reference) against BL")
        t = time.perf_counter()
        empty = Extracted(field="", value=None, flags=["not_found"])
        fields = [cmp.compare_field(f, fields_raw[f][0] if f in fields_raw else empty,
                                    fields_raw[f][1] if f in fields_raw else empty) for f in FIELDS]
        for fr, f in zip(fields, FIELDS):
            if f in agent_fail:
                fr["note"] = "field agent failed - retry the node"
        decision = cmp.decide(fields)
        ev("compare", "done", "pure", decision["headline"], {"fields": fields}, time.perf_counter() - t)

        # ---- fly gate -------------------------------------------------------------
        fallback = any(e.get("fallback") for e in st.errors)
        doc_conf = min(si.type_confidence, bl.type_confidence)
        ocr = si.ocr_used or bl.ocr_used
        x = build_input_vector(fields, classifier_conf=cls.confidence, doc_type_conf=doc_conf, ocr_used=ocr,
                               engine_fallback=fallback, doc_trigger=False)
        st.gate_vector = [float(v) for v in x]
        det = decision["review_reason"] if decision["status"] == "NEEDS_REVIEW" else None
        ev("gate", "start", "flynet", "fly-brain confidence gate")
        t = time.perf_counter()
        gd = self.gate.decide(x, deterministic_reason=det)
        gate = gd.to_payload()
        gate["decided_by"] = "deterministic_trigger" if det else "flynet"
        ev("gate", "done", "flynet",
           f"suspicion {gd.suspicion:.2f} vs {gd.threshold:.2f} -> {'ESCALATE' if gd.escalate else 'report'}",
           gate, time.perf_counter() - t)

        status = decision["status"]
        review_reason = decision["review_reason"]
        review_detail = decision.get("review_detail")
        suspected: list[str] = []
        if gd.escalate and status in ("OK", "MISMATCH"):
            suspected = list(decision["defect_fields"])
            status = "NEEDS_REVIEW"
            review_reason = "unreadable" if ocr else "missing_value"
            review_detail = gd.reason
            decision = {**decision, "status": status, "review_reason": review_reason, "has_defect": False,
                        "defect_fields": [], "headline": cmp.headline(status, [], fields, review_reason, "low confidence")}
        result.update({
            "status": status, "review_reason": review_reason, "has_defect": decision["has_defect"],
            "defect_fields": decision["defect_fields"], "headline": decision["headline"],
            "fields": fields, "gate": gate, "review_detail": review_detail,
            "suspected_defect_fields": suspected,
            "comparison_performed": True,
            "docs": {"si": si.to_dict(), "bl": bl.to_dict()},
            "engine": {"classifier": cls.engine, "fields": _fields_engine(st, engine)},
        })
        if status == "NEEDS_REVIEW":
            result["escalation"] = {"open": True, "reason": _escalation_reason(review_reason, review_detail),
                                    "evidence": _evidence(fields, review_reason), "resolved": False}
        return self._finalize(result, st, ev, new_events), st

    # ------------------------------------------------------------------
    async def _no_compare(self, email, cls, st, it, result, ev, new_events) -> dict:
        for n in FIELD_NODES:
            ev(n, "skipped", None, "not run: " + (it.reason or "no documents to compare"))
        ev("aggregator", "start", "pure", "attachment preflight")
        ev("aggregator", "done", "pure", it.detail or "", {"preflight": it.reason or "no_documents_requested",
                                                             "detail": it.detail})
        ev("compare", "skipped", "pure", "nothing to compare")
        empty_fields = [cmp.compare_field(f, None, None) for f in FIELDS]
        if it.no_docs_requested:
            ev("gate", "skipped", "flynet", "no comparison performed")
            result.update({"status": "OK", "review_reason": None, "has_defect": False, "defect_fields": [],
                           "headline": "No documents to compare - draft BL requested", "fields": [],
                           "comparison_performed": False, "review_detail": it.detail, "gate": None,
                           "engine": {"classifier": cls.engine, "fields": None}})
            return self._finalize(result, st, ev, new_events)
        x = build_input_vector(empty_fields, classifier_conf=cls.confidence, doc_trigger=True)
        st.gate_vector = [float(v) for v in x]
        ev("gate", "start", "flynet", "fly-brain confidence gate")
        gd = self.gate.decide(x, deterministic_reason=it.reason)
        gate = gd.to_payload()
        gate["decided_by"] = "deterministic_trigger"
        ev("gate", "done", "flynet", f"deterministic trigger: {it.reason} (fly-net suspicion {gd.suspicion:.2f})", gate)
        result.update({
            "status": "NEEDS_REVIEW", "review_reason": it.reason, "has_defect": False, "defect_fields": [],
            "headline": cmp.headline("NEEDS_REVIEW", [], [], it.reason, it.detail), "fields": [],
            "comparison_performed": False, "review_detail": it.detail, "gate": gate,
            "engine": {"classifier": cls.engine, "fields": None},
            "escalation": {"open": True, "reason": _escalation_reason(it.reason, it.detail),
                           "evidence": it.evidence, "resolved": False},
            "docs": {"attachments": [d.to_dict() for d in st.docs]},
        })
        return self._finalize(result, st, ev, new_events)

    # ------------------------------------------------------------------
    def _base_result(self, email: dict, cls: ClassResult, st: RunState) -> dict:
        s = self.inbox.summary(email["email_id"])
        return {
            **{k: s[k] for k in ("email_id", "from", "subject", "received_at")},
            "has_attachments": s["has_attachments"],
            "category": cls.category, "classifier_confidence": cls.confidence,
            "status": None, "review_reason": None, "has_defect": False, "defect_fields": [],
            "headline": "", "fields": [], "gate": None, "escalation": None,
            "engine": {"classifier": cls.engine, "fields": None}, "errors": [], "review": None,
        }

    def _finalize(self, result: dict, st: RunState, ev, new_events: list[dict]) -> dict:
        result["errors"] = list(st.errors)
        ev("report", "done", "pure", result.get("headline") or result["category"],
           {k: v for k, v in result.items() if k != "events"})
        st.events = st.events + new_events
        result["events"] = list(st.events)
        return result

    def _finish_error(self, email, st, ev, new_events, msg: str) -> dict:
        r = {"email_id": email["email_id"], "from": email.get("from"), "subject": email.get("subject"),
             "received_at": self.inbox.received_at(email["email_id"]), "category": "GENERAL", "status": None,
             "review_reason": None, "has_defect": False, "defect_fields": [], "headline": f"Processing failed: {msg}",
             "fields": [], "gate": None, "escalation": None, "engine": {"classifier": None, "fields": None},
             "errors": list(st.errors)}
        ev("report", "error", "pure", r["headline"], {"errors": st.errors})
        st.events = st.events + new_events
        r["events"] = list(st.events)
        return r


def _fields_engine(st: RunState, engine: str) -> str:
    used = set(st.field_engine.values())
    if not used:
        return engine
    return next(iter(used)) if len(used) == 1 else "mixed(" + "+".join(sorted(used)) + ")"


def _escalation_reason(reason: str | None, detail: str | None) -> str:
    base = {
        "missing_attachment": "A document is missing, so SI and BL cannot be compared.",
        "wrong_doc_type": "An attachment is not the expected document type.",
        "unreadable": "A document could not be read reliably.",
        "missing_value": "A required value is missing or the extraction is not confident enough.",
    }.get(reason or "", "The system could not decide confidently.")
    return f"{base} {detail}" if detail else base


def _evidence(fields: list[dict], reason: str | None) -> list[dict]:
    ev: list[dict] = []
    for f in fields:
        interesting = f["state"] == "missing" or (reason in ("missing_value", "unreadable") and f["state"] == "mismatch") \
            or f.get("near_miss") or (f.get("confidence") or 0) < 0.6
        if not interesting:
            continue
        if f.get("si_evidence"):
            ev.append({"doc": "SI", "field": f["field"], "text": f["si_evidence"]})
        if f.get("bl_evidence"):
            ev.append({"doc": "BL", "field": f["field"], "text": f["bl_evidence"]})
    return ev[:14]
