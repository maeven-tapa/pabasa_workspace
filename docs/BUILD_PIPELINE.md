# GitHub build checks and deployment

`cloudbuild.yaml` is the versioned build configuration for the existing GitHub
`^main$` push trigger in project `pabasa-web`, location `global`:
`393c4c29-ff90-43b0-8057-c09eef4c03bb`.
Keep its GitHub status/log reporting enabled. Do not add a second deployment
workflow or trigger for the same branch. Cloud Build publishes the GitHub check
for the complete pipeline, including failures before deployment.

1. Build the Python 3.13 application image.
2. Run `tools/check_build.py` inside that exact image. It uses disposable SQLite,
   runs Django system/model-migration checks and focused account, database,
   enrollment and review workflow tests, and tests release safety behavior.
   It rejects build contexts containing `.env`.
3. Push the checked image and resolve its immutable digest.
4. Create and verify an on-demand backup of the selected service's attached
   Cloud SQL instance. The build identity needs the custom
   `projects/pabasa-web/roles/pabasaReleaseBackup` role, containing only
   `cloudsql.backupRuns.create`, `cloudsql.backupRuns.get`,
   `cloudsql.backupRuns.list` and `cloudsql.instances.get`.
5. Run a unique same-digest Cloud Run migration job. Copy runtime identity,
   database environment/secrets, volumes and Cloud SQL attachment from the
   current service. Require recorded migration readiness, run Django checks and
   the migration plan, apply migrations, then require `migrate --check`.
   The standalone gate defaults to rejecting pending migrations unless
   `--apply-migrations` explicitly requests the backup-protected path.
6. Stage a uniquely named revision with no traffic. Verify readiness, image
   digest and HTTPS home/login responses. Run a same-image authenticated check
   of the teacher dashboard/review queue and anonymous-access rejection. Its
   synthetic users, school and sessions are enclosed in a rolled-back database
   transaction; no student records or speech APIs are used.
7. Refuse promotion if a newer triggered build exists. Move traffic to the
   verified revision only after all checks pass. Keep previous revisions for
   traffic rollback. Do not automatically reverse database migrations.

The build identity also needs
`projects/pabasa-web/roles/pabasaReleaseBuildRead`, containing only
`cloudbuild.builds.get` and `cloudbuild.builds.list`, to check build ordering
before promotion. The existing Artifact Registry writer, Cloud Run admin,
service account user and logging writer bindings remain in place.

The web image retains both startup guards: recorded migration readiness and
`migrate --check`. Speech project selection is read directly from runtime
environment settings; the build does not rewrite application source.

## Retired-project duplicate

On November 15, 2026, GitHub also reported a queued check from retired project
`project-2b0d295d-ee06-40a7-927`, named
`pabasa-workspace-deployment--trigger`. The active account
`tupc.pabasa@gmail.com` was denied access to that project's triggers. Its owner
must disable the retired trigger in Cloud Build. Leave the current `pabasa-web`
trigger enabled. Do not remove the Google Cloud Build GitHub app, which serves
the current trigger too.
