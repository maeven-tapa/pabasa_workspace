# Prescribed materials: HTTP 500 repair and 30-student validation

Measured October 18, 2026. The new release serves https://tupcpabasa.app.
The user's explicit request for 30 students governs this new probe; historical
20-client scripts and reports retain their original scope.

## Findings and changes

Three error paths were reproduced locally before repair: a teacher opening a
recording whose file was missing raised `FileNotFoundError`; malformed progress
JSON reached code expecting an object; and Session 5 recording durations could
fail conversion or violate database constraints after writing a file. The
pre-change regression run produced ten failing subcases across three tests.

Teacher recording playback now checks the existing teacher/roster permissions
and returns 404 for a missing file. Successful playback is private and not
cacheable. Progress/completion JSON must be an object, and Session 5 validates
duration, item, UUID, and file size before writes. These changes do not turn
missing audio or provider failures into a successful reading result.

Session 5 reserves an attempt UUID before replacing audio, locks the parent
student to serialize first uploads, and makes retries idempotent. A UUID owned
by another student cannot mutate the current submission. Replacement retains
files referenced by immutable attempt history. Optional acoustic diagnostics
run after commit through the existing bounded queue: one follow-up thread per
process, capacity 64. Required recordings and submission state commit in the
request. This queue is best effort, not a durable broker; shadow analysis does
not determine grades or teacher approval.

Previously uncovered dedicated speech calls now return their database
connection and HTTP admission slot while waiting for Google or Knowlez, then
reacquire admission before accessing the database. Atomic callers retain their
transaction. Thirty blocked dedicated Lesson 1 calls were tested through real
Django ASGI while another request remained available. The selected speech
provider/language and failure behavior are preserved.

The seven-day request-log investigation found 36 prescribed-material HTTP 503s,
all on older revision `pabasa-01312-hsh`, and no prescribed-route HTTP 500s in
that historical sample. Shared transcription endpoints also had historical
errors, but route-only logs cannot identify which curriculum generated them.
The reproduced failures above establish possible 500 paths; they do not prove
the exact cause of every historical report.

## Shared private recording storage and recovery limits

The previous serving revision had no shared media mount. FileField recordings
were stored on temporary instance disks, so another instance or a replacement
instance could find a database reference without a file. Refresh could change
the instance handling playback without repairing storage.

