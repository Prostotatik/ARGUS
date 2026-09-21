# Idea: Shipping Document Verification — "Drosophila Gate"

## Hackathon task (short)
Email inbox (JSON) → classify messages (document-comparison request / new SI / invoice query / general / spam) →
for document-comparison emails: extract 7 fields from SI and BL, compare, show discrepancies side by side →
if the system is not confident — escalate to a human with context, don't guess or fail silently.

7 comparison fields: shipper, consignee, notify party, port of loading, port of discharge, container count, gross weight (kg).

Self-eval endpoint judges classify/extract/compare accuracy (numbers, not impressions) — this limits how much risk we can take on the "gimmick".

Deadline: preliminary submission — **September 22, 2026, 12:00 PM**.

## Pitch / differentiator
**Not** "we have a real fly brain" (a lie, easily caught by one judge question, gains nothing — decided not to lie).

**Honest version:** the fruit fly olfactory system architecture (sparse random projection → Kenyon cells → winner-take-all)
genuinely fits a specific subtask — few-shot novelty/confidence detection with individually correctable connections.
That's the actual pitch: not "we have a fly", but "we used an architecture evolution already solved for
'quickly tell normal from suspicious from few examples, with the ability to precisely fix a mistake'".

README/pitch wording: **"architecture inspired by the fruit fly's olfactory system"** — confident, no false
claims about data origin (not FlyWire, not a real connectome — our own small network in that style).

## Architecture

### Main pipeline (LLM, agentic graph)
Honest parallelism instead of a fabricated "agents arguing with each other":

```
inbox → [classifier agent] → (only document-comparison requests proceed)
              │
    ┌─────────┼─────────────────────────┐
    │   7 parallel field-agents          │   (shipper, consignee, notify party,
    │   each reads SI + BL,               │    port of loading, port of discharge,
    │   responsible for only its field    │    container count, gross weight)
    └─────────┬─────────────────────────┘
              ▼
        [aggregator agent] → report card (SI vs BL side by side, "No mismatch detected" if all match)
              ▼
      [fly brain: confidence/anomaly gate]
              ▼
   confident → report ready  /  not confident → escalate to human (with context, source evidence, reason)
```

- classify and extract are separate calls with structured (JSON) output, not one combined prompt.
- compare is a pure function, no LLM (exact comparison of extracted values), not wrapped in an extra call.
- Every node in the graph is a real call, not decoration. The UI graph reflects what actually happens on the backend.

### Role of the "fly brain"
Does not decide classify/extract/compare directly (that's the LLM pipeline's job, and that's what the official score measures).
Sits **as a gate over escalation** ("Ask for help" — the capability from the spec):

- Input: vector of discrepancies across the 7 fields (binary/numeric flags) + metadata (extraction confidence).
- Architecture: sparse input layer → Kenyon cells (random sparse projection) → decision neuron (WTA).
- Output: suspicion score → decides whether to escalate to a human or not.
- Learning: Hebbian/STDP-like rule, weights adjusted from the human's verdict (correctly/incorrectly
  escalated). Sparsity gives interpretability — a specific wrong connection can be punished directly,
  unlike an LLM where you can't precisely fix a single mistake.
- Our own network "in the fly's style", not a real FlyWire graph (130k neurons of the real connectome
  can't be integrated and made trainable in the hackathon's time — risks not finishing the rest of the product).

## Scope and build order
1. Frontend on mocks — reference images generated in ChatGPT (see prompt below), test overall flow and UI.
2. Record a demo on mocks → hand off to teammates for editing (done in parallel with the backend).
3. Add LLM pipeline (classify → 7 field-agents → aggregator) on **plain-text** SI/BL (basic task level).
4. Add the fly brain as a confidence gate over escalation.
5. Advanced level: **messier inputs** as the next step after the basic pipeline (varied field labels,
   misleading email subjects, missing attachments) — cheaper to build (still text) and directly hits
   the official criterion "identifying the right discrepancies without creating false alarms".
   PDF/Word and scans/OCR — if time remains after messier inputs.

## Main screen (UI)
A live agent graph + fly brain panel, not just a list of emails with a report:
- Left/center: a web of nodes (classifier → 7 field-agents → aggregator), nodes light up as they process in real time.
- Right: a small fly-network panel (input nodes → Kenyon cells → decision), lights up on every escalation decision.

### Prompt for generating references (ChatGPT images, a loose brief, not a strict spec)
```
Design a dashboard UI for an AI system that reads a shipping company's email inbox, automatically
classifies messages (document check requests, spam, invoice questions, etc.), and compares two shipping
documents (Shipping Instruction vs Bill of Lading) to catch mismatches like wrong port names, container
counts, weights.

The centerpiece is a living node graph: an inbox feeds into a classifier node, which branches into
several parallel "field agent" nodes (each checking one shipment detail), converging into an aggregator
that produces a discrepancy report. Nodes light up / pulse as they process.

There's also a secondary panel showing a small bio-inspired neural net styled after a fruit fly's
olfactory system — sparse input layer expanding into a dense middle layer, converging to a single
decision output — used as a confidence gate before escalating uncertain cases to a human reviewer.

Style: awwwards-level, dark mode, cinematic, glowing nodes and connection lines, subtle motion/particle
feel, technical but elegant — like a mix of a security operations center and a neuroscience
visualization. Not corporate SaaS-bland — more like a control room for autonomous agents.

Give me a few different layout takes.
```

