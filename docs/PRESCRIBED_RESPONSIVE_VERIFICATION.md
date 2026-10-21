# Prescribed Sessions 1–3 responsive verification

Verified locally on October 20, 2026. Baseline template commit: `e555bc84d16d54f75be549161fe9404124bd7f3a`.

## Results

- All 21 activity entry routes rendered through their actual Django view contexts. The fixture renderer rejects database access and uses synthetic empty progress.
- All 84 regular desktop comparisons passed: 21 activities at 1366 × 768, 1440 × 900, 1536 × 864, and 1920 × 1080.
- 80 desktop screenshots were byte-identical PNGs. The four Lesson 7 Gawain 1 screenshots had identical visible element geometry and computed styles; 398 pixels per screenshot differed at blurred shadow edges. The comparator requires exact geometry/styles for non-identical screenshots and permits fewer than 0.1% of pixels to differ by more than 12 channel levels. It does not accept layout or typography changes.
- All 42 large layouts passed at 2560 × 1440 and 3440 × 1440. Every primary panel measured 1780 px wide with 0 px horizontal centering error. No document overflow, distorted wheels, or images extending beyond the audited picture frame remained.
- All 105 narrow/tablet layout measurements passed the horizontal overflow check at 320 × 568, 375 × 667, 390 × 844, 768 × 1024, and 1024 × 768. Tall content retains vertical scrolling.
- Actual large PNG screenshots were inspected in contact sheets for all activities, with individual screenshots inspected for recording, rhyming, picture reading, wheel, handwriting, and shape layouts. This is rendered screenshot verification, not only bounding-box measurement.
- The complete Lesson 1 recording browser regression passed all 14 scenarios, including real 88-second playback/capture using a synthetic microphone, natural completion, auto-submit, teacher retry/approval, failure paths, interruption handling, and responsive recording indicator placement.
- 24 Django tests passed across handwriting validation, prescribed streaming, and admin preview modules.
- 32 pointer checks passed: three handwriting layouts plus shape dragging, resized through 2560 × 1440, 3440 × 1440, 390 × 844, and 1440 × 900 at device pixel ratios 1 and 2.
- 63 native Chrome page-zoom checks passed: every activity at 75%, 125%, and 150%. The audit verified the actual Chrome zoom setting, resulting device pixel ratio and CSS viewport, and absence of horizontal overflow. A disposable browser profile was removed afterward.
- Django system check and Git whitespace check passed.

## Fixes completed during verification

The shape templates' malformed class attributes were repaired. Large layout overrides now account for panels nested in navigation wrappers, inherited fixed widths, and old absolute positioning. The wheel retains its square aspect ratio, writing sheets expand, the large picture stays inside its frame, and the Lesson 5 and Lesson 9 content groups center within their panels.

Lesson 7 Gawain 2A maps pointer coordinates from the current displayed canvas to its existing drawing buffer after resizing. Stroke validation, answer evaluation, scoring, persistence, and progression code are unchanged.

## Session 1 follow-up: rhyming activities

The subsequent screenshot report identified two gaps in the initial pass: the
outer panel was centered while its contents were not, and Basahin inherited a
malformed shared font shorthand (`Basahinvar(...)`), leaving a 13.33 px label.
The earlier outer-panel checks did not establish vertical composition centering.

The Lesson 2 Gawain 1 and Lesson 3 Gawain 1 templates now share a local
`session-one-rhyme` hook. Their title, picture pair, controls, and progress stay
together in normal layout flow. The existing progress placement scripts use CSS
variable fallbacks for positioning only; recording, evaluation, attempts,
progression, content, and persistence were not changed by this follow-up.

The centering correction activates at CSS viewports at least 1600 px wide and
900 px tall, including 1680 × 925 from the reported screenshots. It therefore
intentionally corrects these two pages at 1920 × 1080 as well. Basahin's local
typography correction applies at every size (20 px on desktop, about 27–28 px
at the two large target sizes). The other activities retain the original desktop
comparison requirement. The audit records the two requested exceptions explicitly
instead of reporting them as unchanged screenshots.

`tools/test_prescribed_rhyme_responsive.cjs` exercises the actual introduction
button, reading renderer, answer renderer, and completion renderer at all eleven
requested sizes plus 1680 × 925: 96 rendered states. It checks horizontal overflow,
label size, large-panel control containment, and the vertical center of the complete
composition (within 20 px of the panel center), not only the outer panel. Six
comparisons at 1366 × 768, 1440 × 900, and 1536 × 864 require identical visible
element geometry and non-Basahin typography against the original template.
Animations and transitions are frozen for those comparisons.

Screenshots of both pages at 1680 × 925, 2560 × 1440, and 3440 × 1440 were
rendered and inspected, including introduction, reading, and answer states.
Focused evidence is stored as `rhyme-regression.json` and
`*-rhyme-{intro,reading,answers,completion}.png` in the audit output directory.
These fixtures hold narration and do not establish speech recognition accuracy.

The follow-up pass completed all 96 states and all six desktop geometry
comparisons. The complete layout audit passed again: 76 unchanged desktop
comparisons for the other 19 activities, eight explicitly requested rhyme-page
corrections, 42 large layouts, and 105 narrow/tablet measurements. All 63 native
Chrome zoom checks passed again. One Session 2 Lesson 4 Gawain 2 screenshot at
1366 × 768 had identical computed styles/geometry but a GPU drop-shadow raster
difference; rerunning that activity with `PABASA_AUDIT_SOFTWARE=1` passed the
original pixel tolerance without relaxing it. The two existing baseline script
errors listed below remain unchanged. Django system and Git whitespace checks
also passed.

## Session 2 Lesson 4 Gawain 1: focused-picture refinement

The focused artwork previously inherited a 350 px parent width cap, a
360 × 330 px image cap, and a narrow grid column. The peanut asset additionally
contains transparent margins. The page now loads `lesson4_gawain1_focus.css`,
scoped to this activity's focused state. It allocates more width to the picture,
sets the image itself to fill a definite grid area with `object-fit: contain`,
and sizes that area with viewport height up to 680 px. Original assets are
unchanged. The doll's old vertical offset is replaced by contained centering.

The interaction panel keeps its existing styling and now includes padding and
borders within its assigned width. At tablet widths the picture and controls
stack; narrow phones also stack the buttons. Tall mobile content can scroll.
The overview, wheel artwork, reveal animation, activity JavaScript, narration,
recognition, scoring, attempts, feedback, navigation, and persistence were not
modified by this refinement.

All six pictures (manok, manika, susi, mangga, mais, mani) were rendered through
the existing reading and classification renderers at the eleven requested
viewport sizes: 132 focused layouts passed image/panel containment, horizontal
overflow, control containment, and desktop viewport-fit checks. Desktop image
and panel centers align vertically. The actual contained artwork's linear
dimensions increased approximately 1.6–1.9 times at 1920 × 1080 and 2–2.7 times
at 2560 × 1440, depending on aspect ratio; these figures measure painted image
dimensions, not just enlarged containers.

All six 2560 × 1440 screenshots were inspected together. Individual peanut,
doll, desktop, and 320 px phone screenshots were also inspected. Local evidence
is in `lesson4-focus-before.json`, `lesson4-focus-after.json`,
`lesson4-focus-six-pictures.png`, and `lesson4-focus-*-after.png` under the audit
output directory. Fixtures hold narration and fulfill requests in memory;
these layout checks do not exercise a live speech provider. Django system and
Git whitespace checks passed.

## Session 2 Lesson 4 Gawain 2 and Lesson 5 Gawain 1: centering and spacing

This section records the initial centering pass. The later Lesson 4 Gawain 2
card-height and disabled-label refinement below supersedes its card-height
measurements; Lesson 5's layout is preserved.

These two templates now load `session2_activity_spacing.css`. No shared activity
stylesheet, speech code, scoring code, content, or state transitions were changed
for this refinement. Its body markers and stylesheet are present only on these
two pages; completion states are excluded from the new layout rules.

Lesson 4 Gawain 2 previously forced the page to `justify-content:flex-start`.
Lesson 5 combined fixed intro margins, a viewport-height active card, a
100%-height inner application, and a flex-growing focus section. The new grid
reserves a normal navigation row and centers the card in the remaining viewport.
Lesson 5's card/application/focus use their content height; progress follows
the controls with a normal gap. On phones the persistent 52 px tools and their
14 px clearances have a reserved row before the back link, preventing overlap.

`tools/test_prescribed_session2_spacing.cjs` renders the actual Django fixtures
using the real activity URL paths. It clicks the real introduction gate and
Lesson 5 MAGSIMULA control with synthetic audio completion, and inspects:

- Lesson 4 Gawain 2 active state;
- Lesson 5's 3 × 3 introduction;
- Lesson 5 active reading state.

