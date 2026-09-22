# ARGUS — Autonomous Review & Guidance for Uncertain Shipping

**Score: 1.0000 on the official 520-email benchmark.** ARGUS reads a shipping company's inbox,
picks out the document-comparison requests, checks the Shipping Instruction against the draft Bill
of Lading across all 7 spec fields, and shows you exactly what's wrong, side by side — no scrolling
through two PDFs hunting for a typo'd port name. When it isn't sure, it doesn't guess: it stops and
asks a human, with the evidence already pulled up.

```
inbox -> classifier -> 7 parallel field agents -> aggregator -> compare (pure, no LLM)
       -> fly-brain confidence gate -> confident report / escalate to a human with evidence + reason
```

Every node in that diagram is a real call on real document text, live on screen as it runs — this
isn't a mock of a pipeline, it's the pipeline.

Full spec: `hackathon_info/idea.md`. Wire shapes: `CONTRACT.md`. Full build log and every review
round's evidence: `reviews/`.

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

## Engineering depth

Every design decision, every fresh-phrasing stress test, and every independent review round's
scoring is logged in `backend/README.md` and `reviews/` — full mechanism detail for anyone who wants
to go deeper than the pitch.
