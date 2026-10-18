# CRLA End Session errors and refresh recovery

Investigated October 18, 2026, using read-only Google Cloud CLI queries and local
source inspection. The user identified the incident as last Friday, October 16.
All times below are Asia/Manila. No deployment, scaling change, production write,
authenticated browser session, or load test was performed.

## Finding

**Friday's logs show End Session completion work followed by database pool
exhaustion on one serving instance. The assessment page failed on that instance
while succeeding on two others. A refresh can recover by reaching one of those
healthy instances; it does not repair the exhausted instance.**

This is a strong match to the reported symptom, not identification of a particular
student's browser. The user did not provide an exact incident time or screen.
Request logs do not expose the action POST body, but application markers in the
same window explicitly identify the End Session completion path.

## Friday evidence

Revision: `pabasa-01312-hsh`. Instance names below are arbitrary labels based on
distinct Cloud Run instance IDs, not student or account identifiers.

| Time | Evidence |
| --- | --- |
| 2:16:26.263 PM | Live-session action request on instance A returned HTTP 200 after 5.538 seconds. This timestamp is request start, not response completion. |
| 2:16:26.515–2:16:29.515 PM | Five `end_session_complete_call` markers on instance A. Five notification-queued markers also occurred in this action window. These are completion calls, not a count of classroom enrollment. |
| 2:16:33.045–2:16:33.197 PM | Four background notification callbacks logged total durations of approximately 1.37–1.52 seconds on A. Timing markers alone do not establish successful notification delivery. |
| 2:16:33.213 PM | `/dashboard/assessment/` on A returned HTTP 503 after 10.012 seconds. |
| 2:16:32.579–2:16:33.986 PM | Four requests to the same assessment-page path on B/C returned HTTP 200 in approximately 1.43–1.71 seconds. |
| 2:16:36.715 PM | A logged `Failed to create assessment completion notifications` and `psycopg_pool.PoolTimeout: couldn't get a connection after 5.00 sec`. The fifth callback's total duration was 5.034 seconds. |
| 2:18:49.367 PM / 2:18:50.866 PM | Assessment-page HTTP 503 on A, then HTTP 200 on C about 1.5 seconds later. |
| 2:20:16.273 PM / 2:20:17.548 PM | Assessment-page HTTP 503 on A, then HTTP 200 on B about 1.3 seconds later. |
| 2:28:03.992 PM | A also returned HTTP 500 on `/api/login/`. The request record alone does not establish its exact exception. |

The traceback on A explicitly includes `_run_completion_notifications` and
`_notify_principal_performance_events`, then Django's PostgreSQL connection
acquisition and psycopg pool checkout. The split traceback was correlated within
the same instance and millisecond, not inferred from HTTP status alone.

Later successes share a network address and browser user-agent with failed
requests. A classroom can share both, so this cannot establish a particular
student's refresh. It nevertheless demonstrates that the same page could work
immediately when another instance handled the request.

The complete October 16 Manila-day HTTP-500 query returned one record, the login
failure above. The matching End Session/assessment-page incident primarily used
HTTP **503**, although the user described the visible error as “500.” No screenshot
or response body was available to establish the exact wording shown to the user.

## Mechanism and source

The local active application still contains the relevant lifecycle defect:

- `pabasa_site/pabasa_app/views.py:27886`: `_run_completion_notifications` performs
  ORM queries. Its `finally` block logs timing but does not return its database
  connection.
- `views.py:27986`: `transaction.on_commit` starts a raw daemon thread for each
  qualifying completion. Such threads do not receive Django's ordinary HTTP
  request connection cleanup.
- `pabasa_site/pabasa_site/database.py`: default pool maximum is six connections
  per process, checkout timeout five seconds, queue maximum 32.
- `pabasa_site/pabasa_site/errors.py`: uncaught pool exhaustion becomes retryable
  HTTP 503, including for full-page requests.
- `pabasa_site/pabasa_app/static/pabasa_app/js/assessment_reader.js`:
  `showLiveSessionEnded` stops polling/recording and redirects students to
  `/dashboard/assessment/` after three seconds. That page needs database access
  precisely when completion callbacks are competing for connections.

This explains why the error can appear **after** a successful teacher action:
the subsequent student navigation is a separate request and can fail independently.
HTTP 200 on the teacher action is not independent verification of every result
or notification side effect.

Refresh creates another request. Friday's A/B/C comparison supports recovery
through a different instance. It does not show that refresh releases leaked
connections, that all results were saved, or that A recovered. Fast later 503s
alone do not identify their exception; the notification timeout is the directly
confirmed database exception in this window.

The local checkout is not a verified byte-for-byte copy of Friday's image. The
runtime traceback confirms that Friday executed the named notification functions;
the local source and the earlier PostgreSQL lifecycle experiment explain the
connection-retention mechanism. See `CRLA_CAPACITY_INVESTIGATION_2026_10_15.md`
for that separate experiment; it was not repeated against production here.

## Current configuration, checked October 18

- Service `pabasa`, region `asia-southeast1`, revision `pabasa-01318-lvb`, 100% traffic.
- Revision created October 17 at 1:22:55 AM Manila.
- Image digest `sha256:9c9410e80dc5aa849a5b37960b2ac2d49d71e11a1bcf6f6d7d7df68efc17e2cc`.
- Service minimum three, maximum 20. Revision annotations minimum zero, maximum 20.
- Per-instance concurrency 80, 1 vCPU, 1 GiB, request-based CPU allocation;
  session affinity disabled. No container command/argument override was reported.
- Connected Cloud SQL `pabasa-db-micro`: PostgreSQL 18, `db-g1-small`, zonal,
  10 GiB storage, state RUNNABLE. Current SQL connection limits were not queried.
- The current-revision HTTP 5xx/severity ERROR query returned no entries. Its
  live-assessment action query within the October 14-onward scan also returned
  none. This provides no evidence of a successful current-revision classroom run.

Twenty maximum instances is a ceiling, not a repair. Friday's relevant requests
demonstrate three serving instances with different outcomes. More instances may
provide additional healthy destinations while increasing the aggregate database
connection budget; neither effect corrects background-thread cleanup.

## Repair and validation needed

1. Establish database cleanup in the owning background worker on entry and in
   `finally`, covering successful work and exceptions. Bound notification work
   rather than starting an unbounded number of raw threads. Preserve notification
   delivery and result authorization/scoring.
2. Investigate the long connection-holding finalization work and keep optional
   email work outside the critical database transaction where appropriate.
3. Make retryable failures during post-end navigation recover gracefully without
   forcing manual refresh, while still reporting an unsuccessful save honestly.
4. Verify with the repository-standard 20 distinct enrolled clients first, then
   explicitly validate the user's 30-student classroom workload, including real
   speech, End Session, final result persistence and post-end navigation. No new
   production benchmark was authorized or run in this investigation.

## Query scope and privacy

CLI access checked the active account, service/traffic, serving revision and SQL
instance. Logs were read with `gcloud logging read`, explicit project/service
filters, bounded time windows and limits. Targeted queries for Friday's HTTP 500s,
the 2:16 PM dashboard requests, completion markers, and the timeout's split
traceback did not hit their limits. The initial broad error query hit 4,000 entries
and is not presented as a complete incident total. A separate generic traceback
query hit 150 and was replaced by targeted pool/finalization queries.

No raw logs, network addresses, browser fingerprints, cookies, student identities,
assessment content, recordings, or results are saved in this report.
