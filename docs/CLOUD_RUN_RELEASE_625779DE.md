# Release 625779de and production database migrations

Completed October 14, 2026, approximately 00:08 Asia/Manila.
The user authorized the production backup, migrations, verification, and deployment.

## Result

- Commit: `625779deb322e85f451dbd97872dbb1bb766be91`.
- Cloud Run service: `pabasa`, project `project-2b0d295d-ee06-40a7-927`, region `asia-southeast1`.
- Production database instance: `pabasa-db-micro`, PostgreSQL 18.
- On-demand backup `1791906643101` completed successfully before schema changes.
- Migrations `0030_otp_debug_settings`, `0031_optional_email_default_password`, and
  `0032_student_only_default_password` applied successfully; `migrate --check` passed.
- Revision `pabasa-01299-bid` passed active startup and receives 100% of traffic.
- Previous working revision `pabasa-01288-h27` remains available for traffic rollback.
- Website: https://tupcpabasa.app.

The migration job and web revision use the same immutable image:

```text
asia-southeast1-docker.pkg.dev/project-2b0d295d-ee06-40a7-927/cloud-run-source-deploy/pabasa_workspace/pabasa@sha256:dbcacae478edd72fae0fc6310ca4f637dc5c2ae61c4a3809d3296218c346978d
```

The web service's environment and secret references were preserved. Both startup
guards remain in the image: `check_migration_readiness --require-recorded` and
`migrate --check`, followed by Uvicorn/ASGI.

## Recovery details

The automatic deployments of the commit failed at startup. A production migration
preview confirmed that exactly the three new migrations were pending. The deployment
trigger still has Build, Push, and Deploy steps, without a migration-job step.

The old job `pabasa-revision-check-01172` targets `pabasa-db`, whereas the current web
service targets `pabasa-db-micro`. It was not used or modified for this release.
New job `pabasa-migrate-625779de` was created from the web service's current environment,
secret references, runtime identity, and Cloud SQL connection. It uses one task,
parallelism one, and zero retries. Its final default command checks migration readiness
and displays `migrate --plan`; executing the default does not apply migrations.

The original failed revision's image was no longer present in Artifact Registry.
The repository's observed cleanup policy deletes versions older than 1,800 seconds
and preserves the most recent version. The exact Git commit was rebuilt directly from
GitHub, without uploading the local workspace or its runtime data. Build
`da072f73-385b-448a-b84d-48be9bd5439b` succeeded. No cleanup or deployment-trigger
settings were changed.

Successful job executions:

| Purpose | Execution |
| --- | --- |
| Readiness and migration preview | `pabasa-migrate-625779de-w9fk2` |
| Readiness, apply migrations, and `migrate --check` | `pabasa-migrate-625779de-6c9fc` |
| Application checks against production in a rolled-back transaction | `pabasa-migrate-625779de-c9zk6` |
| Public HTTPS and authenticated admin verification | `pabasa-migrate-625779de-nz7cj` |

The first application-check execution, `pabasa-migrate-625779de-9w9pq`, failed because
the test client omitted Cloud Run's HTTPS proxy header and encountered the production
HTTPS redirect. The corrected check passed; application source was unchanged.

## Verification and limits

- Seventy-one local tests passed across OTP, registration defaults, database
  configuration, account sessions, and enrollment lifecycle modules. The database
  configuration tests were rerun with the application's directory on `PYTHONPATH`
  after their subprocess imports failed in the initial test invocation.
- `makemigrations --check --dry-run` still reports the pre-existing AutoField versus
  BigAutoField differences documented in `CLOUD_SQL_MIGRATION.md`. No migration was
  generated or applied for those differences.
- The release image rendered login and both signup pages with production database
  access, rendered authenticated admin settings with the new OTP control, redirected
  anonymous admin access, and rejected empty student/teacher signup submissions.
  All database writes from this internal check were rolled back.
- On the public website, `/`, `/auth/`, `/signup/student/`, `/signup/teacher/`, and
  authenticated `/dashboard/admin/settings/` returned HTTP 200. The admin response
  contained the new Disable OTP control. The temporary verification session was deleted.
- OTP settings were not changed, and no production signup accounts were created.
  End-to-end email delivery and browser form interaction were not exercised.
- Startup logs showed Uvicorn listening on port 8080 and a successful startup probe.
  No ERROR-or-higher entries were returned for the new revision during verification.
- Temporary traffic tag `recovery-625779de` was removed after verification.

For application rollback, move traffic to `pabasa-01288-h27`; do not automatically
reverse database migrations. Future releases that add migrations still require a
job using their new image and the current database configuration before activation.

Operational configuration snapshots and verification scripts are in the ignored
`backups/release-625779de/` directory. They must remain outside source control and
container build contexts.
