## Round 1 - DESIGNER (visual fidelity vs reference-dashboard.png), 2026-09-21

Method: Vite dev server on :5199, `?mode=mock`, headless Chrome 153 over CDP (Claude-in-Chrome extension not connected) at 1536x1024, plus 1280x800, 1920x1080, 1024x768, 390x844. Reference regions cropped and compared 1:1 against build crops. Shots in `reviews/shots/designer-*.png` (`designer-before-*` = as delivered, `designer-after-*` = after my fixes, `designer-side-by-side.png` = reference | build).

### Faithful already (kept)
- Shell layout: thin left sidebar / centre graph / right emails + fly panel / bottom timeline; panel radii, glass, dark navy body with blue haze.
- Graph topology and colour identity: Inbox -> Classifier -> 7 pills -> Aggregator -> (gate chip) -> Report; pill hues green/amber/red/purple/violet/blue/teal map to the reference accents; curved S-connectors fanning out of the classifier and converging into the aggregator; per-node colour glow.
- Header structure: kicker, title, subtitle, pill top-right. Sidebar structure: logo, System Online, 4 stat blocks with round glowing icons, Top issues with ranked circles, footer tagline + green bar. Email row anatomy (status dot, sender, subject, category chip, time). Timeline: 6 icon nodes joined by dotted connectors. Fly panel: title + info icon, input dots left, network, decision neuron right, "Confidence Gate" figure top-right.
- Honest deviations kept as agreed: real 7 field labels, "Accuracy vs. labels" with n/a, "Architecture inspired by the fruit fly's olfactory system" caption, suspicion/threshold instead of "98.2% confidence", engine badges, LIVE/REPLAY/MOCK pill.

### Drift list (as delivered) and what I did

