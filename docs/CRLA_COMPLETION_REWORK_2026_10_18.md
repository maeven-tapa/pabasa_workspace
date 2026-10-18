# CRLA completion repair and 30-student verification — October 18, 2026

The repair is serving https://tupcpabasa.app on `pabasa-01335-coy` at
100% traffic. The public-domain test completed 996 operations
with zero failed responses, zero transport retries, 30 persisted completed results,
three ended sessions and all 30 student logins preserved. The matching Cloud Run
request logs independently confirm the response counts. These are bounded synthetic
tests, not a guarantee that a future 503 can never occur.

## What changed

- Completion notifications, progress emails and material follow-ups now share one
  bounded worker per process. Every callback closes its Django database connections
  on entry and in `finally`, including after failure. Work is submitted after commit.
- Assessment results and terminal session state remain committed in the request.
  Optional work is in-process and best effort; it is not a durable task broker and
  does not establish guaranteed email delivery during instance termination.
- ASGI HTTP admission waits before Django starts a request worker or checks out a
  connection. With a six-connection pool, four HTTP requests enter at a time.
  Speech uploads release their connection and admission slot only after validation,
  while the selected Google or Knowlez provider runs, and reacquire admission before
  scoring or session middleware can use the database. WebSocket routing is retained.
- Active enrollment lookups use filtered joins rather than scanning every section.
  The official completion selector uses `Exists` instead of a reverse material join
  and wide-row `DISTINCT`. Boolean checks read classifications without content JSON.
  The live roster completion indicator batches scalar result reads while retaining
  each student's calendar and the original classification precedence.
- The reader waits for acknowledged completion before navigating, retries the final
  idempotent live snapshot with bounded delay, blocks navigation after a failed save,
  coalesces duplicate clicks, stops recording and staggers return navigation by about
  one second. Safe HTML page loads have bounded recovery; POSTs are not automatically
  replayed by the busy-page script. An unsuccessful save is displayed honestly.

Friday's notification-thread pool exhaustion and refresh recovery were documented
separately in `CRLA_END_SESSION_REFRESH_INVESTIGATION_2026_10_18.md`. Increasing the
instance ceiling did not correct connection cleanup in the owning worker.

## Deployment and database budget

- Project `project-2b0d295d-ee06-40a7-927`, service `pabasa`, `asia-southeast1`.
- Image: `asia-southeast1-docker.pkg.dev/project-2b0d295d-ee06-40a7-927/cloud-run-source-deploy/pabasa_workspace/pabasa@sha256:31f988c0ee0a54f1ea8a96ad52b2e5e5e5320c2f6b726e4d90fe8a15c3cb6278`.
- Service minimum/maximum **3/3**; revision minimum/maximum **3/3**.
- Per-instance concurrency 80; 1 vCPU, 1 GiB, request-based CPU; timeout 300 s.
- The inherited Docker command runs Uvicorn/ASGI with the existing readiness and
  `migrate --check` startup guards. No worker-count override was introduced.
- Cloud SQL remains PostgreSQL 18, `pabasa-db-micro`, `db-g1-small`, zonal, 10 GiB.
  No SQL tier, disk, CPU or memory resize was made.
- SQL reports 50 connections, three reserved: 47 ordinary slots. Three processes
  with pool maxima of six have a potential steady pool budget of 18. Twenty
  instances could have a potential budget of 120, exceeding that database limit.
  These are configured ceilings, not measurements of simultaneously open connections.
- Backup `1792258090437` succeeded before the additive pending migration
  `0033_student_achievement_awards` created its two tables. The exact release digest
  passed readiness, migration and `migrate --check` in a Cloud Run Job before traffic.
  No model or migration source changes were needed for this repair.
- Canary verification preceded traffic activation. `pabasa-01318-lvb` is
  retained for traffic rollback; database migrations were not reversed.
- Builds applied a bounded patch to the pinned registry image after source preflight,
  preserving unrelated runtime source differences. Credentials, local recordings,
  runtime data and unrelated untracked files were excluded from the release overlay.

## Test scope

The public run used **30 distinct disposable enrolled student accounts**, three
teacher accounts and three legitimate ten-student live sessions. All 30 speech
WebSockets reached ready together before audio was sent. Generated English speech
then exercised real Google Chirp 3, signed evaluations, 30 general recorded uploads
and 30 official CRLA WebM/Opus uploads. All returned the expected six-word result.
Student polling continued during recording and teacher End Session. The probe also
covered real login POSTs, reader and assessment pages, progress updates, completed
snapshots, final result persistence, repeated post-end polls and retained login sessions.

The separate single-class run used one 30-student roster with the product's three
ten-student batches. It completed 1356 operations without a failure
or transport retry, persisted all 30 results and preserved all 30 logins. It did not
bypass the product's ten-student active-batch rule. It ran on the same final digest.

The cloud speech fixture was generated audio, not student recordings. The finalization
fixture used deterministic zero-score temporary completion snapshots, separately from
the six-word speech checks. This validates transport, scoring-response handling and
result lifecycle under this load; it is not a complete curriculum assessment by real
children, nor evidence about classroom devices, Wi-Fi or recognition accuracy across
30 different voices. Browser microphone coverage was performed separately below.

