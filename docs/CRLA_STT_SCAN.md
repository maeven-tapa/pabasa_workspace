# CRLA speech recognition scan

Reviewed October 10, 2026 (Asia/Manila). This is an investigation, not a deployed change.

## Findings

- The main CRLA reading path uses MediaRecorder clips and HTTP POST to
  `/api/reading/transcribe/`. It does not stream audio to Google.
- `assessment_reader.js:447` and `:462` set a 10-second recording window for
  words, sentences, phrases, and paragraphs. Words can finish sooner after
  1.2 seconds of detected silence (`:3797`). The other modes lack that early
  silence trigger.
- The recorder stops and awaits the full transcription response before
  restarting (`:3767`). Continued speech during this interval is not captured
  by this STT recorder. This is a source-confirmed capture gap; its effect on
  actual student scores needs a microphone test.
- `reading_stt.py:549` creates credentials/client/channel for every clip, then
  calls synchronous `Recognize` (`:569`). Reusing a client per worker and
  credentials configuration could reduce connection overhead; the gain has
  not been benchmarked.
- Server recognition has a two-attempt budget, and the browser can retry
  the entire HTTP request once. Temporary failures can therefore produce up
  to four provider attempts for one recording. Keep recovery, but coordinate
  the budgets and retain the same item/session context.
- Official CRLA forces Google Chirp 3, with no provider fallback. Existing
  sentence, rhyme, and story analysis must remain authoritative when adding
  live results.
- Browser SpeechRecognition already exists in answer-recording paths. This
  does not make the main reading path live. Browser recognition also has
  limited cross-browser support and cannot be assumed to match the configured
  Cloud Chirp 3 model.
- Source configuration sends STT to `us`, while the web service is in
  `asia-southeast1`. This adds a cross-region dependency. The size of its
  contribution to latency has not been isolated.

## Observed server timings

Read the latest 500 Cloud Run request logs for the shared transcription endpoint
within a 24-hour window. These cover October 9, 16:04 through October 10, 01:47
in Manila, across 19 older revisions, not the currently serving revision.

| Measure | Observed |
|---|---:|
| Median HTTP server latency | 2.190 s |
| 95th percentile HTTP server latency | 5.734 s |
| Maximum HTTP server latency | 19.533 s |
| HTTP 200 | 497 |
| HTTP 502 | 3 |

These timings exclude browser recording and are not a CRLA-only sample.
HTTP success does not establish transcription accuracy.

The revision inspected, `pabasa-01181-zb2`, was Ready and listed at 100% traffic
when checked. Its configured concurrency was 80, request timeout 300 seconds,
and service template resources 1 CPU / 1 GiB. Service-level Ready was Unknown
at the first read; revision readiness was verified separately. Recheck before
capacity work. The source uses Gunicorn WSGI with 16 threads and has no
WebSocket routing; streaming requires a compatible server or a separate gateway.

## Recommended implementation

1. Benchmark Chirp 3 in Singapore against the current US endpoint using the
   same recordings, languages, and recognition rules. The live Locations API
   returned Chirp 3 recognition availability for `fil-PH`, `en-US`, and `en-PH`
   in both locations. This validates listing/availability, not actual streaming
   behavior or accuracy. Make the location configurable before switching.
2. Add an authenticated WebSocket audio path to a backend gateway that calls
   Google Speech V2 `StreamingRecognize` through gRPC. Keep credentials on the
   server. Capture continuously with an AudioWorklet; start with mono 16 kHz
   PCM frames of roughly 100–200 ms, explicitly resampling the device's rate.
   Frame duration is an implementation starting point, not a latency guarantee.
3. Enable interim results for provisional text. Replace the current interim
   hypothesis instead of appending each update. Use final results for CRLA
   correctness, miscues, advancement, and stored scores, reusing the existing
   analyzers. Streamed final text can still contain recognition errors.
4. Retain current item/session context checks, deduplicate finalized results,
   flush on mute/end/skip, rotate streams before Google's five-minute limit,
   and handle reconnects without losing or counting audio twice. The admin
   test must use the same path while retaining its no-save behavior.
5. Keep clip transcription as a fallback. Shortening clips alone still leaves
   upload/processing delays and can split a child's syllables; test slow,
   syllabic reading before changing endpointing or enabling aggressive silence
   detection. Measure first interim, finalization latency, lost audio, alignment
   accuracy, and concurrent-user capacity before rollout.

A live display can feel responsive without treating an unstable partial word
as a final assessment decision. Target response times require a pilot with real
microphone input; this scan did not benchmark live audio or Google streaming.

## Validation

23 focused tests passed (`tests_chirp_stt`, `tests_basahin_reading_verdict`).
These use provider mocks and verify existing model selection/matching rules;
they do not establish real-world recognition quality or streaming speed.

## Primary references

- [Chirp 3 model, streaming, and endpointing](https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3)
- [Streaming recognition and gRPC](https://docs.cloud.google.com/speech-to-text/docs/streaming-recognize)
- [Interim and final result semantics](https://docs.cloud.google.com/speech-to-text/docs/reference/rpc/google.cloud.speech.v2#streamingrecognitionfeatures)
- [Locations API metadata](https://docs.cloud.google.com/speech-to-text/docs/locations)
- [Streaming limits](https://docs.cloud.google.com/speech-to-text/docs/quotas)
- [Browser SpeechRecognition support](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition)
- [Cloud Run WebSocket reconnection](https://docs.cloud.google.com/run/docs/tutorials/websockets)
