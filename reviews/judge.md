## Round 1 - JUDGE, 2026-09-21

Method: read all briefs + 3 reviews, re-ran everything myself, wrote 6 perturbation harnesses (`reviews/judge_scratch/*.py`, scratch data in `reviews/judge_scratch/data/`), drove the UI in headless Chrome 153 over CDP (Claude-in-Chrome extension not connected) in REPLAY and LIVE mode (real uvicorn + Vite proxy, output dir copied to scratchpad so `backend/out` state untouched). Screenshots: `reviews/shots/judge-*.png`. Dev servers + Chrome stopped, ports 8000/5311 verified free. Originals spot-checked: infopack.docx text and use-case PDF (4 pages) match the `work/*.txt` extracts (incl. "No mismatch detected", scanned docs, "Handle processing failures visibly").

### 1. Independent verification (numbers)

| Check | Result |
|---|---|
| `cd backend && pytest -q` | 62 passed (7.6 s) |
| `python -m sdoc.run_all` | engine=rules, 520 emails, 17.8 s; 220 BL_COMPARISON / 125 SI / 75 INV / 60 GEN / 40 SPAM; 454 OK / 46 MISMATCH / 20 NEEDS_REVIEW |
| `score_cli.py backend/out/submission.json` | **FINAL 1.0000** (stage1 macroF1 1.000, stage3 defect-F1 1.000, e2e 46/46, escalation P=R=1.00, 5/5 per reason). Claim CONFIRMED. (Scorer needs `PYTHONUTF8=1` on Windows cp1251 console, unicode bars crash it - not a product bug.) |
| submission shape | 520 keys == inbox ids == `sample_submission.json` keys; every entry has exactly `category,status,review_reason,has_defect,defect_fields`; non-comparison -> `OK` as in sample. |
| label leakage grep | no read of `ground_truth.json`, `data_v2`, generator, or any `email_NNN` literal in `backend/sdoc` or `frontend/src`; replay/dist contain only one offline number (`accuracy_vs_labels`). `tools/score_local.py` (dev-only) is the only consumer of the scorer. CLEAN. |
| `tsc -b` + `vite build` (to scratch outDir) | 0 TS errors, JS 321 kB (102 kB gzip), 6.3 MB with replay; no ground-truth strings in the bundle. |
| REPLAY drives UI | YES. `index.json` (list, rows carry `result`), `traces/<id>.json`, `stats.json`, `flybrain.json` (1600 KC, 32 inputs, `input_names`, `calibration`) all consumed; sidebar 520/114/72/100%, graph lights per trace, report table, fly panel 1600 KC. **No shape mismatch between backend export and frontend adapters (previous "mock-verified only" risk retired).** |
| LIVE drives UI | YES. `/api/health` auto-detect, SSE via proxy, streamed lighting, `POST /api/review` (backend log 200, real `flybrain.history` entry with `simulated:false`), stats sidebar 20 -> 19 review after my confirm. API retry verified: `inject_fail=field:consignee,field:port_of_loading` -> two red nodes, NEEDS_REVIEW; `/api/retry` re-runs only those 2 + aggregator/compare/gate -> MISMATCH on consignee/notify. |

**Anti-overfit hunt: a perfect 1.0 on the synthetic set IS partly overfit. Evidence below.** The pipeline generalises fail-safe (mostly degrades to NEEDS_REVIEW, rarely silently wrong) but has real false alarms on messier input.

### 2. Robustness results (my own perturbations of 40-84 txt SI/BL pairs re-run through the real pipeline)

Semantics-preserving (expected: unchanged status). "esc" = degraded to NEEDS_REVIEW/missing_value (fail-safe but the real defect is lost); "FA" = false MISMATCH.