### Final visual reference (locked)
`design/reference-dashboard.png` — approved as the final visual style target.

Layout: thin left sidebar (logo, live stats: emails to process, total shipments, discrepancies found,
accuracy %, top issues list) → center node graph (Inbox → Classifier → parallel field-agent pill nodes →
Aggregator → Report, organic curved glowing connectors with particle trails, nodes read as hover/click-able)
→ right column (incoming emails list on top, fly-brain confidence-gate panel below) → horizontal
processing timeline strip along the bottom.

**Known gap to fix during real implementation (not the art pass):** the reference's field-agent labels
(Port Check, Container Count, Weight Verification, Document Check, Customs & Duty, Shipment Match) are
ChatGPT's invented categories — the real build must use the actual 7 spec fields (shipper, consignee,
notify_party, port_of_loading, port_of_discharge, container_count, gross_weight_kg), not these placeholder ones.

## Actual data & output format (confirmed from the provided zips)

**Dataset:** 520 emails. Attachment mix: 192 `.txt`, 28 `.pdf`, 22 `.xlsx`, 8 `.docx`. This means
PDF/Word/Excel parsing is **not just an "advanced" stretch goal — it's already needed to cover the
whole inbox** in the base pipeline, not something to bolt on later.

**Required submission shape** (`sample_submission.json`, keyed by `email_id`, every id required):
```json
{
  "email_001": {
    "category": "BL_COMPARISON",   // BL_COMPARISON | SI_REQUEST | INVOICE_QUERY | GENERAL | SPAM
    "status": "MISMATCH",          // OK | MISMATCH | NEEDS_REVIEW
    "review_reason": null,         // wrong_doc_type | missing_attachment | unreadable | missing_value
    "has_defect": true,
    "defect_fields": ["consignee"]
  }
}
```
Field names in the real schema: `shipper, consignee, notify_party, port_of_loading, port_of_discharge,
container_count, gross_weight_kg`.

**Scoring formula (confirmed):** `final_score = 0.30·stage1_macroF1 + 0.20·stage3_defectF1 + 0.50·end_to_end`.
`NEEDS_REVIEW` cases are graded on a separate reliability axis (escalation precision/recall) — this is
exactly where the fly-brain gate's job is measured, so it's not a decorative feature, it maps to a real
scored axis.

**Self-scoring locally:** `sdoc-hackathon-docker.zip` ships `score_cli.py` + `scoring.py` — these run as
plain Python, **no Docker required**, e.g. `cd server && python3 score_cli.py submission.json`. Docker
is only needed if we want the live HTTP `/submit` endpoint; for solo iteration the CLI is simpler and faster.

**Note on `ground_truth.json`:** the docker zip is labeled "(ORGANIZERS)" and its README says not to
hand it to participants, but the organizers confirmed in Discord that everyone received it and it's fine
to use — noting this here so it's not mistaken for a leak later.

## Tech stack

- **Frontend/hosting: Vercel.** Fast to ship a polished UI + live demo URL, fits the "awwwards-level"
  visual bar from the brief, zero-effort deploys during a time-crunched build.
- **LLM: Google Gemini (free API tier).** Covers classify + the 7 field-agents + aggregator. Free tier
  removes cost/rate-limit risk during heavy iteration and demo recording — the deciding factor over
  paid alternatives given the ~1-day budget.
- **Docker: not required for the product.** Only relevant for the organizers' live-scoring HTTP server;
  self-scoring works via `score_cli.py` directly. Don't spend build time containerizing anything unless
  a teammate specifically wants local API isolation.
- **Backend runtime:** not chosen yet — needs to run Gemini calls (parallel field-agents), parse
  txt/pdf/xlsx/docx attachments, and run the small fly-brain net. Natural fit is a Vercel-deployable
  Node/Python API route architecture; open question is whether the fly-brain net lives in the same
  runtime or as a small isolated service given it needs custom array math (numpy-style), which favors
  Python if Gemini calls end up there too.

## Open questions (not yet resolved)
- Concrete implementation of the fly-gate's Hebbian learning (formulas, exactly how a weight updates when "human disagrees").
- Backend language/runtime pick (Python vs Node) — depends on where the fly-brain net's array math lives.
- PDF/Word/Excel parsing library choice (needed early now, not deferred — see dataset mix above).
- UI for human-in-loop review (how exactly the reviewer sees context and confirms/corrects).
