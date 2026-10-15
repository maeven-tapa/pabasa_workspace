# CRLA connection and request-pressure fixes

Implemented and validated locally on October 15, 2026 (Asia/Manila), following
the [concurrent failure investigation](CRLA_CONCURRENT_FAILURE_INVESTIGATION_2026_10_15.md).
No deployment, migration, traffic change, production database write, or production
load test was performed. Real Google Speech was exercised with synthetic English
audio and disposable local accounts.

## Changes

- WebSocket session loading and ticket authorization now clean database
  connections before and after their synchronous work, in the worker thread
  that owns each connection. The `finally` cleanup also runs after authorization
  errors and cancellation.
- PostgreSQL uses Django's psycopg pool with a default maximum of **6 connections
  per process**, zero pre-opened connections, a five-second checkout deadline,
  at most 32 waiting checkouts, and a 60-second idle limit. `DB_POOL_MAX_SIZE`
  accepts integers from 1 through 32. `CONN_MAX_AGE` remains zero.
- Added the psycopg pool dependency. Cloud Run's existing three-instance cap
  would permit at most 18 application pool connections for a single revision
  running one worker per instance. Other revisions, workers, services, jobs,
  administrative connections, and the database's actual limits must be budgeted
  separately. This is a per-process cap, not a project-wide quota.
- A full pool or checkout timeout returns a retryable HTTP 503 with
  `Retry-After: 5` through production Django error handling. Unrelated exceptions
  retain normal HTTP 500 handling.
- Official CRLA clip recognition releases its database connection after access
  checks and before external speech I/O. It does not close a caller's active
  transaction. Synchronous Google speech transports close on success or failure.
- Session readers share an outstanding state fetch. Polling waits until the
  previous poll completes, with a two-second healthy delay and bounded failure
  backoff of 4, 8, and 15 seconds. Stopped poll generations ignore late responses.
  State fetches have a ten-second browser deadline.
- Periodic heartbeats are omitted while a recovery/score/terminal write is
  pending, and back off after failures. Explicit writes retain their ordered
  queue. Write requests are not aborted on a browser timer: an aborted HTTP
  request could still commit server-side after the next write starts.
- Each MediaRecorder owns its chunk array and MIME type. A late callback from
  an old recorder cannot clear or replace the new recorder or mix container
  headers/frames after navigation. Duplicate starts cannot replace an attached
  recorder. Restarting capture also verifies stream ownership.
- Google errors specifically identifying unreadable audio return HTTP 400 and
  request a fresh recording, with no score and no retry of the same invalid
  clip. Model/configuration errors retain their existing error handling.
  Google provider selection, language, grading, and authorization rules are
  preserved.

## Validation

Python 3.13.16 and Django 6.0.3 were used.

| Check | Result |
| --- | --- |
| Focused Django suite, including database configuration/capacity, stream cleanup, STT routing, and concurrent enrolled students | 49 passed |
| Reader pressure/recorder tests and story timer tests | 17 passed |
| Existing PCM/stream lifecycle JavaScript checks | Passed |
| Full reader in local Chrome with synthetic microphone input | Words, rhymes, sentences, and story passed |
| Chrome microphone through actual Uvicorn WebSocket and signed HTTP evaluator, mock Google | Passed |
| Same browser route with live Google Chirp 3 | Six synthetic English words scored; passed |
| Twenty concurrent enrolled accounts with live Google | 20 overlapping streams and 20 authorized evaluations passed |
| Django system check, JavaScript syntax, dependency consistency, whitespace checks | Passed |

The twenty-student fixture uses **two legitimate ten-student classes and two
teachers** in one synthetic school. The product's ten-student batch rule is
preserved. All twenty students have separate database-backed login sessions and
active enrollments. No production or existing local student database is used.

The default concurrent test verifies:

- Login checks remain responsive while twenty simulated speech requests wait.
- Twenty students perform three synchronized rounds of progress publication and
  polling, retaining distinct recovery snapshots and authenticated sessions.
- Twenty worker session lookups release all twenty acquired SQLite connections;
  this is repeated across three reconnect rounds.
