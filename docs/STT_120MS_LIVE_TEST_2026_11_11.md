# Live 120 ms release and 50-student test — November 11, 2026

The 120 ms PCM frame configuration is active on https://tupcpabasa.app.
The public worklet returns HTTP 200 and contains 1,920 samples/frame at 16 kHz.
Startup/rotation buffering retains ten seconds of PCM. Google model, languages,
provider selection, interim text, grading, and completion rules are unchanged.

## Deployment evidence

- Application commits: `d0d3f32c` and `12eb0854`, pushed to GitHub main.
- Project: `pabasa-web`; region: `asia-southeast1`.
- Service: `pabasa-workspace-deployment--trigger`.
- Active revision: `pabasa-workspace-deployment--trigger-00011-yen`, 100% traffic.
- Verified image: `sha256:f7831373a83f90f567bcec25293c5c8e168650f2483d9f2b626a542be36df714`.
- Successful staged release build: `79977982-4e87-4de3-8c66-edcfc896b635`.
- The same-digest migration job passed recorded readiness, `migrate --check`,
  migrate with no pending changes, and the final migration check. No schema
  change was made. Both web startup guards remain in place.
- The staged revision passed 505 authenticated requests before promotion.
- Previous working revision `pabasa-workspace-deployment--trigger-00007-wit`
  is retained for traffic rollback; migrations must not be automatically reversed.
- The existing main-branch deployment trigger now runs the same-image database
  gate before deploying, pins the verified digest, and uses the Cloud SDK's own
  interpreter path instead of assuming system Python is installed.

## Public-domain 50-student test

Window (UTC): 2026-11-10T16:55:19.268661+00:00 to 2026-11-10T16:56:03.570441+00:00.
User agent: `PABASA-authorized-live-crla-50-c54bf361dbc7`.

Fifty distinct synthetic student logins/enrollments in five legitimate ten-student
classes, with five teacher sessions. Each student joined synchronized waves of
polling, three progress-write rounds, synthetic completion snapshots, teacher
End Session while students continued polling, and post-end session checks.

**505/505 requests returned HTTP 200. Zero 4xx or 5xx.** Cloud Run request logs
independently matched all 505 requests to the intended revision and test marker.
The staged pre-promotion run separately passed 505/505 requests with the same
50-student workload; these were separate runs, not 100 simultaneous students.

| Operation | Requests | Mean ms | p95 ms | Max ms | Errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| complete | 50 | 275.48 | 559.14 | 611.86 | 0 |
| end | 5 | 17931.93 | 29303.37 | 29303.37 | 0 |
| poll | 250 | 314.32 | 627.34 | 822.73 | 0 |
| post_end | 50 | 1912.70 | 3734.18 | 4001.55 | 0 |
| update | 150 | 297.06 | 562.08 | 752.60 | 0 |

Verified database outcomes: 50 completed synthetic results,
5 ended sessions, and 50 preserved
student logins before cleanup. 55 temporary login
sessions were deleted. Cleanup confirmed zero synthetic users and live sessions.
Disposable diagnostic jobs were removed; the reusable release migration job remains.

## Earlier failed attempt and correction

The first staged probe used a 25-second request deadline. Five concurrent teacher
finalizations took up to 29.50 seconds. Its early failure started fixture cleanup
while the last request was still committing, producing one HTTP 400 among 455
logged requests and a foreign-key cleanup error. This failed attempt is retained
as evidence and is not counted as a successful run.

The test now waits up to 60 seconds for teacher finalization (normal polling still
has its 25-second bound) and explicitly deletes its synthetic attempts before
removing enrollment/user fixtures. The old fixture was cleaned by its exact run
identifier; a follow-up job confirmed zero remaining users, sessions and material.
The corrected staged and public runs both completed all 505 requests and cleanup.
The longer test deadline is not a performance improvement.

## Limits and remaining performance issue

End Session remains slow: public-run maximum/p95 was 29.30
seconds across only five requests. This release does not claim responsive
50-student finalization, sustained classroom capacity, or a measured live speech
latency improvement. No CPU, memory, instance/concurrency settings or SQL tier
were resized. Cloud SQL was rechecked as db-g1-small, zonal, 10 GiB.

The HTTP probe performs no microphone capture or real Speech API request and
uses synthetic completion evidence. Separately, 50 overlapping local Chrome
microphone/AudioWorklet/WebSocket/evaluator lifecycles passed with mocked Google
and database access forbidden. The 50-account Django workflow test passed
for concurrent auth/progress, reconnect isolation and provider-error recovery.
Actual Filipino children's speech, noise and sustained 50-student Google speech
recognition remain outside this test. The earlier measured 7.93% improvement
was direct synthetic-English Google API replay, not live website latency.

Raw dated reports, request-log aggregates and local browser/account checks are
saved outside source control under `output/stt_evolution/2026-11-10_232746/`.
