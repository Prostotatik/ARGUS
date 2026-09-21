"""``python -m sdoc.export_replay``  - write static replay artifacts for the frontend (no backend needed).

Writes ONLY into frontend/public/replay/ (CONTRACT.md):
    index.json        list of email summaries + Results (without events)
    traces/<id>.json  full Result incl. events
    stats.json        dashboard stats (accuracy_vs_labels is a single number computed offline, or null)
    flybrain.json     fly-net structure + weights + calibration report
    submission.json   the scored-shape submission

No ground-truth labels are written anywhere. Runs the real pipeline with a fresh, freshly-calibrated
fly gate. Engine defaults to `rules` regardless of a configured key (`--engine gemini` opts in) -
this walks all 520 emails, and REPLAY is meant to work with zero backend/key anyway.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from pathlib import Path

from . import config
from .inbox import Inbox
from .run_all import run
from .store import Store
from .submission import build_submission


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--engine", choices=["rules", "gemini"], default="rules",
                     help="defaults to 'rules' even if a GEMINI_API_KEY is configured - this walks all 520 "
                          "emails to build the static REPLAY bundle, and doing that against a live key by "
                          "accident burns its daily quota for no benefit (REPLAY is meant to run with no "
                          "backend at all). Pass --engine gemini to opt in explicitly.")
    ap.add_argument("--out", default=str(config.REPLAY_DIR))
    a = ap.parse_args()
    out = Path(a.out)
    (out / "traces").mkdir(parents=True, exist_ok=True)
    for old in (out / "traces").glob("email_*.json"):
        old.unlink()

    results, pipe = asyncio.run(run(a.engine))
    inbox: Inbox = pipe.inbox
    rows = []
    for eid in inbox.ids():
        r = results[eid]
        (out / "traces" / f"{eid}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        slim = {k: v for k, v in r.items() if k != "events"}
        rows.append({**inbox.summary(eid), "category": r["category"], "status": r["status"],
                     "defect_fields": r["defect_fields"], "result": slim})
    (out / "index.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    st = Store(config.OUT_DIR)
    st.results = results
    stats = st.stats(len(inbox))
    stats["engine"] = pipe.resolve_engine()
    (out / "stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
    (out / "flybrain.json").write_text(json.dumps(pipe.gate.public()), encoding="utf-8")
    (out / "submission.json").write_text(json.dumps(build_submission(results), indent=1), encoding="utf-8")
    n_ev = sum(len(r["events"]) for r in results.values())
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"replay written to {out}: {len(rows)} emails, {n_ev} events, {size / 1e6:.1f} MB, engine={stats['engine']}")


if __name__ == "__main__":
    main()
