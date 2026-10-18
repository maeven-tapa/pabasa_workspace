# Latest release and thirty-student CRLA interruption test

Completed October 19, 2026, Philippine time, on https://tupcpabasa.app.

## Serving release

**`pabasa-01370-yit` is the newest created and newest ready revision,
with 100% public traffic.** Image:
`asia-southeast1-docker.pkg.dev/project-2b0d295d-ee06-40a7-927/cloud-run-source-deploy/pabasa_workspace/pabasa@sha256:09fb3db52c4a2bf05d1ac68ce46e011e29a3bd6b0766670343d2bfe2d78bf918`.

The image already existed for Git commit `c1d4f63c`; no rebuild or artificial
recommit was needed. The local branch was fast-forwarded to that commit. Before
this work, traffic remained on `pabasa-01346-rew` while newer imported
revisions had no public traffic. A new healthy revision of the newest image was
created after preparing its database, then tested before activation.

Cloud SQL on-demand backup **1792355655257** completed SUCCESSFUL before schema
work. Job `pabasa-crla30-migrate-3d025750`, using the exact new image, passed
`check_migration_readiness --require-recorded`, verified its only pending migration
was `0034_assessmentrequest_live_session_and_more`, applied it, and passed
`migrate --check`. That migration adds a nullable link from assessment requests
to live sessions and extends request status choices. Startup readiness and
migration checks remain in the image command.

The runtime identity, secret references, Cloud SQL attachment and private shared
recording mount were checked against the previously serving revision. The
public reader SHA-256 matches the image's reader and the checked-out source:
`18eb72872db05a2b79fde1cf941f62494f7319bb93e484081b56f08b99ab8b96`.
The previous serving revision remains available for traffic rollback; database
migrations were not reversed.

## Image retention repair

The previous registry policy deleted images older than thirty minutes, including
tagged versions, while keeping only one newest version. The old serving image
had already disappeared from the registry. The newest image was present.

The repository now deletes **untagged images older than thirty days**, keeps ten
recent versions and explicitly protects `release-` and `rollback-` tag prefixes.
The new image has tag **`release-20261019-c1d4f63c`**. Policy and image existence
were rechecked after the release. No recording-bucket contents or permissions
were changed by this retention repair.

## Complete live results

Both final runs used **six independent teachers, each with five distinct actively
enrolled synthetic students**: thirty students active concurrently, thirty-six
authenticated users. Student waves/barriers use thirty workers; teacher actions
use six controls. Each class has one normal five-student active batch.

| Run | October 19, PHT | Requests/connections | HTTP 500/503 | Unexpected failures/retries |
| --- | --- | ---: | ---: | --- |
| Candidate | 04:43:20–04:45:56 | 2,460 | 0 | 0 / 0 |
| Public site | 04:50:09–04:52:46 | 2,430 | 0 | 0 / 0 |

Paginated Cloud Run logs matched every counted request/connection in each run,
across three instances. The public statuses were **2,346 HTTP 200,
42 WebSocket upgrades, six expected HTTP 401 responses after deliberate
login expiry and thirty-six expected HTTP 403 authorization refusals**. Both
final windows had zero server ERROR events, database pool failures, background
worker failures and streaming-failure warnings.

In each final run:

- All thirty students closed/reopened their HTTPS transport and retained their
  acknowledged recovery cursor. Six logins were deliberately expired, returned
  401, and recovered through the normal login endpoint without losing progress.
- All six teachers paused/resumed their classes. Stale writes during pause
  could not advance the students. Teacher exit `interrupt` requests were
  repeated idempotently, controls reopened, recovery was validated and students
  resumed. Teacher transport loss without an unload message did not create an
  official completion or erase progress.
- Save & Exit required thirty final student acknowledgements. Later writes
  could not reopen a saved participant or overwrite the checkpoint. All thirty
  resumed correctly under teacher control.
- Thirty simultaneous real Google streams and thirty signed result evaluations
  succeeded. Sixty generated WebM/Opus uploads exercised both recorded-speech
  paths. Six additional sockets were cut during valid, paced audio, one per
  class, while all thirty students continued polling. Those six students then
  obtained six fresh Google results and accepted evaluations after restarting.
- Temporary workflow evidence covered ten words, five sentences, story
  selection/segments, comprehension, rating and temporary completion. No
  official results existed until teacher End Session. Six simultaneous End
  Session requests finalized exactly thirty classified results: five per
  teacher, one per student, all linked to the correct enrollment. Repeated End
  Session created no duplicates. All thirty-six logins survived before cleanup.
- Student attempts to invoke teacher End Session and cross-class teacher
  actions were rejected. No other class or real student account was changed.

## Browser and local checks

`tools/test_crla_thirty_resilience_browser.cjs` passed with thirty isolated Chrome
student contexts, six five-student class groups, actual Django templates and the
complete latest reader. All thirty paused and stopped controlled capture;
six pages were actually closed/reopened; all thirty recovered their saved item.
Offline API saves could not advance the item. Reconnecting/reloading restored
the acknowledged checkpoint. Every reader then completed words, sentences,
story, two unanswered comprehension questions, rating and waiting-room
navigation. Refresh preserved both section-completion cards. There were zero
page exceptions or premature official-result writes; unanswered scores stayed
null. Browser speech/APIs are controlled fixtures, separate from the real
authenticated/provider probe above. Teacher browser unloads are represented by
the normal interrupt endpoint and transport loss, not six killed teacher browser
processes. Power loss, prolonged outages and infrastructure failures were not
exhaustively reproduced.