All three states passed at 1366 × 768, 1440 × 900, 1920 × 1080, 2560 × 1440,
768 × 1024, and 375 × 812, plus 1680 × 925 matching the supplied screenshots:
21 rendered layouts. Card centers were within 1 px of the remaining viewport's
center, all content stayed inside the cards, and all 21 documents fit without
horizontal or vertical scrolling. Opening each Speech Debug Panel left its card
rectangle identical in all 21 checks. Necessary scrolling remains possible if
future content exceeds the available height.

Before/after measurements confirmed unchanged Lesson 4 card dimensions at all
seven sizes, unchanged desktop picture sizes and heading typography, and the
same Lesson 5 desktop grid/image dimensions. Lesson 5's active card height fell
from 972 to about 567 px at 1920 × 1080, and from 1060 to about 603 px at
2560 × 1440. All three desktop compositions and individual tablet/phone
screenshots were rendered and inspected. Evidence is saved as `spacing-before.json`,
`spacing-after.json`, and `*-spacing-{before,after}.png` in the audit directory.
These local fixtures fulfill API requests in memory and do not write progress
or contact speech providers.

## Session 3 Lesson 7 Gawain 1: viewport centering

The active view resolves to `lesson_7_gawain_1_aligned7.html`, through the older
aligned-template chain and `lesson_7_gawain_1_page.html`. In the current local
baseline, horizontal card centers already matched the viewport; the reported
rightward displacement was not reproduced. Vertical placement was incorrect:
the 1920 × 1080 introduction was about 123 px above center. The cascade retained
legacy `top/left:50%` rules, replaced their positioning mode with static flow,
then applied vertical transforms and margins inside a top-aligned 1250 px wrapper.

The activity alone now loads `lesson7_gawain1_centering.css`. Its full-width
viewport grid centers the card independently of the narrower navigation column.
Equal upper/lower tracks account for navigation without moving the card away
from the viewport center. Old card offsets/transforms/margins are cleared.
At short desktop heights, default heading margins and a little card padding
are reclaimed so the original wheel fits clear of navigation. On narrow screens,
the active layout stacks its wheel and controls; the inherited two-column layout
previously clipped both. Completion states are excluded from the new shell rules.
No wheel, randomization, selection, image, scoring, narration, or recording code
was modified.

`tools/test_prescribed_lesson7_centering.cjs` uses local Django fixtures at the
actual URL path, clicks the introduction gate and Magsimula, and waits for the
real active layout to appear. It passed 14 states (intro/active) across
1366 × 768, 1440 × 900, 1920 × 1080, 2560 × 1440, 3440 × 1440, 768 × 1024,
and 375 × 812. Both states measured these exact desktop card centers:

| Viewport | Card center | Center error |
| --- | --- | --- |
| 1366 × 768 | 683, 384 | 0 px on both axes |
| 1920 × 1080 | 960, 540 | 0 px on both axes |
| 2560 × 1440 | 1280, 720 | 0 px on both axes |

The session label, intro heading, wheel, and Magsimula button share the viewport's
horizontal center. Before/after wheel dimensions match: 384 px outer diameter
on regular desktops and 644 px at 2560 × 1440. All 14 checks passed content
containment, horizontal overflow, navigation separation, and debug-panel geometry
invariance. Desktop documents fit without scrolling. Actual desktop and phone
screenshots were inspected, including the corrected active phone layout.
Evidence is stored as `lesson7-centering-{before,after}.json` and
`lesson7-*-centering-{before,after}.png`. These fixtures use synthetic audio
completion and in-memory API responses, without live speech-provider requests
or student progress writes. Django system and Git whitespace checks passed.

## Session 3 Lesson 7 Gawain 2C: content-fitting handwriting card

The template's `.card { flex:1 }` filled the available page height, and the
large-screen shared stylesheet added a 1060 px minimum height. This page alone
now loads `lesson7_gawain2c_spacing.css`, which removes those card height
constraints, keeps comfortable symmetric padding, and places progress 20 px
after the controls. Equal navigation tracks center the desktop card. Mobile
layout reserves the persistent tools before the back link and allows genuine
content overflow to scroll. Completion styling is excluded from these rules.

The writing sheet, canvas, guideline backgrounds, model letter, buttons, and all
activity JavaScript are unchanged. The card heights measured approximately:

| Viewport | Before | After | Canvas CSS dimensions (unchanged) |
| --- | --- | --- | --- |
| 1366 × 768 | 652 px | 449 px | 780 × 82.94 px |
| 1920 × 1080 | 964 px | 489 px | 780 × 96 px |
| 2560 × 1440 | 1060 px | 508 px | 1130 × 96 px |

`tools/test_prescribed_lesson7_gawain2c_spacing.cjs` renders both uppercase and
lowercase rows at 1366 × 768, 1440 × 900, 1920 × 1080, 2560 × 1440,
3440 × 1440, 768 × 1024, and 375 × 812: 14 rendered layouts. All passed
containment, horizontal overflow, desktop/tablet centering and viewport-fit,
debug-panel geometry invariance, pointer/ink alignment, and Burahin checks.
Before/after comparisons also require identical canvas CSS/buffer dimensions,
guideline backgrounds, and letter font size. The desktop card centers differ
from the viewport center by less than 0.01 px.

Uppercase desktop, lowercase 1440p, and phone screenshots were rendered and
inspected. Evidence is in `lesson7-g2c-spacing-{before,after}.json` and
`lesson7-g2c-row*-spacing-{before,after}.png`. A separate device-pixel-ratio-2
pointer pass completed 16 checks across the three handwriting activities and
shape dragging after viewport resizing. These synthetic local checks do not
exercise recognition/validation or change student progress; the recognition,
case-acceptance, scoring, attempts, and progression code was not modified.

## Lesson 7 Gawain 2C follow-up: handwriting guide alignment

The previous spacing pass intentionally retained the existing model typography.
The subsequent screenshot exposed an older font alignment issue: the guide used
an HTML line box positioned at the top of the row, with a viewport-based font
size. Its visible uppercase ink started 17–30 px below the upper guide and ended
7–15 px below the lower guide on the requested desktops. Lowercase also extended
below the baseline.

`lesson7_handwriting_guide.js` now measures the existing Andika glyph's actual
ink bounds and presents only the decorative guide as SVG text. The uppercase
fits between the inside edges of the blue stripes. Lowercase uses the dotless
i's matching stem metrics to fit its body between the red and lower blue stripes,
with its dot above the red stripe. The initial pass horizontally centered both
glyphs by their ink bounds; the subsequent left-placement correction is recorded
below. Font readiness, row replacement, and a ResizeObserver keep
placement consistent when fonts load, the activity changes row, or the viewport
resizes. Stripe positions and thickness are read from the existing backgrounds;
there are no viewport-specific guide offsets.

This is a visual-only module: the original activity JavaScript, drawing canvas,
buffer sizing, pointer calculations, recognition, validation, attempts, scoring,
audio, and progression remain unchanged. The new module creates its own detached
measurement context and never reads or changes the writing canvas. The existing
guide color, font family/weight, card spacing, and guideline backgrounds remain.

`tools/test_prescribed_handwriting_guide.cjs` renders uppercase and lowercase
from the real template with local assets and in-memory API responses. It checks
1366 × 768, 1440 × 900, 1920 × 1080, 2560 × 1440, 3440 × 1440,
768 × 1024, 375 × 812, and 320 × 568, then returns the same mounted row through
2560 × 1440, 1440 × 900, and 1366 × 768. The reference state disables only the
new guide module, preserving all previous layout improvements. Black-on-white
crops measure actual rendered glyph pixels rather than the model's line box.
The test compares card geometry, canvas CSS/buffer dimensions, and guideline
backgrounds exactly. It also hides only the intentionally corrected glyph to
require identical remaining desktop pixels. Small-screen border rasterization
differences are recorded separately from geometry.

All 44 guide checks passed (22 each at device pixel ratios 1 and 2), including
the repeated resizes. Maximum measured top/bottom alignment error was 1.41 CSS
px and horizontal ink-center error was 0.75 CSS px, including raster rounding.
The requested four desktop sizes had identical remaining screenshot pixels
when the corrected glyph was hidden. Card geometry, writing canvas CSS/buffer
dimensions, and guideline backgrounds were identical at every tested size.
At DPR 1, 320 px screenshots had 100/123 differing pixels at fractional rounded
border edges; their geometry was identical. The comparator records these mobile
raster differences and retains exact desktop pixel assertions.

The 14-layout spacing/pointer/Burahin pass was rerun successfully, along with
16 DPR-2 resize checks across handwriting and shape dragging. All six Django
handwriting case-acceptance tests passed. Normal desktop, large, ultrawide, and
phone screenshots were inspected individually and in a before/after guide
contact sheet (`handwriting-guide-contact.png`). Speech-provider accuracy was
not exercised by these isolated fixtures.

