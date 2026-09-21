"""Optional OCR hook.

OCR is *not required*: no OCR engine is bundled. ``available()`` is true only if a local
Tesseract install is found (pymupdf's OCR needs it). If OCR is used the parsed document is
flagged ``ocr_used`` and the pipeline treats its values as low-trust (the fly gate escalates).
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def available() -> bool:
    if os.environ.get("SDOC_OCR", "auto").lower() in ("0", "off", "false", "no"):
        return False
    return shutil.which("tesseract") is not None


def ocr_pdf(path: Path) -> list[str]:
    """OCR every page of an image-only PDF via pymupdf + tesseract. Returns text lines."""
    import pymupdf

    lines: list[str] = []
    try:
        doc = pymupdf.open(str(path))
        for page in doc:
            tp = page.get_textpage_ocr(dpi=200, full=True)
            txt = page.get_text("text", textpage=tp)
            lines.extend(l.rstrip() for l in txt.splitlines())
        doc.close()
    except Exception:  # noqa: BLE001 - OCR failure == unreadable, handled by caller
        return []
    return lines
