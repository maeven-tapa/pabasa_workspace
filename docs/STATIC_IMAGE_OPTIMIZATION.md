# Static image optimization

Local measurements, source replacement, and direct static serving on October 11, 2026. The compact profile is the smallest profile tested with the selected quality and resolution safeguards. The optimized files replace the original application static images. Production now serves source assets directly, without creating a duplicate `staticfiles` directory. No cloud deployment has been performed.

## Measured results

| Profile | Image library payload | Reduction from original |
| --- | ---: | ---: |
| Original | 624.9 MB | 0.0% |
| First lossless pass | 434.6 MB | 30.5% |
| Web: larger resolution | 112.0 MB | 82.1% |
| Compact: build default | 82.5 MB | 86.8% |

MB uses 1,000,000 bytes. This is an inventory measurement: each original asset is counted once, choosing the smallest retained representation for a browser accepting both AVIF and WebP. It is not a page-load, live-traffic, or capacity benchmark. Actual page savings depend on which assets load and their cache state. All measurements exclude user uploads and include untouched image formats and skipped images.

Compact optimized 945 of 986 PNG, JPEG, and SVG candidates. The tested modern-browser payload was 82,466,640 bytes (78.6 MiB), versus 624,875,118 original bytes. The comparison's WebP-only payload was 87.6 MB. The compact image pool is 81.0% smaller than the first lossless result.

The installed source image library is **82,509,497 bytes (82.5 MB), 86.8% smaller than the originals**. The 42,857-byte difference from the smallest delivery measurement preserves the email logo as a compact PNG for mail-client compatibility. This now measures real files in the source asset directory, rather than selecting among retained sidecars. There are 988 image files: 816 WebP, 110 AVIF, 39 SVG, 20 PNG, one JPEG, one GIF, and one ICO. Files without a worthwhile, validated replacement remain unchanged.

All application static assets, including unchanged audio, video, fonts, CSS, and JavaScript, total 749.4 MB originally and 207.0 MB after replacement: 72.4% smaller. These inventories exclude uploads. Git history still contains historical originals; replacing working files does not rewrite repository history.

| Example | Original KiB | Compact KiB |
| --- | ---: | ---: |
| `color_mode/farm/sheep.png` | 11088.7 | 121.4 |
| `images/picture_word/custom/Bicycle-Bisikleta.png` | 7293.4 | 159.8 |
| `images/phrase_reading/stamp4.svg` | 19757.2 | 117.6 |
| `images/teacher_bg.jpg` | 6037.0 | 529.0 |
| `images/pabasalogo.png` | 1337.7 | 249.3 |

The prior lossless measurement (809 variants, original dimensions, identical RGBA pixels) remains recorded in the comparison. Its original verification is not a claim that the new compact profile is pixel-identical to the full-resolution masters.

## Resolution and quality

| Asset role | Compact longest edge | Web longest edge |
| --- | ---: | ---: |
| General illustrations | 1,024 px | 1,536 px |
| Backgrounds and full-width scene layers | 1,920 px | 2,560 px |
| Phrase-reading SVG embedded color images | 512 px | 768 px |
| Animation frame images | 768 px | 768 px |
| Logos | 1,024 px, lossless encoding | Same |
| Likely raster text, worksheets, workbook images, tracing assets, and CRLA story banners | Original dimensions, lossless encoding | Same |

Images are never upscaled. The 1,024-pixel illustration budget accommodates a 512-pixel display at double pixel density. Compact has less headroom for large screens and zoom than the web profile. The template audit confirmed alphabet labels and story text are rendered separately from their illustrations. Scene sea, clouds, grass, sand, pavement, vines, and fence layers receive the larger background budget because their CSS spans the activity area. Phrase decorations render at up to about 205 CSS pixels, while envelope stamps are smaller.

The existing Pillow 12.2 dependency supports both codecs locally; no extra library was installed. WebP starts at quality 85 and retries 92 and 97 when needed. AVIF starts at 70 and retries 80 and 90, with 4:4:4 color sampling. Every lossy candidate must reach visible PSNR of at least 38 dB using error averaged across light and dark composites, relative to the resized reference. This guards compression distortion, not resolution loss from resizing. Browser inspection is also used because this metric alone does not prove perceptual quality.

