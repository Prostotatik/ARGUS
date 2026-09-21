"""Document intake: role assignment (SI vs BL) + deterministic preflight for a comparison request.

Pure logic over ParsedDoc objects and the email body. Decides, before any field extraction,
whether a comparison is possible at all:

    missing_attachment | wrong_doc_type | unreadable | (None = go ahead and compare)

A comparison request with no attachments that merely *asks for* the draft BL ("please send the draft BL")
is not a failed comparison: nothing was supplied, nothing is escalated (``no_docs_requested``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .classifier import clean_body
from .docparse import ParsedDoc

_CLAIMS_DOCS = re.compile(
    r"\battached\b|\battaching\b|\benclosed\b|\battachments?\b|\bcompare\s+the\s+SI\b|"
    r"\bcheck\s+the\s+draft\s+B/?L\s+against\b|\bfile\s+(?:appears|will)\b|\bwill\s+not\s+open\b", re.I)
_ASKS_DOCS = re.compile(r"\b(?:send|provide|share|forward)\s+(?:us\s+)?(?:the\s+)?draft\s+B/?L\b", re.I)

_TYPE_NAMES = {
    "INVOICE": "Commercial Invoice", "PACKING_LIST": "Packing List", "COO": "Certificate of Origin",
    "SI": "Shipping Instruction", "BL": "Bill of Lading", "UNKNOWN": "unrecognised document",
}


@dataclass
class Intake:
    si: ParsedDoc | None = None
    bl: ParsedDoc | None = None
    reason: str | None = None            # missing_attachment | wrong_doc_type | unreadable
    detail: str | None = None
    no_docs_requested: bool = False      # comparison not possible yet, but not a failure
    evidence: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.reason is None and not self.no_docs_requested and self.si is not None and self.bl is not None


def assess(docs: list[ParsedDoc], body: str) -> Intake:
    it = Intake()
    cb = clean_body(body or "")
    if not docs:
        if _ASKS_DOCS.search(cb) and not _CLAIMS_DOCS.search(cb):
            it.no_docs_requested = True
            it.detail = "requester asks for the draft BL; no documents attached yet - nothing to compare"
            it.evidence = [{"doc": "email", "field": None, "text": _snippet(cb)}]
            return it
        it.reason = "missing_attachment"
        it.detail = "comparison requested but the email has no attachments"
        it.evidence = [{"doc": "email", "field": None, "text": _snippet(cb)}]
        return it

    bad = [d for d in docs if not d.readable]
    if bad:
        it.reason = "unreadable"
        it.detail = "; ".join(f"{d.name}: {d.status_detail or d.status}" for d in bad)
        it.evidence = [{"doc": d.name, "field": None, "text": d.status_detail or d.status} for d in bad]
        return it

    si_c = [d for d in docs if d.doc_type == "SI"]
    bl_c = [d for d in docs if d.doc_type == "BL"]
    others = [d for d in docs if d.doc_type not in ("SI", "BL")]
    wrong = [d for d in others if d.doc_type != "UNKNOWN"]

    if wrong:
        d = wrong[0]
        it.reason = "wrong_doc_type"
        it.detail = f"{d.name} is a {_TYPE_NAMES[d.doc_type]}, not a Shipping Instruction / draft Bill of Lading"
        it.evidence = [{"doc": d.name, "field": None, "text": d.type_evidence or _TYPE_NAMES[d.doc_type]}]
        return it

    si = si_c[0] if si_c else None
    bl = bl_c[0] if bl_c else None
    # untyped documents: fall back to the file-name hint, then to the order of attachment
    unknown = [d for d in others if d.doc_type == "UNKNOWN"]
    for d in unknown:
        if d.role_hint == "SI" and si is None:
            si = d
        elif d.role_hint == "BL" and bl is None:
            bl = d
    for d in unknown:
        if d is si or d is bl:
            continue
        if si is None:
            si = d
        elif bl is None:
            bl = d

    if len(docs) == 1:
        d = docs[0]
        it.reason = "missing_attachment"
        it.detail = f"only one document attached ({d.name}, {_TYPE_NAMES.get(d.doc_type, d.doc_type)}); the counterpart is missing"
        it.evidence = [{"doc": d.name, "field": None, "text": it.detail}]
        return it
    if si is None or bl is None:
        # two documents of the same type (e.g. SI + SI) -> not a comparable SI/BL pair
        types = ", ".join(d.doc_type for d in docs)
        it.reason = "wrong_doc_type"
        it.detail = f"attachments are not an SI + BL pair ({types})"
        it.evidence = [{"doc": d.name, "field": None, "text": d.type_evidence or d.doc_type} for d in docs]
        return it
    it.si, it.bl = si, bl
    return it


def _snippet(text: str, n: int = 200) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t[:n] + ("..." if len(t) > n else "")
