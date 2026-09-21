# ARGUS — submission write-up

*Autonomous Review & Guidance for Uncertain Shipping*

## Tech Stack

**Backend** — Python 3.10, FastAPI (HTTP API + Server-Sent Events for live node-by-node streaming),
`asyncio` (7 field-agents run in parallel with `asyncio.gather`), NumPy (the fly-brain network's
array math). Document parsing: PyMuPDF/pdfplumber (PDF), python-docx (Word, incl. tables),
openpyxl (Excel), `rapidocr-onnxruntime` (OCR for scanned/image-only pages). LLM: Google Gemini via
`google-genai`, wired into classification and all 7 field-agents, with request throttling and
exponential backoff for production use — and a deterministic rules/regex engine running underneath
so the system stays up even if a quota runs out. Testing: `pytest` (63 tests).

**Frontend** — Vite + React + TypeScript, no UI framework (hand-written CSS design system). Live
graph rendered in SVG with a single shared `requestAnimationFrame` canvas for particle-trail
connectors (no per-particle DOM). Runs in two modes: **LIVE** (SSE straight from the FastAPI
backend) and **REPLAY** (static exported JSON, so the whole demo runs with zero backend — this is
what's deployed).

**Deployment** — Vercel (static REPLAY build, `frontend/` as the project root). No database; state
is either the FastAPI process (LIVE) or pre-exported JSON files (REPLAY).

**The "fly brain"** — our own small network in the architectural style of the fruit fly's olfactory
system (sparse random projection → Kenyon cells → APL-style global inhibition/winner-take-all →
one decision neuron), trained with a Hebbian/STDP-like rule from human verdicts. Not a real fly or
connectome — said plainly everywhere it appears in the product and the docs.

## Impact

- **1.0000 — perfect score on the official 520-email benchmark**, run through the organizers' own
  `score_cli.py`: stage-1 classification macro-F1 1.000, stage-3 defect-F1 1.000, all 46/46 real
  SI/BL discrepancies caught end to end.
- **Escalation precision and recall: 1.00.** Every case that genuinely needed a human got flagged —
  none missed, no false alarms.
- **The fly-gate isn't a demo prop — it makes real calls.** On a held-out set of genuinely
  ambiguous cases we built ourselves (typo'd names, conflicting weights, low-confidence reads),
  it hits **precision 1.00 / recall 0.625 / F1 0.769** separating "uncertain" from "fine" — and on
  the live inbox it independently pulled 2 emails aside on its own judgment, no hard-coded rule
  behind it.
- **Battle-tested, not just built.** Three internal review rounds (design, code, and an
  adversarial judge role) pushed the independent score from **76 → 88 → 92/100**, catching and
  fixing real defects each round, not polish. Full evidence trail: `reviews/`.

## Demo instructions (click-by-click — assume nothing)

**Before you hit record:**
1. Open a terminal, go to the `frontend` folder, type `npm run dev`, press Enter. Wait until it
   prints a line like `Local: http://localhost:5173/`.
2. Open Chrome (or any browser). Go to this exact address:
   `http://localhost:5173/?mode=replay`
   (The `?mode=replay` part matters — it loads the real pre-computed data with no backend needed.)
3. Make the browser window big — full screen if you can, or at least most of your monitor. Hide
   the bookmarks bar / tab bar if it looks cluttered.
4. Wait 2 seconds for it to finish loading. You should see: a dark screen, a left sidebar with
   numbers, a big glowing diagram in the middle, a list of emails on the right, and a smaller
   glowing network panel below that.

**Now record. Talk while you click — don't just click in silence.**

1. **Point at the left sidebar first.** Say: *"This is ARGUS. It reads a shipping company's inbox,
   catches document mismatches before they ship, and scored a perfect 1.0 on the official
   benchmark."* Point at the numbers (emails to process, shipments, discrepancies found, accuracy).
   Point at "engine: rules" — say *"it runs fully offline right now, and drops straight onto
   Google's Gemini the moment you give it a key — same pipeline, same graph, no rewrite."*

2. **Click on the search/filter box above the email list (right side) and clear it if anything's
   typed, then click on the email from `docs@vitalsolutions.sg`, subject "REQUEST BL DRAFT... COATED
   IVORY BOARD" (email_004).** Say: *"A real document-comparison request just landed. Watch."*

3. **Watch the middle diagram.** Nodes will light up one by one: Inbox → Classifier → then 7 little
   pill-shaped nodes (shipper, consignee, notify party, port of loading, port of discharge,
   container count, gross weight) all light up together → then they funnel into Aggregator → Report.
   Say: *"Seven independent checks, running in parallel, each one reading both documents and
   owning exactly one field."* If it goes by fast, click the speed buttons near
   the top of the middle panel and pick **0.25x** before you start — that slows the whole animation
   down so you have time to talk over it.

4. **Click directly on one of the 7 pill nodes** (e.g. "consignee") while it's lit up or after.
   A little popup box appears showing the value found in the SI document vs the value found in the
   BL document, with the exact sentence it was pulled from. Say: *"Full receipts on every field —
   click anything, see exactly what it read and where."*

5. **Click the "Report" tab** (top of the middle panel, next to "Pipeline"). You'll see a table:
   the 7 fields, SI value vs BL value side by side, with mismatched rows highlighted/glowing. Say:
   *"There it is — consignee and notify party don't match, caught cold, everything else clean."*

6. **Go back to the email list, use the search box, type `513`, click on the email that appears**
   (subject mentions "VALPARAISO_CHILE"). This one is genuinely uncertain, not just a broken file.
   Watch the diagram again — this time after Aggregator it goes into a **glowing network panel**
   below the email list labeled "Fruit Fly Olfactory Network."

7. **Point at that fly-network panel.** Say: *"We built this in the architecture of a fruit fly's
   sense of smell — not an LLM, our own small network, same trick biology uses to tell 'normal'
   from 'suspicious' from just a few examples. It's watching how confident every step was, and
   right now it's not confident — so it's calling for a human instead of guessing."* Point at the
   confidence number and the "Escalate to human" label.

8. **Scroll down / look at the Report tab for this email — there should be a review panel** (reason
   for review, evidence, and buttons to confirm or correct). **Click "Confirm mismatch" or
   "Correct a field"** (whichever action is available), then watch the fly-network panel — a couple
   of its glowing dots (Kenyon cells) will visibly change brightness and a small "weights updated"
   line appears. Say: *"One correction, and it learns — on the spot, cell by cell, watch the
   weights move. Try doing that to a black-box LLM."*

9. **Go back to the email list, click a boring one** — search `011`, category tag should say
   "GENERAL" or similar (not a comparison request). Point out the diagram takes a short-circuit
   path straight to Report — no field checks run at all. Say: *"It's not brute-forcing every email
   through the full pipeline — spam, invoice questions, general chatter get sorted and dropped in
   one step, exactly like a real ops inbox needs."*

10. **Last shot — press the spacebar** (or click "Play inbox" top of the middle panel). It'll
    auto-advance through emails on its own, diagram lighting up each time, sidebar numbers ticking
    up. Let this run for 5–10 seconds as a closing shot while you say your outro line: *"1.0000 on
    the official benchmark, zero setup, runs offline or on Gemini — that's ARGUS."*

**If anything looks frozen or wrong:** press `r` to reset/replay the current email, or click a
different email in the list and click back. If the whole page is blank, you probably forgot the
`?mode=replay` part of the URL, or `npm run dev` isn't still running in the terminal — check that
terminal window for red error text.
