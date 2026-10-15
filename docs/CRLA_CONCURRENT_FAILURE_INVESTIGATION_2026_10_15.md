# CRLA concurrent failure investigation

Investigated October 15, 2026 (Asia/Manila), following a report that 12 students
using Google STT encountered server errors after progressing through CRLA words.
The user confirmed Google STT but did not provide the incident time. The
strongest matching log cluster is October 14, 2026; matching it to the exact
classroom run remains an inference. No student identities, audio, transcripts,
cookies, authentication tokens, or live-assessment identifiers are included here.

Follow-up: local repairs and their measured scope are recorded in
[CRLA connection fix validation](CRLA_CONNECTION_FIX_VALIDATION_2026_10_15.md).

## Findings

**Database connection exhaustion is confirmed in the matching incident.** Cloud
SQL rejected application connections while Cloud Run returned widespread HTTP
500 responses. Google STT also failed separately. This was a shared backend
failure, rather than evidence that one particular CRLA word was invalid.

### Database failures: October 14, 1:46:47–2:19:08 PM Manila

Cloud SQL logs for the connected `pabasa-db-micro` instance contain:

| PostgreSQL refusal | Log entries |
| --- | ---: |
| Remaining connection slots reserved for privileged roles | 1,478 |
| Too many clients | 30 |
| Total | 1,508 |

The application also logged the following exception during instance startup:

```text
django.db.utils.OperationalError: connection failed ...
FATAL: remaining connection slots are reserved for roles with privileges
of the "pg_use_reserved_connections" role
```

Cloud Run request logs on revision `pabasa-01306-8xf`, in the inspected
1:35–3:05 PM Manila window, contain **979 HTTP 500**, **3 HTTP 503**, and
**66 HTTP 502** responses. The 500s span multiple workflows:

| Workflow | HTTP 500 responses |
| --- | ---: |
| Live assessment session polling | 769 |
| Student progress updates | 96 |
| Notifications | 48 |
| Reading transcription | 30 |
| Other endpoints, including reader pages, dashboards, and stream startup | 36 |

These are request counts, not unique students. Logs do not establish that all
12 reported students failed at the same instant. The shared dependency and
overlapping failure window explain how many students could be affected together.
Production Django logs did not expose a traceback for each individual HTTP 500;
not every 500 can be individually attributed to a database refusal.

Cloud Monitoring corroborates pressure on the same database:

- Application database connections rose from 2 at 1:46 PM to 41 at 1:47 PM.
- The highest one-minute application connection sample was 45 at 2:05 PM.
- The highest new-connection metric sample was 431 connections over the
  sampled interval ending 1:47 PM.
- The highest database CPU utilization sample was 77.8% at 1:47 PM.
- The Cloud Run revision reached 3 active instances in the inspected window.

These are sampled metrics, not instantaneous peaks. The configured PostgreSQL
`max_connections` and reserved-slot values were not queried directly; 45 must
not be treated as a verified configured limit.

### Reproduced connection cleanup defect

The current CRLA WebSocket handler calls both `socket_session` and
`validate_socket_ticket` through `sync_to_async(..., thread_sensitive=False)`.
Both functions can query the database. Neither establishes a database cleanup
boundary around that work. The custom WebSocket route bypasses Django's normal
HTTP request lifecycle.

Relevant current source:

- `pabasa_site/pabasa_app/crla_stream.py:358`: session database lookup.
- `pabasa_site/pabasa_app/crla_stream.py:369`: ticket authorization and ORM access.
- `pabasa_site/pabasa_app/crla_stream.py:409` and `:413`: executor dispatch.
- `pabasa_site/pabasa_site/database.py:35`: `CONN_MAX_AGE=0`, with no pool configured.

A disposable SQLite reproduction using **Python 3.13.16, Django 6.0.3, and
20 concurrent executor workers** invoked the actual `socket_session` function
with synthetic, nonexistent session keys:

```text
Concurrent independent workers: 20
Worker DB connections still open after socket_session: 20
Worker DB connections closed by same-worker close_old_connections: 20
```

The database and temporary directory were removed after the run. No production
database or existing local database was used. This is a connection-lifecycle
reproduction, not a PostgreSQL capacity benchmark or a test of 20 authenticated
student assessments. Connections remain attached to executor threads; this does
not establish an unlimited new connection leak on every word.

This defect is a credible contributor to connection exhaustion. Its exact share
of the historical connection total is not established: the historical server
image was not extracted, and live `pg_stat_activity` was not sampled during the
incident.

### Request overlap adds database pressure

The current browser reader polls the session every 2 seconds and publishes a
heartbeat every 2 seconds while reading. Twelve readers therefore schedule
approximately 12 requests/second from these two loops alone, before navigation,
speech, notifications, or teacher requests. Twenty readers schedule about 20.

- `assessment_reader.js:7257`: heartbeat loop; publications are serialized, but
  slow responses can accumulate queued updates.
