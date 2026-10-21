# Session 1, Lesson 3, Gawain 1: speech validation audit

Audit date: October 21, 2026 (Asia/Manila). Changes are local, not deployed.

## A. Confirmed root cause

The application accepted numeric meaning in place of the spoken Filipino word.
This is a reproducible server-side validation defect, not merely a theory about
the speech provider.

`pabasa_site/pabasa_app/reading_stt.py` contains a shared `NUMBER_WORDS` map:
English `eight` maps to `8`, and generated Filipino entries map `walo` to `8`.
Likewise, `three` and `tatlo` both map to `3`.
`ReadingMatcher.words_match()` calls `number_words_match()` whenever
`strict_rhyme` is false. That comparison uses the numeric values without checking
the language of the two words. The generic matcher deliberately supports numeric
reading elsewhere, including numeric-target tests.

Before this fix, the activity submitted `target_text`, `language=Filipino`, and
`mode=reading`, but no `prescribed_activity_key` or exact-word policy. The endpoint
only enabled `strict_rhyme` for `crla_rhymes=1`; that flag was also absent.
Consequently, a Filipino recognition configuration did not prevent the shared
validator from accepting English number words.

The endpoint then rewrote an accepted one-word reading's `transcript` to
`target_text`. This obscured the mismatch in the processed result, although
`raw_transcript` retained the provider text. The activity advanced its word index
when `success` and `complete` were true.

### Reproduction before production edits

The real `reading_transcribe_api()` was called with synthetic uploaded audio;
only authentication/access and provider I/O were mocked. No alternative grader
was substituted.

| Target | Provider transcript | Old complete | Old returned transcript |
|---|---|---|---|
| WALO | eight | true | WALO |
| TATLO | three | true | TATLO |
| BATA | ang bata | true | BATA |
| WALO, supplied completed syllable index | wrong | true | WALO |
| TATLO, prior syllable context `tat` | lo | true | TATLO |

These last three cases establish additional generic-matcher behavior that a
fresh, isolated word-reading attempt must not inherit.

### Read-only operational corroboration

Cloud Run logs were queried from October 21, 2026, 00:00 Manila onward, using a
500-record cap per query. Only aggregate classifications were printed; no student
identifiers, recordings, or complete learner transcripts were exported.

The shared context and final-result log markers corroborated four `eight` to
`WALO` rewrites and three `three` to `TATLO` rewrites on revision
`pabasa-01416-zoh`. They are request counts, not distinct-learner counts. The logs
corroborate the transcript rewrite; the complete/correctness result was reproduced
directly against local production code. These aggregates do not identify which
student made a request or prove the historical provider selection per request.

At the service-state check, 100% of traffic pointed to `pabasa-01390-vpm`, a
different revision from the observed log records. This audit did not change
images, revisions, traffic, secrets, accounts, or the database.

## B. Actual recognition and validation flow

1. The authoritative template is
   `pabasa_site/pabasa_app/templates/pabasa_app/lesson_3_gawain_1_page.html`.
   Its `pairs` array contains `{a:'WALO',b:'TATLO',yes:true}`. `words()[wi]`
   supplies the expected word. No English translations are present in this array.
2. `record()` opens the microphone through `Basahin.openMicrophone()` and records
   through `Basahin.capture()` in `static/pabasa_app/js/basahin.js`.
   Capture uses MediaRecorder, voice-activity detection, and silence completion.
   A detected voice is not itself a correctness decision. Tracks are stopped and
   capture resources are cleaned up.
3. The clip and target are submitted to `POST /api/reading/transcribe/`, routed to
   `reading_transcribe_api()` and `_reading_transcribe_response()` in `views.py`.
   Optional `Basahin.attachStreamResult()` attaches a signed, flushed Google
   streaming result to the same grading request.
4. `language_code_for('Filipino', 'reading')` returns `fil-PH`. Google defaults
   this path to Chirp 3, with `language_codes=['fil-PH']`, no phrase boosting, and
   no automatic fallback for Filipino clips. `AutoDetectDecodingConfig` detects
   audio encoding, not language. Explicit model selection is preserved.
   The selectable Knowlez adapter sends `language='tl'`. Google streaming also
   configures the requested language explicitly. No translation API is called by
   these activity paths.