Screenshots and results are stored under `tmp/prescribed-responsive-audit/` as
`guide-row*-dpr*-{before,after}.png` and `handwriting-guide-dpr*.json`.

### Requested left-side placement

The user subsequently requested the guide on the left. The decorative model
now retains the activity's original 13% left inset, with SVG ink aligned to the
start of that area (`xMinYMid`). Uppercase and lowercase keep the corrected
vertical glyph bounds. The card, writing canvas, guideline backgrounds, and
activity logic are unchanged by this adjustment.

The same browser check now asserts the original left inset rather than the
viewport center. New evidence uses `guide-left-row*-dpr*-{before,after}.png`
and `handwriting-guide-left-dpr*.json`, preserving the initial centered pass.
All 44 left-placement checks passed at DPR 1 and 2, including repeated resizing.
The maximum measured left-inset error was 1.34 CSS px; vertical alignment and
card/canvas/guideline geometry stayed unchanged. Desktop pixel comparison permits
only one channel level of paint rounding: the initial exact comparison found
one rounded-button edge pixel differing by RGB (1, 1, 1), with no geometry change.
Normal desktop, large desktop, and mobile screenshots were inspected.

## Lesson 7 Gawain 2B follow-up: center the whole card

The existing content-fitting override changed the activity wrapper to a flex
column but left its contents top-aligned. The navigation/card stack therefore
stayed near the top at regular desktops. At large sizes, the shared responsive
sheet additionally imposed a 1060 px minimum card height and centered the stack
including its back button, moving the card below the viewport center.

The template now has a local `lesson7-g2b-centered` marker and loads
`lesson7_gawain2b_centering.css`. Equal flexible grid tracks above and below the
card reserve the existing 64 px navigation height and center the card itself.
The back button occupies the upper track without transforms or positional
offsets. A local override removes the inherited large minimum height so the
card fits its contents. Existing widths, padding, typography, images, controls,
progress indicators, and internal spacing are preserved. Small screens reserve
the fixed tools and allow document scrolling. Completion is excluded; the debug
panel remains fixed independently. No activity JavaScript was edited.

Reading-state measurements:

| Viewport | Card width × height after | Before center Y | After center Y |
| --- | --- | --- | --- |
| 1366 × 768 | 1218 × 484.19 px | 340.09 px | 384 px |
| 1440 × 900 | 1218 × 487.38 px | 341.69 px | 450 px |
| 1920 × 1080 | 1218 × 489.13 px | 342.56 px | 540 px |
| 2560 × 1440 | 1780 × 489.13 px | 752 px | 720 px |

Regular desktop card dimensions are unchanged. At 2560/3440 px widths, only the
unnecessary 1060 px minimum height was removed; the natural reading card height
is 489.13 px and the selection card height is 649.13 px.

`test_prescribed_lesson7_gawain2b_centering.cjs` passed 32 rendered states:
first/last reading items and picture selection at eight viewport sizes, plus
repeated large/regular resizes and two unchanged completion layouts. Sizes were
1366 × 768, 1440 × 900, 1920 × 1080, 2560 × 1440, 3440 × 1440,
768 × 1024, 375 × 812, and 320 × 568. The check compares the whole card's center,
its original width/natural height, component dimensions/styles, regular-desktop
internal spacing, containment, navigation clearance, overflow, and debug-panel
geometry invariance. Desktop centering error was below 0.01 px, with no desktop
scrolling. Screenshots at all four requested desktop sizes were rendered and
inspected; evidence is `lesson7-g2b-centering.json` and
`lesson7-g2b-*-{before,after}.png` in the ignored audit directory. The entry-page
desktop/large/mobile audit was rerun for this activity and merged into the
existing report, with this requested centering correction explicitly recorded.

Both Gawain 2B verdict tests passed, as did the Django system check. A broader
run of `tests_basahin_reading_verdict` ran 26 tests and reported 10 failing
Gawain 6 Kariton/Carton spelling subcases across two methods. Those failures
come from the unchanged backend verdict code; neither that code nor its test
module was edited. They are recorded in `verdict-suite.log` and were left outside
this layout-only fix. Local browser fixtures do not exercise a live speech
provider or write student progress.

## Lesson 7 Gawain 3 follow-up: content-fitting card

The active card inherited both `height:calc(100dvh - 40px)` and `flex:1` inside
a viewport-height wrapper. Centering its contents left large blank bands inside
the card. At large viewports, the shared sheet additionally imposed a 1060 px
minimum height. The progress indicator itself already occupied normal flow;
the oversized card was creating the surrounding empty space.

A local `lesson7-g3-compact` marker and `lesson7_gawain3_spacing.css` now remove
the fixed height, minimum height, and flex growth for this activity. Equal grid
tracks reserve the existing navigation height and center the entire natural
card. Original card widths, padding, picture dimensions, button sizes, fonts,
colors, and component gaps remain unchanged. Progress stays beneath the buttons,
with its existing margin; circles retain their dimensions and wrap on mobile.
The desktop back control uses its intrinsic width and does not wrap its label.
Small screens retain natural document scrolling. Completion is excluded, and
the fixed debug overlay does not affect the card geometry. No activity JavaScript,
items, narration, verdict, scoring, or progression code was modified.

Reading-state card heights:

| Viewport | Before | After |
| --- | --- | --- |
| 1366 × 768 | 634 px | 492.91 px |
| 1440 × 900 | 766 px | 497.48 px |
| 1920 × 1080 | 946 px | 500.73 px |
| 2560 × 1440 | 1060 px | 706.55 px |

The larger existing picture at 2560 px is preserved. In every active state,
the remaining blank bands above the session label and below the indicator equal
only the existing padding plus borders.

`test_prescribed_lesson7_gawain3_spacing.cjs` passed 52 rendered layouts: first,
middle, and last reading items; first and last selection targets; completion;
and repeated resizing. Sizes were 1366 × 768, 1440 × 900, 1920 × 1080,
2560 × 1440, 3440 × 1440, 768 × 1024, 375 × 812, and 320 × 568.
The desktop card center differed from the viewport center by less than 0.01 px.
The checks preserved all 15 reading items and verified the progress states at
1/15, 8/15, and 15/15. All circles are contained, mobile circles remain at least
28 px across, and the progress row remains within 25 px of the buttons. Original
picture/control dimensions and styles matched the before fixtures. No desktop
scrolling, horizontal overflow, clipped components, or navigation overlap was
found; completion geometry and debug-panel invariance passed.

Screenshots at all four requested desktop sizes, mobile progress wrapping,
and selection states were rendered and inspected. Evidence is in
`lesson7-g3-centering.json` and `lesson7-g3-*-{before,after}.png`. The entry-page
audit was rerun for Gawain 3 and neighboring Gawain 2B/2C and merged with the
existing report. All 13 `tests_prescribed_stream` tests and the Django system
check passed. Browser fixtures use local assets and in-memory API responses;
they do not exercise live speech providers or write student progress.

## Lesson 7 Gawain 4 follow-up: compact handwriting card

The active card's `flex:1` stretched it inside a viewport-height page, while
the shared large-screen rules imposed an additional minimum height. The new
local `lesson7-g4-compact` marker and `lesson7_gawain4_spacing.css` remove that
growth/minimum height and place the natural card between equal navigation grid
tracks. Card width/padding, writing sheet and canvas dimensions, guideline
backgrounds, buttons, typography, and inter-component spacing are preserved.
The two-item progress indicator already follows the buttons in document flow;
it retains its original styling and 12 px gap. Completion is excluded, the debug
panel stays fixed, and narrow screens can scroll when the full composition
cannot fit.

| Viewport | Card height before | Card height after |
| --- | --- | --- |
| 1366 × 768 | 652 px | 462.81 px |
| 1440 × 900 | 784 px | 486.89 px |
| 1920 × 1080 | 964 px | 497.17 px |
| 2560 × 1440 | 1060 px | 554.78 px |

The guide audit found existing font/baseline drift as well: at 2560 × 1440,
the visible uppercase O ended about 36 px above the lower guide; lowercase o
also missed its intended band. The existing presentation-only
`lesson7_handwriting_guide.js` now accepts optional row/letter selectors and
retains fonts declared on b/i children. Gawain 4 opts in for `.row` and `Oo`;
Gawain 2C retains its existing defaults. The uppercase ink fits between the blue
stripes, and lowercase fits between red and lower blue. Both retain their
original left-side inset, color, and font weight. The module only measures
decorative text in a detached context and never reads or changes the writing
canvas. Guideline positions/thickness are read from existing CSS backgrounds;
no viewport-specific letter offsets were introduced.

