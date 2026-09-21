# sdoc backend - shipping document verification ("Drosophila Gate")

Python 3.10, FastAPI, numpy. Package `sdoc`. Pipeline (every node is a real call and emits a trace event):

```
inbox -> classifier -> 7 parallel field agents -> aggregator -> compare (pure function, no LLM) -> fly-brain gate -> report
```

## Run

```bash
cd backend
pip install -r requirements.txt
python -m sdoc.run_all                 # 520 emails -> out/submission.json (+ out/results.json)
python tools/score_local.py --errors   # DEV ONLY: scores with work/docker/server/scoring.py
python -m sdoc.export_replay           # -> ../frontend/public/replay/ (static replay for the Vercel build)
uvicorn sdoc.api:app --port 8000       # HTTP API + SSE (CONTRACT.md), CORS open
python -m pytest tests -q              # 62 tests
```

Data: `SDOC_DATA_DIR` (default `../work/bundle`). Official scorer: `python work/docker/server/score_cli.py backend/out/submission.json`.

## Engine selection (honest by construction)

| Node | key present | no key |
|---|---|---|
| classifier | Gemini structured JSON (`engine: "gemini"`) | deterministic weighted-signal rules (`"rules"`) |
| 7 field agents | Gemini structured JSON + verbatim evidence | label-synonym alignment + unit/format normalisation (`"rules"`) |
| aggregator, compare | pure functions (`"pure"`) | same |
| gate | numpy fly-style net (`"flynet"`) | same |

* Key lookup: `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) from the environment or `backend/.env`. **No key exists on the build machine, so every number in this repo was produced by the `rules` engine.** Force with `SDOC_ENGINE=rules|gemini` or `?force_engine=` on the API.
* Every trace event and every Result carries the engine that really produced it. Asking for `gemini` without a key silently *reports* `rules`; nothing is ever labelled `gemini` that was not.
* A Gemini node that fails (after 2 attempts, 45 s timeout) emits a visible `error` event, falls back to its rules twin, and is listed in `Result.errors` (`fallback: "rules"`). `POST /api/retry/{id}` re-runs only the errored nodes (state is kept in memory). For demos: `POST /api/process/{id}?inject_fail=field:consignee` fails that node on the first attempt.
* **Gemini path status: written against the installed `google-genai` 2.18 API (`client.aio.models.generate_content`, `response_mime_type=application/json`, `response_json_schema`) and unit-tested only with a fake client. It has NOT been run against the live API.** Evidence strings returned by the model are verified to occur in the document; unverifiable evidence caps confidence (the gate sees it). Compare stays a pure function - the LLM never decides match/mismatch.

## Parsing (`docparse.py`, `rules_extract.py`)

txt, pdf (pymupdf text layer, rows rebuilt from span positions), docx (paragraphs + tables, merged cells de-duplicated), xlsx (label/value rows). All formats reduce to `Label: value` lines. Image-only PDFs: OCR only if a local Tesseract is installed (`SDOC_OCR=off` to disable), otherwise flagged `unreadable`. Empty / truncated / garbled files -> `unreadable`. Document type is detected from the title block (SI / BL / Commercial Invoice / Packing List / Certificate of Origin).

Normalisation (`normalize.py`): names ignore case, punctuation, `&`/`and`, legal-suffix spelling (LTD/LIMITED, PTE, SDN BHD, GMBH...) but still separate different entities (e.g. `APRIL FINE PAPER TRADING` vs `... (MIDDLE EAST) FZE`); ports ignore country, UN/LOCODE, common aliases; container counts parse `2 x 40HC`, `2X40'HC`, `TWO (2)`, `1x20'+2x40HC`; weights parse kg / MT / lbs and thousand separators. Blank tokens (`???`, `____`, `TBA`, `N/A`) are *missing*, never a mismatch.

## Status semantics (per bundle README)

* `OK` all 7 fields match; `MISMATCH` >=1 differs (SI is the reference) with `defect_fields`; `NEEDS_REVIEW` + `review_reason`:
  `missing_attachment` (0 attachments or only one document, when the email claims documents), `wrong_doc_type` (invoice / packing list / COO / non-SI-BL pair), `unreadable` (empty, corrupt, image-only without OCR), `missing_value` (a required field blank or not found in SI or BL, or a field agent failed).
* Design assumption: a BL_COMPARISON email with **no** attachments that merely asks someone to *send* the draft BL ("please assist to send the draft BL") is not a failed comparison: `status: OK`, `comparison_performed: false`, headline "No documents to compare - draft BL requested". The same email saying documents are attached/dropped -> `missing_attachment`. The bundle's labels follow this split.
* Non-comparison categories have `status: null` in the Result (CONTRACT) and `OK` in `submission.json` (sample shape).
* `received_at` is **simulated** (the dataset has no timestamps): a deterministic arrival stream derived from the email number.

## Fly-brain gate (`flybrain.py`) - architecture inspired by the fruit fly's olfactory system

Our own small network in the style of the Drosophila mushroom body. It is not real fly data, not FlyWire, not a connectome.

```
32 inputs  --fixed sparse random projection (3 inputs/KC, 9% connectivity)-->  1600 Kenyon cells (50x)
           --APL-style global inhibition + top-k winner-take-all (k = 80 = 5%)-->  sparse code
           --plastic KC->decision-neuron weights-->  suspicion in [0,1]  vs  threshold
