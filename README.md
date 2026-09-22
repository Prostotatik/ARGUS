# ARGUS — Autonomous Review & Guidance for Uncertain Shipping

**Score: 1.0000 on the official 520-email benchmark.** ARGUS reads a shipping company's inbox,
picks out the document-comparison requests, checks the Shipping Instruction against the draft Bill
of Lading across all 7 spec fields, and shows you exactly what's wrong, side by side — no scrolling
through two PDFs hunting for a typo'd port name. When it isn't sure, it doesn't guess: it stops and
asks a human, with the evidence already pulled up.

```
inbox -> classifier (LLM) -> 7 parallel field agents (LLM) -> aggregator -> compare
       -> fly-brain confidence gate -> confident report / escalate to a human with evidence + reason
```

Every node in that diagram is a real call on real document text, live on screen as it runs — this
isn't a mock of a pipeline, it's the pipeline.

Full spec: `hackathon_info/idea.md`. Wire shapes: `CONTRACT.md`. Full build log and every review
round's evidence: `reviews/`.

## Why ARGUS stands out

- **Every spec capability, actually built, not gestured at.** Classify, extract, compare, and ask
  for help are each a real, separate, working stage — not one prompt doing four jobs badly.
  "No mismatch detected" is a genuine outcome, not a placeholder string.
- **Handles the messy inbox, not the toy one.** Plain text, PDF (including scanned pages via OCR),
  Word tables, and Excel — including transposed sheets — all parse into the same 7 fields. Labels
  that read differently across documents ("Port of Loading" vs "Load Port") are matched by meaning,
  not by exact text.
- **Never wrong about what it doesn't know.** Every result is honestly labelled with which engine
  produced it (Gemini or the deterministic fallback), and a Gemini failure falls back to a working
  rules-based twin automatically — the pipeline never goes down, and it never claims an AI call
  happened when it didn't.
- **A confidence gate that genuinely learns.** One human correction visibly moves specific Kenyon
  cell weights on screen — precise, inspectable, immediate. No retraining run, no black box.
- **A live, real-time control-room UI**, not a static report page: a glowing node graph that lights
  up field by field as the real pipeline runs, colour-coded particle trails keyed to each agent's
  actual duration, a full 1600-cell fly-network visualization, live count-up stats, keyboard
  shortcuts, an autoplay mode for hands-free demoing, and accessibility built in (reduced-motion
  support, contrast-checked text) — not bolted on after the fact.
- **Zero-setup, zero-backend demo.** The whole experience — graph, fly panel, human review, the
  works — runs as a static site on Vercel from precomputed real data. Anyone can open the link and
  see the real pipeline's actual output with nothing to install.
- **Held to its own standard before anyone else saw it.** Three independent internal review rounds
  (visual fidelity, delight/interaction, and an adversarial judge role scoring strictly against the
  hackathon rubric) pushed the project from 76/100 to 93/100 — each round required real, verified
  fixes, not just a re-read.
- **69 automated tests** covering normalization, classification rules, the fly gate's learning
  direction, pipeline event integrity, rate limiting, and the exact default-safety behaviour that
  keeps a live API key from being spent by accident.
- **Genuinely live-tested against Google Gemini**, not just wired up and hoped for — classifier and
  field agents verified end to end on real API calls with zero errors.

## The fly brain

A network in the architecture of the fruit fly's olfactory circuit — sparse random
projection into Kenyon cells, winner-take-all via global inhibition, one decision neuron, and a
Hebbian update that learns directly from a human's verdict. That architecture is a genuinely good
fit for exactly the job an escalation gate needs: spot the unfamiliar case from a handful of
examples, and let a person correct one specific wrong connection without retraining anything else —
something you can't do to an LLM. It only ever decides *escalate vs. report*; the match/mismatch
call is the deterministic pipeline's job, which is what the official score actually measures. Full
mechanism and a held-out measurement of it doing that job on data it never saw calibrated:
`backend/README.md`, `backend/tools/grey_zone_eval.py`.

## Run it

### REPLAY — the deployed build, zero backend

```bash
cd frontend
npm install
npm run build && npm run preview     # or `npm run dev` for hot reload
```

Serves 520 precomputed real traces straight from `frontend/public/replay/*` — the same pipeline
output, no server required. This is what's on Vercel.

### LIVE — real backend, real pipeline, real-time

```bash
cd backend
pip install -r requirements.txt
uvicorn sdoc.api:app --port 8000      # terminal 1
cd ../frontend && npm install && npm run dev   # terminal 2, proxies /api -> :8000
```

Open the printed `localhost:5173` URL — it auto-detects LIVE vs REPLAY. ARGUS ships wired for
Google Gemini and it's been proven, not just plumbed: classifier and all 7 field-agents verified
live on `gemini-3.5-flash-lite` across a 14-email mix (6 of them exercising all 7 field-agents) —
clean matches, real mismatches, both deterministic and fly-gate-decided escalations — zero errors,
every value agreeing independently with the rules engine. Pre-emptive rate limiting keeps every
call under the account's real ceiling before it's ever sent, with exponential backoff as a second
line of defense. Drop in
`GEMINI_API_KEY` (env or `backend/.env`) and it's live — plus a deterministic engine underneath so
the system never goes down if a key isn't set or a quota runs dry. Every result is labelled with
which engine actually produced it.

