# Practice interface audit — October 21, 2026

## Active source and scope

The three routes in `pabasa_site/pabasa_app/urls.py` call
`practice_word_page`, `practice_sentence_page`, and `practice_para_page` in
`views.py`. Their templates extend `templates/pabasa_app/practice_reader_base.html`,
which loads `static/pabasa_app/js/practice_reader.js`. The similarly named
template JavaScript and root-level `pabasa_app/` are not the active reader.

The existing flow remains: unread items may be skipped; successful reads advance
automatically; continuous listening retries unsuccessful reads and continues
onto the next item until stopped. Hunt keeps its 900 ms success hold and 220 ms
transition, Color its 850 ms success animation, and Free its 320 ms success hold.
No provider selection, recognition language, scoring formula, star threshold,
reward endpoint, authorization rule, or progress storage format was changed.

Hunt's disabled initial Read Aloud button in the supplied screenshot could not be
reproduced in the current local source. Its markup was enabled and its handler
disabled it during playback. Controls now explicitly derive availability from
items and pending operations; playback failure explains the problem and restores
the controls. The screenshot alone does not establish which transient state
caused the old disabled appearance.

Free's conflicting completion text came from the persisted level entry's
`completed` flag, not completion of the current attempt. A saved completed level
now shows the short badge **Practice again**, while the current card counter
continues to describe this attempt.

## Before and after wording

| Location | Before | After |
| --- | --- | --- |
| Hunt card | Look at the word. Read it aloud. | Read the word/sentence/paragraph aloud, matching the page's material type. |
| Hunt idle feedback | Ready to start reading; no words recognized; Begin reading. | One card instruction; idle feedback and recognition details hidden. |
| Color idle feedback | Begin reading. | Read the sentence aloud. (Or word/paragraph as appropriate.) |
| Color success | Earned a practice star; tap Finish while automatic advancement was pending. | Picture grows! Moving on… / Picture complete! Finishing… |
| Free reading prompt | Tap the mic. Read aloud. | Read the card aloud. |
| Free navigation | Repeated Swipe up for the next challenge. | One hint: Swipe up to skip. |
| Free saved completion | Level complete! The next challenge is unlocked. | Practice again, only for a previously completed level. |
| Unread advance | Next / Finish | Skip / Skip & Finish on the last unread item. |
| Playback control | Read Aloud throughout a pending playback | Speaker icon: Read Aloud → Loading Audio… → Playing… → Read Aloud. |
| Microphone control | Start Reading / Stop, including ambiguous pending periods | Microphone icon: Start Reading → Allow Microphone → Stop; spinner and Checking during processing. |
| Student recognition details | Raw microphone text and transcript/debug toggle | Hidden normally; append `speech_debug=1` to the reader URL to inspect diagnostics. |

## Control and transition table

**RA** = Read Aloud (speaker), **SR** = Start Reading (microphone),
**A** = advance control. “Locked” means native disabled state, visible disabled
styling, and a status explanation associated with the controls. Enabled buttons
retain normal keyboard activation and a visible focus outline. Space on a
focused Read Aloud button plays audio; it does not trigger Free's mic shortcut.