The release sets `DJANGO_MEDIA_ROOT=/app/media` and mounts private Cloud Storage
bucket `pabasa-prescribed-recordings-2b0d295d` there. Uniform bucket access and
public-access prevention are enabled. The runtime identity has bucket-scoped
`roles/storage.objectUser`; playback continues through authenticated Django
views. Generation 2 is used for the mount. Metadata cache TTL is zero and
negative type caching is disabled so recordings are visible across instances.
See the [official Cloud Run storage-mount documentation](https://docs.cloud.google.com/run/docs/configuring/services/cloud-storage-volume-mounts).

Before public traffic moved, the user authorized preserving existing audio. The
audit found **22 recording references**, zero reading-attempt audio references,
and no additional populated story-response/PDF fields in the migration snapshot.
None of those 22 files had a matching copy in the serving image or local recovery
sources. Twenty references had no currently authorized active-roster teacher
for legacy playback. The other two could not be read across repeated fresh
connections to the old service. Two bounded preservation attempts each logged
18 old-revision HTTP 500 responses; these are intentional legacy recovery reads,
separate from the synthetic capacity results below.

**No old audio file was recovered.** All 22 original database file references
were retained, and the recovery manifest is in the private bucket. This is a
recovery limitation, not evidence that all 22 were independently readable before
the switch or that an external backup cannot exist. No existing student rows,
grades, enrollments, or recording references were changed to grant access.
Temporary migration sessions were removed. Future FileField recording uploads
use shared storage. Docker build exclusions also cover local runtime media and
test outputs.

## Capacity evidence

Both completed runs used 30 distinct disposable students in one class, one
synthetic teacher, isolated calendar events, and finalized synthetic CRLA
eligibility. Earlier prescribed activities were seeded only for these accounts
to exercise later activities without changing real unlock settings or dates.
The probe used generated speech, not children's audio. Teacher reviews used an
explicit synthetic score of zero and did not simulate successful reading grades.

| Run | Request window, UTC | Operations | Observed statuses | Failures/retries |
| --- | --- | ---: | --- | --- |
| Private revision | 04:28:35–04:29:55 | 1,080 | 990 × 200, 30 × 101, 60 × expected 400 | 0 / 0 |
| Public site | 04:37:38–04:39:24 | 1,110 | 990 × 200, 30 × 101, 60 × expected 400, 30 × expected 404 | 0 / 0 |

Complete paginated Cloud Run logs matched both operation counts across **three
serving instances**. Each successful run had zero ERROR logs, HTTP 500/503s,
pool timeouts, streaming-failure warnings, or follow-up-worker failures in its
bounded window.

Each run verified:

- Thirty logins, dashboard/activity pages, resets, and simultaneous ready
  prescribed WebSockets using real Google Chirp 3 with English recognition.
- Complete-utterance tokens evaluated through the real shared HTTP evaluator;
  all thirty recognized the five-word generated verse. Thirty standalone
  uploaded clips also used the real provider, without retry or provider switch.
- Lesson 13 Activity 1: four uploads per student, **120 teacher playbacks checked
  by audio SHA-256**, 120 teacher reviews, progress saves, thirty completions,
  thirty completion replays, and thirty return-page requests.
- Thirty Session 5 attempt uploads and idempotent replays; thirty unique attempt
  rows with completed queued acoustic analysis. Pending teacher-review behavior
  was retained.
- Thirty invalid-duration requests and thirty non-object JSON requests returned
  400. The public run additionally created thirty disposable missing-file
  references; authorized teacher playback returned 404 for every one.
- Thirty completed activities, 120 reviewed recordings, and all thirty student
  sessions still present before cleanup. All 150 generated files and all test
  users/sessions were removed. The public run also removed its thirty missing
  file references.

An initial public run had no HTTP 5xx but **four Google `Aborted` streaming
failures**. Its artificial readiness barrier held early streams without sending
audio. The corrected probe sends real-time silent PCM while waiting for all
thirty, then sends the same generated utterance; its full run above passed
without retries. The idle-barrier explanation is an inference consistent with
[Google's streaming input timing requirements](https://docs.cloud.google.com/speech-to-text/docs/quotas)
and the successful correction. Those initial failures are not counted as a
passing run or hidden by client retries.

The public run's latency includes waiting in the bounded request queue:

| Operation | Samples | Mean | p95 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Progress/resume | 30 | 0.319 s | 0.570 s | 0.572 s |
| Finish | 30 | 0.392 s | 0.643 s | 0.681 s |
| Finish replay | 30 | 0.366 s | 0.717 s | 0.721 s |
| Recording playback | 120 | 0.869 s | 1.431 s | 1.749 s |
| Standalone speech clip | 30 | 2.234 s | 2.847 s | 2.866 s |
| Recording upload | 120 | 3.347 s | 6.576 s | 8.263 s |
| Session 5 attempt upload | 30 | 3.907 s | 6.648 s | 6.802 s |
| Dashboard after finish | 30 | 3.023 s | 5.084 s | 5.189 s |
| Initial dashboard | 30 | 4.043 s | 9.944 s | 10.918 s |

Successful concurrency is not a one-second latency guarantee: uploads and
dashboard rendering remain slower than state saves. Streaming time includes
provider setup, the readiness barrier, real-time audio, and final recognition.
This exercises selected prescribed workflows, not every curriculum activity,
every browser/device, long recordings, or an indefinitely sustained class.

## Local validation

- **80 focused Django tests passed**, covering the new failures, ASGI admission,
  speech providers, prescribed lifecycle/streaming, audio features, and attempts.
- **Six additional queue and Session 4 recording-integrity tests passed.**
- **Thirty concurrent Chrome recording/evaluation flows passed** through the
  actual English Read UI, AudioWorklet PCM, real Uvicorn WebSocket, mocked Google,
  signed-token HTTP evaluation, cursor save and one verse completion per client.
  Every microphone stopped; all thirty captures connected before any final
  result. A separate single-browser functional run also passed.
- Django system check, Python compilation, `makemigrations --check --dry-run`,
  and whitespace checks passed. No models or migrations changed.
- A wider existing prescribed suite had 16 failures and 11 errors in 397 tests
  before this work. After the six new regression tests, 403 tests had the same
  failure/error set. Those existing lifecycle/action/fixture conflicts remain;
  grading rules were not relaxed to make them pass.

The browser harness was updated for the current continuous reader API and its
separate cursor-save and verse-completion requests. Its synthetic input loops
so a later Chrome context does not start after a finite fixture has run out.
Provisional updates are required, alongside exact final scoring and exactly one
evaluation; their callback count can vary with stream timing.

## Release and operational checks

Active revision: `pabasa-01339-pas`, 100% public traffic.

Exact image digest:
`sha256:0cb33f804a6689036efaac97cb15415cb7aca514413e564d51f984dc6b377f6a`.

The image overlays only the four changed production Python files on the verified
previous serving image. Current local production source matches the built patch.
Build `7ed9184c-4dfa-4e54-b5e5-34f6a1ba2d58` succeeded. The exact new image passed
`check_migration_readiness --require-recorded`, verified an empty migration plan,
ran the no-op migration command, and passed `migrate --check` in release job
`pabasa-prescribed-readiness-846f99b1` before candidate activation. Existing
startup readiness/migration guards and Uvicorn ASGI command are retained.

Rechecked settings: Cloud Run service and revision minimum/maximum **3/3**, one
vCPU and 1 GiB per instance, concurrency 80, request-based CPU, timeout 300 s.
The application admits four database-using HTTP requests per process against a
six-connection process pool, releasing admission during external speech I/O.
Cloud SQL remains PostgreSQL 18, `db-g1-small`, zonal, 10 GiB SSD, with 50 total
connections and three reserved. A post-test audit saw 23 connections; that is a
snapshot, not a peak. Three pools have an 18-connection ceiling; twenty such
pools could request 120 connections against 47 ordinary slots. The number of
students should not be equated with the number of server instances.

There were no schema changes or database reversals. Previous working revision
`pabasa-01335-coy` is retained for traffic rollback. A rollback must retain shared
media configuration or explicitly account for recordings uploaded to the bucket;
the older revision does not itself mount it. The earlier database backup
`1792258090437` was not modified by this release.

Post-test database audit: zero synthetic users, calendars, or schools remain;
one orphaned calendar from an early fixture-cleanup failure was removed after
verifying it had no users, enrollments, sections, or progress. All 22 original
recording references remain. Diagnostic jobs and the test traffic tag are
removed after collecting evidence. The private media bucket and recovery
manifest are retained.

No finite test can establish that HTTP 500/503 will never occur. These results
establish the reported fixes and the measured 30-student scope at this release.