| Perturbation | Result |
|---|---|
| tab / lowercase labels / `Label :   v` / bullets `* L: v` / CRLF / value on next line / blank lines / BOM+trailing ws / upper- or title-case values / double spaces / shuffled lines / preamble+footer / look-alike extra fields (Net/Tare/Container No) | 0 changed. Good. |
| separators `Label - value`, `Label = value`, markdown `\| Label \| value \|` | 84/84 -> esc (all 7 fields "missing") |
| docx 4-column tables (2 label/value pairs per row), transposed docx/xlsx tables (header row of labels + value row) | 84/84 -> esc |
| docx paragraphs, docx 2-col table, xlsx A/B, xlsx B/C, xlsx numeric weight, pdf lines, pdf columns, mixed txt/pdf, mixed docx/xlsx | 0 changed. Good. |
| image-only PDF pair | 84/84 -> NEEDS_REVIEW/unreadable (never read; no OCR/vision path) |
| unseen label synonyms (68 tried) | 12 miss (esc): `Shipper Name & Address`, `Shipper / Consignor`, `Sender`, `Consignee / Buyer`, `Buyer`, `Notify Party / Address`, `Loading Port / Place of Receipt`, `Departure Port`, `Final Destination`, `Port of Delivery`, `Containers/Packages`, `Total Cntrs`, `Equipment Count`, `Gross Weight of Cargo`, `Cargo Gross Weight`, `Weight` ... The rest (POL/POD/G.W./Gross Mass/GW/Qty of Containers...) hit. No false alarms from label misses. |
| value normalisation unit run (138 pairs) | 101 as I expected. **False alarms on plausible formatting** (real SI vs BL of the same entity): `SDN BHD` vs `S/B`; `LLC` vs `L.L.C.`; `... LLC` vs `... LLC, DUBAI`; `GMBH` vs `GMBH & CO. KG`; `PT X` vs `X`; `FZ-LLC` vs `FZLLC`; `(S)` vs `SINGAPORE`; `(M)` vs `(MALAYSIA)`; `SINGAPORE (SGSIN)` vs `SINGAPORE SGSIN`; `PORT KLANG, MALAYSIA` vs `PORT KLANG MALAYSIA` / `Port Klang - Malaysia`; **any country not in the hard-coded `_COUNTRIES` list (IRAN, IRAQ, COLOMBIA, ARGENTINA, ECUADOR, `THE NETHERLANDS`, `DJIBOUTI, DJIBOUTI`)** when only one doc carries the country; `JEBEL ALI, UAE` vs `JEBEL ALI PORT`; `40'HC x 6`; `22 MTON`. |
| truncated BL (90% / 70% / 50% / 30%) | 0 / 35 / 40 / 40 of 40 -> esc missing_value. Good, fail-safe. |
| **BL cut mid-number (`Gross Weight: 2`)** | **22/22 clean pairs -> FALSE MISMATCH "SI 21577 / BL 2"**; 11 real-mismatch pairs get a bogus extra weight defect; only 7 (>=3 diffs) caught by the gate. Silent wrong answer, undetected corruption |
| garbage / binary / empty BL | NEEDS_REVIEW unreadable or missing_value. Good. |
| lookalike field `Gross Weight of container: 2,000 KG` added | 40/40 -> gate escalation (conflict flag). Good grey-zone behaviour. |

True-defect detection (expect MISMATCH): weight +1 kg, +10 kg, +500 kg as MT, container +1: detected on every email the gate did not escalate. **One-letter typo in consignee:** of 60 clean pairs 22 escalated by the gate (near-miss), 11 reported MISMATCH (short names have sim < 0.88), so "typo = defect or review?" depends on name length. Swap POL/POD, notify name -1 letter: detected/escalated, none silently missed.

Fresh-phrasing classifier probe (23 emails I wrote in generic shipping-inbox language): **18/23 = 78%**. Misses: "New booking - please raise BL instruction" -> GENERAL; "Statement of account August" -> GENERAL; "Re: Draft BL update / thanks, will review" -> BL_COMPARISON; "Claim your prize ... send bank details" -> GENERAL; phishing "account is locked" w/ lookalike-domain link -> GENERAL. Cause visible in `classifier.py`: sender allow-list `aprilasia|fujitogrp|safqa|psabdp|roxcel|ifpla|algurg|vitalsolutions`, subject regexes for `_RPA_`, `Berthing Report`, `UPDATE SUMMARY`, `MISSING GR`, OC-code pattern `5[A-Z]{3}-\d+`, `happy and prosperous`. The header claims "generic shipping-inbox language, never ... generator"; that is not fully true: these are dataset-derived vocabulary. No email ids or labels are read, so it is not cheating, but it is overfit to this inbox.

### 3. Spec coverage checklist (`usecase.txt`)