The twenty-four focused skip/completion JavaScript regressions passed. The stream
lifecycle harness passed capture, serialized finals, finalization, stale-item
rejection, fallback and branch-aware status checks. Django `check`, migration
consistency (`makemigrations --check --dry-run`), Python/JavaScript syntax and
whitespace checks passed.

A wider focused Django run on the unchanged latest application source had
**48 passes and seven existing failures (55 tests total)**. The failures involve
older Close & Save/batch fixtures and save acknowledgement expectations,
unfinished-item/notification assertions and a waiting-card text expectation.
Those tests were not weakened and production scoring was not changed to make
them pass. The full suite is not reported green. The live thirty-student save,
acknowledgement and completion checks above passed against the deployed source.

## Observed failures and test corrections

The first candidate probe accidentally sent one oversized PCM frame to each of
its six deliberate-disconnect sockets. The server correctly rejected them with
six ValueError warnings, without HTTP 500/503 or invented grades. The probe was
corrected to send three valid 6,400-byte frames before cutting each connection;
the corrected candidate/public results are in the table.

The first public run stopped on **one Google `Aborted` stream among thirty**.
Its 324 HTTP/WebSocket requests still had no HTTP 5xx or server ERROR events;
no official results were finalized by that stopped run, and its synthetic
resources were removed. This failed run is retained separately and is not
counted as a successful full assessment.

Investigation found the benchmark's synchronization barrier held ready provider
connections without sending captured audio. An input-idle timeout is a plausible
cause of the abort; only the exception type was logged, so its precise provider
cause is not proven. The probe now supplies valid silent PCM while waiting for
all thirty streams to begin the spoken fixture, matching ongoing microphone
capture. It does not retry or hide a failed stream. The final public run passed
without provider errors. The reader's existing provider-error path stops capture,
preserves saved progress and asks the learner to restart the microphone; it does
not invent a reading result or silently switch providers.

The browser fixture was also corrected to reject intercepted API requests while
offline (browser offline mode alone does not stop mocked route fulfillment), and
to wait for the actual resume navigation before inspecting restored state.

## Latency and sampled resources

| Public operation | Samples | Mean | p95 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Create session | 6 | 667 ms | 757 ms | 757 ms |
| Start session | 6 | 162 ms | 170 ms | 170 ms |
| Student workflow save | 780 | 163 ms | 321 ms | 691 ms |
| Teacher Pause | 6 | 67 ms | 77 ms | 77 ms |
| Teacher exit interrupt | 6 | 59 ms | 66 ms | 66 ms |
| Teacher recovery validation | 6 | 161 ms | 180 ms | 180 ms |
| Teacher Save & Exit | 6 | 239 ms | 270 ms | 270 ms |
| Student final save acknowledgement | 30 | 167 ms | 448 ms | 491 ms |
| Temporary completion | 30 | 158 ms | 287 ms | 296 ms |
| Teacher End Session | 6 | 8584 ms | 15104 ms | 15104 ms |
| Repeated End Session | 6 | 6842 ms | 11410 ms | 11410 ms |
| Student dashboard | 210 | 2385 ms | 5185 ms | 7346 ms |

Zero server errors does not mean one-second finalization. End Session performs
durable result work and remained the slowest control operation. Stream durations
include real-time input pacing and the benchmark synchronization wait.

Monitoring returned 3 CPU and 3 memory distribution samples in
the public window with one-minute margins. CPU sample means were
2.2%–50.8%; memory sample means were
28.0%–29.4% of the limit. These are sampled means,
not instantaneous peaks. The service retained three minimum/maximum instances,
concurrency 80 and one vCPU/1 GiB per instance, with request-based CPU. Cloud SQL
remained `db-g1-small`, single zone, 10 GiB SSD. No capacity increase or new
production threading/queue implementation was needed for the successful runs.

## Cleanup and reproducibility

All owned synthetic users, login sessions, classes, calendar events, live
sessions, temporary materials and results were removed. All 5 diagnostic
jobs and the candidate traffic tag were removed. Existing private recordings,
student data, database backup and working rollback revision were preserved.

New tools: `tools/benchmark_crla_thirty_resilience.py` (opt-in Cloud Run job,
requires `PABASA_AUTHORIZED_CRLA30_RESILIENCE=30` and generated mono 16 kHz PCM)
and `tools/test_crla_thirty_resilience_browser.cjs` (local fixture with Chrome,
Playwright Core and the existing Python venv). Use the exact deployed image and
its runtime database/secret references for the diagnostic job.

Candidate ID: `2fc6dd8a7167`. Final public ID: `9765e586dc49`. Earlier aborted
public ID: `43b203d11298`. Private aggregate reports, full paginated log summaries,
backup/release state and browser outputs remain under ignored `tmp/`. Source
changes contain no credentials, cookies, recordings or real student records.

These are bounded observations. External providers, networks and infrastructure
can still fail; no simulation proves that future 500/503 errors are impossible.

Follow-up: the seven regression failures are investigated and repaired in
[CRLA seven-test repair](CRLA_SEVEN_FAILURE_REPAIR_2026_10_19.md). That report
records the subsequent release and additional paused-save and legacy-batch
capacity checks. The measurements above remain historical evidence.