| # | Region | Reference shows | Build showed | Sev | Fix (status) |
|---|---|---|---|---|---|
| 1 | Sidebar logo | 5-6 ray glowing asterisk | Only an "X": the vertical stroke was invisible (SVG `objectBoundingBox` gradient on a zero-width vertical path paints nothing) | High (brand mark broken) | `icons.tsx` Logo: `gradientUnits="userSpaceOnUse"`, unique gradient id, glow drop-shadow. FIXED |
| 2 | Header title | ~21-22 px, regular weight (title spans 285 px) | 25 px / 500 (336 px, 18% too big, heavier) | Med | `.c-title h1` 22px / 450. FIXED |
| 3 | Mode pill | Plain sans "Live" with green dot | Mono uppercase; MOCK dot was alarm-red (reads as an error) | Low-Med | Sans 12px/500; mock dot violet. FIXED |
| 4 | Graph pills | 2px neon border, deep tinted fill, large soft bloom, glowing icon disc | 1.6px border, near-black fill, weak glow | High (core "cinematic" look) | `.node` border 2px; pill gradient 26%->7% tint; double box-shadow (32px bloom + 9px core + inset); icon disc tinted + glow. FIXED |
| 5 | Graph round nodes | Thick bright blue rim, big halo | Thin rim, dim | Med | 6px ring + 38px glow + stronger inset. FIXED |
| 6 | Connectors | Thick saturated lines with soft bloom | 1.7px lines, faint hard glow | High | line 2.2px/0.92, glow 9px + `blur(3px)` at 0.3-0.45, flow 2.8px. FIXED (particle density left to INNOVATOR) |
| 7 | Graph background | Star-dust specks + blue haze at both ends | Flat | Low | `.graph-panel::before` static specks + haze. FIXED |
| 8 | Engine badges on nodes | none | Full-size cyan RULES/PURE tag on every pill, cluttering silhouettes | Med | Kept (honest) but 8.5px, 88% opacity, softer border. PARTIAL (see objection D) |
| 9 | Email chips | Filled tinted pills | Outlined | Low-Med | fill alpha 0x26, border 0x30, 11.5px, more padding. FIXED |
| 10 | Email filter row | (none in ref) | Wrapped to 2 lines, "Spam" orphaned, pushing list down | Med | single nowrap row, tighter chips (also at <=1400 and <=1180 where it overflowed). FIXED |
| 11 | Sidebar stat blocks | Roomier (100 px pitch), delta lines in green/blue, icon glow | 88 px pitch, all sub-lines green, "2 mismatched, 2 to review" wrapped to 3 lines; large void above footer | Med | padding 19px, tone-coloured sub-lines (mismatch = red, not green), copy shortened to "2 mismatch · 2 review" (`Sidebar.tsx`), stronger icon glow, roomier issues list. FIXED |
| 12 | Sidebar footer | Dark teal mountain photo with mist, tagline, green bar | Barely visible 1-path polygon | Low-Med | 3-layer ridges + teal haze SVG, 150px tall. FIXED |
| 13 | Fly network | Smooth fibres converging on the decision neuron, glowing blue nodes, warm-to-cool gradient | Straight rays (spaghetti), KC dots nearly invisible (#2b3d78 on navy), hard white line to decision | High | Cubic S-curve edges for projection, KC->decision and active paths; KC fill/stroke brighter + soft halo; decision halo + larger glow. FIXED (schematic; inter-KC mesh in the reference has no model equivalent and was NOT faked) |
| 14 | Fly figure | White "98.2%" 22px light, no colour | Green 30px | Low | White + blue glow when confident, amber stays for escalate; dark text-shadow so figure stays legible over fibres. FIXED |
| 15 | Fly footer | Line-art fly + glowing ECG trace | 15px bug glyph, dim 64px wave | Low | 22px glowing glyph, 88x28 glowing spike wave. FIXED |
| 16 | Timeline container | Steps sit in an inset rounded strip | Naked | Med | `.tl-steps` inset border/gradient/radius. FIXED |
| 17 | Timeline alignment | Text left-aligned to icon; all rows aligned; beads on connectors | Centred text; "Field agents" dots pushed its rows 11px lower than neighbours; connectors dim with no beads | Med | left-aligned, `order:` rows so all columns align, connector alpha up + one glowing bead per link, the 7 agent dots now ride on the connector after "Field agents". FIXED (hidden <=1400 where the column is too narrow; the "7/7 done" text carries it) |
| 18 | Timeline height | ref ~180 px | 178 px too tight after strip | Low | 192px (204px at <=1400). FIXED |
| 19 | Panel borders | Slightly brighter luminous edge | 0.17 alpha | Low | 0.20 + faint outer bloom. FIXED |

Verification: `npm run build` = 0 TS errors, 1894 modules. Console clean in all captured states (idle, mid-run, OK, MISMATCH, NEEDS_REVIEW, spam bypass, report tab).

### Critique of DEVELOPER's frontend (by name)
A. **Logo shipped broken** (#1): DEVELOPER's Round 1 claim "matches the reference at 1536x1024" was not true for the very first element on screen; the mark was an X. A zoom check on each region would have caught it.
B. **Connector/pill glow under-delivered** (#4-#6): the ambient look was accurate in structure but 30-40% too dim; the "cinematic control room" is the whole pitch. Glow values need to be the first thing tuned, not last.
C. **Fly panel is the weakest match** (#13): the delivered render (straight rays, near-invisible KCs) looked like a debug plot, not a neural network. It also hid honest behaviour: with `n_kc` = 1600 in live mode the sampled 110 KCs at the old contrast were essentially invisible. Verify against the real `flybrain.json` once available, not only the schematic mock (I could only see the schematic; **unverified with 1600 KC / 32 inputs**).
D. **Engine badges as first-class UI on every node** (#8): honest is good, but 9 mono tags at 8-9px are illegible noise at 1536x1024 and fight the pills. Suggest: show engine once per node in the popover/timeline and only badge the node when the engine is *not* the run default (e.g. mixed gemini/rules), or colour-code it with a 6px dot. I only shrank them; a structural fix is DEVELOPER's call.
E. **Small text legibility**: several strings are 8.5-10.5px (`.mode-note` 10px, `.fg-s`/`.m-lbl`/`.fly-foot span` 9.5px, timeline `.eng` 8.5px, node `.eng` 8.5px). At 1536x1024 on a projector demo the 9.5px caption "Schematic layout (no network file found)" and threshold labels are unreadable. Floor should be 10.5-11px for anything a judge needs to read.
F. **Fly panel vertical rhythm**: `Inputs` label (9.5px) sits directly above the dots with no legend in mock mode, and the meter + feedback + footer stack eats ~45% of the panel height, squeezing the network (reference gives the network ~65%). Consider dropping the meter into the "Confidence Gate" block or making it a slim 3px line.
G. **Email panel information density**: filter chips + search cost ~90px, so only 9 rows show vs the reference's 8 larger ones; the "Compare" chip is identical on every comparison email, so the chip column carries no information (the reference uses the chip for issue type). Suggest chip = result status for processed comparison emails (Mismatch red / OK green / Review amber) and category otherwise; the dot already duplicates status, so one of the two should carry the category/issue.
H. **Tablet (<=1180px) layout (not the target, noted)**: at 1024x768 the graph is vertically centred in a ~1000 px tall centre panel (stretched to match the uncapped right column), leaving ~300 px of dead space above the graph; filter chips overflowed there until my fix. Cap `.mail-list` height or align the graph to the top there.
I. **A11y**: good baseline (skip link, aria labels, focus ring, reduced-motion). Objections: node engine badges and status colours (red/green) carry meaning by colour alone in the email dot and timeline dots (no shape/text alternative besides `title`); the mock/Live pill dot colour is the only mode indicator besides text. Contrast of `--mute` (#62729c) on the panel is ~3.3:1, below AA for the 9.5-10px captions using it.
J. **Header controls at 1280**: title wraps to two lines because the three-control cluster takes ~470px of a 634px header; consider collapsing Pipeline/Report to icon-only below 1400px.

### Remaining objections (visual fidelity only)
1. Node engine badges are still visible on every pill/circle (reference has none); needs the structural fix in D. Severity low-medium.
2. Connector particle density/brightness: reference shows many small colour beads per fibre; build has 2-3 white dots. Left for INNOVATOR by brief.
3. Fly network density: the reference's dense KC-to-KC lens mesh cannot be honestly reproduced; current render is closer but still sparser (KC dots ~110, no lateral edges). Also unverified against the real 1600-KC / 32-input net.
4. Email chip semantics (G) and small-text floor (E) not changed.
5. Tablet layout dead space (H), unfixed (outside the 1536x1024 target).

STATUS: OBJECTIONS=5

## Round 2 - DESIGNER (visual fidelity vs reference-dashboard.png), 2026-09-22

Method: `cd frontend && npm run build` first (0 TS errors, verified before and after my edits), then `npm run dev -- --port 5199 --strictPort`, real backend-exported `?mode=replay` data (520 traces, 1600-KC `flybrain.json`). Claude-in-Chrome extension not connected (`tabs_context_mcp` returned "extension is not connected"), so headless Chrome 153 driven directly over CDP (own Node 24 script using the built-in `WebSocket`/`fetch`, no npm deps, in scratchpad) at 1536x1024 primary, plus 1280x800, 1100x850, 1024x768, 390x844. Shots in `reviews/shots/designer-r2-*.png`. Stopped both the dev server and headless Chrome at the end (`taskkill /F /IM chrome.exe /T`, `/IM node.exe /T`); confirmed both `localhost:5199` and `localhost:9333` are unreachable afterward.

### Round 1 objections re-verified

1. **Engine badges fallback-only - RESOLVED.** Read `GraphPanel.tsx`: `runDefaultEngine`/`OddTag` logic (INNOVATOR's Round 1 work) is untouched by DEVELOPER Round 2 (confirmed by diff-reading, and DEVELOPER's own round 2 log says the same). Verified live: a normal all-`rules` run shows zero badges on any of the 7 pills, only a plain `pure` caption under Aggregator (`designer-r2-02-settled.png`, `designer-r2-09` pill zoom). Did not re-verify the mixed-engine fallback case myself (needs a live Gemini key or the fetch-patch INNOVATOR used); trusting their Round 1 verification since the code path is unchanged.
2. **Connector particle beads - RESOLVED, good match.** `designer-r2-10-beads-zoom.png` zoomed crop: warm multi-colour bead trails per field-agent connector, soft glow falloff, close to the reference's density and much better than my Round 1 plain-dot fix. INNOVATOR's "beads carry real per-agent speed" trade-off (fewer beads than the reference's purely decorative count, but each one means something) is a reasonable call, not a regression.
3. **Fly network density - RESOLVED, verified against real data.** `designer-r2-11-fly-zoom.png`: all 1600 of 1600 Kenyon cells drawn from the real `flybrain.json` projection (caption confirms "1600 of 1600"), dense lens-shaped mass, warm-to-cool gradient matching the reference's visual character. This was explicitly unverified in my Round 1 ("unverified against the real 1600-KC net") - now verified with the real replay export, objection closed.
4. **Email chip semantics - RESOLVED.** `EmailList.tsx chipFor()` now shows real per-email outcome for processed comparison emails: "2 defects" (red), "OK" (green), "Review" (amber); category chip otherwise ("SI request", "Invoice"). Verified across multiple screenshots (`designer-r2-01`, `-02`, `-21-spam`) - no email row still shows a generic uninformative "Compare" chip.
5. **Tablet dead space - NOT accepted this round; escalated with a stronger, verified reason (see below).** DEVELOPER's Round 2 log both investigated and declined this ("a real fix risks a visual regression... left as DESIGNER left it"), but the actual behaviour I measured at 1024x768 is materially worse than what either of us described in Round 1: it is not "dead space above a centred graph", it is a broken, effectively unusable layout. I fixed it myself (see below) since the fix was cheap and safe, so this is no longer an open objection, but I'm recording it as a correction of what was previously understood as low-severity.

### New defect found and fixed: tablet layout was not "dead space", it was broken

Selecting any email at 1024x768 (`<=1180px` breakpoint) rendered a **completely empty center panel** - not even a placeholder. Diagnosis via injected JS (`getBoundingClientRect`/`scrollHeight`): `document.body.scrollHeight` was **28,921px**, and the graph `.stage` element had `top: 14008.5px` - the whole pipeline graph was being centered inside a column roughly 29,000px tall, i.e. rendered ~14,000px below the visible viewport. Root cause: `@media (max-width: 1180px) { .app { grid-template-rows: auto minmax(560px, auto) 178px; } }` - the `auto` max on the `'center right'` row has no bound, so with 520 rows in the (otherwise correctly `overflow-y:auto`) `.mail-list`, the grid track's max-content contribution becomes the full unclipped list height (~520 x 55px), stretching that whole row - and therefore `.center`'s graph viewport, whose JS sizing (`GraphPanel.tsx` `ResizeObserver` + `box.h`) reads that real (huge) height - to match. This is a genuine layout bug, not a design/effort trade-off: a user on a tablet-width window could not see the pipeline at all without scrolling roughly three screen-heights down.

Fix (`styles.css`, inside the existing `@media (max-width: 1180px)` block only - no change above 1180px, verified): capped the row at `minmax(560px, 660px)` instead of `minmax(560px, auto)`, and gave `.right` a matching `max-height: 660px` (it already had `min-height: 620px`). This forces `.mail-list`'s own `overflow-y: auto` to actually do its job instead of never triggering. Verified:
- `document.body.scrollHeight` at 1024x768 with an email selected: **1037px** (was 28,921px).
- Graph renders immediately in view, no scrolling needed (`designer-r2-15-tablet-fixed.png`).
- Email list now properly shows a short scrollable window of rows instead of all 520 (`designer-r2-15`, `designer-r2-16` diag).
- No regression at 1536x1024 (`designer-r2-18-primary-recheck.png`, pixel-identical structure to the pre-fix `designer-r2-02`), 1280x800 (`designer-r2-19-1280.png`), 1100x850 (`designer-r2-20-1100.png`, just above/at the breakpoint boundary), or 390x844 mobile (`designer-r2-17-mobile-390.png`, unaffected since the `<=820px` query's own fixed `.right` rows take over and my `max-height:660px` addition is larger than that layout ever needs).
- `npm run build`: 0 TS errors (CSS-only change).

This supersedes Round 1 objection #5 ("tablet dead space, unfixed, outside the 1536x1024 target, low severity") - it was not merely out-of-target polish, it was a real bug, cheap to fix, and now fixed.

### New defect found and fixed: misleading Hebbian "no-op" message survived DEVELOPER's own fix

Verifying DEVELOPER's item #8 (human-review panel moved above the fold; `DEFAULT_INIT_W` 0.9 so a genuine fly-gate LTP confirmation is no longer a silent 1.00->1.00 no-op) surfaced a related bug DEVELOPER's fix did not fully close. DEVELOPER's log for #8 says: "for a deterministic trigger [the backend] returns `review.fly = {skipped: true, reason: ...}` instead, surfaced honestly in the UI ('No fly-net weight update: this escalation was a deterministic trigger...') rather than a misleading `before == after` line. Mirrored in the REPLAY/mock local simulation (`App.tsx`) for consistency across modes."

That upstream wiring is correct - both `source.ts` (`LiveSource.review`) and `App.tsx`'s REPLAY local mirror correctly build a `FlyFeedback` object with `skippedReason` set for a deterministic-trigger review, exactly as described. But **`FlyPanel.tsx`'s render of that object never checked `skippedReason` at all** - it unconditionally rendered `"Weights updated after human verdict ...: suspicion 0.86 -> 0.86"` regardless, which is precisely the misleading no-op line the fix claims to have eliminated. Verified live: selected `email_520` (a `NEEDS_REVIEW`/`missing_value` deterministic-trigger email, flagged filter, REPLAY mode), submitted "Confirm mismatch" - `designer-r2-06-hebbian.png` shows the exact bug (`"Weights updated ... suspicion 0.86 -> 0.86 SIMULATED"`).

Fixed in `FlyPanel.tsx`: added a branch so `feedback.skippedReason` renders as `"No fly-net weight update - <reason>"` (same panel slot/style as the existing message, `.fly-fb.dim`) instead of falling through to the generic "Weights updated" line. Verified:
- Same repro (`email_520`, confirm mismatch) now shows `"No fly-net weight update - this escalation was a deterministic trigger, not a fly-gate decision - no weight update applied (the gate never decided anything here to reinforce)"` (`designer-r2-07-hebbian-fixed.png`).
- Confirmed the *other* path still works and is a real, visible change: found the only two replay emails where `gate.decided_by === 'flynet' && escalate` (`email_513`/`email_514`, real grey-zone escalations per the backend's item #1 fix), submitted a review on `email_513` - shows `"Weights updated after human verdict escalation correct: suspicion 1.00 -> 1.00 · 80 Kenyon cells, mean weight 0.81 -> 0.91"` (`designer-r2-08-flynet-hebbian.png`) - a real, non-trivial per-KC weight change (top-level suspicion is pinned at the 1.00 ceiling here, but the underlying KC weights genuinely move, which is the correct, honest thing to show).
- `npm run build`: 0 TS errors both before and after.

### Review panel placement/style (DEVELOPER item #8) - matches the dashboard's visual language

Verified directly (not just by reading the diff): selected a `NEEDS_REVIEW` email in REPLAY, opened the Report tab. The "Human review needed" panel now renders immediately under the headline banner, above the SI/BL table (`designer-r2-05-review-report.png`), using the same amber-bordered/glow panel treatment as the rest of the report (not a bolted-on grey box), with the radio verdict ("Was the escalation warranted?"), "Confirm mismatch" / "Confirm: no mismatch" / "Correct a field" actions in the existing button language, and the honest `REPLAY: SIMULATED LOCALLY` tag in the same corner-tag style used elsewhere. This is a real fix, at the primary 1536x1024 target, and it reads as native to the design system - no objection.

### Other spot checks (no regressions found)

- Spam bypass arc (`designer-r2-21-spam.png`): field pills correctly dimmed/"skipped", direct curve Classifier->Report, "Aggregate + compare" step correctly shows "not run" (DEVELOPER item #7 - previously showed a false "all 7 match"). Confirmed live, not just by reading the diff.
- Console: 0 errors/exceptions across a scripted click-through of 5 emails + Report tab (`Runtime.consoleAPICalled`/`exceptionThrown` listeners attached before navigation).
- INNOVATOR's Round 1 delight work (bead canvas, count-up stats, sliding email selection, ripples, keyboard shortcuts affordance) all still present and visually intact in every screenshot taken this round - DEVELOPER's Round 2 changes did not touch or regress them, matching DEVELOPER's own "kept all INNOVATOR delight features untouched" claim.
- Small-text floor and `--mute` contrast (my Round 1 objection E, closed by INNOVATOR Round 1): spot-checked still applied (fly panel captions, timeline engine tags all >=11px) - no regression from DEVELOPER's Round 2 CSS edits.

### Critique of DEVELOPER (by name)

A. **Item #8's fix was incomplete - the exact failure mode it names ("a misleading before==after line") still occurred**, just moved one layer down: the backend/orchestration correctly stopped *lying about the number*, but the frontend component that most needed to change (`FlyPanel.tsx`, the one place a judge would actually be looking at when they click "Confirm mismatch") was never updated to read the field the fix's own design depends on. A written claim that mirrors "for consistency across modes" without a screenshot of both modes' UI is exactly how this kind of gap survives review - I only found it by actually clicking through a deterministic-trigger review in the running app, not by reading `App.tsx`/`source.ts` alone (those two files looked correct in isolation).
B. **Tablet breakpoint's actual severity was under-diagnosed twice** (once by me in Round 1 - "dead space", once by DEVELOPER in Round 2 - "a real fix risks a visual regression... left as DESIGNER left it"). Neither of us had actually measured `scrollHeight` or the graph's computed `top` offset; "looks like wasted space in a screenshot" and "graph is rendered 14,000px off-screen and the panel is otherwise completely empty" are very different bugs, and only the latter is what was actually shipping. Given this was a two-line CSS fix once diagnosed, I'd push back gently on the Round 2 framing of "risks a visual regression under this round's time budget" - the fix here took under 15 minutes including full before/after verification at five viewport widths.
C. Nothing else to add to my Round 1 critique (A/B/C/D/E/F/G/H/I/J) - items D (engine badges) through I (a11y) were INNOVATOR's remit and were verified resolved above or in Round 1; J (header controls at 1280) was not addressed by DEVELOPER or INNOVATOR this round and remains a minor, non-blocking cosmetic item at a non-primary width.

### Critique of INNOVATOR (by name)

Nothing new to add for Round 2 - INNOVATOR did not touch frontend files this round (per developer.md's own confirmation that DESIGNER/INNOVATOR were not running). My Round 1 critique of INNOVATOR's Round 1 work stands as resolved: the bead canvas, fly-net canvas, engine-badge policy, text floor and email chip semantics were all re-verified live against the real 520-email/1600-KC replay export this round (not just the mock data INNOVATOR used for some of their own Round 1 checks) and all held up. No objections.

### Files changed this round

- `frontend/src/components/FlyPanel.tsx`: render `feedback.skippedReason` as an explicit "No fly-net weight update" message instead of falling through to the generic (and here misleading) "Weights updated ... before -> after" line.
- `frontend/src/styles.css`: `@media (max-width: 1180px)` - `.app`'s middle grid row capped at `minmax(560px, 660px)` (was `minmax(560px, auto)`) and `.right` given `max-height: 660px`, so `.mail-list`'s existing `overflow-y: auto` can actually engage instead of the row growing to the full unclipped 520-row list height. No change outside this media query.

Verification: `npm run build` = 0 TS errors, 1899 modules, both before and after every edit in this round. Console clean at 1536x1024 across idle/mid-run/OK/MISMATCH/NEEDS_REVIEW/spam-bypass/report-tab/review-submit states in both LIVE-shaped (deterministic-trigger) and flynet-decided review paths. No horizontal overflow observed at 1920 was not re-checked this round (unchanged code path, INNOVATOR verified it Round 1); 1536x1024, 1280x800, 1100x850, 1024x768, 390x844 all checked this round.

### Remaining objections (visual fidelity only)

None found after fixing the two defects above and re-verifying all five Round 1 objections against the real backend-exported data. Header-controls-wrap-at-1280 (item J) remains open but was already known, is non-blocking, and is below the 1536x1024 primary target.

STATUS: NO REMAINING OBJECTIONS