All retained raster variants are decoded and checked for dimensions and ICC preservation. Transparent assets use WebP with an exact alpha channel; AVIF is restricted to opaque, unprotected images because the installed AVIF encoder changes alpha values. AVIF is kept only if smaller than the WebP alternative. Candidates that fail the quality floor can use resized lossless WebP, or remain original. Protected raster text uses full-resolution lossless encoding. Logos are sized for display with lossless encoding.

Standard sRGB gamma/chromaticity declarations are accepted. For nonstandard PNG color information without an ICC profile, a resized PNG preserves the original gamma and chromaticity instead of guessing a color space. Its decoded pixels match the resized reference exactly. High-bit-depth and animated images are not flattened or reinterpreted. SVG vector markup stays intact; only embedded color bitmap data changes, while grayscale masks stay at their original resolution with lossless encoding where supported.

## Serving and build integration

`STATIC_ROOT = None` disables the collected output location. `WHITENOISE_USE_FINDERS = True` includes both the application's `static` directory and installed-package assets such as Django admin CSS/JavaScript. `WHITENOISE_AUTOREFRESH = DEBUG` means production builds its file index once at startup and serves requests from that index, retaining MIME types, ETags, conditional caching, streaming, HEAD, and byte ranges. It does not search source directories on each production request. Development refreshes files as they change.

Docker no longer runs `collectstatic`. It ships the compact source assets and package assets already installed by `pip`, avoiding a second application asset copy of roughly 210 MB. Keep `django.contrib.staticfiles`, the configured finders, and static URL storage: these are Django's asset-discovery components, not a duplicate directory. The `/static/` URL prefix remains the same.

`tools/optimize_static_images.py` generated the measured compact variants in an isolated collected-output directory. It keeps sidecars only when they save at least 5%, excludes uploads, and refuses the source static directory. It defaults to two workers; AVIF encoding uses one codec thread per worker. It remains available for evaluating future master assets, but is no longer run by Docker: repeated builds do not resize or recompress the installed compact assets.

`tools/replace_static_images.py` validates the source against the measured masters, decodes each replacement, detects filename collisions, and verifies an ignored ZIP backup before modifying source. It installs one chosen file per image. SVGs and color-preserving PNG fallbacks retain their filenames; modern raster files use actual `.webp` or `.avif` extensions. Source changes use atomic file replacement, avoiding writes through temporary QA hardlinks. The original raster files are removed from the active source directory.

`pabasa_app/static_image_aliases.json` maps 926 historical raster names to their replacements. `CompactStaticFilesStorage` emits canonical URLs from Django's static helper. `CompactAppDirectoriesFinder` resolves historical names for ordinary development static serving, including the correct MIME type. WhiteNoise middleware resolves those same aliases in production, preserving saved lesson paths and CSS/JavaScript URLs without database migrations. Compact images are served in their installed format; full-size originals and alternate-format fallbacks are no longer shipped. AVIF assets require an AVIF-capable client. The earlier Accept-based variant handling remains available for future generated sidecars, including `Vary: Accept` when representations differ.

Animation discovery includes WebP/AVIF frames. The Picture-Word catalog includes AVIF and matches legacy saved filenames. Sound Detective resolves canonical filenames before checking image existence. PDF logo lookup resolves the compact source and remains readable by ReportLab; the email logo stays PNG. User uploads, recordings, and student data are excluded from replacement. WhiteNoise retains streaming, byte ranges, and cache behavior. Existing migration startup guards remain unchanged.

The original 945 replaced files are backed up locally in `backups/static-images-originals-2026-10-11.zip`, excluded from Git and Docker. `.dockerignore` also excludes any historical collected output and temporary verification artifacts. During the earlier source replacement step, obsolete original/sidecar images were removed from the collected output and it was refreshed; the user subsequently deleted that local directory. The current serving configuration does not depend on it or regenerate it.

## Reproduction

