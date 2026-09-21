"""``python -m sdoc.run_all``  - process every email and write backend/out/submission.json (+ results.json).

Uses a fresh, freshly-calibrated fly gate (never the human-taught persisted one) so the run is reproducible.
Engine defaults to `rules` regardless of a configured key - this generates the OFFICIAL scored
submission across all 520 emails, and it should be deterministic and fast by default.
Pass `--engine gemini` to exercise a live key across the whole set instead (mind its daily quota).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time

from . import config
from .flybrain import FlyBrain
from .inbox import Inbox
from .pipeline import Pipeline
from .submission import build_submission


async def run(engine: str | None, concurrency: int = 8, limit: int | None = None) -> tuple[dict, Pipeline]:
    inbox = Inbox()
    pipe = Pipeline(inbox=inbox, gate=FlyBrain.load_or_calibrate(None), default_engine=engine)
    ids = inbox.ids()[:limit] if limit else inbox.ids()
    sem = asyncio.Semaphore(concurrency)
    results: dict[str, dict] = {}

    async def one(eid: str) -> None:
        async with sem:
            r, _ = await pipe.run(eid)
            results[eid] = r

    await asyncio.gather(*[one(e) for e in ids])
    return results, pipe


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--engine", choices=["rules", "gemini"], default="rules",
                     help="defaults to 'rules' (deterministic, reproducible, no network/quota) even if a "
                          "GEMINI_API_KEY is configured - this generates the OFFICIAL 520-email submission, "
                          "and silently defaulting a bulk run onto a live key's daily quota is exactly the "
                          "footgun this default avoids. Pass --engine gemini to opt in explicitly.")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=str(config.OUT_DIR))
    a = ap.parse_args()
    t = time.time()
    results, pipe = asyncio.run(run(a.engine, limit=a.limit))
    out = config.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sub = build_submission(results)
    (out / "submission.json").write_text(json.dumps(sub, indent=2), encoding="utf-8")
    (out / "results.json").write_text(json.dumps(results), encoding="utf-8")
    from collections import Counter
    print(f"engine={pipe.resolve_engine()} emails={len(sub)} in {time.time() - t:.1f}s -> {out / 'submission.json'}")
    print("categories:", dict(Counter(v['category'] for v in sub.values())))
    print("status    :", dict(Counter(v['status'] for v in sub.values())))


if __name__ == "__main__":
    main()
