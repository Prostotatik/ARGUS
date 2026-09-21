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
