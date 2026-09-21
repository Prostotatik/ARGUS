# ORCHESTRATION — shared brief and state (all agents read this first)

## Ground truth of the task
- Vision doc: `hackathon_info/idea.md`. Visual target: `hackathon_info/design/reference-dashboard.png`.
- Hackathon materials: `work/infopack.txt`, `work/usecase.txt` (text extracts of the docx / pdf in `hackathon_info/`; originals authoritative).
- Dataset (520 emails): `work/bundle/inbox/*.json`, `work/bundle/attachments/*` (txt/pdf/xlsx/docx), `work/bundle/loader.py`, `work/bundle/README.md`.
- Local scoring: `work/docker/server/score_cli.py` + `scoring.py`, labels in `work/docker/data_v2/ground_truth.json`
  (organizers confirmed participants may use it; DEV/JUDGE only, never ship it in the frontend bundle or the deployed app).
- Score = 0.30*stage1_macroF1 + 0.20*stage3_defectF1 + 0.50*end_to_end; NEEDS_REVIEW graded on separate reliability axis.
- Submission deadline 22 Sep 2026 12:00 PM. Demo/pitch quality matters, but accuracy numbers are measured.

## Locked decisions (orchestrator; do not re-litigate without an objection backed by idea.md / hackathon docs)
- Layout: `backend/` (Python 3.10, FastAPI, numpy, google-genai, pymupdf/pdfplumber, python-docx, openpyxl) and `frontend/` (Vite + React + TypeScript).
- Pipeline (real calls, no decoration): classifier -> 7 parallel field-agents (shipper, consignee, notify_party,
  port_of_loading, port_of_discharge, container_count, gross_weight_kg) -> aggregator -> pure-function compare (NO LLM)
  -> fly-brain confidence gate -> confident report / escalate to human with context+evidence+reason.
- LLM = Gemini via `GEMINI_API_KEY` (env or `backend/.env`). **No key is present on this machine right now.**
  Therefore every LLM node MUST have a deterministic offline implementation (regex/heuristic parsing of txt/pdf/xlsx/docx)
  selected automatically when no key exists, and the LLM path must be used when a key exists. The trace/UI must say
  honestly which engine ("gemini" vs "rules") produced each node output. Never fake LLM output.
- Fly brain: our own small network in the fruit-fly olfactory style (sparse projection -> Kenyon cells with APL-style
  global inhibition / winner-take-all -> decision neuron), Hebbian/STDP-like update from human verdict, interpretable
  per-connection weights. Wording: "architecture inspired by the fruit fly's olfactory system". NEVER claim real fly data / FlyWire.
- Fly gate only governs escalation (NEEDS_REVIEW / ask-for-human); it must not corrupt classify/extract/compare accuracy.
- Frontend must run in two modes: LIVE (SSE from backend) and REPLAY (static precomputed traces `frontend/public/replay/*.json`,
  so the Vercel deployment works with no backend). Field-agent labels are the REAL 7 fields, not the placeholders in the reference image.
- Visual style = reference-dashboard.png: dark cinematic control room, left stats sidebar, center glowing node graph
  (Inbox -> Classifier -> 7 field pills -> Aggregator -> Report), right column (incoming emails + fly-brain panel), bottom processing timeline.
- Human-in-loop review UI (confirm/correct a field, updates the report, feeds fly-gate learning) is required (spec: Reliability & human review; also retry on processing failure).
- No git remotes, no pushes, no deploys, no external posting. Local commits only (orchestrator commits).

## Protocol for every subagent
1. Read this file, `hackathon_info/idea.md`, the reference PNG (via Read), and the current repo state before acting.
2. Write your findings/log to `reviews/<role>.md` (append a new dated `## Round N` section; keep prior rounds). Each round MUST end with exactly one line:
   `STATUS: OBJECTIONS=<n>` (n>0 with numbered list) or `STATUS: NO REMAINING OBJECTIONS` — for YOUR OWN area of responsibility only.
3. Critique the other roles' latest work by name with concrete objections. Approving by default is a failure. No objection is only legitimate if you actually verified it (ran it / viewed it / read the code).
4. Do not touch files outside your remit except the fixes stated in your role. DEVELOPER owns backend + all code wiring; DESIGNER/INNOVATOR may edit frontend styling/components (CSS, motion, small components) but coordinate through `reviews/` — DEVELOPER has veto on technically unsound asks with a written reason.
5. Report back to the orchestrator: what changed, verification evidence (commands + output numbers), remaining objections.

## Orchestrator state log (updated each iteration)
- Iter 1: repo empty except hackathon_info; extracted zips to `work/`; no Gemini key; dispatched DEVELOPER backend + frontend bootstrap in parallel (next: DESIGNER -> INNOVATOR -> DEVELOPER -> JUDGE rounds).
