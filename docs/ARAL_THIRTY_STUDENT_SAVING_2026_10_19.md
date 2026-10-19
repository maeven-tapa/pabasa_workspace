# ARAL Sessions 1–15: 30-student saving and recovery investigation

Measured October 19, 2026 (Asia/Manila). Public site: https://tupcpabasa.app.

## Result and limits

Each check used 30 distinct synthetic student accounts, split between six teacher accounts and six classes of five students. The complete backend matrix covered all 85 active prescribed activities and seven legacy progress activities. A final correction changed only two browser scripts, followed by the focused browser checks and a candidate check sampling every session. After activation, the public routing check sampled one active activity in each of Sessions 2–15 and repeated the seven legacy progress checks; Session 1 recording/review brought its coverage to all 15 sessions. Session 1 recording submission, duplicate upload, private teacher playback, teacher review, cross-class denial and expired-login recovery were also checked. No HTTP 5xx responses or ERROR-level revision logs occurred in any of these checks.

This is a **saving and recovery benchmark**, not proof that 30 microphones can finish every spoken item in all 15 sessions. Oral eligibility and some intermediate oral states were synthetic fixtures. Nine cases exercise a restart checkpoint rather than a mid-activity answer. Grades and provider results were not changed to make tests pass. Finite successful runs cannot guarantee that an HTTP 500 or 503 will never occur.

| Run | HTTP requests | Saved checkpoints | Reconnected reloads | Unexpected responses | HTTP 5xx |
|---|---:|---:|---:|---:|---:|
| Candidate: complete activity matrix | 11,190 | 2,550 | 2,550 | 0 | 0 |
| Final candidate: one active checkpoint per session | 2,670 | 420 | 420 | 0 | 0 |
| Public: one active checkpoint per session | 2,670 | 420 | 420 | 0 | 0 |

Each run also preserved 210 completed legacy chart results after an older checkpoint arrived, completed 30 synthetic recording reviews, denied 30 attempts to play another teacher's recordings, and recovered 30 expired student logins. All disposable accounts, authentication sessions and exact owned recording files were removed.

## Reproduced faults and fixes

1. **Concurrent workbook saves accepted the same revision twice.** Before the fix, two of 90 paired save attempts returned two HTTP 200 responses for the same revision. A short database transaction now locks the individual student and rechecks the saved row version before writing. This covers first-row creation too. A concurrent teacher verdict or newer save produces HTTP 409 instead of being overwritten. Speech recognition runs outside the lock.
2. **Malformed legacy JSON caused an uncaught AttributeError.** The previous handler was evaluated against four synthetic non-object JSON values (`[]`, `null`, a number and a string); all raised AttributeError. The actual patched Django route returns HTTP 400 for each. Legacy progress comparison and saving are also serialized by student so an earlier checkpoint cannot undo completion.
3. **Pause could abort a progress save, and some leave dialogs did not wait for writes.** Progress requests are tracked independently of cancellable speech/media requests. The common leave flow waits for pending saves and reports failures before navigation. Restart uses the latest acknowledged workbook revision.
4. **Drawing drafts had no recovery after refresh during an outage.** Session 9 drawings and writing now coalesce changes with a one-second delay and preserve pending drafts locally, scoped by student, school calendar, term and activity. Refresh restores a matching pending draft. A backup from an older server revision requires an explicit restore; it cannot silently overwrite newer progress. Submitted or reviewed work takes precedence. Unsaved local backups expire after 24 hours; successfully saved server progress is not subject to that local expiry.

The final separate overlap check ran 360 requests for 30 students across three rounds per workflow: 90 workbook saves succeeded, 90 conflicting saves returned the expected HTTP 409, and 180 overlapping legacy completion/stale saves returned HTTP 200 while preserving all 90 final results. All 90 workbook pairs were serialized correctly, with zero duplicate acceptance and zero HTTP 5xx. Cloud logs confirmed all 360 requests and zero ERROR entries.

## Scope and reproducibility

`tools/benchmark_aral_thirty.py` is opt-in and requires a Cloud Run execution plus `PABASA_AUTHORIZED_ARAL_TEST=30`. Its fixture calendar is inactive and scoped to a disposable school; global calendars, real students and real recordings are not changed. Every wave has a 30-worker barrier. Teacher playback uses 30 connections belonging to six teacher identities.

`tools/fixtures/aral_save_checkpoints.json` contains synthetic request/state checkpoints validated by Django views. `PABASA_ARAL_SESSION_SMOKE=1` selects one activity per active session; `PABASA_ARAL_RECOVERY_ONLY=1` selects only recording/review/login recovery. The 85 full-matrix activity cases each open the page, save a checkpoint, check the database, close the connection, reload, check restored state and reject a malformed JSON request. Volatile clocks and randomized initialization are excluded from comparison against a fixed fixture; the actual selected target is checked for persistence across reload.

The nine restart-only cases are:

- `session-2-lesson-4-gawain-2`
- `lesson7-gawain2a`
- `lesson7-gawain4a`
- `lesson7-gawain4b`
- `session-4-gawain-5`
- `lesson-13-gawain-4`
- `aral-l22-g5-f-word-search`
- `aral-l23-g5-j-word-search`
- `aral-l24-g6-z-word-search`

The other 76 cases exercise a mid-activity checkpoint. Session 1 audio is generated test audio; its video-completed prerequisite is seeded. The existing local video checks had already passed their real playback and narration checks in the baseline run.