`test_prescribed_lesson7_gawain4_spacing.cjs` passed 44 rendered layouts at
device pixel ratios 1 and 2: uppercase/lowercase at 1366 × 768, 1440 × 900,
1920 × 1080, 2560 × 1440, 3440 × 1440, 768 × 1024, 375 × 812,
and 320 × 568, including repeated resizes and unchanged completion states.
Desktop center error was below 0.01 CSS px. Guide ink alignment was within
1.5 CSS px, including integer/half-pixel raster rounding. All 40 active layouts
passed real pointer/ink alignment and Burahin checks. Before/after comparisons
required identical canvas CSS/buffer dimensions, guidelines, component sizing,
vertical gaps, and horizontal component alignment. No desktop scrolling,
horizontal overflow, clipping, navigation overlap, or debug-panel shifts occurred.
Normal desktop, large desktop, lowercase, and mobile screenshots were rendered
and inspected. Evidence is `lesson7-g4-spacing-dpr{1,2}.json` and
`lesson7-g4-row*-dpr*-{before,after}.png` in the ignored audit directory.

All original inline Gawain 4 activity scripts matched HEAD, including canvas
coordinates, stroke validation, size/case acceptance, feedback, audio, scoring,
and progression. The six existing handwriting case/progress tests passed. The
shared guide's Ii defaults passed 22 additional browser checks, including their
existing left placement. Entry-page audits for Gawain 4, Gawain 2C, and Gawain 3
were rerun and merged with the previous report. These isolated browser fixtures
use local assets and in-memory APIs; they do not verify live handwriting/speech
providers or write student progress.

## Lesson 7 Gawain 4A follow-up: oversized letter grid and clipping

The compact height breakpoint ended at 760 px and therefore missed 1366 × 768.
The default 67.2 px letters with normal font leading produced 114–118 px tiles;
four rows, large tools, and a large heading exceeded the fixed card height.
The card's hidden overflow clipped the lower rows and submit control. Shared
large-screen rules also widened the worksheet to 1200 px and imposed a 1060 px
card minimum height.

The conditional `lesson7_gawain4a_responsive.css` now sizes the heading, tools,
three-column grid, tiles, stamps, and spacing together. The card fits its
contents between equal navigation tracks, and uses visible overflow with natural
document scrolling when needed. All 12 letters retain their IDs and order.
Colors, font families/weights, border styles, and completion layout are unchanged.
The fixed debug panel does not move or resize the card. Other activity keys do
not load this stylesheet.

| Viewport | Card height after | Grid height before → after |
| --- | --- | --- |
| 1366 × 768 | 467.5 px | 530 → 218.1 px |
| 1440 × 900 | 513.7 px | 530 → 248.8 px |
| 1920 × 1080 | 592.1 px | 546 → 290.5 px |
| 2560 × 1440 | 678.7 px | 546 → 344 px |
| 768 × 1024 | 567.8 px | 367 → 277.6 px |
| 375 × 812 | 481.2 px | 319 → 228.4 px |

All six requested viewports were rendered and their full screenshots inspected.
Every tile, both shape tools, and ISUMITE fit without clipping, internal scrolling,
or horizontal overflow. The extra 320 × 568 check allows necessary document
scrolling and verifies that ISUMITE remains reachable. Desktop cards are centered;
letters remain at least 30 px and tiles at least 44 px high.

`test_prescribed_lesson7_gawain4a_responsive.cjs` passed 24 current rendered
layouts across device pixel ratios 1 and 2, including resizing, ultrawide, mobile,
and unchanged completion states. Twenty interaction scenario groups passed:
native square/circle dragging to first and last rows, stamp removal, rejected
submission/retry, and successful completion with all expected placements.
These use controlled API responses in isolated fixtures, not live backend grading.
Original inline activity scripts are unchanged. All four admin prescribed-preview
tests, the Django system check, and source whitespace/syntax checks passed.
Entry-page audits for Gawain 4A and neighboring Gawain 4/4B were rerun and merged;
no unexpected desktop changes or large-screen overflow were reported.

Evidence is `lesson7-g4a-responsive-dpr{1,2}.json` and
`lesson7-g4a-*-dpr*-{before,after}.png` in the ignored audit directory.

### Gawain 4A minor enlargement after the clipping fix

The compact fix above remains the baseline for a second, deliberately small
refinement. The first refinement required 1000 CSS px of viewport height, which
excluded the user's approximately 1680 × 924 screenshot despite ample space.
The corrected rule now covers viewports at least 1200 px wide and 800 px high.
Card and worksheet widths grow about 12%, tile heights 20%,
letter fonts 18%, and square/circle illustrations 15%. Heading, submit control,
padding, and inter-component gaps retain their compact sizes. Natural card
height grows about 9–10%; no fixed height, transform scaling, or hidden overflow
is introduced.

| Viewport | Card dimensions after refinement | Tile height | Letter font |
| --- | --- | --- | --- |
| 1366 × 768 | 814.1 × 467.5 px (unchanged) | 44.5 px | 31.488 px |
| 1440 × 900 | 1068.5 × 560.1 px | 62.6 px | 43.542 px |
| 1536 × 864 | 1025.7 × 543.6 px | 60.1 px | 41.8 px |
| 1680 × 924 | 1097 × 571.8 px | 64.3 px | 44.7 px |
| 1200 × 800 | 949.8 × 518.7 px | 55.7 px | 38.704 px |
| 1920 × 1080 | 1282.2 × 647.7 px | 75.2 px | 49.56 px |
| 2560 × 1440 | 1300 × 745.8 px | 91.2 px | 49.56 px |

The `--refinement` mode compares against the compact rules with just this new
media block removed. It passed 30 current rendered layouts at DPR 1 and 2,
including repeated resizing, mobile, tablet, ultrawide, and completion layouts.
Twenty-six native dragging/removal/retry/completion scenario groups passed using
controlled fixture API responses. All 12 letter IDs/order and three columns
remain unchanged. Browser errors were empty. Full screenshots at 1366 × 768,
1680 × 924, 1920 × 1080, and 2560 × 1440 were inspected: every row, both shape tools, and
ISUMITE are visible, with balanced centering and no desktop scrolling/clipping.
Before/after screenshots at 1366 × 768, 768 × 1024, and 375 × 812
were pixel-identical at DPR 1. No activity scripts or backend behavior changed.
An HTTP request to the actual localhost:8000 static URL confirmed that the
served stylesheet matches the edited source, including the new 800 px threshold.
The template stylesheet URL was advanced to `20261020-3` to refresh cached assets.
The four admin prescribed-preview tests passed again. Django system and source
checks passed. Gawain 4A/4/4B entry-page audits were rerun and merged with the
existing report, with no unexpected desktop changes or large-screen overflow.

Evidence is `lesson7-g4a-refinement-responsive-dpr{1,2}.json` and
`lesson7-g4a-refinement-*-dpr*-{before,after}.png` in the ignored audit directory.

## Lesson 8 Gawain 1 follow-up: compact Ee handwriting card and guides

The Ee template uses `lesson_7_gawain_4.css`: its card grows with `flex:1`
inside a viewport-height page, and the shared large-screen stylesheet adds a
1060 px minimum height. The scoped `lesson8_gawain1_spacing.css` removes that
stretch and places the natural-height card between equal navigation tracks.
Its width, padding, internal gaps, heading, canvas, guidelines, controls, and
two-item progress indicator retain their existing dimensions and styles.
Progress stays in document flow below the buttons. Completion is excluded;
the debug panel remains an independent fixed overlay. Small screens retain
natural document scrolling when needed.

| Viewport | Card height before | Card height after |
| --- | --- | --- |
| 1366 × 768 | 652 px | 432.42 px |
| 1440 × 900 | 784 px | 456.50 px |
| 1680 × 924 | 808 px | 459.95 px |
| 1920 × 1080 | 964 px | 466.78 px |
| 2560 × 1440 | 1060 px | 524.39 px |
| 768 × 1024 | 400.16 px | 400.16 px |
| 375 × 812 | 385.83 px | 385.83 px |

The percentage reduction varies with viewport height because the card fits its
contents; existing internal padding and component gaps are preserved.

The existing E/e guides used different offsets/transforms over HTML line boxes.
At 2560 × 1440, uppercase E ended about 28 px above the lower blue guideline;
lowercase e started about 20 px below the middle red line and extended about
6 px past the baseline. The template now opts into the existing decorative
`lesson7_handwriting_guide.js` with `.row` and `Ee`. Font ink bounds fit E between
the inner blue edges and e between red and lower blue, retaining the original
font family, weight, color, and left-side inset. This helper uses a detached
measurement context and never changes the writing canvas or stroke coordinates.
The shared helper itself was unchanged for this follow-up.

