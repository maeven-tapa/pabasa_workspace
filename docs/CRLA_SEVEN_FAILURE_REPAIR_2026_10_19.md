# CRLA seven-test repair — October 19, 2026

The seven previously reported failures were automated regression failures, not
seven observed production HTTP 500s. Investigation found a real Save & Exit
defect and outdated expectations for accepted assessment behavior. The repair
also fixes final-save handling during Pause and repeated Save & Exit requests.

## Findings and repair

| Previous failing check | Finding and resolution |
| --- | --- |
| Save preserves recovery and membership | Legacy sessions could contain an authorized roster but no batch map. Save & Exit selected an empty batch and returned HTTP 400. Normalize the batches before selecting students and persist normalization inside the version-checked mutation. Verify `save_requested`, then the student's final acknowledgement, then `saved` with the freshest recovery snapshot. |
| Save while paused | The same legacy-map defect masked an additional defect: the paused-state guard ignored the requested final acknowledgement. Accept only a teacher-requested save acknowledgement for the current batch, keep the session paused, and preserve the latest snapshot. Explicit Resume now clears saved participation for paused sessions too. |
| Save does not overwrite completed student | Repair batch selection; continue preserving completed student state and official results. |
| End preserves unfinished cursor | The assertion conflicted with the accepted completed-result safeguard in commit `3ca15729`. End remains terminal: discard unfinished transport data without inventing an official result. Save & Exit remains the recoverable action. |
| End notifies never-started student | Commit `56ece00b` explicitly removed the missed-reading popup and notifications on October 9. Assert the terminal state and absence of an invented result or removed notice. |
| Late heartbeat cannot reopen saved student | Repair batch selection and make the test acknowledge the final save before sending the stale heartbeat. The saved state remains authoritative. |
| Approved overdue request waiting card | The page correctly renders the approved-request branch. Assert its approved context, `REQUEST APPROVED` text and teacher-start message, while continuing to reject self-start and another request button. |

Repeated Save & Exit requests now leave an already pending or acknowledged save
unchanged. An unsolicited student acknowledgement still cannot overwrite paused
progress. Authorization boundaries and scoring rules remain unchanged.

The final snapshot protocol predates this repair (`e88afa38f`): a teacher requests
the save, the student submits its current snapshot, and the server acknowledges
the saved participation. Tests now exercise that protocol instead of expecting
the teacher request alone to finalize the save.

## Local validation

- 57 focused Django tests passed: Close & Save, database configuration, missed
  assessment recovery, CRLA streaming and HTTP admission.
- 28 additional shared workflow tests passed: completion indicators, live CRLA
  export, background work, stale student updates, version-conflict retries,
  participant preservation and batch transitions.
- 24 JavaScript skip/completion recovery tests passed.
- Django system check, migration consistency check and whitespace check passed.
- Running the new isolated paused-save and repeated-save regressions against
  the original HEAD implementation reproduced both defects. The repaired
  implementation passes them; no original source file was overwritten.

## Release and live verification

The release overlays the repaired active `views.py` onto the exact previous
image, after verifying its original source checksum. It adds no migration or
schema change. The exact new image passed recorded migration readiness, an
empty migration plan, no-op migration and `migrate --check` in a Cloud Run Job.

- Previous working revision: `pabasa-01370-yit`.
- Repair revision: `pabasa-01373-kap`.
- Image digest: `sha256:cc52c4294101ad8b80092fc60a7122c9df9e448eb70ff8f66aa6237aff57230c`.
- Protected image tag: `release-20261019-crla-save-exit`.
- Cloud Build: `6860f3c8-3514-4433-984f-a59381cefd5c`.

The extended opt-in probe uses six teachers with five distinct synthetic
students each. In addition to the existing start-to-end interruption and
recording workflow, it exercises six deliberately empty batch maps, thirty
unsolicited paused acknowledgements, thirty requested paused saves, repeated
Save & Exit and teacher Resume. Only the probe's own synthetic sessions are
modified to simulate missing maps.

The candidate run (`a6220d1adba2`, 05:11–05:13 Philippine time) passed:

- 2,574 requests matched all 2,574 Cloud Run request logs: 2,490 HTTP 200,
  42 WebSocket upgrades, six expected expired-login 401s and 36 expected
  authorization-denial 403s. Zero HTTP 5xx, server ERROR events, streaming
  failure warnings or transport retries.
