# CRLA live assessment: student and teacher skipping

Investigated October 18, 2026, after the user confirmed that both student and
teacher skipping sometimes fail. This repair concerns the shared CRLA reader,
including teacher-assisted reading, and the reader's response to a teacher
marking a participant skipped. The current teacher control template does not
expose a separate `skip_student` button; its existing action endpoint was tested
directly, while the shared reader's Skip/Next controls were tested in Chrome.

## Reproduced causes

1. **Unconfirmed cursor saves still advanced the page.** The save function can
   resolve to `null` on an unsuccessful request. Skip awaited that result but
   did not check it, so the student could see the next item while the server
   retained the previous cursor. Comprehension similarly moved before saving.
2. **A rejected save could leave navigation locked.** Reading Skip set
   `isAdvancingItem` and disabled Next, without restoring the controls if an
   exception interrupted persistence. Refresh appeared to fix that local state.
3. **Teacher skip was missing from reader state handling.** The server already
   rejected late student writes after a teacher marked the student `skipped`.
   The browser handled a whole-session End/Pause, but ignored an individual
   skipped participant while classmates were still active. Capture could
   continue in a reader whose updates the server correctly ignored.
4. **Fallback recording was not drained.** Skip waited for a WebSocket stream,
   but not an active MediaRecorder clip when streaming was unavailable. Moving
   the item/version could invalidate a captured, not-yet-checked spoken answer.
   A teacher skip arriving during draining could also display an inappropriate
   microphone-retry status afterwards.
5. **Live status updates could reset comprehension position.** The recovery
   builder used the reading-item index, often zero, for the comprehension
   question index. Its follow-up monitor update could also replace the next
   question just saved with the question still displayed before the UI moved.

These failures were reproduced with the actual reader functions before their
respective fixes. They explain concrete failure paths, not every historical
server error or every report of skipping.

## Repair

Skip now requires a successful server acknowledgement before publishing its
new cursor to local recovery storage or moving the UI. A failed save leaves
the same item available for an explicit retry. An in-flight navigation guard
blocks duplicate clicks; cleanup restores the controls on all exit paths.

Story segment Skip saves the omitted-word evidence and the destination cursor
in one awaited update. Retrying does not duplicate omissions or erase captured
correct words. Comprehension Next saves its intended question before rendering
it. Live snapshots use the comprehension cursor, and the immediate monitor
update preserves the acknowledged destination even before the UI increments.

Both stream and fallback clip paths flush and await pending speech before
changing context. A result that completes the item is retained, and unresolved
speech prevents advancement. A teacher's skip/pause/end is checked again after
the wait, so a late result cannot advance the reader or request a microphone
retry after the teacher's decision.

When polling or an in-flight save reports this student's `skipped`/`missed`
state, capture stops and the reader returns to Reading Assessment with a
follow-up message. Another student's skip does not stop this reader. Stopping
capture also works when the optional pause overlay is absent.

Skipping remains navigation. Unanswered results stay null, prior scores stay
intact, and teacher skip does not fabricate an official completion or grade.
No Python production endpoints, scoring rules, models, authorization rules,
database configuration, or prescribed-recording storage were changed.

## Historical log investigation

The Google Cloud CLI rechecked the active authenticated account and serving
revision. A complete seven-day scan beginning October 11 at 04:54 UTC found
3,364 responses with HTTP status at least 400 across live-state, live-action,
end-state, and shared speech routes. All belonged to older revisions; none
belonged to then-current `pabasa-01339-pas` in that scan.

The shared teacher action route had 15 historical 5xx responses: five HTTP 500s
and ten HTTP 503s. Request URLs do not reveal the posted action, so those cannot
all be attributed to Skip. Browser state/recording races can also fail without
an HTTP 500. Output contains aggregate counts and normalized routes, without
student names, session identifiers, transcripts, audio, or cookies.

## Local validation

- **24 JavaScript tests passed**: twenty focused skip/cursor/recording/state
  regressions plus the four existing completion-recovery tests. They cover
  failed and rejected saves, retry, duplicate clicks, omission preservation,
  teacher-assisted reading, teacher skip during pending work, cross-student
  isolation, and comprehension recovery snapshots.
- **19 focused Django tests passed**, including server-side terminal-state and
  late-heartbeat protection, live compare-and-swap updates, story omission
  scoring, completion selectors, and the updated navigation source checks.
- **30 complete Chrome readers passed** using actual Django-rendered markup
  and the full reader JavaScript. Each stayed on its item after an injected
  local HTTP 503, advanced once after an explicit retry, waited for a controlled
  fallback clip to drain, then stopped capture and returned to the dashboard
  when its teacher skip arrived. Skips created no fabricated spoken scores.
  APIs and recording objects in this browser test are synthetic; it does not
  claim thirty real microphones or real provider calls for this repair.
