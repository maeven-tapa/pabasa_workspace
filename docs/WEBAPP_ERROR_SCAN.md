# Webapp error scan

Checked October 10, 2026, approximately 3:00–3:15 AM, Asia/Manila.

## Live status

- Active Google Cloud account verified. Cloud Run `pabasa` is ready; revision
  `pabasa-01176-rmr` serves 100% of traffic and matches local commit `62dc16b5`.
- Current configuration: 1 vCPU, 1 GiB memory, concurrency 80, maximum 3 instances.
  Cloud SQL is RUNNABLE, `db-custom-2-8192`, regional HA, 250 GiB.
- No ERROR-or-higher entries or HTTP 5xx requests were found for the active
  revision in the queried 24-hour window.
- Eleven public pages returned HTTP 200: home, login, signup entry, teacher signup,
  student signup, forgot password, platform description, about, FAQ, terms, privacy.
  An unauthenticated dashboard request redirected to login as expected.
- All 46 static asset URLs referenced by those pages returned HTTP 200 to HEAD.
  Browser inspection of home, login, signup entry and teacher signup captured no
  console errors or warnings.

These checks did not exercise authenticated assessment submissions, email delivery,
microphone recording, or report downloads. There was no existing authenticated
browser session available. No production records, secrets, configuration or traffic
were changed.

## Confirmed configuration issues

1. **Knowlez STT is offered without a configured key.** The active Cloud Run
   container has no `AZURE_SPEECH_KEY` environment/secret mapping. The settings
   default to an empty key; `knowlez_stt.py:26` returns HTTP 503 when that option
   is selected. The option remains available in
   `templates/pabasa_app/includes/prescribed_stt_settings.html:10`.
   Configure the provider or disable its option when unavailable. This conclusion
   comes from matching deployment configuration with code and adapter tests;
   no real recording was submitted during this scan.

2. **The documented older service URL returns HTTP 400.**
   `https://pabasa-7j5jji5rpa-as.a.run.app` is absent from `ALLOWED_HOSTS` in
   `pabasa_site/settings.py`. The newer URL
   `https://pabasa-363691003404.asia-southeast1.run.app` and the main custom domain
   return HTTP 200. Decide whether the older URL should be supported or removed
   from operational references.

3. **The www hostname failed DNS resolution on this machine.**
   `https://www.tupcpabasa.app` failed with `getaddrinfo failed`, although settings
   accept it. The main hostname works. Verify public DNS and the intended redirect
   if www access is required.

## Source and test findings

- **Template error:** 236 HTML templates were compiled with Django 6.0.3. One
  failed: `templates/pabasa_app/partials/_story_response_create_panel.html:125`
  uses `{% static %}` without `{% load static %}`. No references to this partial
  were found, so an active user-facing failure has not been established.
- **Migration drift:** `makemigrations --check --dry-run` proposes primary-key
  alterations. The current models use implicit IDs without an explicit
  `DEFAULT_AUTO_FIELD`, while recorded migrations include both AutoField and
  BigAutoField. Reconcile the intended types before the next release; do not
  apply the generated alterations blindly. No migration file was created.
- **JavaScript syntax:** all 105 standalone static JavaScript files passed
  `node --check`. This does not validate embedded template scripts or runtime
  interaction behavior.
- **Regression suite:** 1,287 tests ran in 57.612 seconds and reported **222
  assertion failures and 113 errors**, including subtest failures. These numbers
  are not counts of distinct production defects.
- Common test errors include 21 attempts to assign the now read-only
  `Assessment.content`, 18 patches of the removed middleware helper
  `student_session_is_active`, and references to removed principal route names.
  Other failures concern scoring, activity progression, visibility and exports;
  they require individual triage. Two production-settings subprocess errors
  were affected by the scan's forced SQLite environment.
- A separate 30-test focused run with normal password hashing reproduced four
  CRLA Part 2 scoring subtest failures. For example, 80/100 words and zero correct
  comprehension answers produced `Transitioning Reader`, while the test expects
  `High Emerging Reader`. The implementation and tests encode different rules;
  confirm the accepted scoring policy before changing either. The Knowlez,
  Chirp and audio-feature tests in that focused run passed.

Local tests used Python 3.12.14 and Django 6.0.3 with an isolated dependency
directory and disposable SQLite test database. Production uses Python 3.13 and
PostgreSQL. The broad run used a fast password hasher only in its test process.
Some dependencies differ from the production pins. These limitations matter
when interpreting database-specific and environment-sensitive failures.

## Historical errors in the last 24 hours

All were on older revisions, not the current serving revision:

| Evidence | Count | Interpretation |
| --- | ---: | --- |
| Reading transcription HTTP 502 | 21 | One inspected traceback ends in Google Speech `InternalServerError: 500 Internal error encountered`; current recurrence was not established. |
| CRLA export HTTP 500 | 2 | Historical failures; the underlying exception was not found in the inspected request window. |
| Notifications, live server time, teacher overview HTTP 500 | 5 | Around 2:01 AM October 10, alongside Cloud SQL connection-refused logs; the database is now RUNNABLE. |
| Container memory-limit error | 1 | Older 512 MiB revision; current service has 1 GiB. |
| Startup probe failures | 6 | Failed revision `01172`; recovery is documented separately. |

The previous authenticated 15-client benchmark also measured roughly six-second
student-list responses. This scan did not repeat that load test or establish that
the roster performance problem has been resolved.

## Evidence and suggested order

Local raw outputs: `tmp/error-scan-tests-fast.txt`,
`tmp/error-scan-focused.txt`; reusable local runner: `tmp/run_error_scan.py`.
The ordinary `manage.py test pabasa_app` invocation discovered zero tests in this
environment, so the complete run explicitly listed the test modules.

Address the unavailable Knowlez option first. Reconcile the CRLA scoring policy
and its tests before relying on classification results. Then triage the remaining
regression failures, resolve migration drift, and check authenticated workflows
with a suitable test account. The optional hostname and unused template issues
can be handled separately.
