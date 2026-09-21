# ARGUS frontend

Vite + React + TypeScript control-room dashboard for the shipping-document verification pipeline
(inbox -> classifier -> 7 field agents -> aggregator/compare -> fly-brain confidence gate -> report).
Visual target: `../hackathon_info/design/reference-dashboard.png`. Data contract: `../CONTRACT.md`.

## Run

```bash
npm install
npm run dev        # http://localhost:5173, proxies /api -> http://localhost:8000
npm run build      # tsc -b && vite build (zero TS errors), output in dist/
```

## Modes (visible pill in the header: LIVE / REPLAY / MOCK)

| Mode | When | Source |
| --- | --- | --- |
| LIVE | `GET /api/health` answers `{ok:true}` | `/api/*`, pipeline streamed as SSE over `fetch` (POST `/api/process/{id}`), retry via `/api/retry/{id}`, review via `POST /api/review/{id}` |
| REPLAY | no backend, `/replay/index.json` exists | static `/replay/index.json`, `/replay/traces/<id>.json` (events animated by `t_ms`), `/replay/stats.json`, `/replay/flybrain.json` |
| MOCK | neither of the above | hand-written data in `src/mock` (last resort, clearly labelled) |

Force one with `?mode=live|replay|mock`. `public/replay/*` is written by the backend (`python -m sdoc.export_replay`);
the frontend never writes or overwrites those files.

In REPLAY/MOCK, human review and retry are simulated locally and marked as such (`simulated` tags): there is no
server to run nodes or to update the fly-net weights.

## What is on screen

- Sidebar: stats, engine badge (`gemini` = LLM, `rules` = offline deterministic parsers), top issues by defect field.
  Accuracy is the offline self-eval number only (`accuracy_vs_labels`), shown as `-` when absent.
- Center: living node graph (real 7 fields). Nodes light from trace events (start/done/error/skipped, engine badge,
  duration). Hover = popover, click = pin. Report tab: side-by-side SI vs BL table, mismatches highlighted,
  human-review panel (confirm mismatch / confirm OK / correct field) for `NEEDS_REVIEW`, retry for errored nodes.
  Non-comparison emails show classification only.
- Right: incoming emails (filters, search, click = select and run/replay) and the fruit-fly confidence-gate panel
  (inputs -> Kenyon cells -> decision neuron, lit from the `gate` event; shows the Hebbian update after a review).
  Wording: "Architecture inspired by the fruit fly's olfactory system" (our own small network, not fly data).
- Bottom: processing timeline for the selected email.

`prefers-reduced-motion` disables particle trails and pulses. Below 1180px the layout collapses (stats on top, then
graph + emails, then timeline); under 820px it is a single column and the graph scrolls horizontally.

## Layout of `src/`

`App.tsx` (state, run/retry/review orchestration) - `data/source.ts` (LIVE/REPLAY/MOCK adapters, SSE reader, local
review simulation) - `data/usePlayer.ts` (paces events) - `data/graphState.ts` (folds events into node states) -
`components/` (Sidebar, EmailList, GraphPanel, NodePopover, FlyPanel, Timeline, ReportView) - `mock/` - `styles.css`.