5. Google adapters consume the first recognition alternative from each result;
   they do not search alternatives for a target match. Word confidence metadata
   does not decide correctness here. Signed stream results validate the login,
   activity, provider/language constraints, and expiration before grading.
6. Previously, generic normalization, target-aware syllable stitching, token
   scanning, and `analyze_reading()` supplied the reading verdict. Number-value
   equivalence was the confirmed cause of the reported false positives.
7. Now, identified Lesson 3 Gawain 1 requests use
   `analyze_literal_word_reading()` against the complete raw transcript. A fresh
   matcher supplies the usual response fields, but generic equivalence matching
   is never called to decide correctness. Prior indices/context cannot complete
   this word. Raw and processed transcripts remain the provider's text.
8. The client requires a successful HTTP response, `success=true`,
   `complete=true`, and a response target equal to the captured word. Its existing
   generation check discards delayed responses after a render/state change.
   Only then does `wi` advance.
9. Rhyme classification is separate. Answer controls unlock after two accepted
   readings. `answer()` checks the pair's unchanged `yes` value; it now also
   refuses to advance while `wi<2`. Pair completion saves `current_index`,
   `completed_items`, and `correct_items` as completed pairs out of six through
   `lesson_3_activity_progress()`. The final Done action marks activity completion.

### Important presentation detail

The target words exist in the data, image alt text, and generated `<strong>`
labels. Existing CSS (`#game .pairs .word strong{display:none!important}`) hides
the written labels. The browser currently emphasizes pictures of numerals 8
and 3 and prompts learners to name them. Thus the actual screen does not visibly
spell WALO/TATLO in this layout. This may explain why a learner chooses English,
but it does not justify accepting an English reading. The requested UI and
instruction/narration behavior were preserved.

## C. Scope and investigative findings

All twelve words used the same generic reading gate before the fix. The direct
English-number equivalence defect applies specifically to WALO/TATLO among these
twelve targets; the other ten English translations did not reproduce that
particular acceptance. Extra-token and segmented near-match behavior could
affect other targets. The new activity-specific policy covers every pair:

| Pair | Authoritative words | Existing rhyme answer | Regression result |
|---|---|---|---|
| 1 | MAIS — LAPIS | yes | Filipino accepted; corn/pencil rejected |
| 2 | BATA — MATA | yes | Filipino accepted; child/eye rejected |
| 3 | TASA — PAGONG | no | Filipino accepted; cup/turtle rejected |
| 4 | WALO — TATLO | yes | Filipino accepted; eight/three rejected |
| 5 | BAKA — BABOY | no | Filipino accepted; cow/pig rejected |
| 6 | KAHON — DAHON | yes | Filipino accepted; box/leaf rejected |

The original rhyme answer key is preserved without revising its pedagogical rules.

| Investigative possibility | Finding |
|---|---|
| Translation or semantic equivalence | Confirmed numeric-value equivalence in application validation; no translation-service call |
| Fuzzy/phonetic matching | Generic Filipino joined fragments can allow one edit; English homophones are language-gated; neither explains eight/walo |
| Substring/partial/token matching | Whole tokens can be found amid extra tokens; not an arbitrary substring match; partial attempts can combine with prior context |
| Normalization | Generic ASCII normalization can discard other-script content; exact activity check now preserves such mismatches |
| Shared validation | Confirmed: this activity inherited the shared `ReadingMatcher` |
| Alternatives/confidence | First alternatives used; no confidence threshold or alternative search caused the acceptance |
| Speech detected means correct | Not the implemented rule; server complete must pass, but was wrongly computed |
| Stale state | Completed client index/prior context can affect generic grading; new policy ignores them, and client response generation/target are checked |
| Rhyme means reading correct | Not the implemented rule; incorrect reading verdicts wrongly unlocked the separate rhyme stage |

Other Prescribed Activities and shared CRLA components still use their existing
policies. Generic number-value equivalence remains reachable wherever a caller
uses the permissive matcher without a stricter policy; this is a shared risk,
not evidence that every other activity accepts English translations. Lesson 2
already has its own exact-word flag. This patch does not globally remove numeric
reading support or alter CRLA rules.

The existing progress endpoint accepts client-reported completed-pair counts.
This focused accuracy fix does not convert the activity into a server-authoritative
anti-tampering system, add one-time transcript tokens, or certify against deliberate
replay of a valid same-target utterance. Normal stale response, wrong-target,
prior-syllable, and completed-index cases are covered.

