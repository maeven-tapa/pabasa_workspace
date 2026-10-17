# Session 6–7 prescribed activity fixes — October 17, 2026

The active renderer is `pabasa_site/pabasa_app/`. The learner view resolves
Gawain 1 (saved key `lesson-17-18-gawain-5`) to
`prescribed_picture_syllable_matching_page.html`, Gawain 6 to
`prescribed_oral_missing_syllable_page.html`, and Gawain 9 to
`prescribed_oral_picture_word_write_page.html`.

## Result

- Help, Mute, Pause now have the same visual, DOM, and keyboard order. Both
  the CSS order and the Session 6–7 DOM rearranger needed correction.
  Existing localized accessibility labels and actions remain functional.
- Gawain 1 finishes “Magaling! Tama ang pagbasa mo.” before rendering and
  announcing the next word. After the fifth word, it replays the existing
  `GAWAIN_5/01_activity_intro.mp3`. Cancelled queues cannot release stale prompts.
- Gawain 6 awaits written-answer feedback before showing the next oral item
  and playing “Basahin ang larawang ito: [word].” Local audio keys are
  normalized; intentional playback cancellation does not produce an audio error.
  Chrome emits `pause` before `ended` when a clip finishes naturally; the old
  player reported that successful playback as a failure. It now waits for the
  successful `ended` event in that case.
  Real playback failures leave BASAHIN and PAKINGGAN available. The extra
  retry-audio button and its creation/handler code were removed.
- Gawain 9 oral PAKINGGAN plays only the current word MP3, without the previous
  instruction and follow-up clips.

The shared controls script exits outside its explicit Session 6 keys and
Session 7 key prefix. The Session 7 stylesheet include remains conditional;
later-session layout and activity behavior were not changed.

## Existing MP3 selected for Gawain 6

`pabasa_site/pabasa_app/static/pabasa_app/prescribed/audio/SESSION_6/tama_magaling_ang_iyong_sagot.mp3`

This file existed before the changes and was retained without modification.
Local Faster Whisper small transcription, with Tagalog specified, returned
“Tama. Magaling ang iyong sagot.” Duration: 2.35 seconds. Chrome decoded and
played it to completion, including the actual Gawain 6 feedback-to-next-prompt
transition. SHA-256:
`0947B67E0FA0C225272C0087409466CF3954677B373138036CC11267D30A3435`.

Six new MP3s supply the exact requested wording using Google Filipino
`fil-PH-Wavenet-A` at normal speed. They were transcribed locally and played
in Chrome. No existing recordings were overwritten. The original Gawain 1
feedback said “iyong pagbasa”; the original Gawain 6 prompts said
“Ang salitang babasahin ay…”.

## Files changed

Application files, relative to `pabasa_site/pabasa_app/`:

- `static/pabasa_app/css/session67_reference.css`
- `static/pabasa_app/js/session67_ui.js`
- `templates/pabasa_app/includes/session6_prescribed_controls.html`
- `templates/pabasa_app/session8_11_prescribed_controls.html` (scoped asset versions)
- `templates/pabasa_app/prescribed_picture_syllable_matching_page.html`
- `templates/pabasa_app/prescribed_oral_missing_syllable_page.html`
- `templates/pabasa_app/prescribed_oral_picture_word_write_page.html`
- `tests_session67_activity_fixes.py`
- New browser test: `tools/tests_session67_requested_audio.py` (repository root).

New recordings under `static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/`:

- `GAWAIN_5/magaling_tama_ang_pagbasa_mo.mp3`
- `GAWAIN_6/basahin_ang_larawang_ito_pusa.mp3`
- `GAWAIN_6/basahin_ang_larawang_ito_pako.mp3`
- `GAWAIN_6/basahin_ang_larawang_ito_paruparo.mp3`
- `GAWAIN_6/basahin_ang_larawang_ito_rosas.mp3`
- `GAWAIN_6/basahin_ang_larawang_ito_kariton.mp3`

Other new files: `tools/test_session67_requested_audio.cjs` and this report.

## Validation and limits

Focused Django modules: `tests_session67_requested_audio`,
`tests_session67_activity_fixes`, `tests_session67_controls`,
`tests_prescribed_lesson16_activities`, and `tests_prescribed_lesson19_gawain2`.
All 39 tests passed in the final combined run (88.436 seconds).
The browser suite was then extended with two real-media Gawain 1 transitions
and rerun: all 24 browser scenarios passed (87.495 seconds), including playback
of all 18 explicitly checked MP3s.
The browser suite covers desktop/mobile controls, held feedback, all five
Gawain 1 transitions, the final matching introduction, Gawain 6 next-item and
completion transitions, pause/mute cancellation, failed audio, provider error
gating, all five Gawain 9 oral words, and later-session control isolation.
It also plays 18 actual MP3s through Chrome's media decoder. Desktop and
390-pixel mobile screenshots were visually inspected.

Reproduction from the repository root (with Node, Playwright, and Chrome
installed, and `NODE_PATH` pointing to Playwright if it is not installed locally):

```powershell
$env:DB_ENGINE = 'sqlite'
$env:SQLITE_PATH = ':memory:'
.\.venv\Scripts\python.exe pabasa_site/manage.py test `
  tools.tests_session67_requested_audio `
  pabasa_app.tests_session67_activity_fixes `
  pabasa_app.tests_session67_controls `
  pabasa_app.tests_prescribed_lesson16_activities `
  pabasa_app.tests_prescribed_lesson19_gawain2 --noinput --buffer
```

A broader 117-test run passed 114 tests and exposed three existing failures
in unchanged `tests_prescribed_workbook.py` / `prescribed_workbook.py`:

- Lesson 22 `Boo.` versus `bu` transcript expectation.
- Session 9 drawing validation expects Filipino text but receives English.
- Lesson 23 Gawain 5 rejects the old generic `reading` event as `Unknown action.`

Those Session 8/9 workflows were left unchanged. `manage.py check` passed.
Physical microphone capture and real STT providers were simulated, so they
still require a student/device acceptance check. Speech-content verification
was automated; no human listening/naturalness rating is claimed.

All test database work used an isolated in-memory SQLite database. Browser
progress existed only in the test process. No local database writes, migrations,
commits, pushes, or deployments were issued. The local database was already
modified at the start; its hash changed while a separate Django development
server was running, and that file was preserved without restoration.

Automatic approval review blocked removal of the temporary verification
packages. They remain in `%TEMP%/pabasa-audio-verification`; the existing cached
speech model was not changed. The temporary verification script and browser
screenshots also remain under `%TEMP%`.

## Test location update — October 17, 2026

The new Python browser test now lives in `tools/tests_session67_requested_audio.py`,
next to `tools/test_session67_requested_audio.cjs`. Run it directly with
`.\.venv\Scripts\python.exe tools/tests_session67_requested_audio.py`
with `NODE_PATH` pointing to Playwright. Existing tracked test modules retain
their locations. The scope audit found no uncommitted application behavior
changes outside Sessions 6 and 7. The pre-existing modified local database
was preserved.

Validation after relocation: 72 Django regressions passed, including Session 8
recording contracts. The relocated browser test passed all 28 scenarios,
including later-session control isolation and playback of 18 MP3s.
Django system checks and `git diff --check` passed. All newly added test files
are under `tools/`; no activity code required reverting.
