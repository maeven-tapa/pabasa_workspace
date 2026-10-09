# CRLA continuous speech

Implemented locally on October 10, 2026. Deployment has not been performed.

## Behavior

Official CRLA word, rhyme, sentence, and story reading can send continuous audio
to Google Speech V2 Chirp 3. The model, US location, language selection, and
existing assessment content remain unchanged. Interim text is shown separately
as `Hearing: ...`; it cannot mark a word correct, create a miscue, advance an
item, or save a score. Google can emit finalized phrases without any interim
words. This is continuous recognition, not a promise of one update per word.

Google finals carry a short-lived server signature bound to the login session
and original material/reading context. The existing reading evaluator handles
them, including rhyme matching, Filipino syllable stitching, sentence corrections,
and story alignment. There is no second scoring implementation. The existing
reader's completion and persistence code remains responsible for final results;
the admin preview retains its existing no-save behavior.

The browser sends 200 ms mono 16 kHz PCM frames. It buffers during connection
startup and stream rotation, with an explicit limit. Startup audio can be
checked through the original clip endpoint if connection setup fails. Browsers
without streaming support use the original clip recorder. A failed active stream
shows an interruption instead of silently ignoring unconfirmed speech or completing
with an invented zero score. Toggle the microphone off and on to resume.

End, mute, sentence timeout, and forward skip flush captured audio before their
normal transition. Item/attempt guards reject late results. Final messages are
processed in order and deduplicated. Streams rotate after 230 seconds, ahead
of Google's five-minute limit. Both capture buffers and server queues are bounded.

## Runtime

The Docker startup command now runs the Django ASGI application with Uvicorn's
WebSocket implementation. It retains the migration readiness checks. A WSGI
server cannot serve the new `/ws/reading/crla/` route; if started that way, the
reader uses clip fallback when the WebSocket cannot open.

`CRLA_STREAMING_ENABLED` defaults to `true`. Set it to `false` to make new
recordings use the original clip path. This does not stop already connected streams.
No database migration is added. For a release, follow the existing same-image
Cloud Run migration-job/readiness procedure before switching traffic.

The current region remains `us`; the Singapore benchmark/switch is a separate
task. Long-lived connections need a concurrent-user pilot and Cloud Run capacity
verification before treating the feature as ready for a full class.

## Validation completed

- 56 focused Django tests passed using the pinned Google Speech SDK 2.34.0.
  Stream and clip results were compared for words, rhymes, sentences, and stories.
- JavaScript checks covered continuous capture during evaluation, first-item and
  stale-item guards, deduplicated and ordered finals, rotation, flush, explicit
  overflow errors, fallback, and 8/16/44.1/48 kHz input resampling.
- Existing admin CRLA and prescribed preview JavaScript tests passed.
- A headless Chrome test traversed microphone -> AudioWorklet -> actual Uvicorn
  WebSocket -> mocked Google -> signed final -> shared HTTP evaluation. It displayed
  provisional text and awarded four correct words. Database queries/writes were
  forbidden during the test.
- A second Chrome test used synthetic English audio and actual Google Chirp 3
  with the pinned SDK. It recognized `The cat sat on the mat.` and the shared
  evaluator awarded six correct words. No interim updates were returned in that
  short sample. Database access remained forbidden. No student audio was used.

The live test exposed missing startup audio while the connection opened.
Capture now starts before the handshake completes and buffers those frames;
the repeated live test recognized the initial word as well.

These tests do not measure Filipino children's speech accuracy, classroom noise,
Safari/mobile behavior, or full-class capacity. No Cloud Run deployment or
traffic change was performed.

## Repeat checks

```text
python pabasa_site/manage.py test pabasa_app.tests_crla_stream pabasa_app.tests_chirp_stt pabasa_app.tests_basahin_reading_verdict pabasa_app.tests_admin_crla_preview pabasa_app.tests_admin_prescribed_preview
node tools/test_crla_stream.cjs
node tools/test_admin_crla_preview.cjs
node tools/test_admin_prescribed_preview.cjs
```

`tools/test_crla_stream_browser.py` needs Uvicorn, websockets, local Chrome,
and Playwright reachable through `NODE_PATH`. Its default provider is mocked.
The optional `--live-google` mode uses the authenticated gcloud account, incurs
normal Speech API usage, and expects the synthetic WAV at
`%TEMP%/pabasa-crla-stream-test.wav`.