- JavaScript syntax, benchmark Python compilation, and whitespace checks passed.

A wider 137-test Django run had **26 failures and one error on unchanged reader
source**. The first changed-source run had one additional source-string failure
because its assertion expected the old comprehension call. That check was
updated to require the saved destination and acknowledgement before incrementing
the question, then passed. Existing scoring/fixture conflicts were not relaxed.
The full suite is not green.

The legacy `test_crla_live.cjs` harness also has missing globals/outdated section
markers (23 failures in a combined 33-case run including four completion tests
before repair).
A separate legacy preview browser harness rejects the existing read-only
narration route in its persistence allowlist; unchanged source reproduces the
same failure. Neither harness failure is reported as a passing test. The new
focused and full-reader browser tests exercise the repaired behavior directly.

## Final live validation and release

Final serving revision: **`pabasa-01346-rew`**, 100% public traffic.

Image digest:
`sha256:4e5455af9ad713f45bfcc9a68fd153e5015f100c1950f2ed85908acb7589ddb9`.

Build `58443bbf-b168-4629-885b-674988dad9a0` overlays only the reader JavaScript
on the previous serving image. The build verified the baseline file before
applying the patch. The exact final image passed
`check_migration_readiness --require-recorded`, an empty migration-plan check,
the no-op migration command, and `migrate --check` in job
`pabasa-prescribed-skipready-45f85f9b` before activation. No schema changes were
applied. Publicly served JavaScript was checked by SHA-256 against the validated
local source after switching traffic.

| Final-image run | HTTP window, UTC | Requests | Statuses | Unexpected failures/retries |
| --- | --- | ---: | --- | --- |
| Private revision | 05:22:02–05:22:07 | 390 | 330 × 200, 60 × expected 403 | 0 / 0 |
| Public site | 05:24:02–05:24:06 | 390 | 330 × 200, 60 × expected 403 | 0 / 0 |

These correspond to 13:22 and 13:24 Philippine time on October 18. Both runs
used **30 distinct enrolled synthetic students**, three synthetic teachers and
three classes, with one normal active batch of ten per class. This exercises
thirty active students concurrently without overriding the application's
ten-student live-batch rule. It is not a test of a thirty-student active batch
inside one class.

Each run saved three successive reading cursors for every student, saved and
read back comprehension question position 2, then raced teacher skips against
student heartbeats. Thirty late updates attempted to move the skipped students
to another stage; all thirty retained the skipped state and saved position.
Thirty repeated teacher requests remained idempotent. Thirty student attempts
to invoke teacher actions and thirty teacher attempts against another class
correctly returned 403. All thirty student logins remained valid before cleanup,
and **zero official student assessment results** were created.

The endpoint fixture sets temporary workflow positions directly. It does not
pretend to have read every CRLA item or to establish recognition accuracy.
There were no real recordings, speech-provider calls, real student changes, or
outbound messages in this probe. The browser test's injected 503s were local
synthetic responses, not production errors.

Complete paginated Cloud Run logs matched all 390 requests in each final-image
run across **three instances**. Both windows had zero HTTP 500/503s, ERROR logs,
database pool failures, background-worker failures, or streaming-failure warnings.

| Public operation | Samples | Mean | p95 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Reading cursor save | 90 | 187 ms | 362 ms | 433 ms |
| Comprehension cursor save | 30 | 171 ms | 262 ms | 270 ms |
| Comprehension readback | 30 | 146 ms | 238 ms | 256 ms |
| Teacher skip | 30 | 134 ms | 256 ms | 555 ms |
| Late student update | 30 | 94 ms | 141 ms | 144 ms |
| Repeated teacher skip | 30 | 114 ms | 231 ms | 238 ms |

The initial core repair was also tested and briefly served as
`pabasa-01343-var` before the additional clip-draining and comprehension-cursor
regressions were completed. Its two 330-request tests passed; the final table
above describes the final image with all repairs included.

Runtime configuration remains Generation 2, one vCPU/1 GiB per instance,
service/revision minimum and maximum 3/3, and concurrency 80. The existing ASGI
admission limit, database pool, startup migration guards and private shared
recording mount remain in place. Working revision `pabasa-01343-var` is retained
for traffic rollback; the previous prescribed-material revision
`pabasa-01339-pas` is also retained.

All probe users, sessions, classes, calendars and live sessions were removed.
Owned diagnostic jobs and the test traffic tag were removed after evidence
collection. Existing student data and the private recording bucket were retained.
The counts and latencies are bounded observations, not a guarantee that future
network, provider or infrastructure failures cannot occur. Existing open readers
load the repair when they next load the assessment page.
