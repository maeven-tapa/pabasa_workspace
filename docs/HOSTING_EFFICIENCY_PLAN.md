# PABASA hosting efficiency plan — October 10, 2026

Follow-up: the user applied 2 vCPUs / 8 GiB. The subsequent
[15-client test](FIFTEEN_USER_TEST.md) found slow student-list SQL and Cloud Run
memory above 90%. Its results supersede the earlier small-sample Cloud Run
memory sizing recommendation below. No application optimization had been
applied before that test.

Redis is excluded from the current plan. The user wants lower operating costs and responsive dashboards. The capacity testing target is now **20 simultaneous users**; see [the updated benchmark policy](TWENTY_USER_TESTING.md). Historical measurements below retain the workloads actually tested.

The proposed target is Cloud SQL Enterprise with **2 vCPUs, 8 GiB RAM and about 100 GiB SSD**, retaining regional automatic failover unless the user chooses the cheaper single-zone tradeoff. Keep Cloud Run at **1 vCPU and 512 MiB RAM**, request-based billing, minimum zero and maximum three instances. Test concurrency **16** to match the existing Gunicorn thread count. These are recommendations, not applied settings or a performance guarantee.

## Evidence from the live project

- Current Cloud SQL: PostgreSQL 18, Enterprise, 8 vCPUs / 32 GiB, regional HA, 250 GiB SSD, automatic storage growth. Backups, seven-day point-in-time recovery and deletion protection are enabled.
- Current Cloud Run: 1 vCPU / 512 MiB, concurrency 80, min 0 / max 3, request-based billing, startup CPU boost. Healthy revision `pabasa-01173-w2r` receives all traffic.
- A seven-day monitoring query only returned approximately **38.5 hours** of database samples, starting October 8 at 11:01 AM Manila time. Mean database CPU was **2.1%**, with a highest sampled value of **19.4%**. Maximum sampled application database connections: **14**; total including administrative connections: **16**. This is not a week's worth of observations.
- The current revision's roughly 50-minute sample showed mean Cloud Run CPU **1.7%**, maximum sampled CPU mean **14.7%**, mean memory **49.9%** and maximum sampled memory mean **54.1%**. These are limited observations, not a full classroom capacity test.
- Read-only SQL inspection found the application database is **17,266,367 bytes** (about 17 MB decimal / 16.5 MiB). Instance disk usage peaked around **255 MB**, compared with 250 GiB provisioned.
- `shared_buffers` is currently **1,369,472 × 8 KiB**, about **10.45 GiB**. The instance has no explicit shared-buffer override in its configured database flags. Its large current memory footprint must not be treated as the application's irreducible working-memory requirement. Verify the managed buffer setting and actual memory after any resize.
- Database memory metrics disagree in scope: server memory usage excluding OS buffer/cache is around 12 GiB, while database-process total memory is below 1 GiB. These are different scopes, not two interchangeable working-set measurements.
- The deployed Django configuration closes database connections after every request (`CONN_MAX_AGE=0`); health checks are enabled. Gunicorn runs one worker with 16 threads.
- Previous signed-in measurements: student-list API mean **430 ms**, P95 **539 ms**; internal 15-thread test mean **1,018 ms**, about **13 SQL queries/request**. The tested class contains one enrolled student.

## Proposed configuration and sequence

1. Optimize roster queries and test short-lived connection reuse, for example `CONN_MAX_AGE=60` with health checks. Preserve class authorization and assessment correctness. Check session-level database settings before connection reuse. This is an application change requiring validation, not an environment variable supported by the current code.
2. Test Cloud Run concurrency 16 with the existing 16 Gunicorn threads, while keeping CPU, RAM and instance limits unchanged. This allows scaling before excessive internal queuing. Lower concurrency can increase active-instance costs during bursts; it is a latency tradeoff, not guaranteed savings.
3. Take a fresh database backup. The conservative first resize is **4 vCPUs / 16 GiB**, keeping HA and 250 GiB storage. It halves compute charges and provides room for the observed CPU peak.
4. Validate a representative 20-user workload, including assessments and material operations. If CPU, memory, connection count, errors and dashboard P95 remain acceptable, move to **2 vCPUs / 8 GiB**. The observed 19.4% CPU peak on eight CPUs could become roughly 77.6% on two CPUs if the same work scales linearly; this is a rough bound, not a forecast. Keep the intermediate size if peak load warrants it.
5. Handle disk shrink as a separate scheduled operation. Google's read-only shrink check returned a **56 GiB minimum** and an estimated operation time of **19 minutes**. Propose about **100 GiB** instead of that minimum to retain operational headroom. Keep automatic storage growth. Verify extensions, WAL settings and the minimum size again before execution; the inspected `max_wal_size` was 1,504 MB.
6. Retain automatic failover, backups and point-in-time recovery by default. Single-zone operation is a separate cost/reliability decision. It removes automatic cross-zone failover and can produce longer outages during a failure; more Cloud Run instances cannot compensate for a database outage.

