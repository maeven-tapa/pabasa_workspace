# Lessons 26–31 activity audit — October 17, 2026

## Fix verification

The findings below were addressed in the local application. At the user's
subsequent request, Missing Letter's learner-facing correct/error status was
removed; diagnostic errors remain in its debug panel. The
shared Pause backdrop resumes the activity; dismissing Restart returns to Pause.
Word Identifying and Trace & Say use the existing cancellable audio player,
ignore cancelled continuations, and wait for pending saves before restart or
navigation. Trace & Say releases cancelled microphone streams and preserves
unfinished tracing on resume. Returning through browser history reloads saved
state instead of restoring cancelled controls.

Verification: 108 relevant Django cases passed (107 on the combined run, followed
by the remaining case after updating its obsolete no-op-adapter assertion).
`tools/test_lesson28_29_activity_recovery.cjs` passed 24 new browser scenarios,
including desktop/mobile error visibility, repeated pause/resume, delayed audio
and saves, restart, mute, Help, microphone cleanup, tracing preservation, and
browser-history recovery. Existing browser suites passed for Session 6/7 (61
scenarios), Lesson 26 sentence highlighting, Lesson 27 (22 checks), Lesson 31
Activities 1/4 (48 scenarios), and shared sentence continuation (28 recovery,
11 playback, and 42 sentence/viewport cases, plus provider/microphone checks).
Desktop and mobile screenshots of the visible error were also inspected.

These changes have not been deployed; live providers were not called.

Lesson 28 follow-up: Word Identifying now starts its introduction immediately,
prepares the target concurrently, and plays the target word after the intro ends
on the same audio element. Choices remain disabled through both clips. Natural
end-of-media pause events are distinguished from cancellation. The updated
browser suite passed 27 scenarios, including real Chrome playback of the bundled
intro and first-word MP3s; the 39 relevant Lesson 28/catalog Django tests passed.

Answer-flow follow-up: the startup fix had left answer feedback on the older
single-clip path. Native audio's normal end-of-media pause was treated as
cancellation, leaving the rendered controls disabled and skipping the following
word. A real-audio regression reproduced the freeze before correction. Activity
2 now uses ordered sequences for feedback and Listen as well: wrong answers
repeat the current target after retry feedback; correct answers play the next
target after correct feedback; the final answer plays completion feedback only.
Real Chrome playback now exercises wrong/correct choices across all five rows
through completion, alongside cancellation/save-recovery tests. Scoring and the
server's choice of target word are unchanged.
The expanded suite passed 28 browser scenarios, including retrying a saved
second-choice target and real audio through all five rows; all 39 relevant
Django tests passed. Controls disable as soon as an answer is submitted and
unlock after its feedback/target sequence ends.

Conflict-audit follow-up: Help dismissal with Escape now emits the same resume
event as the close button. Trace & Say clears its capture controller when
capture finishes, so muting during upload does not invalidate the saved-phase
render or strand the busy flag. Active capture still cancels on mute. The
expanded suite passed 33 browser scenarios, including idle/recording Help
dismissal, muted uploads, retry after upload completion, and recovery from a
failed progress save while muted. The 59 relevant Lesson 29/catalog Django
tests passed.

## Scope

Reviewed the 15 prescribed activities in the active `pabasa_site/pabasa_app/`
application, their catalog, templates, browser scripts, and relevant Django tests.
Browser reproductions used actual local templates and scripts with controlled
audio, microphone, and HTTP responses. No production accounts, real student
records, external speech providers, or cloud services were exercised.

The initial audit did not change application code. The existing modified
`pabasa_site/db.sqlite3` was preserved throughout the audit and fixes; Django
tests used an isolated in-memory SQLite database.

## Confirmed findings

### 1. Lesson 28, Activity 2: pausing audio blocks answers and restart (P2)

Reproduce: Start Word Identifying, let the introduction and first word finish,
click Listen, open Pause while the word is playing, then click Resume.

Observed: Listen remains disabled and neither choice is enabled. Opening Pause
again and confirming Restart sends no reset request. Reloading is needed to
recover.

`prescribed_word_identifying_lesson28_activity2.js:83` waits for audio `ended`
or `error`, while `stopAudio()` at line 148 only pauses it. The promise never
settles, so `playWord()` keeps `busy = true`. Resume at line 195 does not clear
that state, and reset returns early while busy.

