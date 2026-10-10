# Class materials API efficiency — October 10, 2026

Implemented locally; no production deployment or hosting changes were made.
Final local measurement completed at approximately **9:50 PM Asia/Manila**.

## Behavior and compatibility

- `/api/class/materials/?section_id=…` retains its detailed response. Adding
  `view=summary` returns grouped card metadata and progress without the duplicate
  `all_materials` array, repeated reading text, or full Material exercise JSON.
  Standalone Assessment and Practice prompts are retained for their legacy readers.
- Summary metadata retains activity routing/classification and source-story IDs.
  Material readers continue loading full content by ID when an activity opens.
- Assessment relationships, assigned sections, attempt metrics, practice enrollment
  filters, and story submissions are loaded in batches. Completion lookups return
  only the newest matching row per material, rather than loading result histories
  or recording transcripts into memory.
- Assessment Week, school/class access, publication scope, calendar/term ownership,
  latest-attempt ordering, legacy completion fallback, and the distinct Story
  Reading/Response/Retell/Fluency completion rules are preserved.
- The shared browser loader sends at most two requests concurrently, prioritizes
  the requested section, and shares pending/successful requests within one page.
  Navigation, restored pages, and confirmed completion events refresh listings.
  Failed requests can be retried; unauthorized listings are removed.
- Listings use one section-keyed storage shape. Persisted material contents are
  cleared on student page initialization and replaced by freshly authorized data.
  No Redis or server-side progress cache was added; responses use `private, no-store`.
- The standalone Story Reading page includes the loader before its player script.
  Practice completion refreshes listings only after a successful server save;
  individual free-practice progress updates do not create materials requests.

## Local measurement

Python **3.13.16**, Django **6.0.3**, disposable SQLite database, **20 distinct
students enrolled in one class**, 20 mixed materials plus one standalone assessment
and one practice. Each variant ran three waves of **20 concurrent clients**, with
variant order rotated between rounds. Database writes were disabled during the
measured endpoint calls. All 180 measured responses succeeded.

Baseline source: `eed741b58f1bc1bbffc23aa5bf425a824db8a136`. Detailed response
payloads matched the original implementation for all 20 students before timing.

| Variant | Requests | Mean | P95 | Mean SQL queries | Mean response bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original detailed response | 60 | 7,166 ms | 8,080 ms | 178.65 | 510,879 |
| Optimized detailed response | 60 | 1,574 ms | 1,811 ms | 33.08 | 510,879 |
| Optimized summary response | 60 | 1,657 ms | 1,874 ms | 33.03 | 30,693 |

The summary payload was **94.0% smaller** and sampled P95 was **76.8% lower**
than the original detailed response. Query counts include request-independent
clock-cache variation, hence the fractional means. The detailed and summary
latency difference is sampling variation; summary mode primarily reduces bytes.

These are **internal Django calls on local SQLite**, excluding HTTP middleware,
session transport, network and browser rendering. They are not Cloud Run or
production PostgreSQL capacity measurements and do not predict live-site latency.

Aggregate evidence: `tmp/class-materials-twenty-benchmark.json`. Synthetic HTML
fixtures and test logs remain under ignored `tmp/`; no student records, credentials,
SQL text, or recordings are included in the report.

## Validation

- All **11 new efficiency tests** passed, including compact/full compatibility,
  ownership and progress isolation, enrollment/calendar filtering, special activity
  completion rules, score refreshes, archived/selected-publication filtering, reader
  content loading by ID, and query-count growth from 1 to 20 materials.
- Full application run: **1,300 tests**, with **212 failures and 107 errors**.
  Original endpoint comparison: **1,289 tests**, with the same **212 failures and
  107 errors** and exactly the same failing test IDs. No new failing tests were
  introduced. Existing failures were preserved rather than changing scoring/access
  rules or old test expectations to make them pass.
- Chrome checks passed for request sharing, concurrency/priority, retries,
  authorization clearing, superseded requests, normalized storage, completion and
  navigation refreshes. Actual Django-rendered assessment/session HTML produced
  one shared materials request and retained activity links. The standalone Story
  Reading completion modal enabled its 5W continuation using compact metadata.
  Browser API responses were synthetic and external downloads were intercepted;
  Bootstrap was stubbed for these workflow checks. Microphone/STT behavior was
  outside this change.
- Django system checks, JavaScript syntax checks, and whitespace checks passed.
- `makemigrations --check --dry-run` still reports existing automatic ID-field
  drift across models. Model field/schema AST definitions match the baseline;
  the only model edit is an optional preloaded-attempt argument to the existing
  summary method. No migration was created or applied for this change.

## Repeating the checks

Use a Python 3.13 environment with `requirements.txt`. The benchmark creates and
removes its own local database, refuses Cloud Run execution, and performs no live
site or cloud writes:

```powershell
python tools/benchmark_class_materials.py --baseline-ref eed741b58f1bc1bbffc23aa5bf425a824db8a136
python pabasa_site/manage.py test pabasa_app.tests_class_materials_efficiency
node tools/test_class_materials_browser.js
```

The browser script requires Playwright on `NODE_PATH` and local Chrome; an alternate
Chrome executable can be supplied through `PABASA_CHROME_PATH`. Run the benchmark
first to create its synthetic browser fixtures. The full test comparison enumerated
the active application's `tests*.py` modules explicitly, avoiding the separate
root-level legacy application directory.

Production verification remains a separate release step. Build the new static
assets into the image, follow the repository's migration-readiness/job safeguards,
and retain a working revision for rollback. Measure authenticated HTTP behavior
and production PostgreSQL timings before claiming a live-site speedup.