## D. Implemented fix

- `reading_stt.py`: added a literal whole-word evaluator. It accepts case,
  punctuation, combining accent marks, and exact syllable spacing/hyphenation.
  It rejects translations, extra tokens, unrelated words, near-spelled different
  words, incomplete readings, digits, and other-script/symbol additions.
- `views.py`: selects this evaluator from the Lesson 3 activity identity,
  including legacy signed-stream identity. It keeps Filipino recognition and
  existing provider selection, ignores prior syllables/progress for the fresh
  reading verdict, preserves raw transcripts, and prevents other evaluator flags
  from overriding this policy.
- The activity template now sends its activity key, verifies HTTP success and
  the response target, and guards the separate rhyme handler until both readings
  have passed. All six original pairs, narration paths, recording calls, layout,
  and progression/save behavior remain in place.

There are no `eight`/`three` exceptions or translation-deny lists in production.
Digits such as `8` are deliberately ambiguous: once a provider emits a digit,
the transcript alone cannot establish whether the learner said English or
Filipino. This activity rejects the digit and requires a retry rather than
inventing evidence of a Filipino pronunciation. No fuzzy allowance is introduced
for other provider spellings without supporting pronunciation evidence.

## E. Regression tests and limits

New tests: `pabasa_site/pabasa_app/tests_lesson3_reading.py` and
`tests_lesson3_reading.js`.

- Endpoint coverage: all twelve canonical words and translations, case,
  punctuation, accent marks, exact segmentation, unrelated words, digits,
  extra tokens, other scripts/symbols, previous-word transcripts, stale indices,
  prior syllables, clip/Knowlez/stream parity, legacy stream identity, competing
  evaluator flags, provider failure, and preservation of generic numeric reading.
- Node runs the actual template's `record()` and `answer()` functions, consuming
  verdicts produced by the real endpoint. It checks accepted/rejected reads,
  HTTP/provider failures, stale response generations, response target mismatches,
  stopped tracks, unlocked retry controls, and all six rhyme answer branches.
- A broader run of 156 tests passed: focused tests plus `tests_chirp_stt`,
  `tests_knowlez_stt`, `tests_prescribed_stream`, `tests_crla_stream`,
  `tests.ReadingMatcherTests`, `tests_official_reading_payloads`, and
  `tests_prescribed_reading_attempts`.
- After adding legacy stream identity coverage, the final focused and prescribed
  stream rerun passed all 24 tests (11 focused tests and 13 stream tests).
- `manage.py check` and `git diff --check` passed.
- Separately, `tests_basahin_reading_verdict` ran 26 tests and reported ten
  failing subcases in two existing KARITON/carton test methods. The identical ten
  subcase failures reproduced with unchanged `HEAD` views loaded in memory.
  Those unrelated acceptance rules and tests were not modified.
- Browser verification used the real rendered template and transcription
  endpoint in a disposable local harness, synthetic transcripts/audio capture,
  simulated narration completion, and an in-memory progress sink. All six pairs
  completed. Eight/three caused retry without advancing; walo/tatlo advanced;
  a wrong rhyme answer retained pair 4; Pakinggan remained usable; completion
  posted six completed/correct pairs and redirected to `/dashboard/assessment/`.
  Horizontal fit was checked at 390px mobile, 800px tablet, and the desktop
  viewport. No production student data or database writes were used.

Browser startup also surfaced existing modal DOM observer exceptions in the
synthetic harness. The full reading flow nevertheless completed. Pointer actions
used forced locator clicks to avoid animation/actionability waits; this does not
certify every native pointer/touch interaction. Acoustic recognition accuracy,
real microphone capture, actual narration playback, and a fresh deployment trial
with children were not tested by this synthetic harness. A provider that itself
misrecognizes English speech as the exact Filipino target cannot be distinguished
from a true Filipino reading by transcript comparison alone.

## F. Deployment status

Local source and regression tests only. No build, deployment, traffic switch,
migration, student-data edit, or historical-score correction was performed.
Previously loaded untagged clip clients must refresh to send the activity key;
the server cannot reliably identify that activity from an untagged generic clip.
Legacy signed-stream identity is recognized by the new server policy.

Existing historical results should not be silently recalculated from incomplete
evidence. A release and any learner-specific reassessment should be handled
separately with the school's intended scoring and review process.
