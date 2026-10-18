# Four teachers with five CRLA students each

Investigated October 19, 2026 (Philippine time) against https://tupcpabasa.app.
Final run: **2026-10-19 04:25:19 PHT through 2026-10-19 04:26:44 PHT**.

## Result

The final **four-teacher / twenty-student** live lifecycle test passed:

- **1,240 requests/connections**, all matched by paginated Cloud Run request logs:
  1,196 HTTP 200, 20 successful WebSocket upgrades, and
  24 expected authorization refusals. **Zero HTTP 500/503 or other unexpected failures;
  zero transport retries.**
- Four teacher-created sessions started and ended successfully. Each class had
  five distinct, actively enrolled synthetic students. All twenty were active
  together; this was not twenty sessions sharing one student or one teacher.
- **20 classified results, exactly one per student**, five per class. All twenty
  referenced the correct enrollment. No official results existed before teacher
  End Session. Repeating End Session created no duplicate results.
- All twenty student logins and all four teacher logins remained valid before cleanup.
- **20 simultaneous real Google speech streams**, twenty accepted signed
  evaluations and forty generated WebM/Opus uploads (twenty on each clip path)
  succeeded. Every evaluated synthetic utterance scored its six target words.
- Cloud logs showed **zero ERROR events, database pool failures, background-worker
  failures or streaming-failure warnings** in the final window, across
  **3 serving instances**.
- Temporary accounts, authentication sessions, live sessions and cloned material
  were deleted and counted as zero remaining. All 11 owned
  diagnostic jobs and both temporary private source archives were deleted.

An earlier complete run also passed all 1,260 operations,
result/enrollment checks and cleanup, with no HTTP 500/503s. Its test socket closed
after receiving a signed final but before the provider's finished message,
producing ten `ClientDisconnected` warnings. The benchmark now drains that
finished handshake; the final run above had none. These were not failed
recognitions: all twenty signed results were evaluated successfully in both runs.

## What was exercised

Four independent synthetic teachers created their own sessions through
`/dashboard/teacher/start-live-assessment/`, selected their own five enrolled
students, and started through the normal action endpoint. Teacher control,
student dashboard, invitation, reading and waiting-room HTML endpoints rendered
successfully with separate authentication sessions.

Twenty student workers synchronized speech and state requests; four independent
teacher controls exercised Pause/Resume and End Session. Writes sent while paused
were ignored without moving the saved cursor. Reading workflow snapshots covered
ten words, transition to five sentences, story selection/readiness/segments,
three comprehension positions, learner rating and temporary completion. Late
heartbeats could not reopen completed students. Students kept polling while all
four teachers ended their sessions, then continued opening dashboards and
checking ended state while optional work completed.

Four cross-class teacher attempts and twenty student attempts to invoke End
Session correctly returned HTTP 403. No student or other class was changed by
those attempts.

The HTTP workflow snapshots are **simulated assessment evidence for disposable
accounts**. Real Google recognition used a generated six-word English fixture,
not every official CRLA item or a real child's microphone. Recorded clips were
generated from that fixture; no existing recordings were accessed. This test
does not establish recognition accuracy for all classroom microphones/languages.

## Browser validation

`tools/test_crla_four_teachers_browser.cjs` passed with **twenty independent
Chrome contexts, grouped into four classes of five**. It used actual
Django-rendered templates and the complete reader JavaScript from the serving
release (`ce07c811`), whose reader SHA-256 was checked against the public asset.

Every reader completed ten words, five sentences, story reading, two unanswered
comprehension questions, a learner rating and waiting-room navigation. Reloading
both section-completion screens preserved progress. Each class retained exactly
its five students; unanswered comprehension results stayed null. There were no
page exceptions or premature official completion writes.

This browser check uses controlled speech results and synthetic APIs. The real
authenticated web/database/provider endpoints were exercised separately by the
live probe described above. It does not claim twenty live browser microphones
or four teachers clicking browser controls in the same automated run.

## Latency and resources

