# Drosophila Gate — shipping document verification

An inbox reader for a shipping company: it classifies incoming email (document-comparison
request / new SI / invoice query / general / spam), and for document-comparison emails it extracts
7 fields from the Shipping Instruction (SI) and draft Bill of Lading (BL), compares them, and shows
discrepancies side by side. When the system is not confident, it asks a human for help instead of
guessing or failing silently.

```
inbox -> classifier -> 7 parallel field agents -> aggregator -> compare (pure, no LLM)
       -> fly-brain confidence gate -> confident report / escalate to a human with evidence + reason
```

Full spec: `hackathon_info/idea.md`. Wire shapes: `CONTRACT.md`. Round-by-round build log and
verification evidence: `reviews/developer.md` (and the other roles' reviews alongside it).

## The honest "fly" pitch

We are **not** claiming a real fly brain. The gate that decides whether to escalate a result to a
human is our own small network, architecturally inspired by the fruit fly's olfactory system
(sparse random projection -> Kenyon cells with global inhibition / winner-take-all -> one decision
neuron with a Hebbian/STDP-like update from human verdicts). It is not FlyWire, not a connectome,
not real fly data — a real biological network has ~130k neurons and integrating/training an actual
connectome was out of scope for a hackathon build. The pitch is narrower and, we think, more
defensible: this *architecture* is a good fit for one specific job — "quickly tell normal from
suspicious from a few examples, and let a human fix a single wrong association precisely" — which
is exactly what an escalation gate needs. See `backend/README.md` for the full mechanism and
`backend/tools/grey_zone_eval.py` for a held-out (non-circular) measurement of whether it actually
does that job on data it was never calibrated on.

The gate only ever decides *escalate vs. report*. It never edits an extracted value or a
match/mismatch decision — that is the deterministic rules/LLM pipeline's job, and that is what the
official score measures.

## Run it

### REPLAY (no backend needed — what the deployed/Vercel build uses)

```bash
cd frontend
npm install
npm run build && npm run preview     # or `npm run dev` for hot reload
```

The frontend serves `frontend/public/replay/*` (520 precomputed traces, stats, the fly net's real
weights) — a live backend is not required. Human review/retry in this mode are simulated locally
and clearly labelled `simulated`.

### LIVE (real backend, real pipeline, real Hebbian updates)

```bash
cd backend
pip install -r requirements.txt
uvicorn sdoc.api:app --port 8000      # terminal 1
cd ../frontend && npm install && npm run dev   # terminal 2, proxies /api -> :8000
```

Open the printed `localhost:5173` URL. The header pill shows `LIVE`/`REPLAY`/`MOCK` and auto-detects
which one it can reach. Without a `GEMINI_API_KEY` the backend runs entirely on deterministic
offline "rules" engines (regex/heuristic parsing of txt/pdf/xlsx/docx) — every trace event and
result is labelled with the engine that actually produced it (`rules` or `gemini`); nothing is ever
mislabelled `gemini` that a key did not really produce. Add `GEMINI_API_KEY` (env or
`backend/.env`) to exercise the LLM path — see `backend/README.md` for throttling/backoff details
(written and unit-tested, not exercised against a live key on this machine).

### Regenerate the official submission / re-score

```bash
cd backend
python -m sdoc.run_all                                  # -> out/submission.json (~37s, 520 emails)
PYTHONUTF8=1 python ../work/docker/server/score_cli.py out/submission.json
python -m sdoc.export_replay                             # refresh frontend/public/replay/ after any backend change
python -m tools.grey_zone_eval                            # held-out fly-gate eval, separate from the score
```

## Score (rules engine — no Gemini key on this build machine)

```
FINAL SCORE  1.0000   (0.30 * stage1 macro-F1 1.000 + 0.20 * stage3 defect-F1 1.000 + 0.50 * end-to-end 46/46)
Classification 520/520 · defect fields exact 114/114 · escalation recall 20/20, precision 20/20
```

This is a *synthetic* dataset with regular templates — 1.0000 says the pipeline matches this
generator's semantics, not that it will hold on an arbitrary messy real inbox. We re-verify beyond
the shipped 520 with our own fresh perturbation tests every round (fresh classifier phrasing,
unseen layouts/labels/legal suffixes/countries, truncated/OCR-noisy values) — current numbers and
methodology are in `backend/README.md`, full round-by-round evidence in `reviews/developer.md`.

## What is simulated, and what is real

- **Real:** every pipeline node (classify, 7 field agents, aggregate, compare, gate) is a real
  call/computation on the actual attachment text — never decoration. LIVE mode's human review and
  Hebbian weight updates are the backend's real numpy computation. OCR (`rapidocr-onnxruntime`) is
  a real, working, offline OCR pass on the dataset's 2 genuinely scanned PDFs.
- **Simulated, and labelled as such wherever shown:** email arrival timestamps (`received_at` —
  the dataset carries no timestamps; a deterministic 7-minute arrival stream is used only so the UI
  has something to sort by). REPLAY/MOCK mode's human review and Hebbian updates (no backend to
  actually run them; the same documented rule is applied client-side to the exported weights and
  never presented as a live number).

## Known limitations

- Gemini path is implemented, throttled/backed-off, and unit-tested with a fake client, but has
  **not** been run against a live key (none available in this environment) — review-ready for demo
  time; the system works fully on the deterministic rules engine either way.
- The fly gate's `ambiguous_role` (SI/BL role assignment) recall is the weakest of its measured
  grey-zone categories (0.375 — see `backend/README.md`); it escalates 2 of the real 520 emails on
  its own merit (not a hard-coded rule) and is otherwise measured on a held-out set, not tuned to
  hit a number.
- Classifier rules, while re-verified against fresh phrasing (23/23) this round, are still
  ultimately tuned to this inbox's genre of shipping-operations language.
- Container size/type (20' vs 40') is not compared — the spec's field is *count* only, a locked
  scope decision.
- Tablet-width (<=1180px) layout has some unused vertical space in the centre column; declined as a
  cheap fix given it is outside the reference design's primary 1536x1024 target (see
  `reviews/developer.md`).

## Demo script (~3 minutes)

1. **Open in REPLAY** (or LIVE with the backend running). Point at the sidebar stats and the live
   node graph — say what it is: a real 7-field SI/BL comparison pipeline, not a mock.
2. **Pick a MISMATCH email** from the list (filter chip "Mismatch"). Watch the graph light up per
   field, open the Report tab, show the SI-vs-BL table with evidence lines and the highlighted
   defect.
3. **Pick a NEEDS_REVIEW email.** Open the fly panel (right column): explain the gate in one
   sentence — "architecture inspired by the fruit fly's olfactory system, not real fly data; it
   decides whether to ask a human, never the match/mismatch itself." Point at `suspicion` vs
   `threshold` and the lit Kenyon cells.
4. **Submit a human review** (Confirm/Correct) on that email: watch the Hebbian weight-change
   animation and the "before -> after" suspicion readout — or, if it is a deterministic trigger, the
   honest "nothing to learn here" message instead of a misleading no-op.
5. **(If a Gemini key is available)** toggle a run to the `gemini` engine and show the same email
   processed live, with the "gemini" vs "rules" engine badge visible on each node either way.
6. **Click "Simulate failure"** on any email (LIVE mode) to show a red errored node, then **Retry**
   to show it recover — the processing-failure/retry story from the UI, not just the API.
7. Close on the numbers: `1.0000` on the official 520-email score, plus the held-out grey-zone table
   in `backend/README.md` showing the gate does something real that the official score does not
   measure.