`test_prescribed_lesson8_gawain1_spacing.cjs` checks both states, before/after
component geometry/styles and guidelines, canvas CSS/buffer dimensions, native
pointer alignment, Burahin, progress state, debug-panel invariance, and completion
geometry. Its resize checks wait for the existing button transitions to settle
before comparing measurements. It passed 48 rendered current layouts at DPR 1
and 2, including 44 native pointer/Burahin checks, repeated resizing, ultrawide,
and completion checks. Guide ink alignment was within 1.5 CSS px, including
raster rounding. No desktop scrolling, clipping, horizontal overflow, or debug
panel shifts occurred. Both states at all six requested viewports were
rendered and visually inspected, including the full mobile compositions.
Evidence is `lesson8-g1-spacing-dpr{1,2}.json` and
`lesson8-g1-row*-dpr*-{before,after}.png` in the ignored audit directory.

All six existing handwriting case/progress tests passed, as did the Django
system check and source syntax/whitespace checks. Every original inline Ee
activity script matches HEAD. The actual localhost:8000 stylesheet response
matches the edited source. Entry-page audits for Ee and neighboring Gawain 1A
and Lesson 7 Gawain 4 were rerun and merged without unexpected desktop changes
or large-screen overflow. Browser fixtures use local assets and in-memory API
responses; no live handwriting/speech providers or student progress were used.

## Lesson 9 Gawain 1 follow-up: content-fitting letter-combination card

The original card was absolutely positioned with translate centering and both
`height` and `max-height:calc(100vh - 190px)`. Shared large-screen rules then
imposed a 1060 px minimum height. These constraints stretched the card around
the existing task and 11-item indicator. The new `lesson9-g1-compact` body marker
and `lesson9_gawain1_spacing.css` replace that positioning with equal navigation
grid tracks and a natural card height. The existing desktop and mobile card
widths, padding, colors, typography, and component dimensions remain intact.
Completion is excluded. The debug panel remains an independent overlay, and
small screens can scroll naturally when content is taller than the viewport.

| Viewport | Reading card height before | Reading card height after |
| --- | --- | --- |
| 1366 × 768 | 578 px | 485.56 px |
| 1440 × 900 | 710 px | 492.98 px |
| 1680 × 924 | 734 px | 495.50 px |
| 1920 × 1080 | 890 px | 500.48 px |
| 2560 × 1440 | 1060 px | 515.94 px |
| 768 × 1024 | 834 px | 438.31 px |
| 375 × 812 | 638 px | 392.39 px |

Natural height varies by phase and viewport. Existing components are retained
rather than resized to meet a particular percentage reduction. All 11 indicators
follow the task naturally; on narrow screens they wrap with their existing
28 px size instead of flex-shrinking into a single row.

`test_prescribed_lesson9_gawain1_spacing.cjs` passed 70 current rendered layouts
at DPR 1 and 2, covering syllables, combination, last-item word reading, unchanged
completion states, repeated resizing, all six requested viewports, 1680 × 924,
3440 × 1440, and 320 × 568. Before/after comparisons preserve heading, label,
letter/word display, tile, and button dimensions/styles, desktop indicator
dimensions, and card width/padding/design. No desktop scrolling, clipping,
horizontal overflow, navigation overlap, or debug-panel shifts occurred.
All six requested reading screenshots and representative desktop/mobile
combination and final-word screenshots were rendered and visually inspected.

Six native interaction scenario groups passed with controlled fixture responses:
Pakinggan, rejected-read attempt tracking, the second syllable, wrong combination
order, reset, correct combination, next-item progression, and final completion
with all 11 item indices. Original Basahin button binding and activity callbacks
are exercised; speech results and APIs are supplied in memory. These are client
flow checks, not live microphone/provider or backend grading verification.

All original inline activity scripts match HEAD. All 17 prescribed-stream and
admin preview tests passed. The actual localhost:8000 CSS response matches the
edited source. Lesson 9 Gawain 1/2/3 entry-page audits were rerun and merged with
the existing report, without unexpected desktop changes or large-screen overflow.
Evidence is `lesson9-g1-spacing-dpr{1,2}.json` and
`lesson9-g1-*-dpr*-{before,after}.png` in the ignored audit directory.

## Lesson 9 Gawain 2 follow-up: compact reading and selection cards

The active view renders `lesson_9_gawain_2_active_page.html`, which includes the
base Gawain 2 template. Late rules in that base template force oral cards to
`100vh - 130px` and selection cards to `100vh - 230px`; the shared large-screen
minimum also applies. The local `lesson9-g2-compact` marker and
`lesson9_gawain2_spacing.css` remove those height/position constraints and center
the natural card between equal navigation tracks. Existing card width, header,
picture box, actual images, buttons, and per-phase padding/styles are preserved.
The two progress states retain 15 oral items and five selection rows. Indicators
wrap on narrow screens at their existing mobile size; taller content can scroll
naturally. Completion is excluded and the fixed debug panel cannot shift the card.

| Viewport | Oral height before → after | Selection height before → after |
| --- | --- | --- |
| 1366 × 768 | 638 → 548.56 px | 538 → 495.88 px |
| 1440 × 900 | 770 → 555.98 px | 670 → 529.38 px |
| 1920 × 1080 | 950 → 563.48 px | 850 → 537.95 px |
| 2560 × 1440 | 1060 → 582.94 px | 1210 → 552.94 px |
| 768 × 1024 | 894 → 510.55 px | 794 → 456.44 px |
| 375 × 812 | 692 → 523.55 px | 622 → 393.53 px |

Screenshot inspection also caught an inherited handwriting `.row` height of
150 px on large screens. The unchanged image buttons were taller and overlapped
the heading. A local `#selection-row { height:auto }` now contains those buttons.
Only this parent row's height adapts; image/button dimensions remain identical.
The browser checks explicitly require containment and separation from the heading.

`test_prescribed_lesson9_gawain2_spacing.cjs` compares the real before/after
templates for first/last oral and selection states, completion, all six requested
viewports, 1680 × 924, 3440 × 1440, 320 × 568, and repeated resizing. It checks
component dimensions/styles, all progress states, card centering, debug invariance,
horizontal overflow, clipping, navigation overlap, and unchanged completion.
It passed 92 current rendered layouts at DPR 1 and 2, plus eight native
interaction scenario groups. Desktop card center error was below 0.01 CSS px.
No unnecessary desktop scrolling, clipping, horizontal overflow, heading/image
overlap, navigation overlap, or debug-panel shifts remained.
Both phases at all six requested sizes were rendered and visually inspected,
including selected-answer screenshots and the corrected large/ultrawide row.

Native client-flow checks use controlled speech/API responses to exercise
Pakinggan, rejected-read attempt tracking, picture advancement, oral-to-selection
transition, wrong-selection retry, correct selection/advancement, and completion.
They do not access live microphone/providers or write student progress. All
original inline scripts in both base and active templates match HEAD.

All 17 prescribed-stream/admin-preview tests passed, along with Django system
and source checks. The actual localhost:8000 stylesheet matches the edited file.
Entry-page audits for Gawain 1/2/3 were rerun and merged with the existing report
without unexpected desktop changes or large-screen overflow. Evidence is
`lesson9-g2-spacing-dpr{1,2}.json` and `lesson9-g2-*-dpr*-{before,after}.png`
in the ignored audit directory.

## Lesson 9 Gawain 3 follow-up: balanced word-reading composition

The audit found the defect at regular desktop sizes as well as large monitors:
button-to-indicator gaps were about 88 px at 1366 × 768, 179 px at 1440 × 900,
347 px at 1920 × 1080, and 237 px at 2560 × 1440. The regular pages also had an
unnecessary 8 px document overflow and the card center was 16 px too low.
These layouts therefore needed the spacing correction; component dimensions,
font sizes, colors, card width, and padding were preserved in before/after checks.

The source forced the outer card to `100vh - 150px`, its task to
`calc(100% - 52px)`, and progress to a negative top margin. Large-screen styles
added a 1060 px card height. The local `lesson9-g3-compact` marker and
`lesson9_gawain3_spacing.css` replace those constraints with natural card/task
heights and equal navigation grid tracks. The browser's default body margins
are removed to fix page overflow while retaining the prior content widths.
The tablet/mobile grid explicitly centers its natural-height card so it does
not stretch into the remaining space. Tall content scrolls normally.

| Viewport | Card height before → after | Button/indicator gap before → after |
| --- | --- | --- |
| 1366 × 768 | 618 → 540.05 px | 87.95 → 18 px |
| 1440 × 900 | 750 → 580.94 px | 179.06 → 18 px |
| 1920 × 1080 | 930 → 592.94 px | 347.06 → 18 px |
| 2560 × 1440 | 1060 → 592.94 px | 236.53 → 18 px |
| 768 × 1024 | 874 → 556.88 px | 327.13 → 18 px |
| 375 × 812 | 692 → 512.55 px | 233.45 → 18 px |

The heading/word gap increases from 4 to 20 px, clearing the word card's gold
halo. The word/action gap remains exactly 18 px; the label/heading gap remains
unchanged. All 15 indicators follow the buttons naturally, wrapping on mobile
at their existing 28 px size instead of shrinking. Completion layout is excluded
and unchanged, and the debug panel remains independent.