| Item | Status | Evidence |
|---|---|---|
| Classify 5 categories | MET (on data) / PARTIAL (generalisation) | 520/520; fresh-phrasing 78% for rules; Gemini path would carry generalisation but is unverified live |
| Extract 7 fields SI+BL | MET | txt/pdf/docx/xlsx parsed; alignment by meaning incl. `Load Port`=`Port of Loading`, CJK-glued labels; brittle beyond dataset layouts (see 2) |
| Compare, side by side, "No mismatch detected" | MET | UI SI-vs-BL table with evidence lines; headline "No mismatch detected"; `container_count: SI 3 / BL 4` style headline verified (email_004 live) |
| Ask for help: escalate with context, evidence, reason | MET | reason enum + human-readable reason + evidence rows + open/resolved state; live-verified |
| PDF and Word attachments, tables | MET | 28 pdf / 8 docx / 22 xlsx parsed; my re-rendered variants pass except 4-col/transposed tables |
| Scanned docs (OCR or vision LLM) | **PARTIAL** | image-only PDFs are detected and escalated as `unreadable` with reason, but never READ; no OCR engine installed, no vision path in `llm.py` (`contents=prompt` text only) |
| Messier inputs (labels, formats, misleading subjects, missing attachments) | PARTIAL | dataset's mess handled (score 1.0); misleading subject handled by attachments+body; my harder variants show ~12 label misses, layout misses, ~25 formatting false alarms (sec. 2) |
| Distinguish real discrepancy from formatting issue | PARTIAL | unit/case/legal-suffix/country/code normalisation good for the seen forms; no false alarms on 0-change perturbations of the listed kinds; fails on unseen legal forms/countries |
| Reliability: unreadable / missing value / uncertain -> review with evidence+reason | MET | 4 deterministic reasons + gate on uncertainty (proved on my perturbations: 40/40 conflict cases, 22/33 typo cases escalated) |
| Human confirm/correct -> report updates | MET (LIVE) / PARTIAL (REPLAY = simulated locally, labelled) | live: `POST /api/review` recomputes with pure compare, closes escalation, list dot + stats update |
| Processing failures visible + retry | PARTIAL | backend: per-node error events, fallback, `/api/retry` re-runs only failed nodes (verified). UI: red node + "Retry failed nodes" exist, but failure can be produced only by API `?inject_fail=`; nothing in the UI triggers it, retry is "simulated" in REPLAY |

### 4. Fly-brain: honesty and value