- Real ticket authorization accepts the original sessions and rejects tickets
  belonging to another student.
- Twenty simultaneous sentence requests and twenty story requests recover from
  a mocked first-attempt Google 500, preserving each learner's actual miscues.
- Twenty replacement logins invalidate old sessions and preserve recovery state.

The opt-in real-provider phase additionally exercised **20 simultaneous Google
Chirp 3 streams**, using the actual session loader, ticket authorization, PCM
transport handler, signed finals, and shared HTTP evaluator. Every student's
result scored the synthetic sentence “The cat sat on the mat.” as six correct
words with `google`, `chirp_3`, and `en-PH` retained. The phase took **14.976
seconds**, including ticket preparation, recognition, and evaluation; this is
not a per-request latency measurement.

An initial live probe failed because not every stream returned a usable final;
its exception diagnostics were insufficient to classify the cause. The probe
was changed to collect all outcomes and server exception types before failing.
The instrumented rerun passed all twenty streams without an application/provider
change between those runs. This short successful run does not establish sustained
provider reliability.

## Existing failures found during broader testing

- A broader CRLA run executed 167 tests: 14 failures and 2 errors remain in
  scoring, workflow, and finalization tests. All 16 failing entries reproduced
  against the original `HEAD` Python implementation loaded in an isolated test
  process. No failing entry was introduced by these changes.
- The baseline broad run also exposed two existing subprocess working-directory
  errors in the database configuration tests. The test helper now supplies the
  correct Django project working directory; both pass.
- A separate authorization/enrollment/session/progress run executed 32 tests:
  one failure and two errors. Those same three entries reproduced individually
  against the baseline implementation.
- Existing scoring expectations were not changed to hide these failures. The
  broad suite remains red and should be resolved separately before release.

Baseline comparisons used `git show HEAD:<path>` loaded into a separate process;
working source and local runtime data were not replaced or reset.

## Remaining release validation

The local concurrent database was disposable **SQLite**. The pool configuration
was instantiated and checked, but a real PostgreSQL server was not available for
a local pool saturation test (Docker's engine was not running). The real Google
phase used the actual ASGI handler through a local test driver, rather than Cloud
Run's network ingress. Chrome was checked separately with the full recording
lifecycle and actual Uvicorn.

Before deployment, validate a candidate against PostgreSQL and twenty distinct
enrolled accounts, measure active/idle connections and checkout waits, and include
navigation, reconnects, recovery, terminal completion, and Filipino audio. Resolve
the existing completion/scoring failures. Verify the database connection budget
against actual PostgreSQL reserved slots and all overlapping processes. Preserve
the same-image migration-job/readiness checks and the previous working revision.

## Repeating the focused checks

From the repository root:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe pabasa_site/manage.py check
.venv/Scripts/python.exe pabasa_site/manage.py test pabasa_app.tests_database_config pabasa_app.tests_database_capacity pabasa_app.tests_crla_stream pabasa_app.tests_chirp_stt pabasa_app.tests_live_crla_concurrency
node --test tools/test_crla_request_pressure.cjs tools/test_crla_story_timer.cjs
node tools/test_crla_stream.cjs
```

Browser checks require Chrome and Playwright (`NODE_PATH` or
`CRLA_PLAYWRIGHT_PATH` pointing to the installed package):

```powershell
node tools/test_crla_microphone.cjs
.venv/Scripts/python.exe tools/test_crla_stream_browser.py
```

Live Google is opt-in and uses normal Speech API billing. For the twenty-client
probe, set `PABASA_LIVE_GOOGLE_AUDIO` to the known synthetic English WAV, then run
`pabasa_app.tests_live_crla_concurrency`. The helper refuses to run outside the
disposable SQLite concurrency fixture. Remove that environment variable afterward
to restore the default offline test mode. Credentials and signed results remain
in memory and are not printed or saved.

Implementation references:
[Django PostgreSQL pools](https://docs.djangoproject.com/en/6.0/ref/databases/#connection-pool),
[psycopg pool bounds and checkout timeouts](https://www.psycopg.org/psycopg3/docs/api/pool.html).
