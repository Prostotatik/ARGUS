## Round 1 - INNOVATOR, 2026-09-21

Method: Vite dev server (`npm run dev -- --port 5188`), headless Chrome 153 over CDP (own script in scratchpad,
Claude-in-Chrome not connected), `?mode=replay` against the real `frontend/public/replay/*` (520 traces, 32-input
/ 1600-KC `flybrain.json`), plus a real backend (`uvicorn sdoc.api:app`, no Gemini key -> `rules` engine) for LIVE
verification of the review/Hebbian path. Shots at 1536x1024 in `reviews/shots/innovator-*.png`; also spot-checked
1920x1080, 1280x800, 390x844 and `prefers-reduced-motion: reduce`.

### Critique of DESIGNER (by name) - objections verified, what I did about each

1. **Particle trails (DESIGNER objection #2, left to me by brief).** Verified: DESIGNER's build had 2-3 plain
   white dots per connector (`GraphPanel.tsx` `<Particles>`, `animateMotion` SVG). Replaced the whole particle
   system with `components/BeadCanvas.tsx`: one `<canvas>`, one shared rAF loop, 8-22 colour beads per connector
   (density scales with edge state: ambient/flowing/done/dim), coloured per field agent (matches the pill hue),
   with a soft 3-ring falloff so each bead reads as a small glowing orb, not a dot. Verified against the reference
   crop side by side (`innovator-final-graph-zoom.png` vs `hackathon_info/design/reference-dashboard.png`) - much
   closer in density/warmth than DESIGNER's fix, still short of the reference's literal bead count because ours
   carries real information (see next point) rather than being purely decorative.
   Bead **speed** is not random: `graphGeometry.ts agentSpeed()` derives a per-agent multiplier from that run's
   real `duration_ms` (fast field agents get visibly faster beads than slow ones, relative to the run's median) -
   verified in `innovator-final-mid.png` mid-run (Port of Loading still "reading...", others already "match").
   A one-line legend under the graph ("bead colour = field agent - bead speed = its real runtime") makes this
   honest instead of decorative.

2. **Fly network density (DESIGNER objection #3).** Verified DESIGNER's fix against the real `flybrain.json`
   (32 inputs, 1600 KCs) which DESIGNER said was unverified: their per-KC SVG `<path>`/`<circle>` approach silently
   subsampled to ~110 of 1600 cells. Replaced with `FlyPanel.tsx StaticNet` (memoised `<canvas>`), which draws
   the network from the **real projection** for all 1600 Kenyon cells and additive per-input fibre strokes -
   verified visually (`innovator-a-zoom-fly.png`, `innovator-final-done.png`) that the lens-shaped mass is now
   dense and warm across the colour range like the reference, and the caption honestly says "1600 of 1600 Kenyon
   cells drawn" (was "113 of 1600"). Also added a compact APL node (global-inhibition, from the backend's own
   `_active()` logic) and per-decision KC-\>decision curves so the winner-take-all step is visible, not implied.

3. **Node engine badges (DESIGNER objection #1 / orchestrator ruling 2a).** Implemented the orchestrator's
   ruling exactly: `GraphPanel.tsx runDefaultEngine()` computes the run's majority engine across classifier + 7
   field agents; a node only gets a compact `OddTag` badge when its own engine differs (fallback case) or it is
   an intrinsic non-LLM node (aggregator/compare -> `pure`, styled as a plain caption, not a bordered pill).
   Verified two ways: (a) normal run (all `rules`) - no badges anywhere except the intrinsic `pure` tag under
   Aggregator (`innovator-final-done.png`); (b) synthetic mixed-engine run (patched `fetch` to mark `consignee`
   as `rules` while the rest of the run is `gemini`) - only the Consignee pill carries a `RULES` badge, everything
   else is clean (`innovator-mixed-engine-fallback.png`). Header pill, node popover and Timeline still show engine
   honestly and unconditionally, as required.

4. **Text floor / `--mute` contrast (DESIGNER objection #4E,I / orchestrator ruling 2b).** Audited every
   `font-size`/`font:` declaration in `styles.css` with a script; raised every occurrence below 11px up to 11px
   (33 changed: mode-note, `.fg-s`, timeline `.eng`, node `.eng`, etc.) so nothing a viewer must read is smaller
   than the 11px floor (decorative labels excepted). Re-checked with an in-page text-node walker after the fix -
   0 visible text nodes under 11px in both the Pipeline and Report views and the help overlay. `--mute` raised
   from `#62729c` (3.7:1 on the panel background, below AA) to `#7f8fb9` (~5.5:1, computed via WCAG relative
   luminance against every panel background token) - passes AA for normal text.

5. **Fly panel vertical rhythm (DESIGNER objection #4F) and email chip semantics (#4G).** Fly panel: the network
   now owns essentially the whole body (StaticNet canvas fills `.fly-body`); the suspicion meter was thinned to a
   4px bar. Email chip: `EmailList.tsx chipFor()` now shows the real outcome for a processed comparison email
   (`OK` / `N defect(s)` with the defect field names in the tooltip / `Review`) and the category chip otherwise -
   verified in `innovator-final-done.png`/`innovator-e-autoplay.png` that "Compare" no longer appears on every
   row; it is replaced by e.g. "2 defects" (red) or "OK" (green), which is ruling 2c's requirement.

6. **Tablet dead space (DESIGNER objection #4H).** Left as DESIGNER left it - out of the 1536x1024 target and
   not in my brief; did not touch `@media (max-width: 1180px)` beyond what the new components needed to stay
   inside their panels.

I did **not** revert or fight any of DESIGNER's Round-1 fixes to logo, header sizing, mode pill, connector base
glow, sidebar stat rhythm, sidebar footer art, timeline container/alignment, or panel border alpha - verified
those are all still present and intact in the current build (`innovator-final-done.png`, `innovator-f-1280.png`,
`innovator-f-1920.png`).

### Delight implemented (real data, not decoration)

- **Colour-bead trails** - see above (`components/BeadCanvas.tsx`, `data/graphGeometry.ts`). One canvas, one rAF
  loop for the whole graph; no per-particle DOM nodes, no React re-render per frame (props are read through a
  ref inside the loop).
- **Node completion ripple** - every node (`CircleNode`, `FieldPill`, `GateChip`) fires a two-ring CSS ripple
  exactly once on a real `running -> done` transition (`useCompletion` hook watches state, not time).
- **Mismatch reveal** - a field pill that resolves to a mismatch shakes once and glows once on the graph
  (`.pill.mismatch` keyframes); the corresponding report table row glows once and its two value cells shake once,
  staggered by row (`--ri` CSS var) - verified frame-by-frame (`innovator-reveal-sequence.png`).
- **Count-up stats** - `components/CountUp.tsx` (one rAF per mounted counter, writes to the DOM node directly, no
  re-render) drives the four sidebar stat tiles and the "Top issues" counts; respects reduced-motion (snaps
  instantly).
- **Smooth email-list selection** - `EmailList.tsx` now renders one sliding highlight bar (`transform:
  translateY`, CSS-transitioned) instead of restyling each row, and auto-scrolls the selected row into view.
- **Play whole inbox / auto-cycle mode with a speed control** - `App.tsx` `auto`/`startAuto`/`togglePlay` streams
  through the currently-visible (filtered/searched) email list, throttled per mode (LIVE: >=1.4s dwell so an SSE
  run has time to finish; REPLAY/mock: >=450ms, both further gated by the 1x/2x/4x control which also divides
  every event's playback gap in `usePlayer.ts`). Verified: `innovator-e-autoplay.png` mid-stream on the
  "Flagged" filter; pause/resume verified to freeze/resume the exact in-flight event (no dropped or duplicated
  trace events - `usePlayer.ts` re-queues the in-flight item on pause); auto-play correctly stops and toasts at
  the end of the visible list (`STATUS 517 of 520... stop at end` verified via script).
- **Fly panel hover wiring** - hovering an input dot or a Kenyon cell shows a tooltip built only from real
  `flybrain.json` data: for a KC, its real projection (which inputs feed it) and its real KC->decision weight;
  for an input, how many of the 1600 KCs it feeds and how many are firing right now for the selected email.
  Verified against real wiring (`innovator-b-fly-hover-kc.png`, `innovator-b-fly-hover-in.png` - "wired to 144 of
  1600 Kenyon cells, 3 firing now" for the `mismatch:notify_party` input on `email_004`, cross-checked against
  `fly.projection` by hand).
- **Hebbian weight-change animation on review** - `App.tsx review()` now distinguishes LIVE from REPLAY/mock:
  - **LIVE**: diffs the real `weights` array from `GET /api/flybrain` before and after the review call, so the
    per-KC delta shown is the backend's actual Hebbian update, not a guess. Verified end-to-end against a real
    `uvicorn sdoc.api:app` (no Gemini key -> rules engine): submitted "escalation unneeded" on `email_501`
    (NEEDS_REVIEW, deterministic trigger), suspicion 0.63 -> 0.33, 12 real KCs, mean weight 1.00 -> 0.40 exactly
    matching the backend's `learn()` LTD rule (`w *= 1 - eta_dep`, `eta_dep=0.6` -> `1.00*0.4=0.40`) - screenshot
    `innovator-g-live-hebb.png`.
  - **REPLAY/mock**: there is no backend to update, so I ported the backend's documented rule verbatim
    (`backend/sdoc/flybrain.py` LTD `w*=(1-eta_dep)` / LTP `w+=eta_pot*(1-w)`, `suspicion=1-exp(-sum(w[active])/tau)`,
    `eta_dep=0.6`, `eta_pot=0.5` read from the docstring since the exported `flybrain.json` doesn't carry them -
    see DEVELOPER request #1 below) and apply it locally to the exported weights, kept only in this browser
    session (`simW` state in `App.tsx`), clearly labelled `simulated` everywhere it appears (fly panel gate
    figure, feedback line, and a persistent "taught this session" note with a Reset-weights link) so nothing
    reads as a live number. Verified: `email_501` review -> suspicion 0.63 -> 0.33 (same math as LIVE, run
    against the exported weights); then selecting the near-identical `email_502` shows suspicion **re-evaluated
    with the taught weights** (0.33, "simulated" tag) instead of the stale recorded 0.63 -
    `innovator-c-taught-502.png`. The on-canvas animation itself (one amber/green ring per updated KC, staggered,
    plus a `w 1.00 -> 0.40` label at the winner cell) is identical in both modes -
    `innovator-hebbian-sequence.png` is 4 frames of it firing.
- **Keyboard shortcuts + help overlay** - `j`/`k` (next/prev in the currently visible/filtered list), Space
  (play/pause; starts auto-play from idle), `r` (replay), `a` (toggle auto-play), `1`/`2`/`4` (speed), `g`
  (toggle Pipeline/Report), `?` (help), `Esc` (close). All ignored while focus is in a text input/select. Verified
  by script: `j`/`k` moved selection correctly, `?` opened/closed the overlay (`innovator-b-help.png`), Space
  correctly paused/resumed the in-flight event queue.
- **Subtle background depth** - `components/DepthBg.tsx`: three drifting star-dust layers (`background-image`
  radial-gradients tiled on a CSS `translate3d`+`animation`, opacity-only twinkle on the closest layer) plus a
  page-level parallax that reads pointer position through one shared rAF and writes only `transform` to each
  layer. No `width`/`height`/`padding`/`margin` is ever animated anywhere I touched - grep-verified
  (`grep -n "@keyframes" styles.css` shows only `transform`/`opacity`/`fill`/`stroke`/`box-shadow`/`background-color`
  properties changing).
- **Reduced motion** - extended the existing hook's CSS block (`ripple`, `.f-heb` hidden, dust layers frozen) and
  made `BeadCanvas` and `FlyPanel`'s staged activation skip straight to the settled state instead of animating,
  verified with `Emulation.setEmulatedMedia(prefers-reduced-motion: reduce)`: the graph still lights up
  correctly per state with **zero motion** (`innovator-f-reduced.png`), and the mismatch reveal/ripple/dust
  layers are inert.

### Performance verification (60fps target)

- Idle ambient graph: **100 fps** in the dev build (uncapped by vsync in headless; capped visually by the
  monitor in a real browser) vs 72-77 fps on the pre-existing (DESIGNER Round-1 `dist/`) SVG-`animateMotion`
  particle system on the same machine - the canvas approach is not just prettier, it is cheaper.
- Auto-play at 4x (worst case: continuous bead animation + 5 emails/6s of graph re-renders + fly panel
  re-evaluating every ~1.3s): **67 fps**, worst single frame 70ms (one GC-adjacent frame during a state
  transition, not sustained). No React re-render happens per animation frame anywhere in the new code -
  `BeadCanvas` and the depth layers read current props via a `ref` inside one shared `requestAnimationFrame`
  loop each; `CountUp` writes `textContent` directly.
- Console: clean (no errors/warnings) across idle, mid-run, OK/MISMATCH/NEEDS_REVIEW results, spam bypass,
  auto-play, keyboard nav, help overlay, LIVE review, and all four viewport sizes tested.

### Verification matrix

- `npx tsc -b`: 0 errors. `npm run build`: succeeds, 321 KB JS / 47 KB CSS (gzip 102 KB / 13 KB) - no bundle-size
  regression of note for a hackathon SPA.
- Viewports: 1536x1024 (primary), 1280x800, 1920x1080, 390x844 - no horizontal overflow at any of them
  (`document.documentElement.scrollWidth === clientWidth` checked by script at each size); mobile shows the
  transport bar wrapping under the header as intended.
- LIVE mode exercised against a real `uvicorn sdoc.api:app` (no key -> rules engine): health probe, SSE
  processing, review with real Hebbian diff, `GET /api/flybrain` re-fetch after review.
- REPLAY mode exercised against the real 520-trace export: normal OK/MISMATCH/NEEDS_REVIEW emails, spam bypass,
  auto-play across a filtered subset, keyboard nav, taught-weights persistence across email switches within a
  session.
- Screenshots saved under `reviews/shots/innovator-*.png`; `innovator-d-sequence.png` and
  `innovator-hebbian-sequence.png`/`innovator-reveal-sequence.png` are frame-sequence composites for the
  animations as requested.

### Requests for DEVELOPER (numbered; DEVELOPER may veto with a technical reason)

1. **Expose the fly net's plasticity constants in the export.** `backend/sdoc/flybrain.py` hardcodes
   `eta_dep=0.6`, `eta_pot=0.5`, and `tau=0.15*k` in `FlyBrain.__init__`, but `public()` (and therefore
   `frontend/public/replay/flybrain.json`) does not include them. I read them out of the docstring/source to
   replicate the exact LTD/LTP rule client-side for the REPLAY "teach the net" simulation (request above), which
   works today but is a duplicated constant that will silently drift if you retune the gate. Please add
   `eta_dep`, `eta_pot`, and `tau` (or `k`, `kc_sparsity` is already there so `tau` is derivable) to
   `FlyBrain.public()`'s payload so the frontend's `types.ts FlyBrain.eta_dep/eta_pot/tau` fields (already
   plumbed through, currently falling back to the hardcoded copy) can read the real numbers instead of a mirror.
   Low effort, no CONTRACT shape break (additive fields), removes a divergence risk.
2. **Per-KC weights before/after in `POST /api/review`'s response, not just `GET /api/flybrain.history[-1]`.**
   Not blocking - I implemented this today by diffing two `GET /api/flybrain` calls around the review (works,
   verified in `innovator-g-live-hebb.png`) - but that is a second network round trip and a race if two reviews
   land close together. If cheap, consider having `/api/review` return `{active_kc, before[], after[]}` (or just
   the deltas) directly in its own response the way `developer.md` already asked for `{before, after, verdict}`
   at the top level. This is a nice-to-have, not a correctness issue with what's shipped.

Both are additive/non-blocking; I did not implement anything that depends on them being accepted (REPLAY has a
faithful local fallback for #1, LIVE has a working two-call implementation for #2).

### Files changed/added

- Added: `frontend/src/components/BeadCanvas.tsx`, `CountUp.tsx`, `DepthBg.tsx`, `HelpOverlay.tsx`,
  `frontend/src/data/graphGeometry.ts`.
- Edited: `App.tsx` (transport bar, keyboard shortcuts, auto-play, review/Hebbian orchestration, depth bg),
  `components/GraphPanel.tsx` (canvas beads, ripples, engine-badge policy, hover-linked edge highlight),
  `components/FlyPanel.tsx` (full-network canvas, hover wiring, Hebbian animation, taught-weights display),
  `components/EmailList.tsx` (chip semantics, sliding selection highlight), `components/Sidebar.tsx` (count-up,
  issue-label readability), `components/NodePopover.tsx` (gate drivers), `components/ReportView.tsx` (reveal
  animation hooks), `components/icons.tsx` (minor), `data/usePlayer.ts` (speed control, pause/resume), `types.ts`
  (KcDelta, FlyFeedback.kc/nonce, FlyBrain.taught/eta_dep/eta_pot/tau, GateInfo.drivers), `styles.css` (11px text
  floor pass, `--mute` contrast fix, all new component styles, reduced-motion extensions).
- No backend files touched.

STATUS: OBJECTIONS=2
