# PABASA 15-client test after database resize

Date: October 10, 2026, Asia/Manila. Live HTTP phase: approximately 2:14:06–2:14:42 AM.

**Result: availability passed this short test; student-list latency needs improvement.**

The user resized Cloud SQL to 2 vCPUs / 8 GiB (`db-custom-2-8192`). It was verified RUNNABLE with regional automatic failover and the existing 250 GiB SSD. Cloud Run remained 1 vCPU / 512 MiB, concurrency 80, min 0 / max 3. Revision `pabasa-01173-w2r` continued to receive 100% of traffic.

## Live HTTP test

Fifteen authenticated virtual clients made three rounds of dashboard, student-list and overview GET requests through `https://tupcpabasa.app`. Rounds began together, with five seconds of think time between rounds. This is an intentionally synchronized burst, not a prediction of normal classroom request timing.

| Endpoint | Requests | Mean | P95 | Maximum | Failures |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dashboard HTML | 45 | 1.344 s | 2.387 s | 2.592 s | 0 |
| Student-list API | 45 | 6.064 s | 6.536 s | 7.266 s | 0 |
| Overview API | 45 | 0.312 s | 0.414 s | 0.603 s | 0 |

All **135 requests returned HTTP 200**. JSON APIs also returned `success=true`. Cloud Run request logs matched all 135 test requests; their mean server durations were dashboard 1.304 s, student list 6.052 s and overview 0.300 s. The delay is therefore on the server, rather than primarily the test client's network. No ERROR-severity Cloud Run log entries were found from 2:10 AM through the verification check.

The first dashboard round averaged 1.989 s; the next two averaged 1.051 s and 0.991 s. Student-list means remained near six seconds in every round, so the list delay did not disappear after the first round.

All clients shared the same previously measured teacher and class, which has **one enrolled student**. This is not 15 distinct teacher/student accounts, a 15-student roster, a browser-rendering test, or an assessment-submission test. No real enrollment or assessment records were changed. Fifteen temporary ten-minute sessions were created for the authorized benchmark and all fifteen were deleted afterward. Cookies and personal response data remained in memory and were not logged.

## Database timing diagnosis

The same internal read-only Django view test used before resizing was repeated with up to 15 worker threads and 30 samples per endpoint. Internal requests exclude public HTTP middleware/network timing, so compare them only with the earlier internal test.

| Internal view | Previous 8 CPU / 32 GiB mean | New 2 CPU / 8 GiB mean |
| --- | ---: | ---: |
| Dashboard | 826 ms | 802 ms |
| Student list | 1,018 ms | 5,889 ms |
| Overview | 335 ms | 320 ms |

These are observations from two short runs at different times, not a randomized experiment. The student-list result is a substantial regression associated with the resize; other conditions may contribute.

A focused follow-up profile measured:

- Three single student-list requests: mean total **529 ms**, database connection setup **31 ms**, recorded SQL time **456 ms**.
- Thirty student-list requests with up to 15 threads: mean total **5,925 ms**, connection setup **111 ms**, recorded SQL time **5,774 ms**.
- No profile request failures. Recorded SQL time accounts for approximately **97%** of concurrent request duration. It includes database execution and waiting; it does not identify a particular query plan or prove an instantaneous CPU peak.

This points to database query execution/waiting under concurrent roster requests. More Cloud Run CPU alone would not address the dominant measured time. Query-plan and repeated-query investigation is the next useful step. The post-resize managed `shared_buffers` setting was about **2.59 GiB**, down from about 10.45 GiB; `max_connections` was **400**.

## Resource observations

Minute-level monitoring samples were collected from roughly 2:11–2:16 AM, with a delay for metrics ingestion:

| Resource | Highest sampled value in the window |
| --- | ---: |
| Cloud SQL CPU utilization | 32.1% |
| Cloud SQL memory utilization | 47.9% |
| Cloud Run CPU, sampled mean | 8.1% |
| Cloud Run memory, sampled mean | 92.4% of 512 MiB |
| Cloud Run active instances | 1 |

Cloud Run memory was already around **87% before the test**, then rose above 91%. This supersedes the earlier roughly 50% memory snapshot. The test did not demonstrate an out-of-memory failure, but 512 MiB now leaves little room.

Minute averages smooth short bursts and can miss instantaneous database saturation. Connection gauges sampled before/after the short bursts did not establish the true concurrent connection peak; the 400-connection limit is configuration, not a measured peak. The load-test generator ran in a separate diagnostic job and is not included in the production Cloud Run resource figures.

## Recommendation

- Treat 2 CPUs / 8 GiB as **available under this short test, but not yet validated for responsive 15-user roster access**. Do not reduce the database further based on these results.
- Optimize and inspect the student-list SQL, including redundant roster work and repeated query patterns, then re-test. More RAM in the web container will not by itself fix six-second SQL time.
- Increase Cloud Run memory to **1 GiB** as the next proposed configuration change while retaining **1 vCPU**. Investigate the memory growth as well; added RAM supplies headroom, not a leak fix. This change has not been applied.
- Test concurrency 16 against the server's 16 threads after addressing SQL. Lower concurrency can increase active instances and cost; it should not be described as guaranteed savings.
- If roster response times must improve immediately, a temporary database step back toward 4 CPUs / 16 GiB is an option to compare. That intermediate configuration has not been benchmarked, so no speedup is guaranteed.
- Keep regional failover, backups and recovery. Storage shrink remains a separate proposed maintenance operation and was not performed.

No hosting settings or production application code were changed by the assistant during this test.

Evidence: `tmp/fifteen-user-test.json`, `tmp/fifteen-user-test-metrics.json`, `tmp/student-list-profile.json`. Load execution: `pabasa-revision-check-01172-rnztv`; successful focused profile: `pabasa-revision-check-01172-bz4c9`. Reusable tools: `tools/test_fifteen_users.py`, `tools/collect_fifteen_user_metrics.py`, `tools/profile_student_list.py`.
