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
python -m pytest tests -q              # 63 tests
python -m tools.grey_zone_eval         # held-out fly-gate eval (separate from the 520-email score)
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
* A Gemini node that fails (after up to `SDOC_GEMINI_MAX_ATTEMPTS` attempts, default 4, 45s timeout each) emits a visible `error` event, falls back to its rules twin, and is listed in `Result.errors` (`fallback: "rules"`). `POST /api/retry/{id}` re-runs only the errored nodes (state is kept in memory). For demos: `POST /api/process/{id}?inject_fail=field:consignee` fails that node on the first attempt, or click "Simulate failure" in the UI (LIVE mode, fails the classifier node) - no API param typing needed.
* **Throttling (reviews/judge.md #6):** a single `GeminiClient` is shared per pipeline run (classifier + all 7 field agents), and all its calls share one `asyncio.Semaphore(SDOC_GEMINI_CONCURRENCY)` (default 3) so a comparison email's up to 8 Gemini calls are never all in flight at once. Failed attempts back off exponentially with jitter (`0.8 * 2^attempt` normally, `4.0 * 2^attempt` specifically on a 429/`RESOURCE_EXHAUSTED`/rate-limit response, honouring a server-suggested retry delay when the error text carries one). This is written and unit-tested (fake client forcing 429-shaped errors) but **not exercised against the live API** (no key on this machine) - review-ready for a live key at demo time; if a key is added, run one real smoke email through `POST /api/process/{id}` before relying on it live.
* **Gemini path status: written against the installed `google-genai` 2.18 API (`client.aio.models.generate_content`, `response_mime_type=application/json`, `response_json_schema`) and unit-tested only with a fake client. It has NOT been run against the live API.** Evidence strings returned by the model are verified to occur in the document; unverifiable evidence caps confidence (the gate sees it). Compare stays a pure function - the LLM never decides match/mismatch.

## Parsing (`docparse.py`, `rules_extract.py`)

txt, pdf (pymupdf text layer, rows rebuilt from span positions), docx (paragraphs + tables, incl. 4+-column and transposed "header row of labels / value row below" layouts, merged cells de-duplicated), xlsx (label/value rows, incl. transposed sheets). All formats reduce to `Label: value` lines; accepted label/value separators: colon, whitespace-column, `Label - value`, `Label = value`, markdown table rows (`| Label | value |`), and (only on OCR-read text, where a scan often drops the colon) a bare `Label value` line matched against an exact known synonym only (never fuzzy, to keep it cheap and safe on ordinary prose). Image-only PDFs: OCR via `rapidocr-onnxruntime` (pure Python + onnxruntime, no system binary, ships its own small models - verified working in this sandbox) or a local Tesseract if present; `SDOC_OCR=off` disables both, falling back to the honest `unreadable` flag. A plain-text attachment that does not end with a newline (`ParsedDoc.truncated`) is treated as possibly cut off mid-transfer: a numeric field whose evidence sits on/near the document's last line is never reported as a confident value (it becomes `missing`, not a false MISMATCH - see judge.md #4). Document type is detected from the title block (SI / BL / Commercial Invoice / Packing List / Certificate of Origin).

Normalisation (`normalize.py`): names ignore case, punctuation, `&`/`and`, legal-suffix spelling (LTD/LIMITED, PTE, SDN BHD, GMBH, `L.L.C.`/`LLC`, `FZ-LLC`/`FZLLC`, `S/B`->`SDN BHD`, leading `PT`/`THE`) and a parenthetical/trailing local-registration qualifier (`(S)`/`(Malaysia)`, `, Dubai`) but still separate genuinely different entities (e.g. `APRIL FINE PAPER TRADING` vs `... (MIDDLE EAST) FZE`, or two different explicit qualifiers like `(S)` vs `(M)`); on OCR-read text the near-miss/typo similarity floor is relaxed (0.72 vs 0.88) since OCR itself introduces 1-2 character noise. Ports ignore country/UN-LOCODE/common aliases (country list = `pycountry`'s ~250 official/common names, unioned with a small hand-kept abbreviation list for `UAE`/`USA`/`UK`/`S. Korea`/etc. - not a short hard-coded list any more), `PORT OF X`/`X PORT` wrappers, and known abbreviations (`HCMC`, `PTP`, `KLANG`). Container counts parse `2 x 40HC`, `40HC x 2` (reversed order), `2X40'HC`, `TWO (2)`, `1x20'+2x40HC` (count only - size/type is intentionally not compared, per the locked scope). Weights parse kg / MT / lbs and thousand separators. Blank tokens (`???`, `____`, `TBA`, `N/A`) are *missing*, never a mismatch.

**Generalisation re-verification (fresh phrasing/layouts I wrote myself, not the shipped 520-email set):** classifier 23/23 on fresh generic shipping-inbox phrasing (was 18/23); all 10 layout perturbations (dash/equals/tab/markdown-table/lower-case/spaced/bullets/CRLF/value-on-next-line/blank-lines) 0/84 changed; docx 4-column and transposed tables and xlsx transposed sheets verified extracting all 7 fields correctly; 125/138 name/port/weight/container normalisation cases from a hand-written adversarial set (legal suffixes, missing countries, reversed container order) now pass (was ~112/138) - remaining 13 are either a genuinely contradictory pair in my own test list (documented below) or pre-existing, deliberate design trade-offs (see Known gaps).

## Status semantics (per bundle README)

* `OK` all 7 fields match; `MISMATCH` >=1 differs (SI is the reference) with `defect_fields`; `NEEDS_REVIEW` + `review_reason`:
  `missing_attachment` (0 attachments or only one document, when the email claims documents), `wrong_doc_type` (invoice / packing list / COO / non-SI-BL pair), `unreadable` (empty, corrupt, image-only unreadable even after OCR), `missing_value` (a required field blank or not found in SI or BL, or a field agent failed), `low_confidence` (Round 2 addition - a pure fly-gate grey-zone escalation with nothing missing/unreadable; mapped to `missing_value` only in the exported `submission.json`, which has no 5th slot - see CONTRACT.md).
* Classifier confidence is itself routed through the same gate for ANY category (not just BL_COMPARISON): a genuinely ambiguous classification (no rule matched at all) can become `NEEDS_REVIEW`/`low_confidence` even for a SPAM/GENERAL/etc. email; a confidently-matched classification of any category, and every one of the real 520 emails, is untouched (0 impact on the shipped score - verified, see Results).
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
* On the real 520-email run the gate now escalates **2 of 520 on its own** (`decided_by: "flynet"`, not a deterministic trigger): the two genuinely scanned PDFs (`email_513`/`email_514`) that OCR (see below) reads well enough to extract from, but whose per-field confidence is low enough that the gate - not a hard-coded rule - decides a human should see them. A third scanned email (`email_512`) still lands on a deterministic `missing_value` (OCR did not recover one field at all). This is a real, if small, non-zero contribution on the shipped data; it does not touch classify/extract/compare accuracy (still 1.0000 - see Results below).
* **Held-out grey-zone evaluation (`python -m tools.grey_zone_eval`, separate from the 520-email score - reviews/judge.md #1):** builds real SI/BL pairs from the bundle's own clean `.txt` attachments, applies 5 hand-written mutations, and reruns them through the FULL pipeline (not synthetic vectors): `clean` (unmodified) and `clean_defect` (one confident weight defect) are gold "should NOT escalate"; `near_miss_typo` (1-letter consignee typo), `conflicting_line` (a look-alike second weight line), and `ambiguous_role` (both attachments' title lines stripped, so SI/BL role assignment falls back from a confident detection) are gold "should escalate". 40 pairs/bucket, seeded/reproducible:

  | bucket | gold | gate escalated (flynet) | rate |
  |---|---|---|---|
  | clean | no | 0/40 | 0.0 |
  | clean_defect | no | 0/40 | 0.0 |
  | near_miss_typo | yes | 25/40 | 0.625 |
  | conflicting_line | yes | 35/40 | 0.875 |
  | ambiguous_role | yes | 15/40 | 0.375 |

  Overall: **precision 1.00** (0 false escalations on 80 clean/confident-defect controls - a confirmed real defect is never gated away), **recall 0.625** (75/120 of the genuinely-ambiguous cases), **F1 0.769**. This is independent of `calibrate()`'s own synthetic-vector report below (different generation method, real documents, held out from calibration) - it is the non-circular measurement the gate previously lacked. Weakest bucket: `ambiguous_role` (0.375) - stripping only the title line still leaves enough body content (SI/BL-specific wording) for `detect_doc_type` to partially recover in some cases, which is honestly a *good* sign for the parser but means fewer of those cases reach the gate as truly ambiguous; noted as a real, unresolved limitation, not tuned away.
* Human verdicts: `POST /api/review/{id}` applies the decision (confirm_ok / confirm_mismatch / correct_field -> recompute with the pure compare), closes the escalation and updates the net (`escalation_verdict` explicit, or inferred for gate-decided cases) **only when `gate.decided_by == "flynet"`** - a deterministic trigger never went through the gate, so there is nothing for a verdict to reinforce; the API instead returns `review.fly = {skipped: true, reason: "..."}`, shown honestly in the UI instead of a misleading no-op. Weights persist in `out/flybrain_state.json`; `run_all` / `export_replay` always use a fresh calibrated net. KC->decision weights now start at 0.9 (not 1.0): a weight already at the ceiling cannot be potentiated further, so the very first "escalation was correct" confirmation of any pattern used to be an invisible no-op (0.63 -> 0.63) even though real learning happened on the other verdict - see reviews/developer.md #8.
* `many_mismatches` (>=3 confident field differences) is no longer, by itself, an anomaly signal: it only contributes to the gate's suspicion when at least one of those mismatches is itself shaky (near-miss or low-confidence). A confirmed, clean 3+-field defect is reported as `MISMATCH` with all its `defect_fields`, not gated away into a review that would have dropped them (reviews/judge.md #2/#3; verified 0/40 false escalations on the `clean_defect` bucket above).
* A gate escalation of an already-decided `OK`/`MISMATCH` result now **keeps** whatever compare confirmed (`has_defect`/`defect_fields` are not wiped) and uses the honest `review_reason: "low_confidence"` (not `missing_value`/`unreadable` when nothing is actually missing or unreadable) - see CONTRACT.md for the submission-schema mapping note.

## Results (rules engine, local reference labels, 520 emails)

`final 1.0000` = 0.30*macroF1 1.000 + 0.20*defect-F1 1.000 + 0.50*end-to-end 46/46 (re-verified after every Round 2 change: `python -m sdoc.run_all` -> 520 emails in ~37s -> `PYTHONUTF8=1 python work/docker/server/score_cli.py backend/out/submission.json` -> unchanged). Classification 520/520, defect fields exact 114/114 comparable pairs, escalation recall 20/20 and precision 20/20 (5 wrong_doc_type / 5 missing_attachment / 4 unreadable / 6 missing_value - one of the three genuinely scanned emails moved from a deterministic `unreadable` to a genuine gate (`flynet`) escalation once OCR could read it; still 20/20 correctly escalated). This is a *synthetic* dataset with regular templates; expect lower numbers on messier real inboxes - see the generalisation re-verification above and the held-out grey-zone eval for numbers beyond this set.

## API (CONTRACT.md)

`GET /api/health`, `GET /api/emails`, `GET /api/email/{id}` (body), `POST /api/process/{id}` (SSE; final event `report` carries the Result; `?force_engine=`, `?inject_fail=`), `GET /api/result/{id}`, `POST /api/retry/{id}` (SSE, only errored nodes re-run), `POST /api/process_all` (SSE progress, writes `out/submission.json`), `POST /api/review/{id}`, `GET /api/flybrain`, `GET /api/stats`. Extra Result keys beyond CONTRACT (additive): `state` on each field, `flags`, `near_miss`, `review_detail`, `suspected_defect_fields`, `comparison_performed`, `docs`, `classifier_confidence`, `review`, gate `drivers` / `decided_by`.

## Files

`config.py` env/paths; `inbox.py` data access; `docparse.py` + `ocr.py` parsing; `labels.py` label synonyms; `normalize.py` value normalisation; `rules_extract.py` rules field agent; `classifier.py` rules classifier; `llm.py` Gemini nodes; `intake.py` SI/BL role assignment + preflight; `compare.py` pure compare/decide; `flybrain.py` gate; `pipeline.py` orchestration + trace; `store.py` results + human review; `api.py` FastAPI; `run_all.py`, `export_replay.py`, `submission.py`; `tools/score_local.py` dev-only scoring; `tools/grey_zone_eval.py` held-out gate evaluation (Round 2, not part of the submission).

## Known gaps

Gemini path unverified against the live API (no key on this machine; throttled/backed-off and unit-tested with a fake client - see above); retry state is in memory (a server restart loses it); classifier rules, while re-verified against fresh phrasing (23/23) and much broader label/legal-suffix/country coverage this round, are still ultimately tuned against this inbox's genre of language; container size/type (20' vs 40') is not compared (spec compares count only, a locked scope decision); the grey-zone gate's `ambiguous_role` recall (0.375, see the held-out eval above) is the weakest of the three grey-zone categories and was not artificially tuned up; a handful of name/port/weight/container normalisation edge cases in a hand-written adversarial test remain unresolved by design (documented per-case in `reviews/developer.md` Round 2 item #3 - e.g. a name with zero legal suffix always "matches" one that has one, an inherited design trade-off, not a Round 2 regression).
