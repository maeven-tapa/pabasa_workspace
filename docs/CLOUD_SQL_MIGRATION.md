# Move PABASA from local SQLite to Cloud SQL

The source selected for this move is the local `pabasa_site/db.sqlite3`. The prepared
backup/export is in `backups/cloud-sql-20261008T032731Z/`: 171 records, including 10
accounts and 27 Django sessions. The source was opened read-only and was not migrated.
The exporter applies pending migrations only to a separate working copy.

Cloud SQL instance connection name from the console:

```text
project-2b0d295d-ee06-40a7-927:asia-southeast1:pabasa-db
```

## 1. Create the database, application user, and password secret

In **SQL → pabasa-db → Databases**, create a database named **pabasa**.
In **Users**, create a built-in PostgreSQL user named **pabasa_app** with a generated
password. Store this application's database password in **Secret Manager**:

| Secret Manager field | Value |
| --- | --- |
| Name | `pabasa-db-password` |
| Secret value | The password assigned to the `pabasa_app` database user |
| Version | Pin the initial version, `1` |

In Cloud SQL Studio, connect as the administrator to the **pabasa** database and
grant the new user permission to create its application tables:

```sql
GRANT USAGE, CREATE ON SCHEMA public TO pabasa_app;
```

The database password is separate from `DJANGO_SECRET_KEY`. Keep the existing Django
signing key and its secret mapping. Store no password in source, Dockerfile, or an
ordinary Cloud Run environment variable.

## 2. Prepare the runtime identity and settings

Find the existing web service's runtime service account in **Cloud Run → service →
Security**. Use that same identity for the one-time import job. Grant it:

- **Cloud SQL Client** on the project containing the SQL instance.
- **Secret Manager Secret Accessor** on `pabasa-db-password` and access to the
  existing Django signing secret.
- **Storage Object Viewer** on the private migration bucket used in step 4.

For the import job and the eventual web revision, configure these ordinary environment
variables (the code builds the Unix socket path from the connection name):

| Variable | Value |
| --- | --- |
| `DB_ENGINE` | `postgresql` |
| `DB_NAME` | `pabasa` |
| `DB_USER` | `pabasa_app` |
| `INSTANCE_CONNECTION_NAME` | `project-2b0d295d-ee06-40a7-927:asia-southeast1:pabasa-db` |

Under **Containers → Variables & Secrets → Reference a secret**, set:

| Environment variable name | Secret | Version |
| --- | --- | --- |
| `DB_PASSWORD` | `pabasa-db-password` | `1` |
| `DJANGO_SECRET_KEY` | Your existing Django signing secret | Its existing pinned version |

Under **Cloud SQL connections**, attach **pabasa-db**. Adding an environment
variable alone does not create the Cloud SQL socket connection. Use the supported
Cloud SQL integration for the public-IP instance; no public-IP allowlist is needed
for that integration.

Cloud Run services and jobs both require PostgreSQL in the updated code. A missing
database setting fails startup instead of creating an instance-local SQLite database.
Local development still defaults to SQLite. Do not deploy the web revision yet.

## 3. Build the updated application image

Build this updated checkout using your normal container build pipeline. Record the
new image's full Artifact Registry URL for the import job and subsequent web revision.
An old image will not contain `import_cloud_sql_export` or the PostgreSQL settings.
The `backups/` directory is excluded from Git and the Docker build context.

## 4. Upload the prepared export privately

Create a private Cloud Storage bucket in `asia-southeast1`. Upload these two files
from `backups/cloud-sql-20261008T032731Z/` into its root:

- `pabasa-data.json`
- `manifest.json`

These contain private student/account records and password hashes. Keep the bucket
private. Keep `source.sqlite3`, the untouched backup, locally. Uploading it is not
necessary for the import.

If source data changes before cutover, pause application writes and generate a fresh
export with `python tools/export_cloud_sql.py`, then upload that export and manifest
together. Keep production writes paused through the final import and traffic switch.

## 5. Run the one-time import job

In Cloud Shell, set the following values. Replace all uppercase placeholders with
the new image, the existing runtime identity, your private bucket, and the EXISTING
Django secret name/version. The command never contains the database password.