- Thirty simultaneous Google streams returned thirty final transcripts;
  sixty generated WebM/Opus clips were uploaded. Six deliberate microphone
  connection drops were followed by six successful replacement streams and
  signed evaluations.
- Six legacy batch maps repaired; thirty requested saves acknowledged while
  paused; unsolicited paused writes ignored; repeated saves left version
  numbers unchanged; all thirty students became active after teacher Resume.
- Thirty student transport rejoins, six expired-login recoveries and six
  teacher-exit recoveries passed. End produced exactly thirty classified
  results with the correct enrollments, five per teacher, with no duplicates
  after replay. All thirty-six login sessions remained valid until cleanup.
- All owned synthetic users, login sessions, live sessions and materials were
  removed. Public traffic switched only after these results and logs passed.

The public-domain repeat (`e28ec23c8adc`, 05:15–05:17 Philippine time) also
passed the same assertions, including all six repaired batch maps, thirty
paused-save acknowledgements and unchanged versions after repeated Save & Exit.
It produced exactly thirty classified, correctly enrolled results across six
ended sessions. All owned synthetic database resources were removed.

| Evidence | Candidate | Public domain |
| --- | ---: | ---: |
| Requests / matching Cloud Run logs | 2,574 / 2,574 | 2,574 / 2,574 |
| HTTP 200 / WebSocket 101 | 2,490 / 42 | 2,490 / 42 |
| Expected expired-login 401 / authorization 403 | 6 / 36 | 6 / 36 |
| HTTP 5xx / server ERROR / streaming failure warnings | 0 / 0 / 0 | 0 / 0 / 0 |
| Failed requests / transport retries | 0 / 0 | 0 / 0 |
| Completed results / ended sessions | 30 / 6 | 30 / 6 |
| Results per teacher | 5 each | 5 each |
| Simultaneous streams / final transcripts | 30 / 30 | 30 / 30 |
| Generated recorded clips / replacement stream finals | 60 / 6 | 60 / 6 |
| Remaining synthetic users / login sessions / live sessions / materials | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |

There were no aborted probe attempts during this repair's release. Both runs
also preserved all thirty-six synthetic logins until their explicit cleanup.
Request logs show three serving instances. No new production threading or
queueing system, capacity increase or speech-provider fallback was introduced.

## Public latency and resource observations

| Operation | Requests | Mean | p95 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Pause | 12 | 70 ms | 78 ms | 78 ms |
| Save & Exit, including repeated requests | 18 | 224 ms | 290 ms | 290 ms |
| Student save acknowledgements, including rejected unsolicited updates | 90 | 137 ms | 251 ms | 300 ms |
| Resume | 24 | 79 ms | 148 ms | 157 ms |
| End Session | 6 | 9,521 ms | 15,906 ms | 15,906 ms |
| Repeated End Session | 6 | 7,953 ms | 13,153 ms | 13,153 ms |
| Student dashboard | 210 | 2,230 ms | 4,630 ms | 5,905 ms |

End Session remains a multi-second operation under this load. Zero failures
does not establish one-second finalization. Monitoring returned three CPU and
three memory distribution samples in the public window with one-minute margins:
CPU sample means 22.0%–58.7%; memory sample means 25.1%–27.2%. These are
sampled means, not instantaneous peaks.

## Final release state

Final checks confirm `pabasa-01373-kap` is the latest created and ready revision
and receives 100% of traffic. Its exact image is present in Artifact Registry,
protected by the release tag and existing retention policy. The three owned
diagnostic jobs and temporary traffic tag were removed. Working rollback
revision `pabasa-01370-yit` remains available.

Runtime identity, secret references, Cloud SQL attachment and the private shared
recording bucket/mount were preserved. No schema change was made. The public
reader asset matches both the image and checkout. Production source checksum
matches the patched build input; tests and benchmark changes after that build
do not modify production application code. Private aggregate reports and release
state remain under ignored `tmp/`; no credentials, real audio or real student
records are included here.

The previous capacity evidence remains in
[the original thirty-student report](CRLA_THIRTY_STUDENT_RESILIENCE_2026_10_19.md).
These are bounded checks with generated speech and synthetic workflow evidence;
they cannot establish that future infrastructure, network or provider failures
are impossible.