An earlier exploratory candidate run stopped on a fixture mismatch when Lesson 28 selected a valid random next word. It produced no HTTP 5xx and cleaned up its synthetic users; its measurements are excluded from the final pass table. Fixture comparison was corrected. A later exploratory recording check expected HTTP 404 for a cross-class request; the endpoint correctly returned HTTP 403. That harness expectation was corrected, and the complete final build was tested again. These earlier runs are excluded from the final pass table. An earlier exploratory race and matrix briefly overlapped; the final race, final candidate matrix and public matrix ran separately.

The complete backend matrix ran on `pabasa-01385-rij` with image `asia-southeast1-docker.pkg.dev/project-2b0d295d-ee06-40a7-927/cloud-run-source-deploy/pabasa_workspace/pabasa@sha256:57ef9d578bffbb5f4bc368a0601229c0329625355a493449ca5b82330f608484`. A final browser regression then identified speech audio posted to the progress URL being kept alive by pause. The correction changed only `prescribed_pending_saves.js` and `prescribed_session8_11_controls.js`; all backend, template and other asset hashes were unchanged. The final image passed the focused audio-cancellation browser check, the 30-context drawing/navigation browser check, and a 30-student candidate check sampling every session before activation. The public check then repeated that sample on the serving revision.

## Local checks

- Eight backend regression/matrix tests passed, including 85 active-activity subcases.
- Thirteen queue tests passed, including 30 isolated student draft recoveries, coalescing, offline failure, stale backups, save draining and HTTP 400/401/403/409/500/503 handling.
- A focused Chrome regression confirmed that pause cancels reading audio sent to a progress endpoint while preserving JSON draft saves and already captured recording uploads.
- Thirty isolated Chrome contexts passed offline drawing recovery, refresh, pause during an in-flight save, workbook leave waiting and Session 15 leave waiting. These functional browser checks ran in three batches of ten; they are not the concurrent HTTP capacity measurement. Browser network faults were local fixtures.
- Django system check, migration drift check and whitespace check passed. No schema changes were needed.
- The broader relevant suite ran 548 tests: 510 passed, 23 failed and 15 errored. All 38 failing/erroring checks were present in the pre-change baseline; no new failing checks were introduced. Two long browser/video checks from the original 542-test baseline were excluded from the fast repeat; eight new tests were added. Existing scoring, media and fixture conflicts remain unresolved and are not represented as successful tests.

Existing failing/erroring test modules:

- `pabasa_app.tests_aral_template_activities`: 5
- `pabasa_app.tests_lesson13_gawain2`: 1
- `pabasa_app.tests_prescribed_lesson19_matching_items`: 1
- `pabasa_app.tests_prescribed_lesson20_21_gawain4`: 2
- `pabasa_app.tests_prescribed_lesson23_gawain1`: 2
- `pabasa_app.tests_prescribed_lesson24_gawain5_startup`: 1
- `pabasa_app.tests_prescribed_lesson24_gawain6_audio`: 1
- `pabasa_app.tests_prescribed_lesson24_startup`: 1
- `pabasa_app.tests_prescribed_workbook`: 3
- `pabasa_app.tests_prescribed_workbook_data`: 17
- `pabasa_app.tests_session4_gawain5_tracing`: 4

## Timing and operating configuration

Public operation latency (aggregate over the complete run):

| Operation | Requests | Mean ms | P95 ms | Maximum ms |
|---|---:|---:|---:|---:|
| `dashboard` | 30 | 3311.29 | 5638.49 | 6580.58 |
| `activity_start` | 420 | 819.67 | 1633.66 | 2510.71 |
| `checkpoint_save` | 420 | 449.71 | 1014.24 | 1545.84 |
| `activity_reload` | 420 | 863.9 | 1789.92 | 2488.78 |
| `session1_upload` | 30 | 3173.23 | 5812.6 | 5826.0 |
| `playback` | 30 | 832.96 | 1416.45 | 1541.74 |
| `session1_teacher_review` | 30 | 386.98 | 679.46 | 705.61 |
| `login_recovery` | 30 | 4097.97 | 6941.76 | 7049.88 |

Cloud Run remained at three service minimum/maximum instances, concurrency 80, one vCPU and one GiB per instance, with request-based CPU. Cloud SQL was reverified as `db-g1-small`, zonal, 10 GiB. These are observations for these bounded runs, not a hardware comparison or a guarantee for higher loads.

Final revision: `pabasa-01386-tey`. Latest created and ready, serving 100% of traffic. Image:

`asia-southeast1-docker.pkg.dev/project-2b0d295d-ee06-40a7-927/cloud-run-source-deploy/pabasa_workspace/pabasa@sha256:69d3ead00d12bcbd31659e4fdfb46b8d841eee9ef453734d7c016040ed66c2fb`

The exact image passed `check_migration_readiness --require-recorded`, an empty migration-plan check, `migrate` and `migrate --check` in a release job before activation. Sixteen application/template/static file hashes matched the tested checkout and image. Startup readiness and migration guards remain in place. Runtime identity, secret references, Cloud SQL connection and private shared recording mount were preserved. The recording bucket still enforces public access prevention. Working rollback revision `pabasa-01379-kib` is retained; no database migration was reversed. Owned diagnostic jobs and the temporary traffic tag were removed. The release digest is pinned under the existing retention policy.

This report records the validation completed before Git publication. The revision and image above identify that tested release; subsequent Git publication and CI releases are verified separately.
