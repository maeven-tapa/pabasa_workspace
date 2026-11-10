# Principal PDF presentation

The principal export uses `principal_report_pdf.py` for presentation. The existing
`build_principal_snapshot`, `report_rows`, request filters and response headers
remain unchanged. No models, scoring rules or parent report code are changed.

## Layout and data contract

- A4 executive dashboard: school identity, PABASA branding, selected reporting
  scope, generation timestamp, four KPI cards, section/task counts and the exact
  existing metric definition.
- Detailed school analytics: CRLA participation and accuracy, ARAL engagement,
  prescribed completions and supplementary assignment/completion counts. All 19
  existing school export metrics remain represented. Additional future export
  metrics are retained in an additional institutional metrics block.
- Other principal report types retain every supplied header and record. Wide
  detail tables use landscape A4 after the portrait executive page. Long rows
  can continue across pages with repeated headers.
- Blue, amber, teal and the parent report's embedded Lato fonts create a shared
  brand system. Cards wrap their text and align metric baselines. Footers include
  confidentiality and current/total page numbers.
- Bars represent only already calculated percentages between 0 and 100. No new
  ratios, benchmarks, classifications, trends or recommendations are calculated.
  Missing accuracy remains N/A; a recorded zero remains zero. ARAL counts are
  explicitly not sequential stages. Activity completion is not skill mastery.
- The configured school logo is respected. Salawag's bundled school seal is
  used when no school-specific logo is configured, rather than the generic
  PABASA mascot fallback. Other schools do not acquire Salawag's identity.

## Validation (November 10, 2026)

Presentation tests cover all metric/value pairings, scope and definition
retention, zeros, unavailable accuracy, empty exports, every report type, new
future metrics, multipage narrative text, page totals, landscape detail pages,
no payload mutation and no renderer database access. A database-backed workflow
test verifies that a principal's PDF reflects their own school and selected year,
term and assessment period.

The existing principal PDF endpoint tests and parent PDF presentation tests were
also exercised: 32 targeted checks passed, and Django's system check passed.
Broader principal preview/isolation checks expose six existing
failures (five assertion failures and one error). All six reproduce with the
original HEAD exporter restored in memory: outdated grade-filter/preview
expectations, Grade 5 inclusion expectations in a Grade 2 cohort, and redirects
from old principal assessment URLs. They are outside this presentation change.
The baseline comparison syncs the current models into a disposable memory
database without historical sample-data migrations; the initial broader run
also used the normal migrated test database.

`tools/generate_principal_report_samples.py` reads an existing local SQLite
database with `PRAGMA query_only=ON`. It exports only the selected school's
aggregate school report, then produces explicitly illustrative, zero-data and
long-text pagination samples. For this review, the older local schema was
upgraded only in a disposable database copy after its migration readiness check
passed. The original database SHA-256 remained unchanged.

All pages of the four samples were rendered with Poppler and visually reviewed:
two-page existing-data, illustrative and zero-data school reports, plus a
four-page narrative pagination sample. All ten pages had zero PDF character
boundary violations. Generated PDFs are git-ignored review artifacts, not hardcoded inputs to
the application. No live deployment or database record change is involved.

Run normal application validation from the repository root:

```powershell
python pabasa_site/manage.py check
python pabasa_site/manage.py test pabasa_app.tests_principal_report_pdf pabasa_app.tests.PrincipalReportsExportTests pabasa_app.tests_reading_report_pdf
python tools/generate_principal_report_samples.py --database path/to/a/schema-ready-local-copy.sqlite3
```
