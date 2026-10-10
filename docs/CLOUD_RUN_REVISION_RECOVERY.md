# Recover the failed PABASA revision

Verified on October 10, 2026 (Asia/Manila).

## Recovery completed

The user authorized applying migrations and redeploying. Recovery succeeded:

- On-demand Cloud SQL backup `1791563828493` completed successfully.
- Migration execution `pabasa-revision-check-01172-dzxrx` succeeded.
- Verification execution `pabasa-revision-check-01172-9gjrk` ran `migrate --check`
  successfully, confirming there were no pending migrations.
- Replacement revision `pabasa-01173-w2r` passed its port 8080 startup probe and
  started Gunicorn. It now serves 100% of traffic.
- The homepage and `/auth/` returned HTTP 200. An unauthenticated `/dashboard/`
  request reached the login page successfully. Authenticated reading workflows
  were not exercised during this deployment check.
- No ERROR-or-higher logs were returned for the new revision at the final check.
- The temporary `recovery-01173` traffic tag was removed after verification.

The diagnostic job remains configured to run `migrate --plan` by default;
execution overrides were used for the migration and verification runs.

## Original diagnosis

The failed revision `pabasa-01172-mqt` uses commit `080a9662` and has four
unapplied migrations: `0026_reading_fluency_review`,
`0027_prescribed_reading_attempt`, `0028_prescribed_reading_audio_features`, and
`0029_prescribed_reading_validation_label`. A read-only `migrate --plan` execution
against production confirmed this exact list. These migrations add fields and
tables; they do not delete existing records.

The Docker startup command runs `migrate --check` before Gunicorn. That check
exits with status 1 when migrations are pending, so no server listens on port 8080.
Keep this startup guard. Apply migrations once using the same release image,
then deploy a new revision. Increasing the startup timeout does not apply migrations.

Before recovery, working revision `pabasa-01171-npz` served all traffic. The existing
job `pabsa` is an old data import job; do not use it for schema migrations.

## Recovery procedure used

The commands below change the production database and deploy the application.
They document the approved recovery. Recheck the service and diagnostic job
configuration before reusing them for another release.

Run in PowerShell. The helper stops on any unsuccessful command.

```powershell
$GcloudExecutable = 'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
$ProjectId = 'project-2b0d295d-ee06-40a7-927'
$Region = 'asia-southeast1'
$ReleaseImage = 'asia-southeast1-docker.pkg.dev/project-2b0d295d-ee06-40a7-927/cloud-run-source-deploy/pabasa_workspace/pabasa@sha256:4416cd4a25dfc9515c8f169bac9de053d99e3356d94bbdbcb88ae6eec4d1473a'
$DiagnosticJob = 'pabasa-revision-check-01172'
$RecoveryTag = 'recovery-01173'

function Invoke-RecoveryGcloud {
    & $GcloudExecutable @args
    if ($LASTEXITCODE -ne 0) { throw 'Google Cloud command failed. Stop and inspect the error.' }
}

# Preserve a backup before changing the database.
Invoke-RecoveryGcloud sql backups create --instance=pabasa-db --project=$ProjectId --description='Before recovery of PABASA revision 01172'

# This job was created with the exact failed image, runtime service account,
# Cloud SQL connection, and database/signing secret references.
# Override arguments for this execution only; the job's default remains migrate --plan.
Invoke-RecoveryGcloud run jobs execute $DiagnosticJob --project=$ProjectId --region=$Region --args='pabasa_site/manage.py,migrate,--noinput' --wait

# Confirm that every migration required by this image is now applied.
Invoke-RecoveryGcloud run jobs execute $DiagnosticJob --project=$ProjectId --region=$Region --args='pabasa_site/manage.py,migrate,--check' --wait

# Create a replacement revision using the same image, retaining service settings.
# Keep traffic on the working revision until startup has been verified.
$ReplacementRevision = Invoke-RecoveryGcloud run services update pabasa --project=$ProjectId --region=$Region --image=$ReleaseImage --no-traffic --format='value(status.latestCreatedRevisionName)'
# An untagged revision with no traffic can remain retired without starting.
# A temporary tag activates the revision so startup can be checked.
Invoke-RecoveryGcloud run services update-traffic pabasa --project=$ProjectId --region=$Region --update-tags="$RecoveryTag=$ReplacementRevision"
$RevisionState = (Invoke-RecoveryGcloud run revisions describe $ReplacementRevision --project=$ProjectId --region=$Region --format=json) | ConvertFrom-Json
$ReadyCondition = $RevisionState.status.conditions | Where-Object { $_.type -eq 'Ready' }
if ($ReadyCondition.status -ne 'True' -or $ReadyCondition.reason -eq 'Retired') { throw 'Replacement revision has not passed active startup verification.' }

# Proceed only after the replacement revision's Ready condition is True.
Invoke-RecoveryGcloud run services update-traffic pabasa --project=$ProjectId --region=$Region --to-revisions="$ReplacementRevision=100"
Invoke-RecoveryGcloud run services describe pabasa --project=$ProjectId --region=$Region --format='json(status.latestReadyRevisionName,status.traffic)'
# After checking the public site, remove the temporary test URL.
Invoke-RecoveryGcloud run services update-traffic pabasa --project=$ProjectId --region=$Region --remove-tags=$RecoveryTag
```

Verify https://tupcpabasa.app, login, and the affected Lesson 14 reading activity.
Inspect the new revision's logs for startup and request errors. A migration check
and Ready status establish schema/startup readiness, not correctness of every feature.

If the new application has a problem, move traffic back to `pabasa-01171-npz`.
Do not reverse the migrations automatically; newer records may depend on them.

## Future releases

Run a migration job with the newly built image before switching the web service
to that image. A job using an older image cannot apply migrations added in a new
commit. Pin both the migration job and web deployment to the same image digest.

References:

- [Django migrate --check](https://docs.djangoproject.com/en/6.0/ref/django-admin/#cmdoption-migrate-check)
- [Cloud Run job execution overrides](https://docs.cloud.google.com/run/docs/execute/jobs)