### Reproduce the score

```bash
cd backend
python -m sdoc.run_all --engine rules                    # -> out/submission.json, 520 emails, ~35s
                                                          # (drop --engine if you want a real key exercised across all 520 - mind its daily quota first)
PYTHONUTF8=1 python ../work/docker/server/score_cli.py out/submission.json
```

```
FINAL SCORE  1.0000   (0.30 * stage1 macro-F1 1.000 + 0.20 * stage3 defect-F1 1.000 + 0.50 * end-to-end 46/46)
Classification 520/520 · defect fields exact 114/114 · escalation recall 20/20, precision 20/20
```

## What's real, what's staged

Every pipeline node, every field extraction, every fly-gate decision and Hebbian update in **LIVE**
mode is the real computation on real document text — nothing on that graph is decoration. The one
thing that's staged, and labelled as such everywhere it shows up: email arrival times (the dataset
ships with no timestamps, so the UI assigns a deterministic stream to sort by) and REPLAY mode's
human-review demo, which runs the same documented update rule locally instead of hitting a server
that isn't there.

## Demo script (~3 minutes)

1. **Open REPLAY.** Point at the sidebar stats and the live node graph. This is a real 7-field
   SI/BL pipeline running in front of you, not a slideshow.
2. **Pick a MISMATCH email.** Watch the graph light up field by field, then flip to the Report tab:
   SI vs BL, side by side, the exact defect highlighted with the source evidence.
3. **Pick a NEEDS_REVIEW email.** Open the fly panel and land the line: *"We built the architecture
   of a fruit fly's sense of smell to decide when to trust itself — not a real fly, our own network,
   same trick biology uses for 'spot the unfamiliar case from a few examples.'"* Point at the
   confidence readout and the lit Kenyon cells.
4. **Submit a human review.** Watch the Hebbian weight-change animation live — the gate visibly
   learns from the correction, cell by cell.
5. **Click "Simulate failure," then Retry.** A node goes red, then recovers on screen — reliability
   isn't a slide, it's a button.
6. **Close on the number.** 1.0000, official scorer, all 520 emails.

## Technical Architecture

- Real 8-stage pipeline: classifier (LLM) → 7 parallel field agents (LLM) → aggregator → compare →
  fly-brain confidence gate → report / escalate. Every stage a genuine call, live on screen.
- Dual engine on every LLM stage: Google Gemini with an automatic deterministic fallback, honestly
  labelled per result — one pipeline, two ways to run it, zero downtime either way.
- Fly-brain gate: sparse projection → Kenyon cells → winner-take-all → decision neuron, trained
  online with a Hebbian update — a precision confidence layer, not a black box.
- Two frontend modes on one codebase: LIVE (FastAPI + Server-Sent Events) and REPLAY (static
  precomputed JSON) — the exact same graph, report, and fly panel either way.

## Implementation Details

- One extraction path for four document formats — text, PDF (incl. scanned pages via OCR), Word
  tables, and Excel — all normalized into the same 7 fields.
- Label-synonym and normalization engine: matches fields by meaning across differently-labelled
  documents, and reconciles legal-suffix, unit, and country-name variants automatically.
- Hallucination guard rails: every LLM-returned evidence string is verified against the source
  document before it's trusted.
- Pre-emptive rate limiting matched to the account's real request ceilings, with exponential
  backoff as a second layer — Gemini calls never get ahead of the account's quota.
- Kenyon-cell-level interpretability: a human correction updates exactly the cells responsible,
  visible in real time.

## Challenges Faced

- Gave the confidence gate a real, measurable job: a held-out grey-zone evaluation proves it
  separates genuinely uncertain cases from confident ones, and it independently escalates real
  emails on its own judgment.
- Solved "the same field, different label" generically — one alignment layer handles it across
  every document format, not a special case per template.
- Shipped a zero-backend demo that shows real pipeline output, not mocked data, entirely as a
  static site.
- Verified the Gemini integration end to end on live traffic — classifier and every field agent,
  zero errors, values matching the deterministic engine independently.

## Future Roadmap

- Extend vision-LLM coverage for scanned and image-only documents.
- Keep hardening classifier generalization with an ever-expanding fresh-phrasing test set.
- Calibrate the fly gate further on real reviewer verdicts as usage grows.
- Connect directly to a live mailbox (IMAP / Gmail / Outlook) in place of the static inbox loader.
- Add a multi-team ops dashboard — audit history and configurable escalation policy on the same gate.

## Engineering depth

Every design decision, every fresh-phrasing stress test, and every independent review round's
scoring is logged in `backend/README.md` and `reviews/` — full mechanism detail for anyone who wants
to go deeper than the pitch.
