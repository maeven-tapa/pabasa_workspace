# Practice modes: 30-student resilience investigation — October 19, 2026

## Baseline finding

The existing live revision `pabasa-01373-kap` returned HTTP 200 for all 480
baseline requests. All 480 request logs matched; there were no server ERROR
events. Nevertheless, simultaneous completion of one shared material by thirty
distinct students retained only **20 Free, 19 Color and 16 Hunt completions**.
Successful response counts alone concealed lost progress.

Baseline ID: `b60e120d1a4d`, 05:25 Philippine time. The probe used thirty
disposable student accounts, each completing all three modes, with one shared
synthetic material per mode. A replay and return-page wave followed each save.
The persisted counts above were checked immediately after the first save wave.
All owned synthetic users, login sessions and materials were removed.

An earlier fixture setup attempt stopped before issuing any HTTP request because
the fixture occupied an existing administrator material slot. It cleaned up its
owned records. The corrected JSON-only fixtures retain normal reader items and
avoid occupying an existing administrator slot; no live material was replaced.

## Repairs

- Reload and merge the shared material's completion JSON under a PostgreSQL row
  lock. Different students cannot overwrite one another's completions. Color
  and Hunt retain their accepted best-star rules when a stale snapshot arrives.
  Achievement follow-up work runs after the material lock is released.
- Reject malformed completion bodies, invalid/nonfinite practice metrics and
  invalid Hunt indices with HTTP 400 instead of HTTP 500.
- Require Hunt deposits to reference an available, published system practice
  material, using the same access checks as the reader. Recheck publication and
  ownership while acquiring its row lock. Preserve the existing per-word and
  per-attempt award protocol and scoring thresholds.
- Persist pending browser completion jobs separately for each signed-in student.
  Serialize saves; retry transient failures at one-second intervals, up to three
  attempts per flush; expose Retry Save after failure. Reopen the reader or
  practice menu, reconnect, or retry to resume a pending job.
- Queue Hunt's original word deposits and completion bonus with their original
  attempt IDs. A failed word upload or lost response can be replayed without
  double-crediting the wallet. Do not report a queued completion as saved until
  its required deposits and completion request succeed.
- Bind queued completion payloads to the student who read the material. A stale
  page cannot save that result to another account signed in on the same browser.
- Stop continuous recognition after speech service, authorization or microphone
  permission failure. Keep the current item and let the learner explicitly
  restart. Incorrect readings still follow the accepted same-item retry flow;
  provider failures do not invent results or switch providers.

No model, migration, scoring-rule, instance-limit or provider-default change is
required. Existing CRLA fixes and private recording storage are preserved.

## Local and browser validation

The original implementation failed the new stale-material and stale-lower-score
regressions and returned server errors for invalid input. The repairs pass those
regressions. Older practice tests were corrected to use explicit global-material
fixtures, the current per-word Hunt protocol, and current progression states
and styles. For example, a completed Level 1 correctly unlocks Level 2; it must
not simultaneously render Level 2's old locked message.

- 90 Django regressions passed across practice, material streaming, CRLA
  Save & Exit, background work and HTTP admission; the additional stale-account
  completion regression passed separately (91 distinct tests in total).
- 40 JavaScript tests passed, including sixteen durable-queue cases and the
  existing CRLA skip/completion checks. Five practice-menu debug/star scenarios
  also passed.
- Thirty isolated Chrome contexts, ten per mode, ran the actual reader, rendered
  templates and queue with local API fault fixtures. All thirty provider failures
  and thirty microphone denials stopped automatic recording retries without
  advancing or scoring the item. All thirty offline completions remained pending
  with Retry Save. After closing and reopening all thirty pages, every pending
  result saved once; each Hunt wallet received exactly thirteen stars through
  six unique deposits.
- Django system check, migration consistency and whitespace checks passed.

Browser fault fixtures are local simulations. Live HTTP, speech, persistence,
authorization and deployment verification are recorded separately below.

## Live release verification

The image overlays five reviewed production files onto the exact serving
baseline. Cloud Build verifies the baseline checksums before applying the patch.
The exact new image passed recorded migration readiness, an empty migration
plan, no-op migration, `migrate --check` and production source-hash verification
in a Cloud Run Job. No schema change was made.

- Build: `1bcb9896-3a34-4b4a-849e-2a68dbaa984b`.
- Digest: `sha256:628a73bf2237fd07743c9db26b80d9d50727a1128785723234fce31e9559741d`.
- Protected tag: `release-20261019-practice-resilience`.
- Previous working revision: `pabasa-01373-kap`.

The full live probe uses thirty concurrent student clients in each of Free,
Color and Hunt, sequentially. Each mode includes thirty actual Google word
streams and signed generated WebM clip evaluations, six deliberate stream
disconnects before replacement streams, student transport rejoins, invalid
request and account-isolation checks, simultaneous completion, duplicate saves
and return pages. Free also exercises thirty direct generated clips without a
stream token. Hunt verifies all five per-word deposits, identical replays,
completion bonus replays and conflicting replays against the database wallet.
All thirty expired sessions are followed by ordinary HTTP login and return.