- `assessment_reader.js:7573`: interval polling has no outstanding-request guard;
  responses slower than 2 seconds allow overlapping polls.
- `views.py:29402`: polling accesses the database and advances session state.

The incident's failing session polls averaged roughly 5 seconds on the main
affected session, making polling overlap plausible. The publicly served reader
JavaScript matched the local source after line-ending normalization when checked.

### Separate speech provider and recording failures

The same revision recorded 66 transcription HTTP 502s between 1:50:02 PM and
2:41:27 PM Manila. The associated split traceback logs contain:

- 21 `google.api_core.exceptions.InternalServerError: 500 Internal error encountered.`
- 45 `google.api_core.exceptions.InvalidArgument: 400 Audio data does not appear
  to be in a supported encoding ...`

The HTTP 502 request latency averaged 25.169 seconds; the maximum was 44.305
seconds. Google errors are surfaced as HTTP 502 by the application's speech view.
The Google error text itself can therefore display “500” while the site's HTTP
response is 502. These errors do not, by themselves, explain the widespread
session/dashboard HTTP 500s.

Invalid audio is not proof of a Google quota problem. The exact malformed-audio
trigger has not been reproduced. Recorder ownership and chunk lifecycle around
navigation should be tested with synthetic audio; shared recorder/chunk state
is a code-review lead, not a confirmed incident cause.

Six later completion errors reported `TypeError: Object of type datetime is not
JSON serializable` while saving material completion data. These are a separate
completion concern and do not explain the earlier mid-reading failure cluster.

## Deployment verified during investigation

- Cloud SQL: `pabasa-db-micro`, PostgreSQL 18, `db-g1-small`, single zone,
  10 GiB SSD; state RUNNABLE.
- Both incident revision `pabasa-01306-8xf` and current revision
  `pabasa-01307-zkm`: 1 vCPU, 1 GiB, concurrency 80, maximum 3 instances.
- No container command/argument override was configured. Incident request logs
  confirm Uvicorn. The current Dockerfile starts ASGI and retains both migration
  readiness guards; the Procfile's 16 Gunicorn threads do not describe this runtime.
- Current revision `pabasa-01307-zkm` was created October 14 at 3:09:58 PM
  Manila and had 100% traffic when checked.
- Incident image digest:
  `sha256:676db7d6f9ab841feff4b7141a5a6737adaf34417c8353de3a7a6da8093fdbd5`.
- Current image digest:
  `sha256:b36972cd16d14d19d5183efe7cdecefbc27746e10a886349601469e16b6350ce`.
- A non-capped sample of 3,747 current-revision requests, October 14 3:13:32 PM
  through October 15 7:28:09 AM Manila, contained no HTTP 5xx. This is not
  evidence that the newer revision can sustain the reported classroom workload.

## Recommended repair and validation

1. Wrap WebSocket ORM operations with cleanup before execution and in `finally`,
   **inside the same synchronous worker**. Cover successful authentication,
   rejected tickets, exceptions, cancellation, and reconnects. Closing connections
   from the event loop or a different worker will not close the original thread's
   connection.
2. Introduce a bounded PostgreSQL connection budget across all instances,
   overlapping revisions, and jobs. Evaluate Django's psycopg pool (including
   the required pool dependency), and tune Cloud Run concurrency against measured
   database capacity. Keep `CONN_MAX_AGE=0` for ASGI. Increasing the database tier
   or connection limit alone would leave the cleanup defect in place.
3. Prevent overlapping session polls; apply bounded backoff after failures and
   coalesce redundant heartbeat updates while preserving recovery snapshots,
   scores, terminal transitions, and school/class authorization.
4. Reproduce invalid audio with synthetic recordings across item navigation,
   microphone toggle, stream-start fallback, and stop/restart. Keep selected
   Google provider/language and existing scoring behavior. Provider failures must
   leave an explicit retry path without fabricating a score.
5. Validate with **20 distinct authenticated student accounts enrolled in the
   tested roster**, exercising words, navigation, progress/recovery, actual Google
   STT, and completion. Measure backend connections, latency, failures, and cleanup
   after disconnect/reconnect. The local lifecycle reproduction is insufficient
   for this capacity claim.

No application patch, database migration, deployment, traffic switch, cloud
configuration change, or production load test was performed during this
investigation. The only repository change is this report.

## Primary technical references

- [Django database connection management and PostgreSQL pooling](https://docs.djangoproject.com/en/6.0/ref/databases/)
- [Database cleanup around asynchronous consumers](https://channels.readthedocs.io/en/stable/topics/databases.html)
  (The application uses a custom ASGI route, not Channels; this documents the
  cleanup behavior missing from bare `sync_to_async`.)
- [Cloud SQL connection management](https://docs.cloud.google.com/sql/docs/postgres/manage-connections)

Evidence was collected through read-only Cloud Run/Cloud SQL Logging queries,
Cloud Monitoring time-series reads, revision/service descriptions, and inspection
of public static JavaScript. Raw logs and metric authentication material were
not saved to the repository.