From the repository root, using Python 3.13:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'pabasa_site'
.\.venv\Scripts\python.exe pabasa_site/manage.py test pabasa_app.tests_static_images pabasa_app.tests_database_config pabasa_app.tests_email_backend pabasa_app.tests_sound_detective.SoundDetectiveCatalogTests
.\.venv\Scripts\python.exe pabasa_site/manage.py check
```

Neither local development nor production requires `collectstatic`. Ordinary `runserver` serves compact assets with compatibility aliases; `--nostatic` is not needed. A changed production static file is picked up when the service starts with the new source/image, not by writing files into a running revision. To reevaluate compression, start from recovered full-resolution masters copied into a separate evaluation directory containing `pabasa_app`, run the optimizer with `--static-root` pointing there and `--profile compact`, `web`, or `lossless`, and review its report. Do not encode successive lossy versions of the installed images. The replacement utility's preflight requires original masters matching its report; it is a one-time installation step, not a recurring build step.

## Verification

- The direct-serving validation passed all 55 selected tests: 25 image tests, eight database configuration tests, sixteen email tests, and six Sound Detective catalog tests. Production tests explicitly set `DEBUG=False`, `STATIC_ROOT=None`, finders enabled, and autorefresh disabled. They serve all 988 source image URLs and legacy aliases, package admin CSS/JavaScript, HEAD/304/range responses, and missing/application routes. A lookup guard verifies indexed production requests do not call `find_file`. The full Sound Detective suite's historical access failure is recorded below; that unrelated authorization test was not rerun for the serving configuration change.
- A local Uvicorn/ASGI browser check used production serving settings with the collected directory absent. All 18 homepage image elements loaded, eight stylesheets were present, and image-slider navigation worked. HTTP checks confirmed package admin CSS/JavaScript and a legacy PNG URL served correctly; an AVIF range request returned 206 with exactly 100 bytes. Django system checks and diff whitespace checks passed.

- Both web and compact profiles were measured across all 986 candidates in separate output directories. Compact files now replace 945 original source images.
- The replacement validation run passed 55 of 56 tests: all 20 image tests, eight database configuration tests, sixteen email tests, and eleven Sound Detective tests. The remaining Sound Detective reopen test returns 403 because its fixture supplies a section ID without an authorized enrollment. The same failure was reproduced with HEAD's original views/catalog and original WhiteNoise middleware, resolving original image existence through the replacement map. No assessment or authorization rules were changed to bypass the failure.
- Image tests cover pixel checks, sizing, exact alpha, color metadata, protected raster text, animation preservation, SVG embedding, PNG fallback, AVIF/WebP negotiation, HEAD, conditional caching, source manifest integrity, canonical URLs, legacy URLs with correct MIME types in both production and development, animation discovery, saved Picture-Word filenames, and ReportLab/email logos. Django system checks and diff whitespace checks passed.
- A browser comparison at a 1,366-pixel viewport showed the original, web, and compact logo, sheep, bicycle, SVG stamp, background photo, and bear. Each image loaded, with illustration boxes about 404 CSS pixels wide, and the samples showed no obvious pixelation or compression blocks.
- Final HTTP checks verified the selected compact WebP/AVIF dimensions, color-preserving PNG fallback, embedded WebP SVG data, and format variation headers. An AVIF byte-range request returned 206 and exactly the requested 100 bytes. The protected CRLA banner's decoded HTTP pixels matched the full-resolution source exactly.
- After source replacement, the homepage loaded all 18 image elements, including its mascot animation, canonical WebP/AVIF images, and compact PNG email/header branding, with no missing images. The production inventory check verified all 988 image URLs, including 926 legacy aliases, and compared served bytes and collected files with the installed source.
- Existing worksheet completion failures were reproduced with the original middleware during the prior pass (seven failures and nine errors). Assessment source and tests remain unchanged; their scoring or completion rules were not altered for this image work.

The smallest tested profile is not a theoretical minimum. Smaller files are possible with lower resolution, lower quality, or more per-image tuning; this preset retains a conservative quality floor and enough detail for ordinary app displays.
