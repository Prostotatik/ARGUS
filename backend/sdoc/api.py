"""FastAPI app implementing the HTTP API in CONTRACT.md (prefix /api, CORS open, SSE for processing).

Run:  uvicorn sdoc.api:app --port 8000      (from the backend/ directory)
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import config
from .flybrain import FlyBrain
from .inbox import Inbox
from .pipeline import Pipeline
from .store import Store, apply_review
from .submission import build_submission

app = FastAPI(title="sdoc - shipping document verification", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

INBOX = Inbox()
STORE = Store()
GATE_PATH = config.OUT_DIR / "flybrain_state.json"
GATE = FlyBrain.load_or_calibrate(GATE_PATH)
PIPE = Pipeline(inbox=INBOX, gate=GATE)


def _sse(obj: Any) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _require(email_id: str) -> dict:
    e = INBOX.get(email_id)
    if e is None:
        raise HTTPException(404, f"unknown email {email_id}")
    return e


async def _stream_run(email_id: str, *, force_engine: str | None, inject: set[str], retry: bool) -> AsyncIterator[str]:
    q: asyncio.Queue = asyncio.Queue()
    prior = STORE.states.get(email_id) if retry else None

    def on_event(e: dict) -> None:
        q.put_nowait(e)

    async def worker() -> None:
        try:
            result, state = await PIPE.run(email_id, force_engine=force_engine, inject_fail=inject, prior=prior,
                                           on_event=on_event)
            STORE.put(result, state)
        except Exception as exc:  # noqa: BLE001 - visible to the client instead of a dead stream
            q.put_nowait({"seq": -1, "t_ms": 0, "node": "report", "state": "error", "engine": "pure",
                          "duration_ms": None, "summary": f"pipeline crashed: {type(exc).__name__}: {exc}",
                          "payload": {"error": str(exc)}})
        finally:
            q.put_nowait(None)

    task = asyncio.create_task(worker())
    try:
        while True:
            item = await q.get()
            if item is None:
                break
            yield _sse(item)
    finally:
        await task


# ---------------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "engine": PIPE.resolve_engine(), "n_emails": len(INBOX),
            "gemini_key_present": bool(config.gemini_key()),
            "note": "engine 'rules' = deterministic offline twins; 'gemini' only when GEMINI_API_KEY is set"}


@app.get("/api/emails")
def emails() -> list[dict]:
    out = []
    for e in INBOX.emails():
        s = INBOX.summary(e["email_id"])
        r = STORE.get(e["email_id"])
        s["result_summary"] = Store.summary(r) if r else None
        out.append(s)
    return out


@app.get("/api/email/{email_id}")
def email_detail(email_id: str) -> dict:
    e = _require(email_id)
    return {**INBOX.summary(email_id), "body": e.get("body", ""), "attachments": e.get("attachments", [])}


@app.post("/api/process/{email_id}")
async def process(email_id: str, force_engine: str | None = Query(None, pattern="^(rules|gemini)$"),
                  inject_fail: str | None = Query(None, description="demo: comma list of nodes to fail on this attempt, e.g. field:consignee")):
    _require(email_id)
    inject = {s.strip() for s in (inject_fail or "").split(",") if s.strip()}
    return StreamingResponse(_stream_run(email_id, force_engine=force_engine, inject=inject, retry=False),
                             media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/retry/{email_id}")
async def retry(email_id: str, force_engine: str | None = Query(None, pattern="^(rules|gemini)$")):
    _require(email_id)
    if email_id not in STORE.states:
        raise HTTPException(409, "nothing to retry: process this email first (state is kept in memory)")
    return StreamingResponse(_stream_run(email_id, force_engine=force_engine, inject=set(), retry=True),
                             media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/result/{email_id}")
def result(email_id: str) -> dict:
    r = STORE.get(email_id)
    if r is None:
        raise HTTPException(404, f"{email_id} not processed yet")
    return r


@app.post("/api/process_all")
async def process_all(force_engine: str | None = Query(None, pattern="^(rules|gemini)$"), concurrency: int = 8):
    ids = INBOX.ids()

    async def gen() -> AsyncIterator[str]:
        sem = asyncio.Semaphore(max(1, min(concurrency, 16)))
        q: asyncio.Queue = asyncio.Queue()
        done = 0

        async def one(eid: str) -> None:
            async with sem:
                try:
                    r, st = await PIPE.run(eid, force_engine=force_engine)
                    STORE.put(r, st)
                    await q.put({"type": "progress", "email_id": eid, "category": r["category"], "status": r["status"]})
                except Exception as exc:  # noqa: BLE001
                    await q.put({"type": "error", "email_id": eid, "message": str(exc)})

        tasks = [asyncio.create_task(one(e)) for e in ids]
        while done < len(ids):
            item = await q.get()
            done += 1
            item.update({"done": done, "total": len(ids)})
            yield _sse(item)
        await asyncio.gather(*tasks)
        config.OUT_DIR.mkdir(parents=True, exist_ok=True)
        sub = build_submission(STORE.results)
        (config.OUT_DIR / "submission.json").write_text(json.dumps(sub, indent=2), encoding="utf-8")
        (config.OUT_DIR / "results.json").write_text(json.dumps(STORE.results), encoding="utf-8")
        yield _sse({"type": "done", "done": len(ids), "total": len(ids), "submission": str(config.OUT_DIR / "submission.json"),
                    "stats": STORE.stats(len(INBOX))})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/api/review/{email_id}")
def review(email_id: str, body: dict = Body(...)) -> dict:
    r = STORE.get(email_id)
    if r is None:
        raise HTTPException(404, f"{email_id} not processed yet")
    try:
        updated = apply_review(r, body, GATE, GATE_PATH)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    STORE.put(updated)
    STORE.persist_review(updated)
    return updated


@app.get("/api/flybrain")
def flybrain() -> dict:
    return GATE.public()


@app.get("/api/stats")
def stats() -> dict:
    return STORE.stats(len(INBOX))