Suggested correction: settle cancelled playback, invalidate its continuation,
and restore controls on resume. Allow restart to cancel playback and perform
the reset.

### 2. Lesson 29, Activity 3: pausing Listen leaves recording unresponsive (P2)

Reproduce: Start Trace & Say, click Listen, open Pause during playback, then
click Resume. Try Listen and Record my sound.

Observed: both controls accept clicks but perform no work. The narration
request count stays unchanged and no microphone call occurs.

`prescribed_trace_say_lesson29_activity3.js:23` resolves playback on `ended`
or `error` only. The Session 13 pause handler dispatches `pagehide`, whose
activity handler pauses the audio. The unfinished `speak()` keeps `busy = true`;
the activity has no resume handler that recovers this operation.

Suggested correction: use cancellable playback and handle pause/resume explicitly.

### 3. Lesson 28, both activities: clicking the Pause backdrop does not resume (P2)

Reproduce: open Pause, then click outside its card.

Observed: the dialog closes but the activity remains paused. Activity 1's Read
does not call speech capture; Activity 2's choices remain disabled. Reopening
Pause and using its Resume button recovers this case when no audio is in flight.

`prescribed_controls.js:176` closes the pause modal on a backdrop click without
calling `config.adapter.resume()`. Both Lesson 28 adapters retain their paused
flag. This shared handler is also used by other activities; the reproduction
scope here is the two Lesson 28 activities.

Suggested correction: resume when dismissing Pause, or keep the backdrop from
dismissing it. Validate other callers of the shared control before changing it.

### 4. Lesson 28, Activity 1: errors are omitted from the learner interface (P2)

Reproduce: Start Missing Letter, click Read, and have microphone capture reject
with a permission error.

Observed: the visible activity contains no error or recovery instructions. The
debug panel is hidden by default, and rendering also clears its error field.

`prescribed_missing_letter_lesson28_activity1.js:38` accepts `message` and `kind`,
but its markup at line 45 displays neither. Microphone, provider, save, and audio
errors passed to `render()` therefore have no visible feedback.

Suggested correction: render an accessible status/error message and retain the
diagnostic error until a new attempt starts.

## Validation

- 89 tests passed across `tests_prescribed_lesson26_word_search`,
  `tests_prescribed_lesson26_sentence_continuation`,
  `tests_prescribed_lesson27_rhyming_verses`,
  `tests_prescribed_lesson28_word_identifying`,
  `tests_prescribed_lesson29_oral_blank`, `tests_prescribed_lesson29_spot_word`,
  `tests_lesson29_trace_say`, and `tests_prescribed_lesson30_match_it`.
- All 13 tests in `tests_prescribed_sentence_reading` passed in the additional
  run: **102 lesson-specific Django tests passed in total**.
- Django system checks reported no issues.
- `tools/test_lesson26_sentence_highlighting.cjs` passed its desktop/mobile,
  highlighting, continuation, save recovery, audio, and microphone checks.
- `tools/test_lesson27_word_highlighting.cjs` passed 22 checks.
- `tools/test_lesson31_activity_controls.cjs` passed 48 scenarios for Activities
  1 and 4.
- `tools/test_prescribed_sentence_reading.cjs` passed 28 save/recovery scenarios,
  11 Lesson 31 Activity 2 playback scenarios, and 42 sentence/viewport cases,
  plus its additional provider and microphone lifecycle checks.
- Separate controlled browser reproductions confirmed all four findings above,
  with no JavaScript runtime errors in those fixtures.

## Test maintenance and limits

`tools/test_lesson29_oral_blank.cjs` timed out waiting for Read because its old
fixture loads only the activity script. The activity now requires
`window.PrescribedSentenceReading`, which that fixture does not provide. This is
a fixture failure, not evidence that the real page cannot render; the newer
shared-sentence browser suite exercises the actual template with that helper.

The broader `tests_activity_recovery` run had five failures outside these
prescribed lessons: two old PNG-path assertions now receive optimized WebP/AVIF
paths, two custom-material completion/progress tests receive HTTP 403, and a
custom syllable-combination result test receives HTTP 400. These were not
changed or diagnosed further in this lesson audit.

These results establish local behavior with controlled provider responses. They
do not establish the deployed site's behavior, real microphone recognition
accuracy, or live speech-provider availability.
