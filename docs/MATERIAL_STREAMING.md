# Supplementary and practice speech streaming

Implemented locally on October 11, 2026. No deployment or database migration was performed.

Supplementary reading uses the existing PCM/Google Chirp 3 WebSocket transport.
The shared word, phrase, sentence, and story readers evaluate signed final
phrases through the existing reading evaluator. Word Decoding and the timed
fluency activity retain their complete original recordings and submit a signed,
fully flushed transcript to their original endpoints.

Free, Color, and Hunt practice stream audio while the existing recording window
is open. Provisional text appears while the learner speaks. Confirmed phrases
are joined into one completed utterance before the existing practice evaluator
checks it. Current practice completion, Hunt confidence/star rules, and timed
fluency scoring remain unchanged. Streams do not invent confidence values.

`/api/reading/material-stream/start/` authorizes the material and fixes its saved
language, target, reading mode, purpose, and login session. Authorization is
rechecked when the WebSocket opens and when a result is evaluated. Current-term
Supplementary lifecycle/publication checks, enrolled class boundaries, teacher
ownership, practice difficulty locks, and teacher-access restrictions apply.
Material tokens cannot enable prescribed or official CRLA grading paths.

Interim text cannot award credit. Active connection failures, empty finals,
access rejection, and cancellation cannot become successful attempts. Unsupported
browsers/providers or unavailable startup connections retain the existing clip
path. Explicit Knowlez and Chirp 2 selections do not open a Chirp 3 stream.
Practice rejects results from a previous item or attempt and releases capture
when the microphone stops, practice restarts, or the page closes.

The ASGI runtime and `CRLA_STREAMING_ENABLED` switch described in
`CRLA_STREAMING.md` apply to these readers as well.

## Validation

- 59 focused Django tests passed across material streaming, CRLA streaming,
  prescribed streaming, Chirp recognition, and shared reading verdicts.
- The broader practice/material/lifecycle run passed 40 of 45 tests. Five
  existing ARAL fluency/vocabulary completion tests return access-denied responses;
  the same five failures were reproduced with the original `HEAD` views.
- Existing CRLA transport and Basahin recorder JavaScript checks passed. Four
  new capture checks cover signed flush, clip fallback, access rejection,
  cancellation, empty finals, active failure, and provider selection.
- Local Chrome exercised the actual Free, Color, Hunt, and supplementary
  reader templates through microphone capture, AudioWorklet PCM, the real
  Uvicorn WebSocket, mocked Google, signed results, and shared HTTP evaluation.
  Practice microphone tracks stopped after the listening toggle was disabled.
  Database queries/writes and clip-provider calls were forbidden during this test.
- Django system checks and JavaScript syntax checks passed.

Browser tests use synthetic microphone input and mocked Google; they do not
measure children's speech accuracy, classroom capacity, or mobile compatibility.

## Repeat checks

Use the repository Python 3.13 environment and an isolated SQLite test database.

```text
python pabasa_site/manage.py test pabasa_app.tests_material_stream pabasa_app.tests_crla_stream pabasa_app.tests_prescribed_stream pabasa_app.tests_chirp_stt pabasa_app.tests_basahin_reading_verdict
node tools/test_crla_stream.cjs
node --test tools/test_basahin.cjs tools/test_material_speech_capture.cjs
python tools/test_material_stream_browser.py
```

The browser test needs Uvicorn, websockets, local Chrome, and Playwright available
through `NODE_PATH`. It performs no cloud calls or persistent database writes.
