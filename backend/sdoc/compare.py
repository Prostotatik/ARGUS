"""Pure-function comparison + status decision. NO LLM, no I/O.

``compare_field`` takes the two extracted values (SI, BL) for one field and returns a
``FieldResult`` dict (CONTRACT.md). ``decide`` folds the seven FieldResults + document-level
preconditions into status / has_defect / defect_fields / review_reason following the bundle README:

* OK            - all 7 fields compared and match
* MISMATCH      - >=1 field differs (SI is the reference)
* NEEDS_REVIEW  - cannot decide: wrong_doc_type | missing_attachment | unreadable | missing_value
"""
from __future__ import annotations

from typing import Any, Mapping

from . import normalize as nz
from .config import FIELDS

FIELD_LABELS = {
    "shipper": "Shipper",
    "consignee": "Consignee",
    "notify_party": "Notify party",
    "port_of_loading": "Port of loading",
    "port_of_discharge": "Port of discharge",
    "container_count": "Container count",
    "gross_weight_kg": "Gross weight (kg)",
}


def _get(x: Any, key: str, default=None):
    if x is None:
        return default
    if isinstance(x, Mapping):
        return x.get(key, default)
    return getattr(x, key, default)


def normalise_value(field: str, raw: str | None):
    """Return (comparable_key, display_norm, meta). key None => value missing/unparseable."""
    if raw is None or nz.is_blank(raw):
        return None, None, {}
    if field in ("shipper", "consignee", "notify_party"):
        k = nz.norm_name(raw)
        return k, k.full, {}
    if field in ("port_of_loading", "port_of_discharge"):
        k = nz.norm_port(raw)
        disp = k.core + (f" ({k.code})" if k.code else "")
        return k, disp, {}
    if field == "container_count":
        cp = nz.parse_container_count(raw)
        return cp.count, cp.count, {"sizes": cp.sizes, "ambiguous": cp.ambiguous}
    if field == "gross_weight_kg":
        wp = nz.parse_weight_kg(raw)
        return wp, nz.fmt_kg(wp.kg), {"converted": wp.converted, "ambiguous": wp.ambiguous}
    return raw.strip().upper(), raw.strip().upper(), {}


def compare_field(field: str, si: Any, bl: Any) -> dict:
    """Compare one field. ``si``/``bl`` are Extracted objects or dicts with value/evidence/confidence/flags."""
    sv, bv = _get(si, "value"), _get(bl, "value")
    sk, sn, sm = normalise_value(field, sv)
    bk, bn, bm = normalise_value(field, bv)
    sflags = list(_get(si, "flags", []) or [])
    bflags = list(_get(bl, "flags", []) or [])
    conf = min(float(_get(si, "confidence", 0.0) or 0.0), float(_get(bl, "confidence", 0.0) or 0.0))

    res = {
        "field": field,
        "si_value": sv if sk is not None else (sv if sv else None),
        "bl_value": bv if bk is not None else (bv if bv else None),
        "si_norm": sn if not hasattr(sn, "full") else sn,
        "bl_norm": bn,
        "match": False,
        "state": "missing",
        "confidence": round(conf, 3),
        "si_evidence": _get(si, "evidence"),
        "bl_evidence": _get(bl, "evidence"),
        "note": None,
        "near_miss": False,
        "flags": sorted(set(sflags + bflags)),
    }
    if sk is None or bk is None:
        side = "SI" if sk is None and bk is None else ("SI" if sk is None else "BL")
        both = sk is None and bk is None
        res["note"] = ("value missing or unreadable in SI and BL" if both
                       else f"value missing or unreadable in {side}")
        res["confidence"] = 0.0
        return res

    if "possibly_truncated" in sflags or "possibly_truncated" in bflags:
        # A document that does not end with a newline and whose value for this field sits on
        # its last line may have been cut off mid-value (e.g. a BL number or weight truncated
        # mid-digit). Never report a confident MISMATCH from a partial number/name: treat the
        # value as untrustworthy so it escalates for human review instead of silently lying.
        side = "SI" if "possibly_truncated" in sflags and "possibly_truncated" not in bflags else \
            ("BL" if "possibly_truncated" in bflags and "possibly_truncated" not in sflags else "SI/BL")
        res["state"] = "missing"
        res["note"] = f"document ends abruptly; the {side} value for this field may be truncated mid-value"
        res["confidence"] = 0.0
        return res

    ocr_noisy = "ocr" in sflags or "ocr" in bflags
    if field in ("shipper", "consignee", "notify_party"):
        c = nz.names_equal(sv, bv, near_miss_floor=0.72 if ocr_noisy else 0.88)
    elif field in ("port_of_loading", "port_of_discharge"):
        c = nz.ports_equal(sv, bv, near_miss_floor=0.72 if ocr_noisy else 0.88)
    elif field == "container_count":
        c = nz.Cmp(sk == bk, None)
        if c.match and sm.get("sizes") and bm.get("sizes") and sm["sizes"] != bm["sizes"]:
            c.note = f"size/type differs ({sm['sizes']} vs {bm['sizes']}); count equal"
    else:
        c = nz.weights_equal(sk, bk)
        if not c.match and sm.get("converted") is False and bm.get("converted") is False:
            pass
    res["match"] = bool(c.match)
    res["state"] = "match" if c.match else "mismatch"
    res["note"] = c.note
    res["near_miss"] = bool(getattr(c, "near_miss", False))
    # JSON-safe norms
    res["si_norm"] = _jsonable(sn)
    res["bl_norm"] = _jsonable(bn)
    return res


