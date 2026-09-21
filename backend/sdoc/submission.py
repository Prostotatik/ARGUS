"""Result -> submission entry (work/bundle/sample_submission.json shape)."""
from __future__ import annotations


def submission_entry(result: dict) -> dict:
    status = result.get("status")
    if status is None:            # non-comparison categories: the bundle shape uses OK
        status = "OK"
    needs = status == "NEEDS_REVIEW"
    return {
        "category": result["category"],
        "status": status,
        "review_reason": result.get("review_reason") if needs else None,
        "has_defect": bool(result.get("has_defect")) and not needs,
        "defect_fields": [] if needs else sorted(result.get("defect_fields") or []),
    }


def build_submission(results: dict[str, dict]) -> dict[str, dict]:
    return {eid: submission_entry(r) for eid, r in sorted(results.items())}
