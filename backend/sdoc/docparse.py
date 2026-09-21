"""Deterministic attachment parsing: txt, pdf (text layer), docx (incl. tables), xlsx.

Every format is reduced to the same intermediate: a list of text *lines* where a
label/value row becomes ``"Label: value"`` and continuation lines (addresses,
multi-line cells) are prefixed with two spaces. The label/field alignment lives in
``labels.py`` / ``rules_extract.py`` and works only on that intermediate.

No LLM, no ground truth. If a PDF has no text layer we try OCR *only if* a local OCR
engine is available (``ocr.py``); otherwise the document is flagged ``unreadable``.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from . import ocr

# ---------------------------------------------------------------------------
# Document type detection
# ---------------------------------------------------------------------------
DOC_TYPES = ("SI", "BL", "INVOICE", "PACKING_LIST", "COO", "UNKNOWN")

_TYPE_RULES: list[tuple[str, re.Pattern[str], int]] = [
    ("INVOICE", re.compile(r"\bcommercial\s+invoice\b|\bproforma\s+invoice\b|^\s*invoice\b", re.I), 5),
    ("PACKING_LIST", re.compile(r"\bpacking\s+list\b", re.I), 5),
    ("COO", re.compile(r"\bcertificate\s+of\s+origin\b", re.I), 5),
    ("SI", re.compile(r"\bshipping\s+instruction|\bbl\s+instruction|\bbill\s+of\s+lading\s+instruction|\bshipping\s+order\b|\bs\.i\.\s*$", re.I), 5),
    ("BL", re.compile(r"\bbill\s+of\s+lading\b|\bdraft\s+b/?l\b|\bb/l\s+draft\b|\bdraft\s+bill\b", re.I), 4),
]
_NOT_SI_BL = re.compile(r"not\s+an?\s+(?:si|shipping\s+instruction|bl|bill)|not\s+a\s+shipping|no\s+port\s+or\s+vessel", re.I)


def detect_doc_type(lines: list[str]) -> tuple[str, str, float]:
    """Return (doc_type, evidence, confidence) from the title block (first lines) + banner lines.

    Title lines are decisive; body keywords only break ties, so a BL that *mentions* an invoice
    number is not mistaken for an invoice.
    """
    head = [l for l in lines if l.strip()][:6]
    scores: dict[str, int] = {}
    ev: dict[str, str] = {}
    for i, line in enumerate(head):
        for dt, pat, w in _TYPE_RULES:
            if pat.search(line):
                bonus = 3 if i == 0 else 1
                scores[dt] = scores.get(dt, 0) + w + bonus
                ev.setdefault(dt, line.strip())
    # explicit disclaimers anywhere: "*** THIS IS A COMMERCIAL INVOICE - NOT A SHIPPING INSTRUCTION ***"
    for line in lines:
        if line.strip().startswith("***") or _NOT_SI_BL.search(line):
            for dt, pat, w in _TYPE_RULES:
                if dt in ("INVOICE", "PACKING_LIST", "COO") and pat.search(line.split("-")[0] if "-" in line else line):
                    scores[dt] = scores.get(dt, 0) + 4
                    ev.setdefault(dt, line.strip())
    if not scores:
        return "UNKNOWN", "", 0.3
    best = max(scores, key=lambda k: scores[k])
    total = sum(scores.values())
    conf = 0.6 + 0.39 * (scores[best] / total)
    return best, ev.get(best, ""), round(min(conf, 0.99), 2)


# ---------------------------------------------------------------------------
@dataclass
class ParsedDoc:
    path: str
    name: str
    fmt: str = "unknown"          # txt | pdf | docx | xlsx | unknown
    status: str = "ok"            # ok | empty | unreadable | image_only
    status_detail: str = ""
    lines: list[str] = field(default_factory=list)
    doc_type: str = "UNKNOWN"     # SI | BL | INVOICE | PACKING_LIST | COO | UNKNOWN
    type_evidence: str = ""
    type_confidence: float = 0.0
    role_hint: str | None = None  # SI/BL guessed from the file name (hint only)
    ocr_used: bool = False
    n_bytes: int = 0

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def readable(self) -> bool:
        return self.status == "ok" and bool(self.lines)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "format": self.fmt,
            "status": self.status,
            "status_detail": self.status_detail,
            "doc_type": self.doc_type,
            "type_evidence": self.type_evidence,
            "type_confidence": self.type_confidence,
            "role_hint": self.role_hint,
            "ocr_used": self.ocr_used,
            "n_bytes": self.n_bytes,
            "n_lines": len(self.lines),
        }


def _role_from_name(name: str) -> str | None:
    n = name.lower()
    if re.search(r"(^|[^a-z])si([^a-z]|$)", n) or "instruction" in n:
        return "SI"
    if re.search(r"(^|[^a-z])(bl|bol|b_l)([^a-z]|$)", n) or "lading" in n:
        return "BL"
    return None


def _clean_cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v)
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    return s.strip()


def _emit_kv(lines: list[str], label: str, value: str) -> None:
    label = re.sub(r"\s+", " ", label.strip())
    vlines = [re.sub(r"[ \t]+", " ", v.strip()) for v in value.split("\n")]
    vlines = [v for v in vlines if v]
    if not label and not vlines:
        return
    if not vlines:
        lines.append(f"{label}:")
        return
    if label:
        lines.append(f"{label}: {vlines[0]}")
    else:
        lines.append(vlines[0])
    for extra in vlines[1:]:
        lines.append("  " + extra)


# ---------------------------------------------------------------------------
# format readers
# ---------------------------------------------------------------------------
def _read_txt(data: bytes) -> tuple[list[str], str]:
    if b"\x00" in data[:2048] and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return [], "binary content in .txt"
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            txt = data.decode(enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:  # pragma: no cover
        txt = data.decode("latin-1", errors="replace")
    lines = [l.rstrip() for l in txt.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return lines, ""


def _read_docx(path: Path) -> tuple[list[str], str]:
    import docx  # python-docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(str(path))
    lines: list[str] = []
    body = d.element.body
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            t = Paragraph(child, d).text.strip()
            if t:
                lines.append(t)
        elif tag == "tbl":
            tbl = Table(child, d)
            for row in tbl.rows:
                # de-duplicate merged cells (python-docx repeats them)
                cells: list[str] = []
                prev = None
                for c in row.cells:
                    if c._tc is prev:
                        continue
                    prev = c._tc
                    cells.append(_clean_cell(c.text))
                cells = [c for c in cells]
                nonempty = [c for c in cells if c]
                if not nonempty:
                    continue
                if len(cells) >= 2:
                    _emit_kv(lines, cells[0], " | ".join(c for c in cells[1:] if c) if len(cells) > 2 else cells[1])
                else:
                    for i, seg in enumerate(nonempty[0].split("\n")):
                        if seg.strip():
                            lines.append(seg.strip())
    return lines, ""


def _read_xlsx(path: Path) -> tuple[list[str], str]:
    import openpyxl

    wb = openpyxl.load_workbook(str(path), data_only=True, read_only=False)
    lines: list[str] = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            cells = [_clean_cell(v) for v in row]
            nonempty = [c for c in cells if c]
            if not nonempty:
                continue
            if len(nonempty) == 1:
                for seg in nonempty[0].split("\n"):
                    if seg.strip():
                        lines.append(seg.strip())
                continue
            # first non-empty cell = label, rest = value cells
            first_idx = next(i for i, c in enumerate(cells) if c)
            label = cells[first_idx]
            rest = [c for c in cells[first_idx + 1:] if c]
            _emit_kv(lines, label, " | ".join(rest))
    return lines, ""


def _pdf_rows(page) -> list[list[tuple[float, str, bool]]]:
    """Group text spans of a page into visual rows -> list of [(x0, text, is_bold)]."""
    d = page.get_text("dict")
    spans: list[tuple[float, float, str, bool]] = []
    for b in d.get("blocks", []):
        for l in b.get("lines", []):
            for s in l.get("spans", []):
                t = s.get("text", "")
                if not t.strip():
                    continue
                ox, oy = s.get("origin", (s["bbox"][0], s["bbox"][3]))
                bold = bool(s.get("flags", 0) & 16) or "bold" in s.get("font", "").lower()
                spans.append((oy, ox, t, bold))
    spans.sort(key=lambda s: (round(s[0] / 3.0), s[1]))
    rows: list[list[tuple[float, str, bool]]] = []
    cur_y = None
    for oy, ox, t, bold in sorted(spans, key=lambda s: (s[0], s[1])):
        if cur_y is None or abs(oy - cur_y) > 2.5:
            rows.append([])
            cur_y = oy
        rows[-1].append((ox, t, bold))
    for r in rows:
        r.sort(key=lambda c: c[0])
    return rows


def _read_pdf(path: Path) -> tuple[list[str], str, str, bool]:
    """Return (lines, status, detail, ocr_used)."""
    import pymupdf

    try:
        doc = pymupdf.open(str(path))
    except Exception as e:  # noqa: BLE001 - any parser failure == unreadable
        return [], "unreadable", f"cannot open PDF ({type(e).__name__})", False
    try:
        if doc.page_count == 0:
            return [], "unreadable", "PDF has no pages", False
        lines: list[str] = []
        n_images = 0
        for page in doc:
            n_images += len(page.get_images())
            rows = _pdf_rows(page)
            if not rows:
                continue
            xmin = min(r[0][0] for r in rows)
            for r in rows:
                if len(r) == 1:
                    x0, t, _ = r[0]
                    t = re.sub(r"\s+", " ", t.strip())
                    lines.append(("  " if x0 > xmin + 30 else "") + t)
                elif len(r) == 2:
                    lab = re.sub(r"\s+", " ", r[0][1].strip())
                    val = re.sub(r"\s+", " ", r[1][1].strip())
                    if r[0][0] > xmin + 30:
                        lines.append("  " + lab + " " + val)
                    elif re.search(r"[:：]\s*$", lab):
                        lines.append(f"{lab} {val}")
                    else:
                        lines.append(f"{lab}: {val}")
                else:
                    lines.append(" | ".join(re.sub(r"\s+", " ", c[1].strip()) for c in r))
        text_chars = sum(len(l.strip()) for l in lines)
        if text_chars >= 20:
            return lines, "ok", "", False
        # no usable text layer
        if ocr.available():
            o_lines = ocr.ocr_pdf(path)
            if sum(len(l.strip()) for l in o_lines) >= 20:
                return o_lines, "ok", "text recovered by OCR", True
            return [], "image_only", "scanned PDF: OCR found no usable text", False
        if n_images:
            return [], "image_only", "scanned/image-only PDF (no text layer, OCR unavailable)", False
        return [], "unreadable", "PDF has no extractable text", False
    finally:
        doc.close()


# ---------------------------------------------------------------------------
def parse_document(path: str | Path, data: bytes | None = None) -> ParsedDoc:
    p = Path(path)
    name = p.name
    pd = ParsedDoc(path=str(path), name=name, role_hint=_role_from_name(name))
    ext = p.suffix.lower().lstrip(".")
    pd.fmt = ext if ext in ("txt", "pdf", "docx", "xlsx") else "unknown"
    try:
        if data is None:
            data = p.read_bytes()
    except OSError as e:
        pd.status, pd.status_detail = "unreadable", f"cannot read file ({type(e).__name__})"
        return pd
    pd.n_bytes = len(data)
    if pd.n_bytes == 0:
        pd.status, pd.status_detail = "empty", "0-byte file"
        return pd

    try:
        if pd.fmt == "txt" or pd.fmt == "unknown":
            lines, detail = _read_txt(data)
            if not lines and detail:
                pd.status, pd.status_detail = "unreadable", detail
        elif pd.fmt == "pdf":
            if data[:5] != b"%PDF-":
                pd.status, pd.status_detail = "unreadable", "not a PDF (bad header)"
                return pd
            import tempfile, os
            # pymupdf can open bytes directly; go through a temp file only when path is missing
            if p.exists():
                lines, st, detail, used = _read_pdf(p)
            else:  # pragma: no cover - bytes only
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
                    tf.write(data)
                    tmp = tf.name
                try:
                    lines, st, detail, used = _read_pdf(Path(tmp))
                finally:
                    os.unlink(tmp)
            pd.ocr_used = used
            if st != "ok":
                pd.status, pd.status_detail = st, detail
            else:
                pd.status_detail = detail
        elif pd.fmt == "docx":
            lines, _ = _read_docx(p)
        elif pd.fmt == "xlsx":
            lines, _ = _read_xlsx(p)
        else:  # pragma: no cover
            lines = []
    except Exception as e:  # noqa: BLE001 - corrupt containers etc.
        pd.status, pd.status_detail = "unreadable", f"parse error: {type(e).__name__}"
        return pd

    if pd.status == "ok":
        pd.lines = [l for l in lines]
        if not any(l.strip() for l in pd.lines):
            pd.status, pd.status_detail = "empty", "no text content"
            pd.lines = []
        else:
            pd.doc_type, pd.type_evidence, pd.type_confidence = detect_doc_type(pd.lines)
    return pd
