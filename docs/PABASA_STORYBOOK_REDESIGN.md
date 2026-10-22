# The PABASA Storybook

Implemented October 21, 2026. Local preview:
http://127.0.0.1:8767/what-is-pabasa/ . Not deployed to production.

## Concept and structure

The introduction now reads as a connected editorial story: a centered title
spread welcomes visitors with the existing Pip-and-learners illustration;
separate reading materials gather into a shared digital workspace; teacher and
student chapters follow in warm cream and sky blue. A community passage and a
short learning-loop closing lead to the existing signup and About pages.

The opening uses the supplied headline and description. The teacher chapter
explicitly preserves manual review and teacher judgment. The student chapter
describes guided practice without promising improved reading outcomes.
Printed materials are presented as valuable resources with organization work to
bring together. No capacity statistics, learner results, or outcome claims were
invented.

The five existing public navigation anchors remain available:
`platform-overview`, `platform-purpose`, `platform-tools`, `platform-audience`,
and `platform-process`. Two chapter anchors support the new contents navigation.
The shared header, footer, URLs, Andika font system, and backend are unchanged.

## Files and assets

Product files:

- `pabasa_site/pabasa_app/templates/pabasa_app/pabasa_info.html`
- `pabasa_site/pabasa_app/static/pabasa_app/pabasa_info.css`
- `pabasa_site/pabasa_app/static/pabasa_app/js/pabasa_storybook.js` (new)
- `pabasa_site/pabasa_app/static/pabasa_app/images/storybook/teacher-reading.webp` (new)

Existing Pip assets are reused unchanged: `hero1.webp`, `footer-mascot.webp`,
and `student-studio-bird.webp`. A new teacher-at-a-laptop illustration was
generated with the imagegen skill and optimized to a transparent 1024×1024 WebP
of 144,632 bytes. It contains no invented interface text or mascot replacement.
No further illustration assets are required.

The interface illustrations are HTML, not flattened screenshots or playable
activities. The teacher illustration references the existing Student Monitor,
with empty placeholders and an explicit no-student-data label. The student
illustration references Session 3, Lesson 7, Gawain 2C, Letrang Ii, using a model
letter and blank writing area. Preview controls are not focusable or styled as
functional buttons. Existing images retain their dimensions; below-fold imagery
loads lazily, while the opening illustration receives loading priority.

## Interactions and accessibility

- Chapter links use normal anchor navigation. No scroll interception, trapping,
  mandatory sequence, animation framework, or new dependency was introduced.
- The optional “Bring the pages together” button tidies the printed sheets and
  emphasizes the workspace using transform/shadow transitions. Its pressed state
  is exposed through `aria-pressed`; a polite live caption describes the result.
  Both versions of the story remain readable.
- A native `details` disclosure explains teacher review and works with Enter.
- One-time IntersectionObserver reveals use opacity and transform. Essential
  content is visible without JavaScript or without IntersectionObserver support.
- Story motion respects `prefers-reduced-motion`; the JavaScript reduced-motion
  branch and CSS overrides were checked. Native OS preference changes were not
  used during browser testing.
- Keyboard activation, toggle reset, disclosure state, and visible focus outlines
  were verified in the browser. There is one H1 and labeled chapter regions.
  Main paragraph text remains at least 16px at the tested widths.
- Sampled contrast ratios: body on cream 6.52:1, body on sky 6.10:1,
  eyebrow 6.22:1, large blue heading 4.17:1, primary button 11.34:1,
  and closing text 8.53:1. Decorative placeholder marks were not treated as text.

## Verification

Browser screenshots and layout measurements were reviewed for the requested
sizes. Tablet chapters become full-width spreads; mobile follows the deliberate
introduction → Pip → materials → teacher → student order.

| Requested width | Reported CSS viewport | Horizontal text overflow | Chapter copy/figure collisions |
|---:|---:|---|---|
| 320 | 320 | None | None |
| 375 | 375 | None | None |
| 430 | 430 | None | None |
| 768 | 768 | None | None |
| 1024 | 1024 | None | None |
| 1366 | 1367 | None | None |
| 1440 | 1440 | None | None |
| 1920 | 1920 | None | None |
| 2560 | 2560 | None | None |

The in-app browser's 80% host scale rounds the requested 1366px case to a
1367px CSS viewport. The other eight CSS viewport measurements match exactly.
Screenshots and measurement JSON are in `tmp/storybook-qa/`; a four-scene
overview is `tmp/storybook-qa/storybook-preview.jpg`.

Checks performed:

- `manage.py check`: passed.
- `node --check .../pabasa_storybook.js`: passed.
- `manage.py test pabasa_app.tests_static_images pabasa_app.tests_typography`:
  all 32 tests passed.
- Rendered public view: HTTP 200; one H1; seven unique destination anchors;
  all final static references resolve.
- Production JavaScript executed with normal/reduced-motion media mocks, with
  and without IntersectionObserver: toggle, ARIA states, and visibility fallback
  checks passed.
- Browser: original navigation and new chapter anchors, keyboard toggle and
  disclosure, all loaded illustrations, responsive geometry, and final scene
  screenshots checked. No browser console errors were reported in the final run.
- `git diff --check`: passed.

Testing used the in-app Chromium browser, not physical devices or a Safari/Firefox
matrix. No screen-reader session, Lighthouse run, acoustic feature test, or
performance benchmark is claimed. Explicit image dimensions and lightweight
enhancements reduce layout-shift risk; measured zero CLS is not claimed.

## Scope and deployment

Only this public introduction's template, styles, decorative JavaScript, and new
illustration were changed. CRLA, STT, scoring, student activities, authentication,
teacher review logic, shared navigation components, and database schema were not
modified. The existing local database modification was preserved.

The preview is local. No cloud image, revision, traffic, migration, or production
website was changed by this redesign.