```bash
PROJECT='project-2b0d295d-ee06-40a7-927'
REGION='asia-southeast1'
CONNECTION="$PROJECT:$REGION:pabasa-db"
IMAGE='YOUR_NEW_ARTIFACT_REGISTRY_IMAGE_URL'
RUNTIME_SA='YOUR_EXISTING_CLOUD_RUN_SERVICE_ACCOUNT_EMAIL'
BUCKET='YOUR_PRIVATE_MIGRATION_BUCKET'
DJANGO_SECRET='YOUR_EXISTING_DJANGO_SECRET_NAME'
DJANGO_SECRET_VERSION='YOUR_EXISTING_PINNED_VERSION'

gcloud run jobs deploy pabasa-db-import \
  --project="$PROJECT" --region="$REGION" --image="$IMAGE" \
  --service-account="$RUNTIME_SA" \
  --set-cloudsql-instances="$CONNECTION" \
  --set-env-vars="DB_ENGINE=postgresql,DB_NAME=pabasa,DB_USER=pabasa_app,INSTANCE_CONNECTION_NAME=$CONNECTION" \
  --set-secrets="DB_PASSWORD=pabasa-db-password:1,DJANGO_SECRET_KEY=$DJANGO_SECRET:$DJANGO_SECRET_VERSION" \
  --add-volume="mount-path=/migration,type=cloud-storage,bucket=$BUCKET,readonly=true" \
  --command=python \
  --args="pabasa_site/manage.py,import_cloud_sql_export,/migration/pabasa-data.json,--expected-database,pabasa" \
  --tasks=1 --parallelism=1 --max-retries=0 --task-timeout=30m

gcloud run jobs execute pabasa-db-import \
  --project="$PROJECT" --region="$REGION" --wait
```

The importer verifies the export checksum, requires a completely empty PostgreSQL
database, creates the schema, clears only the new bootstrap data, and restores the
source's records/IDs. It then compares every exported record and field with the
restored data. Expected success for the prepared snapshot:

```text
Imported and verified all 171 records in pabasa.
```

It refuses to overwrite a database that already has tables. Disable automatic retries.
If schema creation or import fails, inspect the failure before doing anything else;
use a separate new empty database for another attempt. Never clear a live database
to make the importer run again.

## 6. Deploy the web revision after the job succeeds

Use the same new image, Cloud SQL connection, runtime identity, four environment
variables, and two secret references described above. Preserve all existing speech,
email, and other environment/secret settings. Test login, dashboard, account creation,
and progress saves on the new revision, then direct traffic to it and resume writes.
The web container checks that migrations have already run; it does not change the
schema when Cloud Run adds instances.

Set Cloud Run's maximum instance count with the SQL instance's connection limit in
mind; each concurrent request can use a database connection. This image has 16 worker
threads. Tune concurrency and instance count after checking the chosen SQL capacity.

The export includes existing Django sessions, but they remain usable only with the
same Django signing key that signed the source sessions, and a valid browser cookie
on the same hostname. Users may need to sign in once if the source key differs.

Cloud SQL stores database records, including recording filenames. Uploaded audio,
images, and other files need their own persistent storage, such as Cloud Storage;
moving the database does not transfer those files.

## Validation performed locally

- Imported and compared all 171 records against a temporary PostgreSQL 18 server.
- Confirmed a repeated import refuses an existing database.
- Checked that primary-key sequences in 42 tables allocate IDs above imported IDs.
- Fixed seven repeated AddField operations and integer-to-Boolean SQL in the
  consolidated migration, which PostgreSQL rejected on a fresh install.
- Configuration and account-session tests exercise SQLite and PostgreSQL.

The repository already has ID-field drift between current models (BigAutoField) and
some recorded migrations (AutoField); `makemigrations --check --dry-run` reports it.
This move preserves the existing migration field types rather than generating a
separate change to all primary keys. The old `tools/verify_migrations.py` also assumes
there are no follow-up migrations, so its migration-file assertion is outdated.

## References

- [Connect Cloud Run to Cloud SQL](https://docs.cloud.google.com/sql/docs/postgres/connect-run)
- [Reference Secret Manager secrets in Cloud Run](https://docs.cloud.google.com/run/docs/configuring/services/secrets)
- [Mount a Cloud Storage bucket in a Cloud Run job](https://docs.cloud.google.com/run/docs/configuring/jobs/cloud-storage-volume-mounts)
