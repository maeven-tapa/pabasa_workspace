# About PABASA: four-chapter redesign

Implemented locally on October 22, 2026 for `http://127.0.0.1:8000/about/`.
No deployment, migration, or cloud operation was performed.

## Scope and hero preservation

The approved hero is the complete `section#about-overview` immediately before
`#project-origin`. Its original markup is unchanged, including the photograph,
Pip detail, labels, copy, classes, inline styles, and layout. The existing
IntersectionObserver that controls its fade-in is retained unchanged.
`about.css` is unchanged. New styles and scripts target only `.pabasa-journal`
and its descendants. There is no added introductory section.

The four original navigation targets remain in their original order. Homepage,
What Is PABASA, assessment/STT/scoring/activity behavior, authentication, models,
APIs, and unrelated templates were not edited. The pre-existing local database
modification was left in place.

## Previous and new layouts

| Chapter | Previous layout | Implemented layout |
| --- | --- | --- |
| Where It All Began | Three stock-photo cards and long article dialogs | An illustrated research desk with ruled observation paper, an annotated planning sheet, and a taped existing interface print. Artifacts respond to hover and keyboard focus. Mobile uses a vertical sequence. |
| The Decisions Behind the Design | Three separate principle cards | An asymmetric navy design lab with a vertical principle index, active yellow selection, large authentic UI capture, annotations, challenge, and design response. Mobile uses a horizontal index. |
| The Road to Salawag | Conventional four-step timeline and oversized support sidebar | An alternating editorial journey connected by a winding SVG route, with four distinct visual artifacts and a compact project identification panel. Mobile uses a continuous vertical route. |
| The People Behind PABASA | Small repeated portrait cards with dark gradient overlays | A spacious numbered yearbook with larger portraits, captions, and biography drawers. Three columns on desktop, two on tablet and wider mobile, one below 430px. |

## Content and assets

- Used the supplied chapter headings, eyebrows, three origin statements, three
  design challenges/responses, and four milestone descriptions.
- Removed the superseded article dialogs and repeated promotional/feature copy.
- Preserved all six portraits, full existing names, roles, contribution
  descriptions, both existing sets of biography/personal-message text, contact
  links, and contribution tags. The extra existing perspective is available in
  an expandable biography disclosure.
- Kept “Built by students. Made for readers.” subordinate to the team heading.
- Reused `images/screenshot.avif`, all six `images/pabasa_team/*.png` portraits,
  and `images/overall_image/7.png` for a different classroom context. The hero's
  `overall_image/1.png` is not repeated.
- Added three WebP captures of existing UI: Phrase Reading selection, Phrase
  Reading guidance, and the empty Student Monitor. These use public sample text
  or no records. No student accounts, sessions, scores, or recordings were used.
  See the capture provenance in `static/pabasa_app/images/about/README.md`.
- Paper notes and the wireframe are new HTML/CSS illustrations, explicitly
  labeled as summaries or retrospective schematics. They are not represented
  as original research documents. The development artifact is the existing
  Django About view excerpt, rather than invented development evidence.
- The compact identification panel contains the institution, degree program,
  project/focus, and school specified in the brief and existing page context.

## Files

- Modified `pabasa_site/pabasa_app/templates/pabasa_app/about.html`: retains the
  hero and its observer, includes the chapters, and loads their isolated assets.
- Added `pabasa_site/pabasa_app/templates/pabasa_app/about_chapters.html`.
- Added `pabasa_site/pabasa_app/static/pabasa_app/about_chapters.css`.
- Added `pabasa_site/pabasa_app/static/pabasa_app/js/about_chapters.js`.
- Added three WebP images and their README under
  `pabasa_site/pabasa_app/static/pabasa_app/images/about/`.
- Added this implementation and QA report.

Temporary capture HTML was removed. No dependency was added.

## Interaction and accessibility verification

Performed in the connected in-app browser:

- Selected Clarity, Usefulness, and Confidence and checked the active ARIA state,
  visible panel, heading, screenshot source, and loaded image.
- Tested desktop Up/Down, Home, and End navigation, and mobile Left/Right
  navigation. Tab orientation changes with the mobile layout.
