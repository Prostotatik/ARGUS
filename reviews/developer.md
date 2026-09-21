
## Round 1 - DEVELOPER (frontend half), 2026-09-21

### What I built (`frontend/`, Vite + React + TS, plain CSS, no chart libs)
Kept the previous agent's scaffold (source.ts, usePlayer, graphState, GraphPanel, NodePopover, Sidebar, EmailList, icons, mock) and finished the rest:
- `main.tsx`, `App.tsx` (state, run/retry/review orchestration, run-id guard against stale streams), `styles.css` (whole theme), `hooks/useReducedMotion.ts`.
- `components/FlyPanel.tsx`: inputs -> Kenyon cells -> decision neuron, staged activation (inputs, KCs, neuron) from the `gate` event, winner KC highlight, suspicion vs threshold meter, Hebbian-update feedback (before -> after, "simulated" tag in REPLAY), input legend from backend `input_names` (mismatch / low conf / near-miss / doc), seeded KC layout, subsamples large nets (draws ~110 of 1600 KCs plus every active one; caption says so), caption "Architecture inspired by the fruit fly's olfactory system".
- `components/Timeline.tsx`: 6-step strip (Received, Classified, Field agents with 7 status dots, Aggregate+compare, Fly gate, Report ready), t+ms, engine badge + duration, skipped states for non-comparison mails.
- `components/ReportView.tsx`: headline ("No mismatch detected" when all match), SI vs BL table for the 7 fields with evidence, mismatches highlighted, gate line, classification-only card for non-comparison mails, processing-failure box with retry, human-review panel (reason text, escalation reason, source evidence, "was escalation warranted" verdict, Confirm mismatch / Confirm no mismatch / Correct a field form; per-row pencil to correct any field), fly-net feedback line. REPLAY/MOCK marks the review as "simulated locally".
- Center header with Pipeline/Report tabs, Replay/Re-run/Skip, and LIVE/REPLAY/MOCK pill; result banner under the graph ("Review" pulses amber for NEEDS_REVIEW).
- Fixes to inherited code: circular-JSON crash in `simulateReview` (report event payload references the result), mock report payloads copied, compare fields prefer the (possibly human-corrected) result over stale event payload, MISMATCH label colour, sidebar wrap.
- `README.md` in `frontend/`.

### Verification (evidence)
- `npm run build` (tsc -b && vite build): 0 TS errors, 1894 modules, built OK.
- Claude-in-Chrome extension was NOT connected, so I drove the installed Chrome 153 headless over CDP (own script in scratchpad, no deps) at 1536x1024, 1280x800, 1024x768, 390x844 and read screenshots. Compared with the reference: sidebar, graph with curved glowing connectors + particle trails, 7 real field pills, incoming emails, fly panel with lit decision neuron, bottom timeline all match the reference layout/style at 1536x1024.
- Exercised in MOCK mode: OK email, MISMATCH email, NEEDS_REVIEW (errored node) email, non-comparison (spam) bypass arc, popover, report, review confirm -> status flips to MISMATCH, list dot + stats update, fly feedback "0.83 -> 0.92 simulated".
- Exercised LIVE mode against a throwaway fake FastAPI-contract server (Node, scratchpad, now stopped): /api/health detection, Vite proxy, SSE parsing over fetch stream, streamed node lighting, NEEDS_REVIEW -> POST /api/review -> updated report, 32-input / 1600-KC fly net with 80 active KCs. Console: no errors except the expected 502/404 on `/api/health` when no backend is running (that is the auto-detect probe).
- Dev servers, fake server and headless Chrome stopped.

### Deviations from the reference
- Sidebar copy is honest, not the reference numbers: "Emails to process", "Shipments compared", "Discrepancies found", "Accuracy vs. labels" (offline self-eval, `-` when absent); top issues are real defect fields, padded with zero-count fields.
- Added: filter chips + search on the email list (520 emails), gate chip node between Aggregator and Report, Pipeline/Report tabs, mode pill says LIVE/REPLAY/MOCK instead of just "Live".
- Fly panel big number is suspicion (0-1) with threshold, not "98.2% confidence"; input labels are group legend + tooltips because 32 inputs cannot carry text labels at this size.
- Timeline shows t+ms from trace events (relative) instead of wall-clock times.
- Under 820px the graph scrolls horizontally at a readable scale instead of shrinking to illegibility.

### Known gaps
- Not run against the real backend or real replay files: `backend/out` and `frontend/public/replay/` were empty while I worked. The adapters accept several index.json shapes (array or {emails|items|results}; per-row `result`, `result_summary` or inline fields) but this is unverified against the real export.
- REPLAY: retry and review are simulated (clearly marked); the fly-net update there is a heuristic (x0.82 / x1.08+0.02), not the real Hebbian rule.
- No automated tests; verification was visual + build. No live Gemini path exercised (no key).
- ~100 KC drawn out of 1600 by design; the drawn set is a fixed stride sample plus active KCs.
- Chrome extension unavailable: cross-browser (Firefox/Safari) untested.

### CONTRACT objections / requests (none blocking)
1. Report event `payload` must not embed `events` (circular / huge); please keep events only at the Result top level of `traces/<id>.json`.
2. Request `POST /api/review` response (or `GET /api/flybrain`.history[-1]) to carry `{before, after, verdict}` in a stable shape; I read `history[-1]` after a review.
3. SSE framing is unspecified; I accept `data: {json}\n\n` and bare NDJSON. Please keep one JSON Trace event per message and no named `event:` types.
4. `/api/retry/{id}`: please emit fresh `start`/`done|error` events for the retried nodes and a new `report` event; frontend folds by last-event-per-node.
5. `flybrain.input_names` (already in `flybrain.py`) is used for the legend: please keep it in the replay `flybrain.json`, and keep `kc_active` indices in `[0, n_kc)`.
6. `index.json` rows: please include `from`, `subject`, `received_at`, `category`, `status`, `defect_fields` per row (list dots/chips rely on them).

STATUS: NO REMAINING OBJECTIONS
