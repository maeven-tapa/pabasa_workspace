# PABASA shared-core database: 15-client test

October 10, 2026, Asia/Manila. Public HTTPS phase: approximately **3:23:21–3:24:04 PM**.

**Result: all requests succeeded; the student list remains slow under simultaneous access.**

## Verified live setup

- Cloud SQL `pabasa-db-micro`: PostgreSQL 18, Enterprise, `db-g1-small`, single zone, 10 GiB SSD. The name contains “micro,” but the actual tier is the larger shared-core small tier, with about 1.7 GiB RAM.
- Cloud Run revision `pabasa-01197-ht7`: 1 vCPU / 1 GiB RAM, concurrency 80, minimum zero / maximum three instances, request-based billing. This revision served all test requests and still received 100% of traffic afterward.
- The diagnostic job used the live image digest `sha256:2e31beae0adb182a4c94d62d06fc0d3d61fa1b9620d760fbe3fa9aade9167abe`, the same database connection, runtime identity, and secret references.
- A read-only migration check passed. Database size was 12,990,143 bytes (about 13 MB decimal). `max_connections` was 50; `shared_buffers` was 128 MiB; `work_mem` was 4 MiB.

## Measured waiting times

Three sequential requests per endpoint established a small single-user baseline. The load phase then ran three rounds of 15 simultaneous requests to each endpoint, with five seconds between rounds. All clients in a wave started together, and the next endpoint waited for that wave to finish.

| Endpoint | Single-user mean | 15-client mean | 15-client P95 | Maximum | Failures |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dashboard HTML | 0.199 s | 1.152 s | 1.300 s | 3.833 s | 0 / 45 |
| Student-list API | 0.665 s | 6.447 s | 6.623 s | 6.658 s | 0 / 45 |
| Overview API | 0.102 s | 0.446 s | 0.516 s | 0.561 s | 0 / 45 |

P95 is the sample's 95th percentile: approximately 95% of measured requests finished within that time. There were 135 concurrent-phase requests and nine baseline requests; all returned HTTP 200 with the expected authenticated HTML or successful JSON.

Student-list means in the three rounds were 6.513 s, 6.461 s, and 6.368 s. The delay persisted across rounds. Student-list concurrency increased mean response time by about 9.7 times relative to this small sequential baseline.

Cloud Run logs matched all 144 requests and attributed them to the expected revision. Across baseline plus concurrent requests, student-list mean server latency was 6.058 s. This supports a server-side delay; the test does not identify a specific SQL query plan or establish a network-free end-user rendering time.

No ERROR-or-higher application logs appeared in the checked request window. Fifteen temporary ten-minute sessions were created and all fifteen were deleted. No enrollment, student, or assessment records were modified by the benchmark.

## Resource observations

Monitoring was collected after ingestion caught up. The following are the highest reported samples in the surrounding **3:22–3:26 PM** window, which includes the test and background activity. They are not instantaneous burst peaks.

| Resource | Highest reported sample |
| --- | ---: |
| Cloud SQL CPU utilization | 45.4% |
| Cloud SQL memory utilization | 46.0% |
| Cloud Run CPU utilization, sample mean | 13.5% |
| Cloud Run memory utilization, sample mean | 40.9% of 1 GiB, about 419 MiB |
| Cloud Run active instance count | 1 |

The minute samples did not show memory exhaustion or sustained full CPU utilization. They do not establish that CPU or database access never limited a short burst. The database connection gauge only captured up to three connections including administrative connections; its sampling interval missed the transient request fan-out and cannot establish peak connection demand. The benchmark does not prove which database query or application behavior caused the student-list delay.

## Scope and interpretation

- This was a short authenticated GET test with 15 separate sessions sharing one existing teacher and class. The class contains **one active enrolled student**.
- It did not test 15 distinct accounts/classes, a larger roster, browser rendering, speech recognition, recordings, or assessment submissions.
- The test client ran in Google Cloud Singapore and requested the public `https://tupcpabasa.app` site. Philippine users' network latency and browser work can add waiting time.
- This demonstrates availability for the bounded workload, not sustained classroom capacity. Dashboard and overview responses were relatively quick; student-list access at 6.45 seconds average needs optimization.
- The earlier 2-CPU / 8-GiB test used a different load scheduling pattern and ran at a different time. Do not interpret the two reports as a controlled hardware comparison.

## Evidence

- `tmp/current-fifteen-user-test.json`: client measurements and cleanup counts.
- `tmp/current-fifteen-user-metrics.json`: resource samples, sanitized HTTP logs, and error count.
- `tools/test_current_fifteen_users.py`: bounded benchmark, with failure cutoff.
- `tools/collect_current_fifteen_metrics.py`: metric and request-log collection.
- Diagnostic execution: `pabasa-loadtest-small-3d5a88-47jvp`.

No production hosting settings or application code were changed during this test. The separate benchmark job only executed the test code and was deleted after its results were saved. All temporary authentication sessions were also removed.