Public run: **October 18, 2026 11:39:30 AM to
October 18, 2026 11:41:32 AM, Asia/Manila**.

| Operation | Count | Mean | p95 | Maximum | Failures |
| --- | ---: | ---: | ---: | ---: | ---: |
| login | 30 | 4.10 s | 8.11 s | 8.61 s | 0 |
| start | 3 | 0.25 s | 0.29 s | 0.29 s | 0 |
| reader | 30 | 0.53 s | 0.92 s | 0.92 s | 0 |
| ticket | 30 | 0.75 s | 1.37 s | 1.39 s | 0 |
| stream | 30 | 14.98 s | 15.02 s | 15.23 s | 0 |
| evaluate | 30 | 1.56 s | 2.62 s | 2.92 s | 0 |
| clip | 30 | 3.04 s | 3.80 s | 3.87 s | 0 |
| crla_clip | 30 | 2.94 s | 3.67 s | 4.03 s | 0 |
| update | 90 | 0.20 s | 0.37 s | 0.41 s | 0 |
| complete | 30 | 0.17 s | 0.27 s | 0.31 s | 0 |
| end | 3 | 12.54 s | 18.95 s | 18.95 s | 0 |
| dashboard | 90 | 2.29 s | 4.03 s | 4.69 s | 0 |
| poll | 240 | 0.15 s | 0.34 s | 0.39 s | 0 |
| post_end | 330 | 0.95 s | 1.55 s | 2.43 s | 0 |


Stream durations include connection setup, the all-ready barrier, real-time audio
pacing and the provider response; they are not isolated provider processing times.

The single-class bulk End Session took **20.55 s**.
Its post-end polls had p95 **5.67 s** and
maximum **15.69 s**. The public dashboard
figures combine the pre-session and two post-session page waves. There is no claim
that every operation finishes within one second; the navigation delay is a small
stagger to reduce synchronized bursts.

## Validation and investigation evidence

- **104 focused Django tests passed**, covering queue cleanup and saturation,
  commit/rollback, ASGI admission and cancellation, 20- and 30-client reconnects,
  database configuration, authorization-sensitive enrollment lookup, result selection,
  live completion/export, Google/Knowlez provider behavior and calendar boundaries.
- **21 JavaScript tests passed** for completion/navigation recovery, request pressure,
  recorder events and story timers.
- **30 concurrent local Chrome capture lifecycles passed**: fake-device microphone,
  AudioWorklet PCM, real Uvicorn WebSockets, mocked provider, signed final and shared
  evaluator, with all 30 captures connected before any final. Provider transports
  were closed. Database access was forbidden for that local streaming test.
- Existing local Chrome recorder tests passed words, rhymes, sentences and story
  stages using non-silent generated WebM, including flush, transition and release.
- Django `check`, `makemigrations --check --dry-run` and `git diff --check` passed.
- Broader shared tests are not wholly green: 63 tests retain the same three failures
  and one error reproduced on the unchanged baseline (61 tests before two new selector
  cases). They concern active-enrollment material assignment and class CRLA finalization
  or export. Scoring or authorization rules were not loosened to make them pass.
- An older `test_crla_live.cjs` harness has 23 of 29 failures on both baseline and
  current source because its mocks omit current globals; it is not reported as passing.
- Before pushing, the commit was rebased onto upstream's Session 6–7 audio fix.
  Its Basahin tests report ten failing `KARITON`/`carton` subcases. The same ten
  failures were reproduced using the unchanged upstream transcription function;
  no spelling or grading rules were changed as part of this repair.

Early canaries exposed real problems and were stopped before public activation:
six dashboard 503s before admission control, then nine general-upload 503s before
provider connection/slot release. Another probe stopped on a transport disconnect
without an HTTP error. Later complete runs needed no transport retries. A slow
error-free run was not used as evidence of fast capacity: SQL profiling identified
the wide completion query, which fell from approximately 230–440 ms to about 8 ms
in separate single-page profiles. Those profiles are not concurrent-load evidence.

The public test and final single-class test each have independently counted request
logs, three observed serving instances, and no ERROR, pool-timeout or follow-up-failure
entries in their bounded windows. Request counts include HTTP and WebSocket upgrades.
The benchmark does not retry HTTP 5xx responses. Its one permitted transport-only
speech retry is separately reported; neither accepted final run needed it.

## Cleanup and reproducibility

All runs deleted their disposable sessions, notifications, activity logs, users,
classes, school, cloned material and cascading results. An independent cleanup job
checked 10 run identifiers and found zero remaining synthetic users,
schools, materials, live sessions, enrollments, assessment roots or login sessions.
Owned diagnostic Cloud Run Jobs and the temporary canary tag were removed. The
database backup and working rollback revision were retained.

`tools/benchmark_live_crla_thirty.py` is an opt-in Cloud Run diagnostic job script.
It requires `PABASA_AUTHORIZED_CAPACITY_TEST=30`, the intended image/database identity
and generated PCM. Its default is three classes; `PABASA_BENCHMARK_CLASSES=1` uses
one roster in normal batches. Historical 15- and repository-standard 20-client reports
were preserved. No raw student data, credentials, session cookies, recordings or
private response bodies are included in this report.
