# Basahin: shared STT capture and button

`pabasa_app/static/pabasa_app/js/basahin.js` exposes `window.Basahin` for session activities and new reading screens. The idle label is **Basahin**. Recording starts only after the volume-based VAD detects speech; each independently decodable clip then lasts **2.4 seconds**. The module does not decide lesson scores, listening unlocks, or activity completion.

## Add a new reading screen

Include the script once in the HTML head, before the screen's own scripts:

```django
{% include 'pabasa_app/basahin_script.html' %}
```

The include loads the shared stylesheet, button dispatcher, and STT controller. It supplies the teal pill styling, microphone icon, gold listening pulse, processing spinner, focus/disabled states, mobile sizing, and reduced-motion support. No Bootstrap icon font is required.

Place the reusable button where the screen needs it (an optional class can position it in the screen's layout):

```django
{% include 'pabasa_app/basahin_button.html' with basahin_button_id='read-word' basahin_button_class='activity-button' %}
<p id="reading-status" role="status"></p>
```

For continuous reading, bind once after the elements exist:

```javascript
const status = document.getElementById('reading-status');
let cursor = 0, context = '';
const reader = Basahin.create({
  button: document.getElementById('read-word'),
  getFields: () => ({
    target_text: 'Uubo si Bibo.',
    language: 'Filipino',
    mode: 'sentence',
    current_syllable_index: cursor,
    syllable_context: context,
  }),
  onResult(result) {
    cursor = result.current_syllable_index ?? cursor;
    context = result.syllable_context || '';
    status.textContent = result.transcript || 'Subukan muli.';
    if (result.complete) {
      // Invoke this screen's existing completion/scoring logic here.
      return true;
    }
    return false;
  },
  onError(error) { status.textContent = error.message; },
});

// On pause, target change, restart or navigation:
// reader.stop();
// On permanently removing the screen/button:
// reader.destroy();
```

The button shows `Sandali...` while preparing/calibrating, then `Magsalita...` while waiting for speech. It changes to `Nakikinig...` when recording starts and `Sinusuri...` during STT, then returns to `Basahin`. It is disabled while busy. Waiting does not pulse or create a MediaRecorder. During a clip, the pulse follows detected speech with CRLA's 240 ms hold between syllables; the clip continues to its 2.4-second boundary even if speech pauses. Recording pauses while the request is processed, and each new clip waits for speech again. `getFields()` is called for every clip; keep the server cursor and stitching context in your screen's state. Reset them when changing the target. `onResult` may return `true` to stop, `false` to continue, or nothing to use `result.complete`. `continuous: false` stops after one result. The default limit is 25 voiced clips per start; `maxChunks` can override it. `deviceId` selects a microphone.

## Existing activity workflows

All migrated reading buttons register their activity callback with the shared dispatcher:

```javascript
Basahin.bindActivity(button, async () => {
  // Apply this activity's prerequisites/locks, then use the shared capture API.
  const result = await Basahin.read(fields, {button});
  // Apply this activity's grading and save its progress here.
});
```

`bindActivity` replaces any old `onclick` registration and stores one callback per button. Rebinding replaces the callback rather than adding another listener. The single shared click handler guards disabled buttons and duplicate clicks. `getActivity(button)` retrieves the registered callback when an existing activity needs to wrap its workflow. New screens should use `create()` above; it registers with this same dispatcher automatically.

`data-basahin-button` marks both template buttons and buttons created by JavaScript. The shared presentation controller preserves the button element, focus and registered workflow while restoring its icon/label after legacy text updates. `window.BasahinButton.LABEL` is the idle label source. `BasahinButton.setState(button, 'idle' | 'calibrating' | 'waiting' | 'listening' | 'processing')` updates the presentation without changing activity locks. The VAD controls the separate `data-basahin-speaking` flag; merely setting a listening label does not start a pulse. Pass `{button}` to `capture()` or `read()` to update these states automatically. When an activity reuses a button for model audio, its `Pakinggan` action and label remain distinct.

Do not add per-screen reading `onclick` handlers, MediaRecorder loops, idle labels, pulse keyframes, or spinner CSS. Keep lesson-specific instructions, scoring, retry limits, and progress callbacks in the activity.

The default transport posts multipart audio plus the supplied fields to `/api/reading/transcribe/`, includes the CSRF cookie, and times out after 35 seconds. Use `url` to change the endpoint or provide `transcribe(blob, fields, {signal, url})` for another transport. Custom transports must respect the abort signal; late results are ignored after cancellation.

## One activity attempt across several clips

For an existing sentence activity that scores only after reading ends:

```javascript
try {
  const result = await Basahin.read({
    target_text: currentSentence,
    language: 'Filipino',
    mode: 'sentence',
  });
  // Count ONE attempt here, then apply this activity's grading policy.
  // result.complete is the server's completion decision.
} catch (error) {
  // Silence/cancellation/microphone errors must not count as wrong answers.
  status.textContent = error.message;
}
```

`read()` carries the syllable cursor/context into the next clip and joins transcripts. It finishes on completion or a response that makes no cursor/context progress. It throws for empty transcripts, cancellation and capture/transport failures. `onProgress(result)` can update highlighting. An optional `signal` cancels the attempt. CRLA sentence word scoring is opt-in through `crla_sentence_word_scoring: '1'`; its word results are carried forward as well.

## Keep an existing activity's endpoint

Word/syllable activities can use capture alone and retain their current request payload and grading:

```javascript
const audio = await Basahin.capture();
// Submit audio to the existing activity endpoint only after capture succeeds.
```

`capture({stream, signal, deviceId, onRecorder, onState})` returns one voiced Blob. It releases microphone tracks by default, including supplied streams. Use `keepStream: true` only when the caller owns cleanup and needs to reuse that stream. `openMicrophone(constraints, {signal, timeoutMs})` is a cancellable alternative for existing code that needs to acquire its own stream. Its default permission timeout is 15 seconds; any microphone grant arriving after cancellation/timeout is released. `isCaptureError(error)` identifies capture failures, silence and cancellation for legacy attempt counters.

## Volume-based VAD and lifecycle

- RMS volume is measured from 1,024 time-domain samples on animation frames.
- The first 800 ms calibrates the background floor. Quiet samples continue adapting it with 0.94/0.06 smoothing.
- Speech threshold: `max(0.014, backgroundFloor * 3.2 + 0.004)`.
- Three above-threshold frames establish speech and start the recorder. Quiet frames reduce that evidence. Evidence resets between clips, so previous speech cannot start a new recording during silence.
- While waiting, only the microphone analyser runs. No audio clip is recorded or sent to STT. Twelve seconds without detected speech ends capture with `NoSpeechError`; no reading attempt should be counted. `capture({maxWaitMs})` can change this limit; the older `maxSilentChunks` option maps to that many 2.4-second waiting intervals.
- Every clip starts a new MediaRecorder so each upload has its own decodable container. This is chunked capture, not a streaming provider connection.
- `cancelAll()` cancels shared captures/controllers. Page exit and the common session controls call it. New custom controls must also call `reader.stop()` or `Basahin.cancelAll()` before changing reading state.
- `basahin:state` events expose `calibrating`, `waiting`, `listening`, `level` and silence-timeout details for debugging/meters. `onVad(state, detail)` provides the controller's capture updates.

The thresholds follow the CRLA reader's volume detector. Volume gating distinguishes quiet audio from sufficiently loud audio; it cannot identify whether a loud sound is speech. Browser microphone access requires HTTPS or localhost and user permission.

## Existing integration and verification

Reading activities using `/api/reading/transcribe/` grade with `result.success && result.complete === true`. Do not compare or search the transcript again in JavaScript: the backend owns word matching, sound aliases and syllable reconstruction. Keep transcripts for display and saved diagnostics. Exact rhyme activities send `salitang_magkatugma_exact=1`; strict syllable exercises retain their specific backend verdict. The Session 7 Lesson 20–21 cluster activity sends its `prescribed_activity_key` so its scoped `check`/`tsek` pronunciation allowance is evaluated on the server.

Session templates that used **Basahin Ngayon** and the workbook's **Basahin ang Salita** now display **Basahin**. Their speech capture uses this module while preserving the existing per-activity server graders. Sentence attempts use `read()` so the 2.4-second clip boundary does not end a full sentence prematurely. Teacher-managed reading buttons also use the shorter label; they retain their existing non-STT behavior. The separate CRLA assessment reader and long-form recording screens retain their existing workflows.

Run the deterministic microphone, VAD, transport and lifecycle checks with:

```sh
node --test tools/test_basahin.cjs
```

These checks simulate microphone data and provider responses; they do not validate a physical microphone or live Google transcription.

The browser check uses installed Chrome and `playwright-core` (or its absolute module path in `BASAHIN_PLAYWRIGHT_PATH`):

```sh
node tools/test_basahin_button_browser.cjs
```

It verifies click dispatch, speech-gated recording/pulsing, quiet pauses, reduced motion, dynamic buttons, mobile sizing and real browser recording with synthetic audio. Physical microphone and live Google STT quality still require manual testing.

`node tools/test_basahin_grading_browser.cjs` exercises actual lesson scripts with conflicting transcript/verdict fixtures to verify saved matches and advancement follow the backend. From `pabasa_site`, run `python manage.py test pabasa_app.tests_basahin_reading_verdict` for word boundaries, segmented speech, sentence progress, exact rhymes and the scoped cluster pronunciation allowance.
