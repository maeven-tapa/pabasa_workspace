# Session 6, Lessons 17–18: Gawain 1 and Gawain 6

Verified locally on October 17, 2026. No commit, push, deployment, or audio
generation was performed.

## Active paths and scope

Django resolved the active app to `pabasa_site/pabasa_app/`, with these templates:

- Gawain 1, saved key `lesson-17-18-gawain-5`:
  `templates/pabasa_app/prescribed_picture_syllable_matching_page.html`.
- Gawain 6, saved key `lesson-17-18-gawain-6`:
  `templates/pabasa_app/prescribed_oral_missing_syllable_page.html`.

Both activities implement their reading and audio flow in inline JavaScript.
Their existing shared controls load `session6_prescribed_controls.js`,
`session6_intro_modal.js`, and `session67_ui.js`; those scripts were not edited.
The catalog has only one active activity for each of these template interactions.
The STT endpoint and narrowly scoped matching allowance are in `views.py`.

## Existing recordings verified

A local user-profile scan found 132 candidate audio paths containing feedback
keywords, representing 64 distinct file contents. Candidate audio was decoded
and transcribed with the already cached local faster-whisper model, without a
network speech service or synthesis. This runtime cannot directly hear audio;
content verification used local transcription plus actual Chrome playback.

Gawain 1 now reuses this existing recording, without modifying its bytes or
changing Gawain 7:

`static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_7/magaling_tama_ang_nabasa_mo_tts.mp3`

- Local transcript: **“Magaling! Tama ang pagbasa mo!”**
- Decoded duration: 2.586125 seconds.
- SHA-256: `4236dd35894a254acca41e4f6b7384fea2b140f44023ab2893f776ae99e5977a`.
- Other checked candidates included the shared “Tama ang iyong pagbasa” clips
  and the previously added Gawain 1 feedback recording.

Gawain 6 prompts now use the existing files below, in the original item order.
Their real filenames include `_tts`; no files without that suffix were invented.
Each local transcript identifies the intended word after the prompt about the
word to read. Every replacement played to completion in Chrome.

| Word | File in `static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_6/` | Decoded seconds |
| --- | --- | ---: |
| PUSA | `babasahin_pusa_tts.mp3` | 2.351 |
| PAKO | `babasahin_pako_tts.mp3` | 2.50775 |
| PARUPARO | `babasahin_paruparo_tts.mp3` | 3.0040625 |
| ROSAS | `babasahin_rosas_tts.mp3` | 3.0824375 |
| KARITON | `babasahin_kariton_tts.mp3` | 2.847375 |

## Matching and preserved behavior

Only Filipino `reading` requests with activity key `lesson-17-18-gawain-6`,
target PUSA, and the isolated normalized transcript USA receive the allowance.
The provider's raw transcript is retained. The existing matcher grades PUSA,
and the existing browser success path handles the written phase. No scoring,
progress, retry, provider-selection, or recording code was replaced.

## Files changed by this request

- `pabasa_site/pabasa_app/templates/pabasa_app/prescribed_picture_syllable_matching_page.html`
- `pabasa_site/pabasa_app/templates/pabasa_app/prescribed_oral_missing_syllable_page.html`
- `pabasa_site/pabasa_app/views.py`
- `pabasa_site/pabasa_app/tests_basahin_reading_verdict.py`
- `pabasa_site/pabasa_app/tests_session67_activity_fixes.py`
- `tools/tests_session67_requested_audio.py`
- `tools/test_session67_requested_audio.cjs`
- This report.

Removed only these five files from the Gawain 6 audio folder, after checking
that no other activity references them and switching this activity's mappings:

- `basahin_ang_larawang_ito_pusa.mp3`
- `basahin_ang_larawang_ito_pako.mp3`
- `basahin_ang_larawang_ito_paruparo.mp3`
- `basahin_ang_larawang_ito_rosas.mp3`
- `basahin_ang_larawang_ito_kariton.mp3`

Recoverable copies are outside the repository in
`C:/Users/Amiel/AppData/Local/Temp/pabasa-s6-request-n5bk1iyx/removed-audio/`.
The older `SESSION67_ACTIVITY_AUDIO_FIXES.md` retains its historical descriptions.
The pre-existing untracked Gawain 1 feedback MP3 was retained.

## Checks and results

Python 3.13.15 from the repository virtual environment was used.

- **37 tests passed:** `tests_basahin_reading_verdict`, `tests_prescribed_stream`,
  the Gawain 1 saved-reading-before-matching workflow test from
  `tests_prescribed_lesson16_activities`, and
  `tests_admin_prescribed_preview.Session6Gawain6AdminPreviewTests`.
  Database-dependent tests used explicitly isolated in-memory SQLite.
- **9 tests passed:** `tests_session67_activity_fixes` and
  `tests_session67_controls`. This includes `node --check` on rendered inline
  JavaScript from both edited templates and the existing shared scripts.
- **1 browser test passed:** `tests_session67_requested_audio`, containing
  **25 Chrome scenarios** and **18 real MP3 playbacks to completion**.
  Coverage includes all five Gawain 1 feedback transitions, final matching
  introduction, Gawain 6 prompt order, backend USA verdicts in the browser,
  wrong written answers, three retries, provider failure, normal other-word
  matching, pause/mute cancellation, and completion.
- All four changed Python files compiled successfully; the changed browser
  test script passed `node --check`; targeted `git diff --check` passed.
- Before/after SHA-256 checks confirmed all unrelated pre-existing local
  changes and the runtime database remained unchanged. No existing audio bytes
  were modified. Browser speech capture/provider calls and progress storage were
  mocked; MP3 decoding and playback used the actual local files.

Total: **47 focused Django tests passed**. Changes remain uncommitted and unpushed.
