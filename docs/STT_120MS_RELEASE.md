# 120 ms speech framing release — November 11, 2026

The user authorized applying and pushing the saved evolutionary search's best
configuration, and requested a 50-student error/capacity check.

## Change

- Browser AudioWorklet frames: 3,200 to 1,920 samples at 16 kHz (200 to 120 ms).
- Google Chirp 3, selected language/provider, provisional text, scoring and
  completion rules are unchanged.
- Startup/rotation buffering retains its prior ten-second PCM allowance using
  a 320,000-byte bound; a fixed 50-frame bound would shrink to six seconds.
- Reading templates version both speech assets so returning browsers load them.

## Measured basis and limits

Saved search: `output/stt_evolution/2026-11-10_232746`, completed November 11 at
00:04:10 Manila. Direct real Google Speech replay of synthetic English only.
Best training candidate: 120 ms, interim results enabled. Final holdout test:
three waves of 20 simultaneous streams for each configuration (60 samples each).

| Holdout metric | 200 ms baseline | 120 ms candidate |
| --- | ---: | ---: |
| p95 completion overhead | 1,089.53 ms | 1,003.13 ms |
| Mean word error rate | 0 | 0 |
| Failed requests | 0 | 0 |

Observed p95 reduction: 86.40 ms (7.93%). These measurements do not establish
live website latency, Filipino children's accuracy, classroom noise performance,
or classroom capacity. Local checkpoint/audio remain outside source control.

## Verification and release

- PCM/transport JavaScript checks cover 120 ms frame limits, all trailing audio,
  sample rates, startup/rotation byte bounds, ordered final results, interruption,
  stale results and recording fallback. Stale status-renderer test mocks were
  updated to match existing Filipino text and DOM behavior; app status text was
  not changed.
- The independent-account Django concurrency fixture supports an explicit
  50-student case in five legitimate ten-student classes. It checks authentication,
  concurrent polling/writes, reconnect isolation and provider-error recovery.
- The browser test uses synthetic capture and mocked Google. Fifty simulated
  microphones share one Windows PC, so microphone initialization ramps in groups;
  the fake provider waits for all requested streams before issuing any final.
  It continues consuming PCM during ramp-up rather than blocking real queues.
- The live HTTP probe defaults to 20 and accepts explicitly authorized 50 clients.
  It creates only disposable users/classes/material, stops on a failed wave,
  reports exact status counts, verifies completed results and cleans its fixtures.
  It does not send audio or establish real Speech API classroom capacity.
- `tools/cloud_release_gate.py` copies runtime identity, env/secret references,
  volumes and Cloud SQL attachment from the selected web service. A same-digest
  Cloud Run Job checks recorded migration readiness, requires no pending schema
  changes, runs migrate and checks again before deployment. Environment values
  and tokens are never printed. No model/schema change is part of this release.

Current deployment was rechecked under the user's selected account
`tupc.pabasa@gmail.com`: project `pabasa-web`, region `asia-southeast1`, service
`pabasa-workspace-deployment--trigger`; the prior ready revision was
`pabasa-workspace-deployment--trigger-00007-wit`. The existing GitHub main-branch
Cloud Build trigger is retained with the database gate inserted before activation.
The old-project service listed in historical reports is not assumed current.

Final live status, fifty-student metrics and request-log correlation are recorded
after deployment verification; successful local tests alone are not live evidence.

Local validation before push: 53 existing focused Django tests passed; the newly
added 50-account test initially exposed a fixture limited to three classes.
After generalizing that fixture, the 50-account case passed separately (52.6 s).
Fifty overlapping Chrome capture/evaluation lifecycles passed with mocked Google,
all connected before any final, and database access forbidden. The JavaScript
suite and two migration-gate unit checks passed. Django system check and
`makemigrations --check --dry-run` passed with no model changes.
