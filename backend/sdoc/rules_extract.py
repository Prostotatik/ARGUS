"""Deterministic (offline) field extraction from a ParsedDoc.

This is the *rules* twin of the Gemini field agent. It works only on the label/value line
intermediate produced by ``docparse`` and aligns labels by meaning (``labels.py``).
No ground truth, no generator internals: only generic layout heuristics
("Label: value", "Label   value", label on one line and value on the next, "value | address" cells).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import normalize as nz
from .docparse import ParsedDoc
from .labels import match_label, match_label_prefix_words

_CONTAINER_NO = re.compile(r"\b[A-Z]{4}\d{7}\b")
_LABEL_LIKE = re.compile(r"^[^:：]{1,60}[:：]\s")


@dataclass
class Extracted:
    field: str
    value: str | None = None          # raw text as read from the document (None = not found)
    evidence: str | None = None       # the source line
    confidence: float = 0.0
    flags: list[str] = field(default_factory=list)   # blank | not_found | placeholder | fuzzy_label | ambiguous | conflict | inconsistent
    engine: str = "rules"

    @property
    def blank(self) -> bool:
        return self.value is None or "blank" in self.flags or "not_found" in self.flags

    def to_dict(self) -> dict:
        return {"field": self.field, "value": self.value, "evidence": self.evidence,
                "confidence": round(self.confidence, 3), "flags": list(self.flags), "engine": self.engine}


# ---------------------------------------------------------------------------
def _label_candidates(label: str) -> list[str]:
    """Extra label variants: PDF renderers turn CJK glyphs into junk cells 'A | II | (KGS)'."""
    out = [label]
    if "|" in label:
        segs = [s.strip() for s in label.split("|") if s.strip()]
        if segs:
            out.append(segs[0])
            if len(segs) > 1:
                out.append(segs[0] + " " + segs[-1])
    return out


def _match_any(label: str, *, exact_only: bool = False) -> tuple[str | None, bool]:
    fuzzy: tuple[str | None, bool] = (None, False)
    for c in _label_candidates(label):
        f, exact = match_label(c, exact_only=exact_only)
        if f and exact:
            return f, True          # an exact synonym in any variant beats a fuzzy hit
        if f and fuzzy[0] is None:
            fuzzy = (f, False)
    return fuzzy


def split_line(line: str) -> tuple[str, str, str] | None:
    """Return (canonical_field, value, kind) for a 'label: value' style line, else None.

    Accepted separators: colon, whitespace-column, ' - ', ' = ', and a markdown-table row
    (``| Label | value |``). A candidate is only accepted when the text left of the separator
    actually resolves to a known field synonym (``_match_any``), so a value that happens to
    contain a dash/equals ("Jebel Ali - UAE") is never mistaken for a label line.

    kind: 'exact' | 'fuzzy'.
    """
    s = line.strip()
    if not s:
        return None
    # markdown table row: '| Label | value |' (also '| Label | value | extra |')
    if s.startswith("|") and s.count("|") >= 2:
        segs = [x.strip() for x in s.strip("|").split("|")]
        if len(segs) >= 2 and segs[0]:
            f, exact = _match_any(segs[0], exact_only=True)
            if f:
                val = " | ".join(x for x in segs[1:] if x)
                return f, val, "exact" if exact else "fuzzy"
    # colon separated: try each colon as the label/value boundary (label may contain ';' or '(:)')
    idx = [m.start() for m in re.finditer(r"[:：]", s)][:4]
    for i in idx:
        label, value = s[:i].strip(), s[i + 1:].strip()
        f, exact = _match_any(label)
        if f:
            return f, value, "exact" if exact else "fuzzy"
    # whitespace-column layout: 'Port of Loading      SINGAPORE'
    m = re.match(r"^(.{3,60}?)(?:\t+|\s{3,})(\S.*)$", s)
    if m:
        f, exact = _match_any(m.group(1).strip())
        if f:
            return f, m.group(2).strip(), "exact" if exact else "fuzzy"
    # dash / equals separated: 'Label - value' / 'Label = value'
    m = re.match(r"^(.{2,60}?)\s+[-=]\s+(\S.*)$", s)
    if m:
        f, exact = _match_any(m.group(1).strip(), exact_only=True)
        if f:
            return f, m.group(2).strip(), "exact" if exact else "fuzzy"
    # separator-free 'Label value' (seen on OCR-read scanned documents, which often drop the
    # colon): only fires on an exact multi/single-word synonym prefix, so ordinary prose is safe.
    toks = s.split()
    if len(toks) >= 2:
        norm_toks = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in toks]
        f, n = match_label_prefix_words(norm_toks)
        if f and 0 < n < len(toks):
            return f, " ".join(toks[n:]), "exact"
    return None


def _first_name_line(value: str) -> str:
    """Names: keep the party name only. xlsx cells look like 'NAME | address; address'."""
    v = value.split(" | ")[0].strip()
    return v


def _clean_value(field_name: str, value: str) -> str:
    v = re.sub(r"\s+", " ", value).strip()
    if field_name in ("shipper", "consignee", "notify_party"):
        v = _first_name_line(v)
    return v


def _rank(kind: str, label_line: str, field_name: str) -> int:
    r = 0 if kind == "exact" else 5
    if field_name == "gross_weight_kg":
        if re.search(r"\btotal\b", label_line, re.I):
            r -= 2
        if re.search(r"\bnet\b|\btare\b|\bcargo\b", label_line, re.I):
            r += 6
    return r


def _scan(doc: ParsedDoc, field_name: str) -> list[tuple[int, int, str, str, str]]:
    """All candidate (rank, line_no, value, evidence_line, kind) for one field."""
    lines = doc.lines
    out: list[tuple[int, int, str, str, str]] = []
    for i, raw in enumerate(lines):
        if raw.startswith("  ") and not re.match(r"^\s{2}[A-Za-z][^:]{0,40}[:：]", raw):
            continue  # continuation / address line
        sp = split_line(raw)
        if not sp or sp[0] != field_name:
            continue
        f, value, kind = sp
        ev = raw.strip()
        if not value.strip():
            # value on the next (non-indented, non-label) line: "Shipper:\nACME LTD"
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if nxt.strip() and not nxt.startswith("  ") and not _LABEL_LIKE.match(nxt.strip()) \
                    and not split_line(nxt):
                value = nxt.strip()
                ev = f"{raw.strip()} / {nxt.strip()}"
        out.append((_rank(kind, raw, field_name), i, value, ev, kind))
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def _table_container_rows(doc: ParsedDoc) -> list[str]:
    rows = []
    for l in doc.lines:
        if l.count("|") >= 2 and _CONTAINER_NO.search(l):
            rows.append(l)
    return rows


def _table_weight_sum(rows: list[str]) -> float | None:
    tot = 0.0
    for r in rows:
        cells = [c.strip() for c in r.split("|")]
        w = nz.parse_weight_kg(cells[-1]) if cells else None
        if w is None or w.kg is None:
            return None
        tot += w.kg
    return tot if rows else None


def extract_field(doc: ParsedDoc, field_name: str) -> Extracted:
    """Extract one canonical field from one document (rules engine)."""
    ex = Extracted(field=field_name)
    if not doc.readable:
        ex.flags.append("not_found")
        ex.evidence = f"{doc.name}: {doc.status_detail or doc.status}"
        return ex
    cands = _scan(doc, field_name)
    conf_base = 0.98
    if doc.ocr_used:
        conf_base = 0.6
        ex.flags.append("ocr")
    if not cands:
        # container_count fallback: count container-number rows in a table
        if field_name == "container_count":
            rows = _table_container_rows(doc)
            if rows:
                ex.value = str(len(rows))
                ex.evidence = f"{len(rows)} container rows in table"
                ex.confidence = 0.6
                ex.flags.append("derived_from_table")
                return ex
        ex.flags.append("not_found")
        ex.confidence = 0.0
        ex.evidence = None
        return ex

    rank, line_no, raw_value, ev, kind = cands[0]
    value = _clean_value(field_name, raw_value)
    ex.evidence = ev
    if doc.truncated:
        last_content = max((i for i, l in enumerate(doc.lines) if l.strip()), default=-1)
        if line_no >= last_content - 1:
            # the document does not end with a newline (looks cut off mid-transfer) and this
            # value's evidence sits on/near the very last line: it may be a partial number/name
            # (e.g. 'Gross Weight: 21577' cut to 'Gross Weight: 2'). Never report this as a
            # confident value - the caller (compare.py) treats 'possibly_truncated' as missing.
            ex.flags.append("possibly_truncated")
    if kind == "fuzzy":
        ex.flags.append("fuzzy_label")
        conf_base -= 0.12
    if nz.is_blank(value):
        ex.value = None
        ex.flags.append("blank")
        ex.confidence = 0.0
        ex.evidence = ev
        return ex
    if nz.has_placeholder(value):
        ex.flags.append("placeholder")
        conf_base -= 0.4
    # competing candidates with different values -> conflict
    if len(cands) > 1:
        other = _clean_value(field_name, cands[1][2])
        if other and not nz.is_blank(other) and other.upper() != value.upper() and cands[1][0] == rank:
            ex.flags.append("conflict")
            conf_base -= 0.15
    ex.value = value

    if field_name == "gross_weight_kg":
        wp = nz.parse_weight_kg(value)
        if wp.kg is None:
            ex.flags.append("ambiguous")
            conf_base -= 0.4
        else:
            if wp.ambiguous:
                ex.flags.append("ambiguous")
                conf_base -= 0.25
            if wp.converted:
                ex.flags.append("unit_converted")
                conf_base -= 0.03
            rows = _table_container_rows(doc)
            ts = _table_weight_sum(rows)
            if ts is not None and abs(ts - wp.kg) > max(2.0, 0.001 * wp.kg) and not wp.converted:
                ex.flags.append("inconsistent")
                conf_base -= 0.15
    elif field_name == "container_count":
        cp = nz.parse_container_count(value)
        if cp.count is None:
            ex.flags.append("ambiguous")
            conf_base -= 0.4
        else:
            rows = _table_container_rows(doc)
            if rows and len(rows) != cp.count and len(rows) < 12:
                ex.flags.append("inconsistent")
                conf_base -= 0.15
    ex.confidence = max(0.05, min(0.99, conf_base))
    return ex


def extract_all(doc: ParsedDoc, fields: list[str]) -> dict[str, Extracted]:
    return {f: extract_field(doc, f) for f in fields}
