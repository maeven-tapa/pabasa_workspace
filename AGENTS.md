# PABASA agent instructions

## Repository and local development

- PABASA is a Django reading assessment and guided practice application for
  students, teachers, and school administrators.
- Use Python 3.13 and the dependencies in `requirements.txt`.
- Run commands from the repository root. The Django entry point is
  `pabasa_site/manage.py`; the active application is `pabasa_site/pabasa_app/`.
  Settings and database configuration are in `pabasa_site/pabasa_site/`.
  Resolve the active import/template path before editing similarly named files
  in the separate root-level `pabasa_app/` directory.
- Application templates and static assets are under
  `pabasa_site/pabasa_app/templates/` and `pabasa_site/pabasa_app/static/`.
- Settings load `.env` from the repository root. Local development defaults to
  SQLite; production requires PostgreSQL and `DJANGO_SECRET_KEY`.
- Preserve existing local changes and runtime data. Keep credentials, session
  cookies, recordings, and student data out of source control and command output.

For a new local environment, use PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python pabasa_site/manage.py check_migration_readiness
python pabasa_site/manage.py migrate
python pabasa_site/manage.py runserver
```

Confirm the database configuration targets the intended local database before
running migrations. If the readiness check rejects an existing database, follow
its recovery guidance instead of bypassing it.

## Validation and application behavior

- Always use **20 concurrent students/users/clients** for capacity benchmarks
  that previously used 15, including HTTP load tests, roster SQL profiling, and
  dashboard/cache benchmarks. Keep session counts, worker pools, barriers,
  reports, log markers, and metrics collectors consistent with 20 clients.
- Existing `tools/*fifteen*` filenames are retained for compatibility, but their
  benchmarks now use 20 clients and write new `twenty` report/output names.
  See `docs/TWENTY_USER_TESTING.md` for the updated scripts and expected counts.
- Preserve historical 15-client measurements as historical evidence. Record
  new results separately; a shared teacher/class benchmark is not evidence for
  20 distinct student accounts or a roster containing 20 enrolled students.
- Run relevant Django test modules for the affected workflow. Broaden testing
  when changes affect shared assessment, authorization, enrollment, or progress
  logic. Run schema checks when changing models or migrations.
- Useful commands from the repository root:

```powershell
python pabasa_site/manage.py check
python pabasa_site/manage.py test pabasa_app.tests_database_config
python pabasa_site/manage.py test pabasa_app
python pabasa_site/manage.py makemigrations --check --dry-run
```

- Preserve school, class, teacher, and student authorization boundaries when
  changing queries, caching, exports, or endpoints.
- Keep reading grades and completion behavior consistent with the accepted
  scoring rules. Investigate conflicting tests and implementation before
  changing either rule to make a check pass.
- For speech changes, verify the selected provider, language, error handling,
  and recording lifecycle. Provider failures must not invent successful reading
  results or silently switch the learner's selected provider.
- Browser recording requires microphone permission and HTTPS or localhost.
  Verify affected interactive workflows in the browser when Django tests do
  not cover recording, navigation, or layout behavior.
- Inspect scripts under `tools/` before running them: some target the live site
  or create temporary authentication sessions. Match execution to the task's
  authorized scope and clean up temporary resources.

## Live website and cloud work

- The live website is https://tupcpabasa.app (confirmed by the user).
- Google Cloud project: `project-2b0d295d-ee06-40a7-927`.
- Cloud Run service: `pabasa`, region: `asia-southeast1`.
- Cloud Run service URL: https://pabasa-7j5jji5rpa-as.a.run.app.
- On this Windows computer, Google Cloud CLI is installed at
  `C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd`.
  If `gcloud` is absent from the terminal PATH, invoke this full path in PowerShell.
- Google Cloud CLI authentication and log access were verified on October 10, 2026.
  Recheck the active account, service state, and traffic before cloud work; they can change.
- For live-site debugging, correlate browser behavior with Cloud Run logs and local source.
- Run database migrations in a Cloud Run Job using the same new image digest
  before deploying or switching traffic. Match the intended database connection,
  runtime identity, and secret references to the web service.
- Check `check_migration_readiness` before migrating. Current web startup runs
  `check_migration_readiness --require-recorded` and `migrate --check`; preserve
  both guards. If historical migrations are missing, use the previous release
  containing the originals as directed by the readiness check.
- Confirm the migration job succeeds and `migrate --check` passes before
  activating the new revision. Preserve a database backup before schema changes.
- Verify active startup, the intended image digest, affected authenticated
  workflows, and request logs before switching traffic. Retain a working revision
  for traffic rollback; do not automatically reverse database migrations.
- The Dockerfile currently starts Uvicorn/ASGI; the Procfile starts
  Gunicorn/WSGI. Inspect the deployed command before assuming worker counts,
  thread counts, or concurrency behavior from historical reports.
- The existing job `pabsa` is an old data import job, not the release migration job.
- The October 10, 2026 revision recovery is recorded in
  `docs/CLOUD_RUN_REVISION_RECOVERY.md`.

## Dated operational evidence

- Treat repository reports as dated evidence, not live configuration. Recheck
  the connected Cloud SQL instance, tier, availability mode, storage, Cloud Run
  memory, concurrency, instance limits, image, and traffic before cloud changes.
- The earlier October 10, 2026 resize to `db-custom-2-8192` (2 vCPUs / 8 GiB),
  regional HA, and 250 GiB storage is documented in `docs/FIFTEEN_USER_TEST.md`.
  That bounded test found slow roster SQL and high Cloud Run memory usage.
- A later October 10 report, `docs/SHARED_CORE_FIFTEEN_USER_TEST.md`, records
  Cloud SQL `pabasa-db-micro` on `db-g1-small`, single zone, 10 GiB SSD, and
  Cloud Run at 1 vCPU / 1 GiB. It measured student-list responses averaging
  about 6.45 seconds for 15 simultaneous clients. These settings were recorded
  by that report and have not been reverified by updating this file.
- Both tests used separate sessions sharing one teacher/class with one active
  student. Successful HTTP responses do not establish responsive classroom
  capacity, larger-roster performance, or assessment/recording capacity.
- Correlate slow requests with SQL timing and Cloud Run logs. Report sample
  scope, latency, errors, and resource observations; avoid treating sampled
  averages as instantaneous peaks or uncontrolled runs as hardware comparisons.
- Additional context: `docs/CLOUD_SQL_MIGRATION.md`,
  `docs/WEBAPP_ERROR_SCAN.md`, `docs/CRLA_STREAMING.md`, and
  `docs/HOSTING_EFFICIENCY_PLAN.md`. Prefer newer measured evidence over older
  recommendations, and verify runtime behavior against source and live state.