`test_prescribed_lesson9_gawain3_spacing.cjs` passed 70 current rendered layouts
at DPR 1 and 2, with first/middle/last words, long sentences, unchanged completion,
all six requested viewports, 1680 × 924, ultrawide, 320 × 568, and repeated resizes.
Comparisons require unchanged word-card, heading, label, and button dimensions
and typography/styles, card width/design, plus exact 20/18/18 px component gaps.
All six requested layouts and long-sentence desktop/mobile screenshots were
rendered and visually inspected. No desktop scrolling, clipping, navigation
overlap, horizontal overflow, or debug-panel shifts remained. The extra 320 px
screen uses necessary document scrolling with the full content retained.

Six native fixture scenario groups passed for Pakinggan, rejected reads without
advancement, middle-item progression, and final progress through item 15.
Responses are controlled in memory; these do not verify a live microphone,
speech provider, or backend grading. All original inline scripts in both base
and active templates match HEAD, and no activity mechanics were edited.

All 17 prescribed-stream/admin-preview tests, the Django system check, and
source checks passed. The actual localhost:8000 stylesheet matches the source.
Lesson 9 Gawain 1/2/3 entry audits were rerun and merged without unexpected
desktop changes or large-screen overflow. Evidence is
`lesson9-g3-spacing-dpr{1,2}.json` and `lesson9-g3-*-dpr*-{before,after}.png` in
the ignored audit directory; `lesson9-g3-spacing-audit.json` records the initial
unmodified layout measurements.

## Session 1 Lesson 3 Gawain 2: initial spacing follow-up (superseded)

This section records the first pass. The next section documents the current
refinement, including the smaller CSS viewport shown in the user's screenshot.

The active view renders `lesson_3_gawain_2_page.html` and mounts the existing
`lesson3_gawain_2_sequence.js` renderer. At 2560 × 1440, the shared large-display
stylesheet imposed a 1060 px minimum card height. Stretched grid tracks and
automatic picture/progress margins spread the reading composition through that
height. The card was also centered together with its navigation row, leaving
the card itself 44 px below the viewport center.

`lesson3_gawain2_spacing.css` is scoped to the new `lesson3-g2-spacing` body
marker and activates only at the existing large-display breakpoint: width at
least 2500 px and height at least 1000 px. It removes the card minimum height
and stretched tracks, retains fluid section spacing, and centers the actual
content-fitting card between equal flexible grid tracks. The navigation has
its own track. The original script's automatic progress margin has no excess
height left to absorb. The existing picture cards, images, connector, label,
heading, buttons, and six indicators retain their dimensions and styling.

At 2560 × 1440, the reading card changes from 1060 to 907.25 px tall (14.4%
shorter). Heading/picture spacing changes from 159.58 to 122 px; picture/action
row spacing changes from 197.59 to 140 px; action row/progress spacing changes
from 147.58 to 90 px. The existing 16 px lift applied to the reading buttons by
the original script is retained. The rhyme-answer state keeps its existing
49 px picture/action and 8 px action/progress gaps; only its expansive automatic
picture margin is replaced, resulting in a 720.25 px content-fitting card.

All new rules are inactive at 1366 × 768, 1440 × 900, 1536 × 864, 1920 × 1080,
768 × 1024, and 375 × 812. Completion is excluded from the refinement. No
activity JavaScript or backend logic is changed.

The focused regression is `tools/test_prescribed_lesson3_gawain2_spacing.cjs`.
It renders the real Django fixture with local assets, checks before/after
geometry and computed styles, inspects screenshots, and drives the original
reading/rhyme buttons with controlled in-memory provider/API responses. It
does not access a microphone or write to an account.

Verification passed 70 current rendered layouts and 18 native fixture scenario
groups at DPR 1 and 2. Coverage includes all six requested viewports, 1536 × 864,
3440 × 1440, 320 × 568, repeated 2560 → 1440 → 2560 resizing, both reading
targets, rhyme answers, all six picture pairs, and unchanged completion. The
large card's measured horizontal and vertical center errors are zero CSS
pixels. The actual Session 1 speech debug overlay was toggled independently in
35 layouts without moving the card.

All requested viewport screenshots and ultrawide/answer screenshots were
rendered and visually inspected. All regular desktop geometry and computed
styles match the immediately preceding layout exactly. Across 24 desktop
screenshot comparisons, the largest significant compositor difference was
0.061% of pixels (unchanged animated outline/shadow edges); answer screenshots
were pixel identical. No horizontal overflow was introduced. The three
neighboring Session 1 entry audits were rerun and merged: 84 desktop
comparisons across the existing 21-activity report show no unexpected changes,
and the large-screen report has no document overflow.

The 17 prescribed-stream/admin-preview Django tests, system check, JavaScript
syntax check, and diff whitespace check passed. Original inline activity
scripts match HEAD, and localhost:8000 serves the exact new stylesheet. The
existing `Invalid or unexpected token` script error remains identical in the
before/after fixtures; this layout change adds no browser errors. Evidence is
`lesson3-g2-spacing-dpr{1,2}.json`, `lesson3-g2-desktop-pixels.json`, and
`lesson3-g2-*-dpr*-{before,after}.png` in the ignored audit directory. The
initial measurements are retained in `lesson3-g2-spacing-audit.json`.

## Session 1 Lesson 3 Gawain 2: screenshot viewport and tighter spacing

The follow-up screenshot was 1679 × 916 pixels. The first pass activated only
at CSS widths of at least 2500 px, so a monitor using a smaller browser viewport
or display scaling missed that fix. Even where active, the first pass retained
90 px picture/action and action/progress margin rules. The screenshot's
processing button state was not the cause: the same gaps existed when idle.

The activity-specific stylesheet now activates at width ≥1600 px and height
≥900 px. It also removes the padded-body/full-viewport-child mismatch at those
sizes and puts the actual outer card into the same symmetric grid used on the
larger display. The card has natural height; three separate, bounded fluid gaps
control heading/pictures, pictures/actions, and actions/progress. No image,
card, heading, label, connector, button, indicator, or state styling is resized.
The smaller rhyme-answer state retains its already comfortable component gaps.
Completion is excluded. The stylesheet URL is versioned `20261020-2`.

| Viewport | Reading card height before → after |
| --- | --- |
| 1366 × 768 | 658 → 658 px (unchanged) |
| 1440 × 900 | 790 → 790 px (unchanged) |
| 1536 × 864 | 754 → 754 px (unchanged) |
| 1680 × 916 | 806 → 683.48 px |
| 1680 × 924 | 814 → 684.23 px |
| 1920 × 1080 | 970 → 698.58 px |
| 2560 × 1440 | 907.25 → 733.86 px |
| 3440 × 1440 | 907.25 → 733.86 px |
| 768 × 1024 | 914 → 914 px (unchanged) |
| 375 × 812 | 662 → 662 px (unchanged) |

The screenshot-sized card is 15.2% shorter, and the 2560 px card is 19.1%
shorter than the preceding implementation. At 2560 × 1440, heading/picture,
picture/action-row, and action-row/progress gaps change from 122/140/90 px to
81.11/65.83/31.67 px. At 1680 × 916, those gaps change from
78.84/116.84/66.84 px to 55.95/60.06/24 px. The existing 16 px button lift is
preserved, so the actual visible button/progress gap is 47.67 px on the largest
screen and 40 px in the screenshot-sized viewport.

`test_prescribed_lesson3_gawain2_spacing.cjs --refinement` compares against the
immediately preceding stylesheet preserved in the ignored audit directory as
`lesson3_gawain2_spacing-before-refinement.css`. The default test compares
against the activity with the local spacing stylesheet omitted. The new
coverage holds an in-memory transcription response and invokes the existing
processing label API, mirroring `Basahin.capture`, so `Sinusuri...` and its
disabled listening control can be rendered without accessing a microphone.
All actual application scripts, provider behavior, button labels, and mechanics
remain unchanged.

The refinement passed 104 current rendered layouts and 22 native fixture
scenario groups at DPR 1 and 2. All six requested viewports plus 1680 × 916,
1680 × 924, 1536 × 864, ultrawide, 320 × 568, repeated resizing, processing,
both reading targets, rhyme answers, all six pairs, and completion were covered.
The maximum measured card-center error on affected viewports was 0.0078125 CSS
pixels. Toggling the actual debug overlay did not move the card in any of the
104 current layouts. Component dimensions/styles were compared before/after
in each affected state, including `Sinusuri...`.

All requested viewport screenshots, the screenshot-sized processing state,
ultrawide, the leaf/box pair, and the answer state were visually inspected.
At 1366/1440/1536 and the smaller screens, all visible element geometry and
computed styles match the preceding implementation exactly. Raw PNG comparison
diagnostics were retained for 24 regular-desktop state comparisons: most were
pixel identical, with a maximum difference of 0.125% around an unchanged
fractionally positioned picture-card border. Visual inspection and identical
computed geometry/styles indicate rasterization differences at those edges;
the PNG files are not all byte identical.