* Honesty: wording is correct everywhere I looked ("Architecture inspired by the fruit fly's olfactory system", "our own small network"). No FlyWire/connectome claim in UI, README, code. PASS.
* Real on real data: max suspicion 0.0003 over 109 comparisons, 0 gate-only escalations; all 20 NEEDS_REVIEW are deterministic triggers and every one shows the SAME suspicion (0.6321 = 1-1/e for the 13 non-missing-value ones, 0.8854 for the rest). A judge who opens 3 review emails sees an identical number and asks "is it doing anything?". As shipped, the demo path reads as decorative. DEVELOPER's own objection #1/#2 in developer.md is correct and unresolved.
* But the gate is NOT decorative when the input is genuinely grey. My measurements (fresh gate, reproducible: `reviews/judge_scratch/run_e.py`, `run_f.py`): 63/80 near-miss-typo'd consignee pairs and 40/40 pairs with a conflicting look-alike weight line are escalated by the gate on its own; on those data the rules alone would have printed a wrong MISMATCH (typo) or a possibly wrong pick (conflict). **Few-shot correction works and is local:** teaching `escalation_unneeded` on one pattern drops suspicion 0.487 -> 0.234 -> 0.101 -> 0.042, the pattern stops escalating after 3 verdicts (updates 9-54 of 1600 KC), and other near-miss vectors drop from 62/62 to 27/62 escalating. That is exactly the idea.md pitch and it is measurable. It is simply not in the shipped demo/replay data.
* Weak spots: (a) calibration recall 0.995 is measured on synthetic anomalies authored by the same developer from the same 32 input semantics: circular, present as a sanity check only; (b) `many_mismatches` (>=3 diffs) is an anomaly by construction, so a genuinely bad BL with 3+ real defects is escalated and its `defect_fields` are dropped (`has_defect:false`) - for e2e scoring that trades a caught defect for a review; (c) a gate escalation is reported with `review_reason: missing_value` (or `unreadable` when OCR) although nothing is missing; that is a lie in the field the scorer/UI reads; (d) escalation of a MISMATCH email also drops confirmed non-near-miss mismatches (12/15 emails with 1-2 real defects + one typo lost their real defects).
* What would make it demonstrably matter without hurting accuracy: ship a **"messy inbox" grey-zone set** generated by script (the mutations in `perturb.py`/`run_d.py`: typo'd names, conflicting weight lines, 4-col tables, truncated values, OCR-read scans, unseen labels) as extra replay traces, run the same pipeline, and publish a 2x2 table: with/without gate x (false alarms, missed defects, human-review load) + the 3-verdict teaching curve above. Keep the official 520-email number untouched (gate = 0 contribution there, say so). In the UI make a "Grey-zone demo" chip list that opens escalations where the fly panel lights up and the verdict flips future behaviour. Do not present the gate as raising the official score.

### 5. Architecture vs idea.md

| idea.md element | Verdict |
|---|---|
| classifier -> 7 parallel field agents -> aggregator -> pure compare -> fly gate -> escalation | REAL: `pipeline.py` asyncio.gather of 7 per-field tasks each emitting start/done/error; aggregator collates and reports failed agents; `compare` is pure (no LLM); gate is numpy; events are the ones the UI renders (`t_ms`, duration, engine). In rules mode the "agents" are regex twins (labelled `rules`); not an LLM claim. |
| UI graph reflects backend events | YES (verified live SSE and replay events; per-node engine + duration) |
| Gemini path | Exists, structured JSON, evidence verified verbatim, fallback visible. **Unverified live** (fake-client tests only). See objection 7. |
| Fly-brain gate | real net, real learning, interpretable; see sec. 4 |
| Vercel replay | READY: `vercel.json` rewrites exclude `replay/`,`assets/`,`api/`; auto-detect falls back LIVE -> REPLAY -> MOCK in ~1.5 s; build 6.3 MB. In replay, review/retry are simulated + labelled; the Hebbian update uses the real rule on exported weights (INNOVATOR change), so the "unneeded" verdict visibly changes weights; the default click (verdict = "escalation correct" for deterministic triggers) is a no-op: 0.63 -> 0.63, mean weight 1.00 -> 1.00. |

Cost of untested Gemini with judges: HIGH-severity/medium-probability. If a judge drops a key in: 1 classify + 7 field calls per comparison email; free-tier limits for flash-class models are a small number of requests per minute (I believe ~10 RPM / a few hundred per day for gemini-2.5-flash free tier - verify against current docs). `GeminiClient` has 2 attempts with 0.8-1.6 s sleep and no throttle/`retry-after`; 7 parallel calls will 429, fall back to rules, and the UI will show red errored nodes + fallback engine on most runs; a full `process_all` on Gemini would exhaust a daily quota. Model id `gemini-2.5-flash` and google-genai 2.18 call shape are unverified. If it works, it fixes the generalisation gaps above; if it does not, the demo still works on rules (good design).

### 6. Demo / pitch / UX

Strong: cinematic reference match, real 7 fields, engine badges, honest pills (REPLAY/LIVE), "Accuracy vs labels ... offline self-eval on the synthetic set" caption, keyboard shortcuts, 520-email list with filters/search, report table with evidence, mismatches highlighted, non-comparison classification card. LIVE and REPLAY both actually work. Defects I saw:
* Timeline step "Aggregate + compare" prints **"all 7 match"** for NEEDS_REVIEW emails where compare was skipped (email_512, 513, 517; unreadable/missing value). A false statement on the demo's key strip.
* At 1536x1024 in Report tab the Human-review block (the required HITL feature) is below the fold behind an inner scroll; buttons are not visible without scrolling.
* Default verdict for deterministic escalations = "escalation correct" -> the fly net update shown is a no-op ("0.63 -> 0.63 ... mean weight 1.00 -> 1.00 SIMULATED"), a judge clicking the obvious button sees nothing learn.
* "w 1.00 -> 1.00" chip overlaps the "suspicion / threshold" text in the fly panel after a review.
* Sidebar footer tagline "Smarter checks. Smoother trade." is copy from the reference art, meaningless for this product.
* Times such as 04:10/15:58 are simulated (`received_at` is not in the data) but displayed as if real; only the README says so.
* Human reviewer cannot see the source document, only 1-2 evidence lines; in the unreadable/scanned case there is nothing to review against, yet "Confirm: no mismatch" is accepted and flips status to OK.
* No way from the UI to demonstrate a processing failure/retry (API `inject_fail` only).
* No pitch script/deck material in the repo: no root README, no "what to click in 3 minutes", no slide with the honest fly story or the measured grey-zone table.

### 7. Rubric (each /10; weighted overall /100)

| Category (weight) | Score | Why |
|---|---|---|
| Accuracy (20) | 9 | 1.0000 verified, 520/520, 46/46; -1: vocab/allow-lists dataset-derived, false MISMATCH on mid-value truncation, ~25 formatting false alarms on unseen forms |
| Spec coverage (15) | 8 | all basics + PDF/Word/xlsx + HITL + retry API; scans only flagged, failures not demo-able from UI |
| Reliability / HITL (15) | 7 | deterministic triggers 20/20, live confirm/correct works, real gate grey-zone behaviour on my data; -3 for gate drops confirmed defects, mislabelled `missing_value`, uncertain classifier never asks for help, "all 7 match" lie, no source-doc view, replay HITL simulated |
| Architecture / innovation (15) | 8 | honest real graph, pure compare, evidence-verified Gemini design, interpretable few-shot gate that demonstrably learns locally (my curve); -2 gate invisible on shipped data, circular calibration, Gemini unverified |
| UX / demo (15) | 8 | best-in-class look, live+replay work, deployable; -2 for the misleading timeline text, below-fold review, no-op default verdict, tagline, no demo script |
| Robustness (10) | 5 | fail-safe by default (escalates rather than lies in most breakages) but brittle on layout/labels/legal forms/countries and undetected truncation |
| Docs / reproducibility (10) | 7 | backend + frontend READMEs accurate and candid, 62 tests, deterministic run; no root README/pitch, no innovator.md, scorer unicode crash undocumented, no pinned versions |
| **Overall** | **76 / 100** | (9x2 + 8x1.5 + 7x1.5 + 8x1.5 + 8x1.5 + 5x1 + 7x1) |

### 8. Critique by name

* DEVELOPER (backend): honest and unusually candid (no fake Gemini, engine labelled, tests 62, fixes at root not id special-cases, the 0.9606 -> 1.0 story is credible). Objections: (a) header comment/README claim "generic language" while `classifier.py` hard-codes this inbox's sender domains and subject templates and `normalize.py` a country list/UNLOCODE table copied from the data; the perturbation check in README (89 txt pairs re-rendered with MT/lbs) tested only unit/case/LTD-LIMITED, exactly the forms the author had already handled - not layout, labels, legal forms, countries, truncation. (b) gate-escalated results are labelled `missing_value`/`unreadable` and drop confirmed defects. (c) `many_mismatches` treated as anomaly conflicts with the e2e metric. (d) `GeminiClient` has no throttle for the very API the idea.md picked for its free tier. (e) 86 of 220 BL_COMPARISON emails ("send me the draft BL") are `OK` with `comparison_performed:false`; correct per the labels and honestly documented, but the sidebar "114 compared" vs classification 220 needs one sentence in the pitch. Credit: retry, review, replay export, no ground-truth leak in artefacts are all verified.
* DEVELOPER (frontend): adapters are correct against the real export (I verified) - the earlier "mock-verified only" gap is closed. Objections: timeline "all 7 match" text, review panel hidden below fold, simulated replay review with default no-op verdict.
* DESIGNER: layout fidelity is excellent and the logo/glow/fly-panel fixes are visible in my screenshots. Objections of DESIGNER (engine badges, small text floor) I agree remain open; add: the reference tagline placeholder, panel overlap in fly footer, and the Report tab spends 40% of height on the header/back row so the review block is pushed out of view. No design work addresses the review flow, which is the scored-by-spec feature.
* INNOVATOR: `reviews/innovator.md` does not exist (screenshots `innovator-*.png` do), so its claims cannot be checked against a log; the observable changes (replay Hebbian update with the real rule, help overlay, KC hover, sequence shots) are good. Objection: the interactive teaching demo only shows learning if the user picks "unneeded"; default path is a no-op. Write the log.

### 9. Ranked point-losers, with concrete fixes

1. **Gate invisible on real data + circular validation** (-4). Fix: generate the grey-zone replay set from `reviews/judge_scratch/perturb.py` mutations (typo consignee, conflicting weight line, truncated value, OCR read), export as `traces/grey_*.json` with "Grey-zone demo" filter chip, publish gate on/off table + 3-verdict curve; keep the 520-email score separate.
2. **Gate escalation drops confirmed defects and mislabels reason** (-3). Fix: keep a `confirmed_defect_fields` (state=mismatch and not near_miss) in the Result and in the submission when status stays MISMATCH; escalate to NEEDS_REVIEW only when the ambiguity is on a field that would decide the outcome; use a new UI reason "low confidence" and map it to `missing_value` only in `submission.json`; remove `many_mismatches` as auto-escalation or lower it to a review flag that leaves status MISMATCH.
3. **Rules brittleness / overfit vocabulary** (-3). Fix: (a) add separators `-`,`=`,`|`, 4-col and transposed docx/xlsx tables; (b) replace country list with "compare the part before the first comma/dash" + code-in-parens stripping + `pycountry`; legal forms `S/B`, `L.L.C.`, `GMBH & CO KG`, `THE`, `(S)`/`(M)` locale tags; (c) synonym table + generic fuzzy (token-set) for unseen labels e.g. `Gross Weight of Cargo`, `Consignee / Buyer`; (d) drop the sender allow-list, keep only content signals; (e) add `tests/test_messy.py` from `run_a..d.py` so the robustness is a regression suite.
4. **Undetected truncation -> false MISMATCH** (-2). Fix: flag a document whose last line lacks a newline/whose weight is < 1/10 of the other doc or that has < N of the standard SI/BL keys; escalate `unreadable`/`missing_value`.
5. **Scans not read** (-2). Fix: add `rapidocr-onnxruntime` (pure pip) or Gemini vision (`Part.from_bytes` PNG page) for image-only PDFs, set `ocr` flag (conf 0.6) so the gate escalates with the read text as evidence (keeps the label `unreadable`/NEEDS_REVIEW for the 3 scanned test emails, but the human sees the text - the natural gate showcase).
6. **Gemini path unverified / no throttle** (-2, high impact if judges use a key). Fix: one real smoke run before submission; `asyncio.Semaphore(4)`, exponential backoff honouring 429 retry-after, per-node timeout, cache by (doc hash, field); record measured quota in README.
7. **Timeline "all 7 match" on skipped compare** (-1.5). Fix: `Timeline.tsx` show the event `summary` / "not run" when compare is `skipped` or status NEEDS_REVIEW.
8. **HITL panel placement and default verdict** (-1.5). Fix: move "Human review needed" above the field table or make the Report tab header collapse; pre-select "unneeded" only for gate-decided escalations and require an explicit verdict click for deterministic ones; make the update visible (show the KCs changed).
9. **No pitch/README root + INNOVATOR log** (-1). Fix: root `README.md` (2 commands, modes, honest numbers, the fly story with measured grey-zone table, what is simulated), `reviews/innovator.md`, remove reference tagline, label simulated timestamps.
10. **Classifier uncertainty never asks for help; failure demo not reachable** (-1). Fix: if classifier confidence < 0.5 push into the same escalation UI ("classify as ... ?" human verdict); add a "Simulate node failure" toggle (calls `?inject_fail=`) in LIVE for the retry demo.

### 10. Blockers

None that stop submission: the 520-email output is correct, reproducible and well-shaped; REPLAY (Vercel) and LIVE both work. The items above are score/impression risks, not build breaks. Biggest risks for a judge session: (1) live Gemini attempt with a real key (untested, quota), (2) a judge feeding a hand-made messy document (layout/label/legal-form false alarms or silent mid-value truncation), (3) the "what does the fly do?" question with only deterministic triggers on screen.

STATUS: OBJECTIONS=10
1. Gate has no visible/measured role on shipped data; calibration is circular (ship a grey-zone replay set + gate on/off table).
2. Gate escalation drops confirmed defects and reports a wrong `review_reason` (`missing_value`); `many_mismatches` conflicts with the e2e metric.
3. Rules engine vocabulary/normalisation overfit and brittle (layouts, labels, legal forms, countries, classifier 78% on fresh phrasing).
4. Mid-value truncation gives a silent false MISMATCH (22/22 clean pairs).
5. Scanned PDFs are never read (no OCR/vision) - advanced item only partial.
6. Gemini path unverified live and unthrottled (429 -> red nodes/fallback for any judge with a key).
7. Timeline says "all 7 match" for skipped compare (false statement on NEEDS_REVIEW emails).
8. Human-review panel below the fold at 1536x1024; default verdict makes the Hebbian update a no-op; no source-document view; replay HITL simulated.
9. Docs/pitch: no root README, no `reviews/innovator.md`, reference tagline left in sidebar, simulated timestamps shown as real, no demo script.
10. Classifier uncertainty never escalates; processing-failure/retry cannot be demonstrated from the UI.