CPU/RAM changes in this Enterprise instance require a brief database restart. Google documents less than 60 seconds offline for the resize, with the operation taking several minutes overall. Storage shrink requires downtime and is a separate, longer operation. See [instance-setting impacts](https://docs.cloud.google.com/sql/docs/postgres/instance-settings#impact_of_changing_instance_settings) and [storage shrink](https://docs.cloud.google.com/sql/docs/postgres/about-storage-shrink).

## Monthly database list-price estimate

These are **730-hour public list-price estimates**, not the user's actual invoice. Use PHP 63/USD for planning. Exclude credits, negotiated or committed-use discounts, taxes, currency/card fees, backup storage, network charges, and all other project services.

Singapore Enterprise General Purpose rates verified in the [Google Cloud SQL pricing table](https://cloud.google.com/sql/pricing), with Singapore selected: zonal CPU $0.0578/vCPU-hour; RAM $0.0098/GiB-hour; HA CPU $0.1156/vCPU-hour; HA RAM $0.0196/GiB-hour. SSD $0.000326027/GiB-hour zonal, $0.000652055 HA. Storage amounts below use the provisioned GiB, not database file size.

| Configuration | Compute/month | SSD/month | Total USD | Approximate PHP |
| --- | ---: | ---: | ---: | ---: |
| Current: 8 CPU / 32 GiB, HA, 250 GiB SSD | 1,132.96 | 119.00 | 1,251.96 | 78,873 |
| Conservative first step: 4 CPU / 16 GiB, HA, 250 GiB SSD | 566.48 | 119.00 | 685.48 | 43,185 |
| 2 CPU / 8 GiB, HA, existing 250 GiB SSD | 283.24 | 119.00 | 402.24 | 25,341 |
| Target after validation: 2 CPU / 8 GiB, HA, 100 GiB SSD | 283.24 | 47.60 | 330.84 | 20,843 |
| Optional single-zone target: 2 CPU / 8 GiB, 100 GiB SSD | 141.62 | 23.80 | 165.42 | 10,421 |

The HA target saves approximately **PHP 58,030/month (74%)** against the current database's list price. The first compute-only step saves approximately **PHP 35,688/month**. Actual cash savings depend on the billing account's credits and discounts. A low additional-budget limit from the Redis evaluation is not a total hosting-budget limit.

Cloud Run cost depends on billable active time, concurrent work, requests and shared billing-account free-tier usage, so the database table is not a whole-project bill estimate. Keep minimum instances at zero for cost priority; this permits cold starts after idle periods. Do not increase CPU or memory merely because the database is smaller. Revisit warm instances only if measured cold-start delays justify their ongoing cost. See [Cloud Run pricing](https://cloud.google.com/run/pricing) and [concurrency tradeoffs](https://docs.cloud.google.com/run/docs/about-concurrency).

Short connection reuse can reduce repeated connection setup in this WSGI deployment. Each thread maintains its own connection, so check the resized database's connection limit against three instances × 16 threads, overlapping rollout revisions and diagnostic jobs. See [Django persistent connections](https://docs.djangoproject.com/en/5.2/ref/databases/#persistent-connections).

No production resize, disk shrink or application configuration change was made for this recommendation. Read-only diagnostic execution: `pabasa-revision-check-01172-d9htf`. Aggregate evidence: `tmp/hosting-sizing-metrics.json`, `tmp/database-sizing-settings.json`, `tmp/hosting-sizing-costs.json`.
