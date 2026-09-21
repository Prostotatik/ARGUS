"""OCR hook for scanned/image-only PDFs.

Two independent engines, tried in this order:

1. ``rapidocr-onnxruntime`` - pure Python + onnxruntime, ships its own small detection/
   recognition ONNX models inside the wheel (no system binary, no model download at
   runtime, no network access needed). This is the primary engine because it works in a
   plain ``pip install`` environment (verified in this repo's own sandbox, no internet
   access assumed at run time beyond the initial ``pip install``).
2. Tesseract via pymupdf's built-in OCR support (``page.get_textpage_ocr``) - used only if
   a local Tesseract binary is found on PATH. Kept as a fallback for environments that
   already have Tesseract installed and might prefer it.

If neither is available the document is honestly flagged ``unreadable`` by ``docparse.py``
(no silent guessing). ``SDOC_OCR=off`` disables OCR entirely (useful for a fast test run).
"""
from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path

_RAPIDOCR_ENGINE = None
_RAPIDOCR_TRIED = False
_RAPIDOCR_LOCK = threading.Lock()


def _rapidocr_engine():
    """Lazily construct the RapidOCR engine (loads its bundled ONNX models once).

    Documents are parsed in a thread pool (``asyncio.to_thread`` per attachment), so this can be
    entered by several threads at once the first time; a lock (not just a "tried" flag set before
    construction finishes) keeps a slower second attachment from observing a still-``None`` engine
    while the first construction is in flight."""
    global _RAPIDOCR_ENGINE, _RAPIDOCR_TRIED
    if _RAPIDOCR_TRIED:
        return _RAPIDOCR_ENGINE
    with _RAPIDOCR_LOCK:
        if _RAPIDOCR_TRIED:
            return _RAPIDOCR_ENGINE
        try:
            from rapidocr_onnxruntime import RapidOCR
            _RAPIDOCR_ENGINE = RapidOCR()
        except Exception:  # noqa: BLE001 - any import/init failure -> engine unavailable
            _RAPIDOCR_ENGINE = None
        _RAPIDOCR_TRIED = True
    return _RAPIDOCR_ENGINE


def _rapidocr_available() -> bool:
    return _rapidocr_engine() is not None


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def available() -> bool:
    if os.environ.get("SDOC_OCR", "auto").lower() in ("0", "off", "false", "no"):
        return False
    return _rapidocr_available() or _tesseract_available()


def engine_name() -> str | None:
    if os.environ.get("SDOC_OCR", "auto").lower() in ("0", "off", "false", "no"):
        return None
    if _rapidocr_available():
        return "rapidocr"
    if _tesseract_available():
        return "tesseract"
    return None


# ---------------------------------------------------------------------------
def _rows_from_detections(dets: list[tuple[float, float, str]], y_tol: float = 12.0) -> list[str]:
    """Group OCR text detections into visual rows by y-coordinate (same idea as the
    native-text-layer row grouping in docparse.py), joining same-row cells left-to-right.
    A single-cell row is emitted as-is; a two-cell row without its own colon is joined
    with ': ' so it still looks like a 'Label: value' line to rules_extract.split_line."""
    if not dets:
        return []
    dets = sorted(dets, key=lambda d: (d[0], d[1]))
    rows: list[list[tuple[float, str]]] = []
    cur_y: float | None = None
    for y, x, t in dets:
        if cur_y is None or abs(y - cur_y) > y_tol:
            rows.append([])
            cur_y = y
        rows[-1].append((x, t))
    out: list[str] = []
    for r in rows:
        r.sort(key=lambda c: c[0])
        cells = [t for _, t in r]
        if len(cells) == 1:
            out.append(cells[0])
        elif len(cells) == 2 and not cells[0].rstrip().endswith((":", "：")):
            out.append(f"{cells[0]}: {cells[1]}")
        else:
            out.append(" ".join(cells))
    return out


def _ocr_page_rapidocr(engine, png_bytes: bytes) -> list[str]:
    result, _ = engine(png_bytes)
    if not result:
        return []
    dets = []
    for box, text, score in result:
        if not text or not text.strip() or score < 0.35:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        dets.append((min(ys), min(xs), text.strip()))
    return _rows_from_detections(dets)


def ocr_pdf(path: Path) -> list[str]:
    """OCR every page of an image-only PDF. Returns text lines (best-effort, may be empty
    on failure - the caller treats an empty/short result as still unreadable, honestly)."""
    import pymupdf

    lines: list[str] = []
    try:
        doc = pymupdf.open(str(path))
        engine = _rapidocr_engine()
        for page in doc:
            if engine is not None:
                pix = page.get_pixmap(dpi=200)
                lines.extend(_ocr_page_rapidocr(engine, pix.tobytes("png")))
            elif _tesseract_available():
                tp = page.get_textpage_ocr(dpi=200, full=True)
                txt = page.get_text("text", textpage=tp)
                lines.extend(l.rstrip() for l in txt.splitlines())
        doc.close()
    except Exception:  # noqa: BLE001 - OCR failure == unreadable, handled by caller
        return []
    return lines
