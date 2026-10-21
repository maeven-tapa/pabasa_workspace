# Session 6 and 7 requested activity fixes — October 21, 2026

All affected student URLs use
`/dashboard/assessment/activity/prescribed/<activity_key>/` and resolve through
`prescribed_activity_page` in the active `pabasa_site/pabasa_app/views.py`.
No URL, view, model, migration, answer, provider, or scoring changes were made.

## Active route and asset map

Template paths below are relative to
`pabasa_site/pabasa_app/templates/pabasa_app/`; asset paths are relative to
`pabasa_site/pabasa_app/static/pabasa_app/`.

| Activity key | Active template | Activity-specific CSS / JavaScript |
| --- | --- | --- |
| `lesson-16-gawain-1` | `prescribed_missing_syllable_page.html` | Inline CSS and JS |
| `lesson-16-gawain-2` | `prescribed_missing_syllable_page.html` | Inline CSS and JS |
| `lesson-16-gawain-3` | `lesson_16_gawain_3_page.html` | `css/lesson_16_gawain_3.css`, `js/lesson_16_gawain_3.js` |
| `session-6-lesson-16-gawain-4` | `prescribed_picture_word_write_page.html` | Inline CSS and JS |
| `lesson-17-18-gawain-5` | `prescribed_picture_syllable_matching_page.html` | Inline CSS and JS |
| `lesson-17-18-gawain-6` | `prescribed_oral_missing_syllable_page.html` | Inline CSS and JS |
| `session-7-lesson-19-gawain-2` | `session7_missing_syllable_page.html` | Inline CSS and JS |
| `session-7-lesson-19-gawain-3` | `session7_circle_word_page.html` | Inline CSS and JS |
| `session-7-lesson-19-gawain-4` | `session7_letter_ordering_page.html` | Inline CSS/JS and `css/session7_l19_g4_refinement.css` |
| `session-7-lesson-20-21-gawain-2` | `prescribed_cluster_syllabification_page.html` | Inline CSS and JS |

Lessons 17–18 display Gawain 1 at the existing `lesson-17-18-gawain-5` key.
There is no separate active `lesson-17-18-gawain-1` catalog entry. Its stored
identity, attempt counters, guided listening cycle, and audio paths are retained.

Every route above also loads `css/session67_reference.css` and
`js/session67_ui.js` through the Session 6 or Session 7 controls include.
The shared reading stack comes from `basahin_script.html`, including
`js/basahin_button.js`, `js/basahin.js`, and `js/crla_speech_stream.js`.
Those reading-stack files were inspected and left unchanged. New layout rules
require an exact `data-session67-layout` key set only for the ten routes above.

## Files changed for this request

- `pabasa_site/pabasa_app/static/pabasa_app/css/session67_reference.css`
- `pabasa_site/pabasa_app/static/pabasa_app/js/session67_ui.js`
- `pabasa_site/pabasa_app/templates/pabasa_app/includes/session6_prescribed_controls.html`
- `pabasa_site/pabasa_app/templates/pabasa_app/session8_11_prescribed_controls.html`
- `pabasa_site/pabasa_app/templates/pabasa_app/prescribed_missing_syllable_page.html`
- `pabasa_site/pabasa_app/templates/pabasa_app/prescribed_oral_missing_syllable_page.html`
- `pabasa_site/pabasa_app/templates/pabasa_app/prescribed_picture_syllable_matching_page.html`
- `pabasa_site/pabasa_app/templates/pabasa_app/session7_circle_word_page.html`
- `tools/test_session67_requested_layout.cjs`
- `docs/SESSION67_REQUESTED_ACTIVITY_FIXES.md`

Pre-existing local edits, including other Session 6–7 work and the local SQLite
file, were preserved. The two controls includes change only the cache versions
of the Session 6–7 layout assets.

## Verification

Use the repository's Python 3.13 virtual environment. The system Python lacks
the application's existing `av` dependency.

- `python pabasa_site/manage.py check`: passed in the virtual environment.
- 51 Django tests passed across `tests_session67_controls`,
  `tests_session67_activity_fixes`, `tests_session67_navigation`,
  `tests_prescribed_lesson16_activities`, `tests_prescribed_lesson19_gawain2`,
  `tests_prescribed_lesson19_gawain3_restart`,
  `tests_prescribed_lesson19_gawain4`, `tests_prescribed_lesson20_21_cluster`,
  and `tests_prescribed_reading_attempts`. These include rendered inline and
  external JavaScript syntax checks.
- `node tools/test_session67_requested_layout.cjs` renders the real Django
  templates and loads local assets in Chrome at 1366×900, 1366×768, 960×640,
  768×600, and 390×844. It checks reading/writing layouts, introductions,
  centered `dagat` feedback, clipping, scrolling, overlap with floating tools,
  the removed labels, evaluation/feedback locks, and all nine scored words.
  The final full run passed 109 checks: 95 layout states plus 14 speech,
  sequence, incorrect-feedback, and resize checks. All 95 states fit without
  horizontal/vertical scrolling, clipped content, or overlap with floating tools.
  After the final example-font adjustment, all 24 focused Lessons 20–21 and
  speech/sequence/feedback/resize checks passed again.
- 38 desktop card comparisons against the pre-edit styles/scripts passed.
  The largest bounding-box difference was 0.03125 CSS pixels (render rounding).
  Lesson 19 Gawain 2 measures its original desktop card height on rendering and
  resizing, then fits the larger inner content within that existing height.
- The final focused Django rerun passed all 10 tests in the three Session 6–7
  modules above. `node --check` and `git diff --check` also passed.
- The retry regression uses the real `basahin_button.js`. It holds evaluation
  and feedback separately, then exercises the end event of the actual local
  incorrect-feedback MP3. The first two failures restore enabled Basahin;
  the third retains the existing guided-listening action.
- The pre-existing `test_session67_layout_navigation.cjs` passed 54 checks
  during this work, covering navigation, progress-save draining, and speech
  success/failure transitions.

Chrome screenshots and measurements are generated in the system temporary
directory under `pabasa-session67-requested-layout`. No real accounts,
recordings, or student data are created by this browser harness. Microphone
capture, provider responses, and progress saves are synthetic; the actual
local feedback audio is played for the retry check.

The referenced screenshots were not attached to the available conversation.
The viewport matrix above is an explicit approximation, not a comparison with
the missing reference screenshots. Live speech-provider and physical-microphone
verification remain outside the local synthetic test coverage.