The 17 Django regression tests, system check, JavaScript syntax check, and diff
whitespace check passed. Original inline activity scripts still match HEAD,
localhost:8000 serves the exact version-2 stylesheet, and the existing parser
error remains identical before/after. The three neighboring Session 1 entry
audits were rerun and merged without unexpected desktop changes or large-screen
document overflow. Evidence is `lesson3-g2-refinement-spacing-dpr{1,2}.json`,
`lesson3-g2-refinement-desktop-pixels.json`, and
`lesson3-g2-refinement-*-dpr*-{before,after}.png` in the ignored audit directory.

## Session 2 Lesson 4 Gawain 1: intro spacing and Basahin typography

The intro used `height: calc(100dvh - 108px)`, a mobile viewport minimum,
and a flex-growing `.overview`. The progress widget was already in normal flow;
the growing overview distributed surplus space above the wheel and below
Magsimula. The local `lesson4_gawain1_spacing.css` makes only the intro card and
overview use their content height. A two-row page grid reserves the existing
top navigation, then centers the entire card in the remaining activity area.
The original wheel, six wheel images, heading, session label, start button,
progress sizes, and card width/padding/design are preserved. A 12 px overview
margin keeps the heading/wheel gap comfortable without growing the card.

| Viewport | Intro height before → after | Start/progress gap before → after |
| --- | --- | --- |
| 1366 × 768 | 660 → 632.69 px | 39.66 → 20 px |
| 1440 × 900 | 792 → 689.84 px | 77.08 → 20 px |
| 1680 × 920 | 812 → 698.52 px | 82.75 → 20 px |
| 1920 × 1080 | 972 → 725.78 px | 149.11 → 20 px |
| 2560 × 1440 | 1060 → 962.16 px | 74.92 → 20 px |
| 768 × 1024 | 916 → 695.33 px | 136.34 → 20 px |
| 375 × 812 | 728 → 487.94 px | 16 → 16 px |

The large-screen wheel remains 648 × 648 px; at Full HD it remains 418 × 418 px.
The mobile start/progress gap was already comfortable and is retained; the
mobile viewport minimum was responsible for its excessive bottom padding.

The shared Basahin shorthand contains the invalid family expression
`Basahinvar(--font-family-primary)`, leaving this button at 13.3333 px and
weight 400. Pakinggan is 16.8 px at weight 900, with the same Andika family and
normal line height. Activity-scoped font longhands now give Basahin exactly
those properties, and its decorated nested label explicitly inherits them.
The shared stylesheet is unchanged. Button boxes, padding, colours, borders,
shadows, rounded corners, and state behavior remain unchanged. The instruction
panel and all six focused-picture dimensions retain their existing sizes.
Desktop/tablet active component positions are also unchanged. On phones at
480 px or narrower, a top navigation row below the fixed tools prevents the
existing Back-label overlap. The phone activity moves as a group and uses
natural document scrolling when needed; no component is resized.

`test_prescribed_lesson4_gawain1_spacing.cjs` uses real Django-rendered fixtures
and local assets, with provider/microphone/audio/progress responses controlled
in memory. It compares dimensions and visual styles before/after, permits only
the requested Read typography changes, and drives the existing start, listen,
reading, retry, and classification handlers. The source application scripts are
unchanged. An initial read-only `--audit` pass is retained as
`lesson4-g1-spacing-audit.json` in the ignored audit directory.

Verification passed 90 current rendered layouts and 16 native fixture scenario
groups at DPR 1 and 2. Both intro and active states at all six requested sizes,
1680 × 920, ultrawide, viewport resizing, rejected reading, processing, rejected
classification, correct progression, all six focused images at 1920/2560, and
unchanged completion at 1366/2560 were covered. All requested intro and active
screenshots were rendered and visually inspected. Tests compare component
dimensions, visual styles, desktop/tablet active positions, matching nested
Read/Listen typography, no horizontal overflow, containment, necessary phone
scrolling, and independence of the actual speech debug overlay.

All 17 prescribed-stream/admin-preview Django tests and source checks passed.
The existing standalone retry test's literal LF marker rejected the unchanged
CRLF template. A temporary test copy normalizing only input line endings passed
all seven retry checks; the original test and all activity scripts were left
unchanged. The served version-2 stylesheet matches local source. Neighbor entry
audits for Lesson 4 Gawain 2 and Lesson 5 Gawain 1 were rerun and merged without
unexpected desktop changes or large-screen overflow. Evidence is
`lesson4-g1-spacing-dpr{1,2}.json`, the `lesson4-g1-spacing-*-dpr*-*.png`
screenshots, phone rerun logs, and retry/Django logs in the ignored audit folder.

## Session 2 Lesson 4 Gawain 2: compact card and disabled-label follow-up

The remaining lower whitespace came from `#feedback` and `#status`: both were
already permanently hidden by the template, but their minimum line heights and
flex gaps still occupied space after the progress circles. Large displays also
inherited the shared 1060 px minimum card height. The scoped additions in
`session2_activity_spacing.css` remove those invisible layout rows, clear the
minimum card height, and use balanced 24–36 px responsive vertical padding.
The existing navigation grid continues to center the actual outer card in the
available viewport. Completion layouts are excluded.

Only this activity matches the new `session2-centered-activity:has(#activity-data)`
rules. The picture card, image dimensions, yellow border, badge, heading,
buttons, and six progress circles retain their original dimensions and styles.
Picture-to-button separation remains 22 px, including the picture's margin;
the progress row remains 14 px below the buttons. Neither separation was changed.

| Viewport | Reading card before → after | Space below progress before → after |
|---|---|---|
| 1366 × 768 | 643.77 → 573.39 px | 102.38 → 26 px |
| 1440 × 900 | 684.84 → 620.47 px | 102.38 → 29 px |
| 1920 × 1080 | 684.84 → 631.25 px | 102.38 → 34.39 px |
| 2560 × 1440 | 1060 → 856.47 px | 180.95 → 38 px |
| 768 × 1024 | 651.92 → 594.98 px | 102.38 → 32.72 px |
| 375 × 812 | 615.52 → 545.86 px | 102.38 → 26.36 px |

Disabled Basahin/Pakinggan labels now use the existing `#183e63` text color on
the unchanged `#b5c5c7` muted background: 6.17:1 contrast. This color rule applies
only to disabled oral controls in idle/model states. Recording/processing colors,
enabled styling, disabled attributes, and availability conditions are unchanged.
The local HTTP static response was checked against the saved stylesheet, and
all 11 inline script blocks remain identical to HEAD.

`tools/test_prescribed_session2_lesson4_gawain2_refinement.cjs` uses Chrome and the
real Django-rendered activity template. Its baseline disables only this latest
CSS block, retaining all preceding responsive changes. It inspects disabled,
enabled, audio-playback, processing, and initial-sound choice states; exercises
rejected reads/choices and correct progression; renders all six items and
completion at 1920/2560 widths; and resizes from 2560 to 1440 and back.
Microphone, provider, audio, and persistence responses stay in memory.

The focused checks cover 320 × 568, 375 × 812, 768 × 1024, 1024 × 768,
1366 × 768, 1440 × 900, 1536 × 864, 1680 × 922, 1920 × 1080,
2560 × 1440, and 3440 × 1440 at display pixel ratios 1 and 2. Screenshots
of the requested desktop/tablet/phone layouts and the large/ultrawide layouts
were rendered and inspected. All activity components remain within the card,
no horizontal overflow is introduced, desktop/tablet states fit without page
scrolling, and the short phone viewport can scroll naturally. Toggling the
Speech Debug Panel leaves the outer card rectangle identical.

Both pixel ratios passed: 69 current activity layouts each (138 total), with
44 combined before/after interaction groups, zero browser script errors, and
a maximum available-viewport centering error of 0.0078125 CSS px. The neighboring
comparison passed eight intro/active layouts per pixel ratio (16 total).

The original Session 2 spacing regression also passed all 21 states, including
Lesson 5's intro and active views. The focused test additionally compares that
stylesheet's only other consumer, Lesson 5 Gawain 1, before and after at
1366, 1920, 2560, and 375 widths. Its intro and active geometry and selected
computed styles remain identical. The 17 relevant Django stream/admin-preview
tests passed; production JavaScript, backend logic, runtime data, and activity
content were not edited for this follow-up.

Evidence: `s2l4g2-refinement-dpr{1,2}.json`,
`s2l4g2-refinement-*-dpr{1,2}-{before,after}.png`,
`s2l4g2-refinement-django.log`, and `s2l4g2-neighbor-spacing.log` in the ignored
audit directory. `--neighbors-only` reruns the neighboring-page comparison while
retaining a complete, previously measured main-activity matrix.