```

* Inputs: per-field mismatch flag (7), per-field low extraction confidence (7), per-field near-miss/typo-like difference (7), many mismatches, OCR used, weak document-type detection, weak classifier confidence, unit conversion, ambiguous/conflicting parse, internal inconsistency, benign normalisation applied, engine fallback, deterministic trigger, missing value.
* KCs are coincidence detectors (one lone input cannot fire a KC) and inputs below a floor are silence, so a *combination* of signals that has not been seen as normal fires unfamiliar cells.
* Learning (dopamine-gated, STDP-like eligibility): KC->output weights start at 1 ("everything is novel"). Familiarity = depress active KCs (`w *= 1-eta`); "escalation correct" = potentiate (`w += eta(1-w)`). Only ~5% of cells change per update, so a correction is local and inspectable (`explain` returns active KCs, the inputs each reads, per-input drive share).
* **Scope**: it decides escalate-vs-report only, in the grey zone. It never edits extracted values or match/mismatch. Deterministic triggers (missing attachment, unreadable, wrong doc type, blank value) go straight to NEEDS_REVIEW; the net still scores them so the demo shows the pattern and the human verdict can teach it (`decided_by: deterministic_trigger`). A gate escalation of an OK/MISMATCH result becomes `NEEDS_REVIEW` (`review_reason` = `unreadable` if OCR was used, else `missing_value`; `suspected_defect_fields` keeps what it would have reported).
* **Calibration** (`FlyBrain.calibrate`, seeded, reproducible, no ground truth): (1) 2500 synthetic *normal* pipeline outcomes (0-2 confident mismatches, benign notes, fallback noise) are shown once each with depression; (2) the threshold is set from the 99.5th percentile of suspicion on 1000 held-out synthetic normals (+0.03, floor 0.08); (3) recall is measured on 10 kinds of synthetic anomalies never trained on. Current numbers (`out`/`flybrain.json` -> `calibration`): held-out normal false-escalation 0.0, anomaly recall 0.995 overall (worst kind: `low_conf_only` 0.95).
* On the real 520-email run the gate escalates **0** results on its own (max suspicion 0.0003 over 109 comparisons, threshold 0.08): every escalation in `submission.json` is a deterministic trigger. It cannot lower classify/extract/compare accuracy on this data. It matters when confidence drops (Gemini path, OCR, typo-like near misses) and when a human teaches it.
* Human verdicts: `POST /api/review/{id}` applies the decision (confirm_ok / confirm_mismatch / correct_field -> recompute with the pure compare), closes the escalation and updates the net (`escalation_verdict` explicit, or inferred for gate-decided cases). Weights persist in `out/flybrain_state.json`; `run_all` / `export_replay` always use a fresh calibrated net.

## Results (rules engine, local reference labels, 520 emails)

`final 1.0000` = 0.30*macroF1 1.000 + 0.20*defect-F1 1.000 + 0.50*end-to-end 46/46. Classification 520/520, defect fields exact 114/114 comparable pairs, escalation recall 20/20 and precision 20/20 (5 of each `review_reason`). This is a *synthetic* dataset with regular templates; expect lower numbers on messier real inboxes. Robustness checks beyond the labelled data: unit tests for normalisation, and a dev perturbation run (89 txt pairs re-rendered with MT/lbs/`KGS.00`, upper/title case, LTD->LIMITED) still gives 0 false alarms and 0 missed defects.

## API (CONTRACT.md)

`GET /api/health`, `GET /api/emails`, `GET /api/email/{id}` (body), `POST /api/process/{id}` (SSE; final event `report` carries the Result; `?force_engine=`, `?inject_fail=`), `GET /api/result/{id}`, `POST /api/retry/{id}` (SSE, only errored nodes re-run), `POST /api/process_all` (SSE progress, writes `out/submission.json`), `POST /api/review/{id}`, `GET /api/flybrain`, `GET /api/stats`. Extra Result keys beyond CONTRACT (additive): `state` on each field, `flags`, `near_miss`, `review_detail`, `suspected_defect_fields`, `comparison_performed`, `docs`, `classifier_confidence`, `review`, gate `drivers` / `decided_by`.

## Files

`config.py` env/paths; `inbox.py` data access; `docparse.py` + `ocr.py` parsing; `labels.py` label synonyms; `normalize.py` value normalisation; `rules_extract.py` rules field agent; `classifier.py` rules classifier; `llm.py` Gemini nodes; `intake.py` SI/BL role assignment + preflight; `compare.py` pure compare/decide; `flybrain.py` gate; `pipeline.py` orchestration + trace; `store.py` results + human review; `api.py` FastAPI; `run_all.py`, `export_replay.py`, `submission.py`; `tools/score_local.py` dev-only scoring.

## Known gaps

Gemini path untested live; no vision-LLM reading of scanned pages (image-only PDFs are flagged unreadable unless Tesseract is installed); retry state is in memory (a server restart loses it); classifier rules are tuned to the language of this inbox; container size/type (20' vs 40') is not compared (spec compares count only).
