# PABASA 20-client benchmark policy

All capacity benchmarks formerly using 15 concurrent clients now use 20.
Historical reports in `FIFTEEN_USER_TEST.md` and
`SHARED_CORE_FIFTEEN_USER_TEST.md` retain their actual measured counts.
This change updates the tools; it does not report a completed live 20-client run.

The existing script names remain compatible with references and dispatchers:

| Script | Updated workload/output |
| --- | --- |
| `tools/test_fifteen_users.py` | 20 temporary sessions, 20 HTTP workers, three rounds of three endpoints: 180 HTTP requests, 60 per endpoint. Internal profiling uses 40 samples per endpoint with up to 20 workers. Emits `PABASA_TWENTY_USER_TEST`. |
| `tools/test_current_fifteen_users.py` | Nine single-client baseline requests, then 20 synchronized clients across three rounds of three endpoints: 180 concurrent requests, 189 total when successful. Emits `PABASA_CURRENT_TWENTY_TEST`. |
| `tools/profile_student_list.py` | Three sequential samples, then 40 samples with up to 20 workers. Reports `concurrency: 20` and `concurrent_20`. |
| `tools/benchmark_dashboard_cache.py` | 20 workers and 40 samples per endpoint for internal views and synthetic cache reads. Reports `concurrency: 20`. |

Both HTTP benchmarks expire temporary sessions after ten minutes and delete them
in `finally`. The current benchmark retains its early abort on baseline failure
or at least five failures in one concurrent wave. Incomplete runs can therefore
have fewer requests than the successful totals above.

These scripts share an existing teacher and class. They measure concurrent user
requests; they do not create 20 students or prove performance for a 20-student
roster. Report the actual class row count and tested account/workflow scope.

## Results and metrics

- Save the `PABASA_TWENTY_USER_TEST` JSON report as
  `tmp/twenty-user-test.json`. `tools/collect_fifteen_user_metrics.py` reads it
  and writes `tmp/twenty-user-test-metrics.json`. The dispatcher writes
  `tmp/twenty-user-test-execution.txt`.
- `tools/collect_current_fifteen_metrics.py` uses the job name in
  `tmp/current-loadtest-job-name.txt`, reads the new log marker, and writes
  `tmp/current-twenty-user-test.json` and
  `tmp/current-twenty-user-metrics.json`.
- Both collectors reject reports whose client count is not 20. Their HTTP log
  filters use the benchmark's reported user agent.
- Before live execution, recheck the active cloud account, image, job identity,
  database connection, service revision, traffic, and collector resource filters.
  The scripts retain historical job/revision/instance targets that may need
  adjustment to match the intended environment.

Run offline benchmark regression checks without contacting production:

```powershell
python -m unittest discover -s tools -p test_load_benchmark_config.py
```
