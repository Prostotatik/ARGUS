"""Result -> submission entry (work/bundle/sample_submission.json shape)."""
from __future__ import annotations

# The required submission schema only has 4 review_reason slots (wrong_doc_type|
# missing_attachment|unreadable|missing_value). The live Result/API/UI can also report the more
# honest 'low_confidence' (a pure fly-gate grey-zone escalation with nothing missing/unreadable -
# see pipeline.py and reviews/developer.md item #2) - map it down to the closest of the four
# required values only at this export boundary, so the shipped submission stays spec-compliant
# without the live product ever lying about *why* it escalated.
_SUBMISSION_REASON_MAP = {"low_confidence": "missing_value"}


def submission_entry(result: dict) -> dict:
    status = result.get("status")
    if status is None:            # non-comparison categories: the bundle shape uses OK
        status = "OK"
    needs = status == "NEEDS_REVIEW"
    reason = result.get("review_reason")
    reason = _SUBMISSION_REASON_MAP.get(reason, reason)
    return {
        "category": result["category"],
        "status": status,
        "review_reason": reason if needs else None,
        "has_defect": bool(result.get("has_defect")) and not needs,
        "defect_fields": [] if needs else sorted(result.get("defect_fields") or []),
    }


def build_submission(results: dict[str, dict]) -> dict[str, dict]:
    return {eid: submission_entry(r) for eid, r in sorted(results.items())}
