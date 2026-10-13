# CRLA read aloud with ElevenLabs

CRLA words, active rhyme words, sentences, story segments, and comprehension
questions use ElevenLabs voice `4RLeKvASM0Zt73Htf5GF`. The reader sends
`tts_profile=crla` to the existing authenticated, CSRF-protected read-aloud
endpoint. Existing CRLA MP3 assets are retained, but no longer override this voice.
Other assessment and practice profiles retain their existing audio providers.
Student recording, speech recognition, scoring, and completion are unchanged.

Set `ELEVENLABS_API_KEYS` in the repository-root `.env` or the server environment,
then restart Django. It accepts keys separated by commas or whitespace, in the
order they should be used. For example (placeholders only):

```dotenv
ELEVENLABS_API_KEYS=your_first_key,your_second_key,your_third_key
```

The legacy single `ELEVENLABS_API_KEY` still works when the pool is empty.
Use ElevenLabs keys with text-to-speech permission and
access to this voice. Never add the real key to source control or browser code.
No additional Python dependency or database migration is needed.

The backend uses `eleven_v3`, explicitly selects `fil` for Filipino/Tagalog or
`en` for English, and requests MP3 at 44.1 kHz / 128 kbps. A single speed setting
of `0.92` preserves the previous modest slowdown. It returns base64 audio using
the existing browser playback flow. Responses identify `tts_provider`, `voice_id`,
and `model_id`. Missing credentials, provider errors, empty audio, and invalid
responses fail visibly without switching voices or affecting assessment scores.

Ordered failover tries each available key once, using the same voice, model,
language, and text. Successful requests stop the search. Provider quota errors
(including `quota_exceeded` returned as HTTP 400/401), rejected keys, inaccessible
voices, rate limits, network failures, and invalid audio can advance to the next
key. Invalid request parameters and explicit account restrictions fail immediately.
An all-keys-unavailable response contains no credentials or provider message text.

Quota failures cool down for 15 minutes, key/voice access failures for 5 minutes,
rate limits for 30 seconds, and transient failures for 5 seconds. Keys are identified
in the Django cache by a SHA-256 digest. Subsequent requests skip cooling keys;
expired entries allow them to be retried after account credits or access recover.
The current local-memory cache tracks this per process and resets on restart;
a shared cache is needed to coordinate cooldowns across server instances.
Individual provider attempts use at most a 20-second socket timeout, and no new
attempt starts after a 60-second request budget. This avoids spending one full
timeout on every configured key.

Quota decisions use ElevenLabs' responses rather than a local 10,000-character
counter, so usage outside PABASA and account resets are respected. Keys belonging
to the same workspace share its quota; additional keys do not create more credits.
See [API key limits and workspace quotas](https://elevenlabs.io/docs/overview/administration/workspaces/api-keys)
and [provider error codes](https://elevenlabs.io/docs/help-center/technical/api-error-code-400-or-401).

Provider references: [Create speech](https://elevenlabs.io/docs/api-reference/text-to-speech/convert)
and [model language support](https://elevenlabs.io/docs/overview/models).

Local verification (Python 3.13):

```powershell
.\.venv\Scripts\python.exe pabasa_site/manage.py check
.\.venv\Scripts\python.exe pabasa_site/manage.py test pabasa_app.tests_crla_tts pabasa_app.tests_admin_crla_preview
node tools/test_crla_tts_browser.cjs
```

The Chrome test requires installed Chrome and `playwright-core`; set
`CRLA_PLAYWRIGHT_PATH` to its module directory if it is installed outside the
repository. It runs the production playback functions with a mocked TTS endpoint
and a repository MP3, checking all five stages, audio playback, stop/end cleanup,
failure messages, cancellation, recording-analysis locks, and non-CRLA routing.

Tests mock ElevenLabs requests and do not consume API credits. An actual voice
quality check requires the configured API key and account access to the voice.
This change does not deploy the app or configure cloud secrets.