def _jsonable(v):
    if v is None or isinstance(v, (int, float, str, bool)):
        return v
    return str(v)


def compare_all(si_ext: Mapping[str, Any], bl_ext: Mapping[str, Any]) -> list[dict]:
    return [compare_field(f, si_ext.get(f), bl_ext.get(f)) for f in FIELDS]


# ---------------------------------------------------------------------------
def headline(status: str | None, defect_fields: list[str], fields: list[dict],
             review_reason: str | None, detail: str | None = None) -> str:
    if status == "NEEDS_REVIEW":
        return f"Needs review: {(review_reason or 'uncertain').replace('_', ' ')}" + (f" - {detail}" if detail else "")
    if status == "MISMATCH":
        by = {f["field"]: f for f in fields}
        parts = []
        for d in defect_fields:
            f = by.get(d, {})
            if d in ("container_count", "gross_weight_kg"):
                a, b = f.get("si_norm"), f.get("bl_norm")
            else:
                a, b = f.get("si_value"), f.get("bl_value")
            parts.append(f"{d}: SI {a} / BL {b}")
        return " | ".join(parts)
    if status == "OK":
        return detail or "No mismatch detected"
    return detail or ""


def decide(fields: list[dict], preflight_reason: str | None = None,
           preflight_detail: str | None = None) -> dict:
    """Pure status decision. ``preflight_reason`` is a deterministic NEEDS_REVIEW trigger found
    before comparison (missing_attachment / wrong_doc_type / unreadable)."""
    if preflight_reason:
        return {"status": "NEEDS_REVIEW", "review_reason": preflight_reason, "has_defect": False,
                "defect_fields": [],
                "headline": headline("NEEDS_REVIEW", [], fields, preflight_reason, preflight_detail),
                "review_detail": preflight_detail}
    missing = [f["field"] for f in fields if f["state"] == "missing"]
    if missing:
        detail = "no usable value for: " + ", ".join(missing)
        return {"status": "NEEDS_REVIEW", "review_reason": "missing_value", "has_defect": False,
                "defect_fields": [],
                "headline": headline("NEEDS_REVIEW", [], fields, "missing_value", detail),
                "review_detail": detail}
    defects = [f["field"] for f in fields if f["state"] == "mismatch"]
    if defects:
        return {"status": "MISMATCH", "review_reason": None, "has_defect": True,
                "defect_fields": defects, "headline": headline("MISMATCH", defects, fields, None),
                "review_detail": None}
    return {"status": "OK", "review_reason": None, "has_defect": False, "defect_fields": [],
            "headline": "No mismatch detected", "review_detail": None}