| Operation | Samples | Mean | p95 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Teacher creates session | 4 | 501 ms | 508 ms | 508 ms |
| Teacher starts session | 4 | 142 ms | 150 ms | 150 ms |
| Student workflow save | 500 | 125 ms | 223 ms | 420 ms |
| Student temporary completion | 20 | 195 ms | 395 ms | 437 ms |
| Teacher End Session | 4 | 5946 ms | 9568 ms | 9568 ms |
| Repeated End Session | 4 | 4991 ms | 8046 ms | 8046 ms |
| Student dashboard | 140 | 1516 ms | 2591 ms | 3014 ms |
| Generated recorded upload | 20 | 2539 ms | 3218 ms | 3269 ms |
| Generated CRLA recorded upload | 20 | 2474 ms | 2926 ms | 2955 ms |

End Session succeeded, but takes several seconds under simultaneous finalization;
zero server errors should not be read as a one-second response-time claim.
The recorded upload measurements include provider processing. Stream durations
also include real-time audio pacing and are not HTTP processing latency.

Monitoring provided 2 CPU and 2 memory distribution samples in
the window spanning one minute before/after this run. CPU sample means ranged
from 18.3% to 44.0%; memory sample means ranged from
27.2% to 27.5% of the configured limit. These are sampled
distribution means for the serving revision, not instantaneous peaks or an
isolated measurement excluding all other traffic.

Rechecked serving configuration: `pabasa-01346-rew`, 100% public traffic,
image `sha256:4e5455af9ad713f45bfcc9a68fd153e5015f100c1950f2ed85908acb7589ddb9`; three minimum/maximum instances, concurrency
80, one vCPU/1 GiB each, request-based CPU. Cloud SQL was RUNNABLE on
`db-g1-small`, single zone, 10 GiB SSD. No service limits, SQL sizing, startup
guards, schema or production application code were changed for this test.

## Investigation findings and diagnostic corrections

1. **Registry retention is too aggressive for release recovery.** Artifact
   Registry's `delete-old` policy deletes images older than 1,800 seconds, with
   `tagState=ANY`; `keep-latest` protects only one version. The serving release's
   digest was already absent. Two attempted diagnostic job creations failed
   with image-not-found before any assessment traffic. Retain serving and
   rollback images before the next release. This policy was inspected and
   documented, not changed by this assessment test.
2. **Use source matching the live schema for diagnostics.** An available later
   image contains unapplied migration/model changes, including an
   `AssessmentRequest.live_session` field absent from the live database.
   An initial completed web run's diagnostic ORM cascade failed during cleanup;
   it was not a production HTTP 500. Matching source recovered and verified
   twenty results/four ended sessions, then removed all its owned test records.
   Final probes used a private SHA-256-verified archive from serving-source
   commit `ce07c811` inside the available runtime image, retaining the web
   service's runtime identity, database attachment and secret references.
   Readiness and `migrate --check` passed with that source; no migrations ran.
3. Fixture preflight also corrected a generated identifier exceeding the
   twenty-character field limit and an inactive-calendar enrollment. The latter
   correctly caused four HTTP 400 roster refusals in each of two aborted fixture
   attempts, with no 5xx responses. Current-year enrollments and test-school-only
   calendar events were then used without altering the existing calendar.
4. The provider-finish handshake correction is in the new benchmark; no extra
   application threading/queue changes were indicated by the successful runs.

The measured result is bounded to these tests and configuration. Future network,
provider and infrastructure failures remain possible; no finite load test proves
that an HTTP 500/503 can never occur.

## Reproduction and evidence

- `tools/benchmark_crla_four_teachers.py`: opt-in Cloud Run job only; requires
  `PABASA_AUTHORIZED_FOUR_TEACHERS=4x5` and a generated mono 16 kHz PCM fixture in
  `PABASA_BENCHMARK_PCM_BASE64`. Use the serving source, PostgreSQL identity and
  normal HTTPS hostname. It creates and removes only owned synthetic resources.
- `tools/test_crla_four_teachers_browser.cjs`: local Chrome/Django fixture;
  accepts `CRLA_READER_SOURCE_PATH` and `CRLA_TEMPLATE_ROOT` for the serving
  source. Requires the existing Python venv and Playwright Core/Chrome.
- Final test ID: `3cf0bfbcac50`. Previous completed test ID: `4f96cfb2d2df`.
  Recovered initial test ID: `61e90a84696d`.
- Private aggregate reports, paginated log summaries, sampled monitoring and
  browser output remain under ignored `tmp/`; credentials/cookies/audio and
  student records are not included in the report or source changes.