| State | Hunt | Color | Free |
| --- | --- | --- | --- |
| Initial load | RA and SR enabled; A = Skip. Card names the material type. | RA and SR enabled; A = Skip. One reading instruction. | RA and SR enabled; A = Skip. Card instruction plus one swipe hint. |
| Audio request/playback | RA = Loading Audio… / Playing…; SR and A locked. Listen to the text. | Same. | Same; swipes are ignored while playback is pending. |
| Microphone permission | SR = Allow Microphone; RA, SR, A locked. Allow microphone access in your browser. | Same. | Same; swipe cannot bypass the request. |
| Listening | SR = Stop; RA and Skip enabled. RA pauses capture for playback and resumes the existing listening choice. | Same. | Same; Skip and swipe discard the old item's capture before moving. |
| Speech processing | SR = Checking; RA, SR, A locked. Checking your reading… | Same. | Same; swipe is locked too. |
| Successful read | Existing points awarded; Great reading! Moving on…; SR locked for the resolved item; Next may advance early; existing timer also advances once. | Picture reveal and existing automatic advance; controls locked during the animation. | Great reading! Moving on…; controls locked during the existing automatic advance. |
| Unsuccessful read | Same item, no successful outcome; Try this text again. I'm still listening.; automatic retry retained. Stop remains available between requests. | Same item; retry instruction; automatic retry retained. | Same card; retry instruction; automatic retry retained. |
| Provider/microphone error | Same item; no successful outcome/reward. Actionable error; RA, SR and Skip restored. Provider errors require explicit SR restart. | Same. | Same. |
| Skip or advance | Existing skip classification/award request, then one 220 ms transition; controls restore on the new item. | Existing skip path; 250 ms duplicate-click guard. An accepted read is not overwritten as a skip. | Button and up/down swipe use the same existing skip helper and 450 ms gesture guard. |
| Final item | Unread A = Skip & Finish; read A = Finish during the automatic success hold. | Unread A = Skip & Finish; Finish only completes the activity; successful final read still finishes automatically. | Unread A = Skip & Finish; successful final read still finishes automatically. |
| Completed level | Reading controls hidden/disabled; existing results actions remain. Duplicate completion is ignored. | Same. | Same; Practice Again resets the current card to 1 and renders the Free reader. |

Permission requests time out after 20 seconds; late microphone streams are
stopped. Read Aloud requests time out after 30 seconds and transcription requests
after 45 seconds. These failure paths do not score a read or switch providers.
The existing live capture implementation remains responsible for its own stream
completion. The final unread Color item is explicitly recorded through the
existing skip helper before completion, matching the visible skip action.

## Validation and limits

Passed with the repository's Python 3.13 virtual environment:

```powershell
.\.venv\Scripts\python.exe pabasa_site/manage.py check
.\.venv\Scripts\python.exe pabasa_site/manage.py test pabasa_app.tests.HuntScoringRuleTests pabasa_app.tests_practice_resilience pabasa_app.tests_practice_persistence pabasa_app.tests_practice_material_selection pabasa_app.tests_practice_material_visibility pabasa_app.tests_practice_debug
node --check pabasa_site/pabasa_app/static/pabasa_app/js/practice_reader.js
git diff --check
```

The Django run passed **23 tests**. It emitted an existing migration fixture's
naive-datetime warning. No application schema changes were made.

Browser verification used the real Django views, templates, and reader script in
the in-app Chromium browser at 1280 × 720, with a disposable SQLite database and
two-item synthetic materials. A temporary local harness supplied simulated
microphone, playback, transcription, and award responses. It was not added to the
application. This is interaction testing, not a classroom capacity benchmark.

Observed checks:

- Initial controls and hidden diagnostics in all three modes.
- Successful reads, automatic next-item listening, and completion in all modes;
  Free showed 2/2, Color 6/6 words, and Hunt retained its existing fixed points
  denominator. Mock award totals are not evidence of live reward persistence.
- Hunt microphone permission request, denial, and timeout recovery.
- Color speech processing locks and provider-error recovery: same item, zero
  progress, usable controls afterward.
- Free unsuccessful read: same card, continuous retry; Stop did not score it.
- Free playback loading/playing/error recovery and keyboard Space on Read Aloud.
- Hunt and Color double-click Skip advanced exactly one item. Free wheel/swipe
  and button skip paths produced two skipped words and a 0/2 result.
- Color final skips produced 0/6 with six skipped words; Free Practice Again
  returned to card 1. Previously saved completion displayed Practice again.

Not verified: real microphone grant/denial dialogs and physical recording,
actual live recognition/playback providers and their network failures, full
normal-level reward persistence, screen-reader announcements, or a physical
touchscreen swipe. Browser wheel input exercised the same Free advancement
handler as touch. Shared failure handlers were exercised in representative
modes, not every possible combination of mode and provider.