Candidate revision `pabasa-01376-xic` passed the full probe before promotion
(ID `f35593542d77`, 05:48–05:49 Philippine time): all thirty completions survived
in each mode, all thirty Hunt wallets held exactly thirteen deposited stars, and
all thirty expired logins recovered. There were 1,698 requests and matching
request logs: 1,230 HTTP 200 responses, 108 WebSocket upgrades, 180 intentional
invalid-input 400s, 120 authorization-denial 403s, thirty conflicting-deposit
409s and thirty expired-session 401s. There were zero failed requests, HTTP
5xx responses, server ERROR events, streaming failure warnings or pool/queue
failure warnings. Request logs show three instances.

All three modes had thirty simultaneous ready Google streams and thirty
successful signed clip evaluations. Eighteen deliberately dropped streams were
followed by replacement streams; Free additionally passed thirty direct clip
evaluations. Successful speech alone did not create a completion. All owned
synthetic accounts, login sessions and materials were removed.

The public-domain repeat also passed (ID `682626bbb5f0`, 05:51–05:53 Philippine
time). Its 1,698 requests matched 1,698 request logs with the same status counts
and zero HTTP 5xx, server ERROR events, streaming failure warnings or pool/queue
failure warnings. There were no aborted full-probe attempts or hidden transport
retries in either successful verification run. The probe reports expected
validation/authentication denials as successful checks rather than concealing
them as generic request failures.

| Verified outcome | Baseline | Candidate | Public domain |
| --- | ---: | ---: | ---: |
| Free completions retained after thirty simultaneous saves | 20 | 30 | 30 |
| Color completions retained | 19 | 30 | 30 |
| Hunt completions retained | 16 | 30 | 30 |
| Matched request logs | 480 | 1,698 | 1,698 |
| HTTP 5xx / server ERROR events | 0 / 0 | 0 / 0 | 0 / 0 |
| Three modes: simultaneous successful speech streams | Not tested | 30 each | 30 each |
| Deliberate stream disconnects followed by replacements | Not tested | 18 | 18 |
| Exact thirteen-star Hunt wallets after duplicate deposits | Not tested | 30 | 30 |
| Expired logins recovered through HTTP login | Not tested | 30 | 30 |
| Remaining synthetic users / login sessions / materials | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

## Public latency and resources

| Operation | Concurrent clients | Mean | p95 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Practice menu | 30 | 788 ms | 1,299 ms | 1,488 ms |
| Free completion | 30 | 412 ms | 721 ms | 735 ms |
| Color completion | 30 | 407 ms | 700 ms | 744 ms |
| Hunt completion | 30 | 397 ms | 641 ms | 656 ms |
| Hunt completion bonus deposit | 30 | 550 ms | 976 ms | 1,008 ms |

Monitoring returned three CPU and three memory distribution samples in the
public test window with one-minute margins. CPU sample means were 6.7%–39.0%;
memory sample means were 25.8%–28.0%. These are sampled means, not instantaneous
peaks. Request logs identify three instances. The verified configuration remains
three service minimum/maximum instances, concurrency 80, one vCPU/1 GiB per
instance and request-based CPU. Cloud SQL remains `db-g1-small`, single zone,
10 GiB SSD. No capacity increase or new server worker/thread pool was needed.

## Final release state and scope

`pabasa-01376-xic` is the latest created and ready revision and receives 100% of
public traffic. Its static assets match the verified image and checkout. The
release image is present and its release tag is pinned to the serving digest
under the verified retention policy. Working rollback revision
`pabasa-01373-kap` is retained. All six owned diagnostic jobs, including an
unstarted job left by a control-plane timeout, and the temporary traffic tag
were removed. Runtime identity, secret references, Cloud SQL connection and
private shared recording storage were preserved.

Live capacity checks exercised English word/easy practice in all three modes,
with generated audio and synthetic completion metrics. They do not establish
recognition accuracy for every word, difficulty, language, device or microphone.
The local thirty-browser fault checks use intercepted APIs; they are separate
evidence from the actual Cloud Run and Google requests. New tools are
`tools/benchmark_practice_thirty.py`, `tools/test_practice_thirty_browser.cjs`
and `tools/test_practice_completion_queue.cjs`. The live tool requires an opt-in
Cloud Run job and briefly publishes synthetic shared practice materials; inspect
its fixture and cleanup scope before reuse. It never modifies existing library
materials or reads existing students' audio.

Only generated audio and synthetic account/workflow data are used. Aggregate
reports and release helpers stay under ignored `tmp/`; no credentials, session
cookies, real student data or real recordings belong in this report. This bounded
exercise cannot prove that future network, infrastructure or provider failures
are impossible.