- Opened all six biographies. Checked their titles, image loading, initial close
  focus, Escape dismissal, and return of focus to the originating portrait.
- Tested the explicit forward/backward Tab loop. This was added after finding
  that native dialog behavior alone allowed transient focus on the body.
- Tested the drawer at 320px, 375px, 768px, and 1440px during the QA iterations.
  At 320px, expanded the contribution disclosure and confirmed the sticky close
  control remains visible while the dialog scrolls. No drawer horizontal
  overflow was observed.
- Inspected the accessibility tree for chapter headings, labeled images,
  tab relationships, dialog titles, close controls, and disclosures.
- Used the retained desktop section anchors and the mobile navigation toggle
  and Principles anchor. The existing mobile menu remains open until toggled
  closed; its behavior was not changed.
- Confirmed all 17 image elements in the chapters/dialogs loaded after visiting
  their views. No browser console warnings/errors were returned during the
  inspected run.
- Confirmed computed Andika font families on chapter headings, body text, and
  principle controls. Code alone uses a code font.

The lab progressively enhances semantic content: all three panels are present
and readable before its script runs. Focus states, nonessential transitions,
and a scoped `prefers-reduced-motion: reduce` rule are implemented. Reduced-motion
preference emulation and a manual screen-reader session were not performed.

## Responsive and hero regression verification

Browser CSS widths checked: **320, 375, 430, 768, 1024, 1440, 1920, 2560**.
The browser's existing 80% application scale rounds the requested 1366 setting
to **1367 CSS pixels**. Both **1365 and 1367** were checked, with no document
overflow. Exact 1366px is not claimed as tested.

At the nine primary samples, recorded document width, chapter layouts, visible
element bounds, and screenshot evidence. No horizontal overflow was found.
Inspected responsive chapter contact sheets and actual mobile/desktop views.
Images preserve their proportions; portraits share the same 4:5 display ratio.
Some full-page exports include the sticky navigation at its current scroll
position or unpainted compositor regions. Viewport captures and DOM bounds were
also used to distinguish export artifacts from layout defects.

Before editing, captured the hero at matching viewport settings and saved its
markup, every descendant's bounding rectangle, and computed styles. Compared
these with the implementation afterward:

- Hero markup: identical at every primary sample.
- Hero and descendant geometry: identical at every primary sample.
- Computed styles: identical at every primary sample.
- Captured hero image regions: identical pixel values at every primary sample.
  The browser exported extra pixels from the next chapter; those pixels were
  excluded from the image comparison. The complete hero DOM/style/geometry
  comparisons are independent of that crop.

Local screenshot and JSON evidence is stored outside the repository at:

`C:/Users/iamdo/.codex/visualizations/2026/10/22/01a16113-8044-7d92-beda-6242b47e3b4d/about-qa/`

Useful evidence files: `hero-regression-comparison.jpg`,
`hero-image-comparison.json`, `hero-baseline.json`, `hero-after.json`,
`responsive-checks.json`, `interaction-checks.json`, `biography-checks.json`,
`chapter-01-responsive-contact.jpg` through `chapter-04-responsive-contact.jpg`,
and `final-biography-320.jpg`.

## Checks and limitations

- `python pabasa_site/manage.py check`: passed, no issues.
- `python pabasa_site/manage.py test pabasa_app.tests_static_images --verbosity 1`:
  **25 tests passed**. These are the relevant existing static asset tests;
  interaction behavior was verified in the browser as described above.
- `git diff --check`: passed; Git reports only the repository's normal CRLF/LF
  normalization notice for the edited template.
- A content audit confirmed all six contribution descriptions, both sets of
  existing biography text, and six dialogs were preserved.
- No model, migration, authorization, assessment, or backend change required a
  schema migration or assessment test suite run.

Historical original research notes, planning wireframes, and development
screenshots were not found among the available assets. The labeled retrospective
illustrations and actual source excerpt are used in their place. Interface
captures are representative template renders, not authenticated classroom
session evidence. Browser verification used the connected in-app browser;
cross-browser/device hardware testing remains unperformed.

**Deployment status: local implementation only. Not deployed.**
