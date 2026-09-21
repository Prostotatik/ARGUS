
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


## Round 1 - DEVELOPER (backend half), 2026-09-21

### What I built (`backend/`, package `sdoc`)
Kept the previous agent's `config.py`, `docparse.py`, `labels.py`, `normalize.py`, `ocr.py` (read fully, sound; only behaviour found by scoring was changed) and finished the rest:
- `rules_extract.py` (rules field agent), `classifier.py` (rules classifier), `llm.py` (Gemini classifier + field agents, structured JSON, evidence verification), `intake.py` (SI/BL role assignment + preflight: missing_attachment / wrong_doc_type / unreadable), `compare.py` (pure compare + decide), `flybrain.py` (numpy gate), `pipeline.py` (7 parallel field agents via asyncio.gather, per-node events, per-node error + retry), `store.py` (results + human review + fly update), `api.py` (all CONTRACT endpoints, SSE, CORS open), `run_all.py`, `export_replay.py`, `submission.py`, `tools/score_local.py` (dev-only), `tests/` (62 pytest), `README.md`, `requirements.txt`, `.env.example`.
- Replay artifacts written to `frontend/public/replay/` only (index.json, traces/*.json x520, stats.json, flybrain.json, submission.json; 4.4 MB; no ground-truth labels; `accuracy_vs_labels` is one offline number).

### Score (rules engine, no Gemini key on this machine; `python work/docker/server/score_cli.py backend/out/submission.json`)
- FINAL 1.0000 = 0.30 * stage1 macro-F1 1.000 + 0.20 * stage3 defect-F1 1.000 + 0.50 * end-to-end 46/46 (1.000).
- Classification 520/520 (all five categories P=R=1.00). Field-level F1 1.000, exact-match 1.000 over 114 comparable pairs (txt, pdf, docx, xlsx all parsed).
- Reliability: escalation recall 20/20, precision 20/20; per reason 5/5 wrong_doc_type, 5/5 missing_attachment, 5/5 unreadable (image-only PDFs flagged, no OCR engine installed), 5/5 missing_value. `python backend/tools/score_local.py --errors` -> "0 emails differ from the reference".
- Error classes found on the way (fixed at the root, no id special-casing): (a) first run scored 0.9606: 3 true MISMATCH emails were sent to NEEDS_REVIEW by the gate because a PDF label with CJK junk (`TOTAL Gross Weight | II | (KGS)`) matched only fuzzily and the container-table detector false-matched "NADU 600102" in an address -> exact-synonym-in-any-variant rule, stricter container-row regex, fuzzy penalty 0.2 -> 0.12; (b) defect_fields ordering (scorer uses sets; submission is sorted anyway); (c) the gate treated `engine_fallback` + a benign formatting note as novel -> fallback is now familiar context in calibration and only low-confidence + fallback counts as an anomaly.
- Caveat: the dataset is synthetic with regular templates. 1.000 says the pipeline matches this generator's semantics, not that it will hold on a messy real inbox. Dev perturbation check (89 txt pairs re-rendered with MT / lbs / `KGS.00`, upper/title case, LTD->LIMITED): 0 false alarms, 0 missed defects. Unit tests cover the same normalisation.

### Fly gate: what it is and what it measurably does
- 32 inputs -> 1600 Kenyon cells (50x, 3 inputs each = 9% connectivity) -> APL-style global inhibition + top-80 WTA (5%) -> one decision neuron with plastic KC weights; verdict-gated LTD/LTP; weights persisted to `backend/out/flybrain_state.json`; interpretable (`kc_active`, `winner_kc`, per-input `drivers`). Wording everywhere: "architecture inspired by the fruit fly's olfactory system".
- Calibration (seeded, no labels): unsupervised familiarity on 2500 synthetic normal outcomes, threshold from held-out normals (0.08), evaluated on 10 synthetic anomaly kinds never trained on: held-out normal false-escalation 0.000, anomaly recall 0.995 (worst kind low_conf_only 0.95). Design lesson recorded in `flybrain.py`: with plain sparse coding a lone input could not be told apart from its familiar combinations; coincidence-detecting KCs + an input floor lifted recall from 0.66 to 0.995.
- On the real 520 emails the gate alone escalates 0 results (max suspicion 0.0003 over 109 comparisons); all 20 NEEDS_REVIEW are deterministic triggers (the net still scores them, 0.63-0.89, so the demo shows the pattern). So the gate cannot have hurt accuracy here, and it has ZERO measured contribution to the score either. It matters when confidence drops (Gemini path, OCR, typo-like near misses) or after human teaching. The pitch must not claim the gate raised the score.

### Objections / notes on ORCHESTRATION and CONTRACT design
1. idea.md says NEEDS_REVIEW is "exactly where the fly-brain gate's job is measured". In the labelled data every NEEDS_REVIEW case is deterministic (no attachment / wrong type / unreadable / blank) so the gate is not measured by any scored axis. Suggest the pitch demos the gate on the synthetic anomalies (calibration report in flybrain.json) and on live human teaching, not on the score.
2. The bundle labels treat a BL_COMPARISON email with no attachments that only asks for the draft BL as status OK, but the "attachments dropped" wording as NEEDS_REVIEW/missing_attachment. I follow the labels via a body-wording rule (`intake.py`, documented in README; Result has `comparison_performed:false`). Arguably that should be a review too; it is a data-semantics call the orchestrator may want to state in the pitch.
3. CONTRACT `status: null` for non-comparison vs `submission.json` needing a status: submission maps null -> "OK" (sample shape). Documented.
4. `received_at` does not exist in the dataset; it is simulated (deterministic 7-minute arrival stream). Frontend should not present it as real time.
5. Retry state (`RunState`) is in memory only; a server restart makes `/api/retry` return 409. Fine for a demo, not for production.
6. Frontend requests honoured: report payload never embeds `events`; SSE = one `data: {json}` message per Trace event; retry emits fresh start/done|error for only the retried nodes + downstream aggregator/compare/gate + a new `report`; `input_names` kept in flybrain.json/API and `kc_active` in [0,1600); `/api/review` response has `review.fly = {before, after, verdict, n_kc_updated}` and `GET /api/flybrain` `history[-1]` has `{before, after, verdict}`; index.json rows carry `from, subject, received_at, category, status, defect_fields` plus nested `result`. Extra Result keys are additive (see backend/README.md).

### Critique of the frontend half (verified by reading code and data, not by running the UI)
- `frontend/src/data/source.ts normalizeRows` reads `it.result ?? it.result_summary ?? inline`: matches my index.json (checked by reading). Not run in a browser by me.
- Objection: REPLAY review shows a heuristic fly update (x0.82 / x1.08) labelled simulated; the real rule exists in the backend. Keep the label, and do not present those numbers as the real Hebbian update; alternatively I can export a real precomputed learning demo.
- Objection: the sidebar "Accuracy vs. labels" shows 1.0 in replay (real, offline, synthetic-data number). Caption it as offline self-eval on the synthetic set so a judge does not read it as production accuracy.

### Verification evidence
- `python -m pytest backend/tests -q` -> 62 passed (compare normalisation, classifier rules, fly learning direction/locality/persistence/calibration, pipeline event order + parallel field starts, missing_attachment / wrong_doc_type / unreadable / missing_value, injected failure + retry, Gemini path with a fake client, Gemini failure fallback, no-key-never-claims-gemini, API SSE + review + 404/422).
- `python -m sdoc.run_all` -> 520 emails in ~18 s; submission keys/shape identical to `work/bundle/sample_submission.json`.
- API smoke via FastAPI TestClient (health, process SSE, result, retry after `?inject_fail=field:consignee,field:port_of_loading`, review, flybrain, stats, emails). Not run under a real uvicorn socket + browser.

### Known gaps
- Gemini path is written against the installed google-genai 2.18 API and tested only with a fake client; NOT verified against the live API (no key). Default model `gemini-2.5-flash` (override `SDOC_GEMINI_MODEL`).
- No OCR engine installed and no vision-LLM path: scanned PDFs are flagged `unreadable` (matches the labels, but a real read would be better UX).
- Classifier rules and label synonyms are tuned to this inbox's language; container size/type is not compared (spec compares count only); the gate has only been calibrated on synthetic vectors.

STATUS: OBJECTIONS=2
1. Gemini path unverified against the live API (needs a key and one real run; fallback-to-rules keeps the system working regardless).
2. Fly gate is validated only on synthetic anomalies and contributes nothing measurable to the official score; it needs real grey-zone data (Gemini/OCR runs, human verdicts) before any accuracy claim.