## Large-monitor 125% sizing follow-up — October 21, 2026

The additional `prescribed_session123_large.css` layer applies only at viewport
widths of at least 2500px and heights of at least 1200px. Its fluid sizing unit
reaches 1.25px at 1440px height and tapers near the height breakpoint. Activity
cards, wheels, images, canvases, grids, reading text, buttons, badges, and progress
indicators use that unit. Existing regular desktop rules remain active below
the breakpoint. Root font sizing stays unchanged so legacy navigation scripts
cannot retain enlarged inline styles after resizing. No CSS `zoom` or whole-page
scale transform is used.

All 21 prescribed activities were rendered from their actual Django views and
templates, with local assets and in-memory API/media responses. The comparison
baseline is the immediately preceding UI with only this new CSS layer disabled.
It includes the earlier refinements documented above; it is not the original
Git HEAD layout.

- **518 baseline/current renders:** 37 activity states at 1366×768, 1440×900,
  1920×1080, 2560×1440, 3440×1440, 768×1024, and 375×812. States include intros,
  focused pictures, uppercase/lowercase handwriting, matching answers, shape and
  picture selections, syllable combination, and word reading.
- **Regular desktop preservation:** 96 primary-state screenshot pairs have
  identical measured rectangles and selected computed styles. 78 PNG pairs are
  pixel-identical; the maximum significant pixel difference in the others is
  0.031%, consistent with compositor/shadow noise. Additional answer/choice
  states also retain their regular desktop geometry and styles.
- **Large screens:** every card width grows exactly 25%, with a maximum center
  error of 0.0078125 CSS px. Component bounds fit inside their cards, desktop
  content fits vertically, and all seven viewports have no horizontal overflow.
  Video preserves its available-height cap instead of forcing a 25% height
  increase. Content-fitting card heights replace the previous stretch behavior.
- **Interaction checks:** 20 handwriting pointer/shape-drag cases pass, including
  both large widths. All 63 native Chrome zoom cases (75%, 125%, 150%) pass.
  The 22 uppercase/lowercase Ii guide alignment checks also pass after resizing,
  including the new large-screen dimensions. The 17 prescribed-stream/admin-preview
  Django tests pass.

Screenshot inspection covered all 21 entry screens at both large widths and
focused/handwriting/selection examples. The review caught and corrected a
content-box image overflow in Lesson 7 Gawain 1, an unintended button wrap in
Lesson 3 Gawain 1, a fixed-width instruction panel in Lesson 4 Gawain 1, and
remaining fixed-size captions/progress labels. Regression assertions now guard
against button wrapping and buttons overflowing their instruction panels.
Existing legacy script errors
on Lesson 3 Gawain 1, Lesson 3 Gawain 2, and Lesson 6 Gawain 1 are identical in
baseline/current runs; this change introduces no new browser script errors.

Evidence is in the ignored audit folder: `scale125-summary.json`,
`scale125-report-dpr1-{regular,small,large,extra}.json`,
`scale125-desktop-pixels.json`, `scale125-*-dpr1-{before,after}.png`, and
`scale125-contact-{2560,3440}-1.png` through `-6.png`.
`final-report.json.large_monitor_125` preserves the consolidated measurements
alongside the historical reports. The old focused tests' absolute large-screen
size assertions describe the preceding UI; this new proportional matrix is the
verification for the 125% follow-up.

Reproduce this follow-up after rendering fixtures:

```powershell
$env:PABASA_SCALE_LABEL='matrix'
node tools/test_prescribed_large_monitor_scale.cjs
$env:PABASA_SCALE_LABEL='extra'
node tools/test_prescribed_large_monitor_scale.cjs --extra
Remove-Item Env:PABASA_SCALE_LABEL
node tools/test_prescribed_responsive_interactions.cjs
node tools/test_prescribed_responsive_zoom.cjs
.\.venv\Scripts\python.exe pabasa_site/manage.py test pabasa_app.tests_prescribed_stream pabasa_app.tests_admin_prescribed_preview.AdminPrescribedPreviewTests
```

This follow-up edits CSS and stylesheet cache versions only. Existing activity
JavaScript and backend behavior are preserved. The local development server was
restarted and serves the current stylesheet with HTTP 200 and a matching SHA-256.
Provider accuracy, live student recordings, and production deployment are outside
these isolated layout checks.

## Reproduce

Run from the repository root with Python 3.13, the project environment, Node, installed Chrome, and Playwright Core. The Node tools use the same bundled Playwright fallback as the existing recording test.

```powershell
$env:PABASA_AUDIT_BASE='e555bc84d16d54f75be549161fe9404124bd7f3a'
.\.venv\Scripts\python.exe tools/audit_prescribed_responsive_render.py
node tools/audit_prescribed_responsive.cjs
node tools/test_prescribed_rhyme_responsive.cjs
node tools/test_prescribed_lesson3_gawain2_spacing.cjs
node tools/test_prescribed_lesson4_gawain1_spacing.cjs
node tools/test_prescribed_session2_spacing.cjs
node tools/test_prescribed_session2_lesson4_gawain2_refinement.cjs
node tools/test_prescribed_lesson7_centering.cjs
node tools/test_prescribed_lesson7_gawain2c_spacing.cjs
node tools/test_prescribed_lesson7_gawain2b_centering.cjs
node tools/test_prescribed_lesson7_gawain3_spacing.cjs
node tools/test_prescribed_lesson7_gawain4_spacing.cjs
node tools/test_prescribed_lesson7_gawain4a_responsive.cjs
node tools/test_prescribed_lesson7_gawain4a_responsive.cjs --refinement
node tools/test_prescribed_lesson8_gawain1_spacing.cjs
node tools/test_prescribed_lesson9_gawain1_spacing.cjs
node tools/test_prescribed_lesson9_gawain2_spacing.cjs
node tools/test_prescribed_lesson9_gawain3_spacing.cjs
node tools/test_prescribed_handwriting_guide.cjs
node tools/test_prescribed_responsive_interactions.cjs
node tools/test_prescribed_responsive_zoom.cjs
$env:PABASA_AUDIT_DPR='2'
node tools/test_prescribed_session2_lesson4_gawain2_refinement.cjs
node tools/test_prescribed_lesson4_gawain1_spacing.cjs
node tools/test_prescribed_lesson3_gawain2_spacing.cjs
node tools/test_prescribed_lesson7_gawain4_spacing.cjs
node tools/test_prescribed_lesson7_gawain4a_responsive.cjs
node tools/test_prescribed_lesson7_gawain4a_responsive.cjs --refinement
node tools/test_prescribed_lesson8_gawain1_spacing.cjs
node tools/test_prescribed_lesson9_gawain1_spacing.cjs
node tools/test_prescribed_lesson9_gawain2_spacing.cjs
node tools/test_prescribed_lesson9_gawain3_spacing.cjs
node tools/test_prescribed_handwriting_guide.cjs
node tools/test_prescribed_responsive_interactions.cjs
Remove-Item Env:PABASA_AUDIT_DPR
.\.venv\Scripts\python.exe pabasa_site/manage.py test pabasa_app.tests_lesson1_video.Lesson1VideoBrowserTests.test_playback_recording_and_failure_lifecycle
.\.venv\Scripts\python.exe pabasa_site/manage.py test pabasa_app.tests_prescribed_handwriting_case pabasa_app.tests_prescribed_stream pabasa_app.tests_admin_prescribed_preview
.\.venv\Scripts\python.exe pabasa_site/manage.py check
git diff --check
```

For deterministic pixel comparisons on a machine exhibiting GPU shadow noise,
set `$env:PABASA_AUDIT_SOFTWARE='1'` before running the layout audit. This selects
Chrome software rendering; it does not alter application styles or comparator
tolerances.

Screenshots, fixture HTML, and machine-readable reports are in the ignored `tmp/prescribed-responsive-audit/` directory. `final-report.json` combines the desktop/mobile measurements with the final large-layout pass. `contact-2560-1.png` through `contact-2560-3.png` and the corresponding `contact-3440-*` files show all 21 entry screens.

## Scope and limits

The layout harness loads local application assets and image aliases, holds narration while inspecting layout, dismisses introduction gates, and fulfills API requests in memory. Its screenshots show primary activity compositions; the separate recording regression exercises actual client lifecycle behavior. These checks do not establish live speech-provider accuracy or production deployment behavior. Native page zoom is applied through Chrome tabs.setZoom in an isolated profile, using the same zoom settings exposed by Chrome’s zoom controls.

The isolated baseline and current fixtures both emitted the same legacy-script syntax errors for Lesson 3 Gawain 2 and Lesson 6 Gawain 1. Their active compositions rendered. Those existing script errors were preserved because this task changes responsive layout and pointer geometry only.

The pre-existing local `pabasa_site/db.sqlite3` change was preserved. No live site, cloud service, or student account was modified.
