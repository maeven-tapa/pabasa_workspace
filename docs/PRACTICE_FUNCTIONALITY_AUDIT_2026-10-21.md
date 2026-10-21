# Practice Mode functionality audit — October 21, 2026

## Result and scope

The tested student flows in Free, Color, and Hunt work with the current layout.
No regression caused by the latest layout assets was found. This audit did not
change application code, scoring rules, speech routing, or navigation rules.

One existing content/scoring mismatch remains: Hunt accepts materials with fewer
than five paragraphs, but grades them against a fixed ten-point total. This is
described below rather than changing an accepted scoring rule during an audit.

The active routes use `pabasa_site/pabasa_app/views.py`, the reader templates
extending `practice_reader_base.html`, and the static `js/practice_reader.js`.
The separate root-level application directory is not the active reader.

## Comparison with past commits

Working tree was compared with HEAD `c8fd45e0` and these relevant reader versions:

| Commit | Date | Relevant change |
| --- | --- | --- |
| `d8a73484` | October 19 | Andika typography; most recent committed reader version |
| `783cf619` | October 19 | Recoverable Practice completion queue |
| `01f7a0f1` | October 11 | Material streaming speech capture |
| `8ae2c2d9` | September 22 | Speech diagnostics |

The Hunt classifier, finalized metrics, reward calculation, Free card progress,
next-level ordering, and Hunt/Color level completion functions are identical to
all four versions. The latest layout round adds presentation assets and removes
header/dot markup; it does not edit the activity script.

Earlier uncommitted interface edits do include functional safeguards. Browser
comparisons using historical reader source confirmed:

- At `d8a73484`, a Free upward wheel gesture advanced without recording an item
  outcome. Current code records `skipped`, consistently with the button. For
  Medium/Hard, the historical behavior could omit that card from the accuracy
  denominator even though it remained in the score denominator.
- At `d8a73484`, a Color double-click advanced from item 1 to item 3. Current
  code advances to item 2 once and briefly locks further advances.
- Current Color final-item skipping records the final outcome before results.
  Successful reads retain their existing automatic advancement.

## Browser results

These checks used the actual templates, current reader, layout assets, and save
queue in the in-app Chromium browser. A disposable localhost fixture supplied
synthetic materials and mocked microphone, audio, transcription, and award
responses. A read-only state display observed the reader's internal state;
successful scoring was reached through its real recording/result handlers.
No real student account, production service, or local application database was
used. This was functional testing, not a capacity benchmark.

| Check | Observed result |
| --- | --- |
| Successful reading in all modes | One outcome and one advance per read; Free/Color reached 100%; a full five-paragraph Hunt reached 10/10 and 100%. |
| Picture building | Color revealed one new layer per newly accepted item and completed normally. |
| Incorrect speech in all modes | Same item, zero correct reads, continuous retry retained. |
| Microphone denial in all modes | Same item, zero correct reads, listening stopped, controls restored. |
| Provider failure in all modes | Same item, no successful outcome, explicit restart available; no retry loop. |
| Permission pending | Controls locked; a double-click requested one microphone; Free swipe did not advance. |
| Speech processing | Controls locked; Free swipe did not advance; hint said skipping was paused. |
| Timeout recovery | Permission, transcription, and playback timeout paths restored controls without scoring. A stream granted after permission timeout was stopped. Timers were shortened only in the external test fixture. |
| Recorder interruption | Color recovered on the same item with zero correct reads and enabled controls. |
| Read Aloud failures in all modes | Controls recovered; no microphone start and no reading credit. Keyboard Space on the focused playback button did not start recording. |
| Playback while listening | Free discarded the old capture, played audio, and resumed listening on the same card; no transcription or reading credit from playback. |
| Explicit Stop | Capture stopped with no reading outcome. |
| Rapid Skip in all modes | A double-click advanced once. |
| All items skipped in all modes | Zero correct reads, all items marked skipped, one completion request. Hunt's existing one-star completion tier at zero points was retained. |
| Restart in all modes | Item 1, zero correct reads, cleared picture/points state, usable controls. |
| Offline save and reload | Free showed Retry Save, retained the original zero-score result, and submitted it once when reloaded online. |
| Missing next-level material | Next Level remained disabled with its existing explanation. |
| Material language | All five Hunt transcription requests retained the material's Filipino language. |

No JavaScript errors were observed in the final current-reader browser run.
Repeated Hunt award requests at completion retain their attempt and word keys;
backend and queue tests cover duplicate-credit prevention.

## Existing issues and testing limits

### Short Hunt materials use the five-item denominator

`HUNT_MAX_POINTS` is 10 and the backend completion award also divides points by
10. The admin form permits at least one paragraph rather than requiring five.
Three correct paragraphs therefore produce six points and 60%, with no skipped
items. A five-paragraph level produces 100% as expected.

This was reproduced using historical reader `783cf619`; the relevant calculation
also matches September's version. It predates the current interface changes.
Resolving it requires an explicit content/scoring decision: require five Hunt
items or revise the denominator for shorter levels. Neither rule was changed.

### Two unrelated Word Decoding language fixtures fail

The main Practice/provider run passed **104 Django tests**. An additional
three-test language/TTS run passed its Read Aloud voice test but failed both
`WordDecodingLanguageTests` tests:

- Page test: expected 200, received 302; it does not authenticate a student.
- Transcription test: expected 200, received 404. Its fixture uses
  `activity_slug='word_decoding'`, while the activity requires `word-decoding`.

This class and the application views are unchanged from HEAD. These routes belong
to the separate Word Decoding assessment, not the three Practice activities.
Their fixtures were left untouched. Combined Django count: **105 passed, 2 failed**.

Real OS microphone prompts, physical recording, live provider/audio services,
real network outages, physical touchscreen swipes, and screen-reader output were
not verified. Wheel input exercised Free's shared touch/wheel advancement helper.
The browser fixture used default Google routing; alternate provider handling was
covered by backend tests, not by real provider calls. Real classroom or cloud
reward behavior is not established by synthetic browser responses.

## Automated validation

Passed: Django system check, JavaScript syntax checks, and `git diff --check`.
The completion queue's **16 Node tests** passed, covering retry bounds, account
isolation, reload recovery, idempotency keys, and partial Hunt-save failures.

```powershell
.\.venv\Scripts\python.exe pabasa_site/manage.py check
.\.venv\Scripts\python.exe pabasa_site/manage.py test pabasa_app.tests.PracticeReaderMaterialTests pabasa_app.tests.PracticeProgressionTests pabasa_app.tests.HuntScoringRuleTests pabasa_app.tests.PracticeAccessControlTests pabasa_app.tests_practice_resilience pabasa_app.tests_practice_persistence pabasa_app.tests_practice_material_selection pabasa_app.tests_practice_material_visibility pabasa_app.tests_practice_debug pabasa_app.tests_material_stream pabasa_app.tests_chirp_stt pabasa_app.tests_knowlez_stt pabasa_app.tests_local_stt_fallback --noinput
node --test tools/test_practice_completion_queue.cjs
node --check pabasa_site/pabasa_app/static/pabasa_app/js/practice_reader.js
node --check pabasa_site/pabasa_app/static/pabasa_app/js/practice_material_layout.js
git diff --check
```

The additional language run used `ReadingMatcherTests.test_read_aloud_uses_filipino_voice_for_tagalog_locale`
and `WordDecodingLanguageTests` in `pabasa_app.tests`. Django runs emitted the
existing migration fixture's naive-datetime warning. No migrations were made.
