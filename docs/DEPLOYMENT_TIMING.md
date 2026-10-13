# Deployment timing investigation

Verified October 11, 2026 (Asia/Manila). Read-only inspection of Cloud Build,
Artifact Registry metadata, Cloud Run state, and local source. No build was
started, no trigger was changed, and no production deployment was performed.

## Finding

The observed six-to-seven-minute deployment is dominated by rebuilding the
Docker image and uploading its layers. The active GitHub trigger explicitly
uses `docker build --no-cache`. Every run therefore repeats OS package
installation and Python dependency installation, even for a template edit.

The eight latest builds all succeeded and took approximately 4m31s to 6m44s,
measured from build creation to completion. This does not measure the interval
from the user's Git push to Cloud Build creation.

## Measured breakdown

| Phase | Build at 01:28 on October 11 | Latest build at 02:37 on October 11 |
| --- | ---: | ---: |
| Fetch source | 36 seconds | 33 seconds |
| Docker build step | 163 seconds | 132 seconds |
| Explicit image push step | 119 seconds | 112 seconds |
| Deploy step, including Cloud SDK image/setup | 76 seconds | 70 seconds |
| Remaining setup and final image push | 10 seconds | 9 seconds |
| Total, rounded | **6m44s** | **5m56s** |

Build IDs:

- [7563c364-78e1-4cc5-931c-b5889e3c2824](https://console.cloud.google.com/cloud-build/builds/7563c364-78e1-4cc5-931c-b5889e3c2824?project=project-2b0d295d-ee06-40a7-927)
- [2a7df11f-e222-4e37-8926-7a8489de02b3](https://console.cloud.google.com/cloud-build/builds/2a7df11f-e222-4e37-8926-7a8489de02b3?project=project-2b0d295d-ee06-40a7-927)

The top-level Cloud Build `BUILD` timing includes the explicit Build, Push,
and Deploy steps. It must not be interpreted as Docker build time alone.

## Why these steps take time

- Trigger `pabasa-workspace-deployment--trigger`
  (`417e490f-6d0e-4967-a36d-8b3d2f3bcab4`) has an inline Build/Push/Deploy
  configuration; it does not reference a repository YAML file. The Docker
  build arguments include `--no-cache`, with no cache import.
- The latest log reports a **771 MB Docker build context**. Locally present
  tracked application static assets account for approximately **713 MiB**.
  These are runtime learning assets; exclusion requires an asset inventory
  and a verified replacement serving path.
- `Dockerfile` installs Tesseract and LibreOffice Calc, then all of
  `requirements.txt`. LibreOffice is used by CRLA exports. Python dependencies
  include PyQt5, audio decoding, and speech libraries. No direct PyQt5 import
  was found in the inspected active application/tools Python files; investigate
  indirect use and development tooling before removing it.
- `COPY . .` brings source/static assets into the image. `collectstatic`
  then copies 3,094 files into `/app/pabasa_site/staticfiles`. Both source assets
  and collected output remain in the image under the current Dockerfile.
- The latest explicit push uploaded multiple new layers and took 112 seconds.
  The automatic final push took another 6.4 seconds. This repeated push is a
  small contributor compared with the first upload.

## Cloud Run timing and live state

Latest revision `pabasa-01210-txh` was serving 100% of traffic at inspection.
Cloud Run reports:

- Revision ready in **28.1 seconds**.
- Image import in **13.91 seconds**.
- Containers healthy in **9.95 seconds**.

The 240-second TCP startup probe is a timeout allowance. This deployment did
not wait four minutes for it. The deployment step also includes Cloud SDK
builder setup and command overhead.

The service has no command/argument override, so the image's Docker CMD applies:
migration readiness checks, `migrate --check`, then Uvicorn/ASGI. The inspected
service uses 1 vCPU, 1 GiB memory, concurrency 80, min 0 / max 3 instances, and
the `pabasa-db-micro` Cloud SQL connection. These are observations, not a
capacity benchmark.

## Recommended order of improvement

1. Replace `--no-cache` with a persistent Docker layer cache strategy. Merely
   removing the flag does not establish reuse between fresh build workers.
   Pull/import a previous cache or use a registry-backed build cache; measure
   its download cost against the saved installation/upload work.
2. Audit runtime dependencies and static assets. Separate development-only
   dependencies and consider serving large learning assets outside the image.
   Retain LibreOffice export support and speech dependencies where required.
3. Reduce duplicated source/collected static content using a verified image
   assembly strategy. Validate Django static serving and export asset paths.
4. Add trigger path filters if documentation-only changes should not deploy.
   No included/ignored path filters were returned for the current trigger.

Google documents Docker cache imports and leaner containers in its
[Cloud Build speed guidance](https://docs.cloud.google.com/build/docs/optimize-builds/speeding-up-builds).
No faster deployment target has been measured yet.

The inspected trigger has no migration-job step. Any replacement release
pipeline must follow the repository's migration-readiness procedure, execute
migrations and verification with the same new image digest before activation,
preserve backups for schema changes, and retain both web startup guards.
Keep a working revision available for traffic rollback.
