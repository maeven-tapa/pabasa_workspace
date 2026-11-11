# Live Assessment Summary email

The live summary uses the dedicated Django template
`pabasa_app/emails/live_assessment_summary.html`, rendered by
`pabasa_app/live_assessment_email.py`.

## Preserved behavior

Only the email presentation call inside `_end_live_assessment_session` changed.
The post-commit queue, first-end-only guard, teacher recipient, subject, sender,
silent-send setting and original plain-text body are preserved. Student
selection, completed/missed grouping, official result creation, finalization,
scoring and scheduling are unchanged. Other email templates and both PDF report
renderers are untouched.

The email still uses Django's configured mail backend and SMTP failover. The
existing PABASA PNG is embedded as a related MIME image inside the HTML
alternative, retaining the plain-text alternative. This avoids a remote image
request for the normal logo. If the local asset is unavailable, the existing
first-party image URL and accessible alternative text are used.

## Displayed information and sources

- Assessment title: the session's Material, using the existing Reading Activity
  fallback. Phase: known official phase/key on that Material or its linked
  Assessment. No phase is guessed from the title.
- Date/time: the existing summary's end-event timestamp, formatted in Django's
  configured local timezone.
- School: session Section.school, then Course.school, then teacher.school_record.
  Missing school identity never defaults to Salawag.
- Grade and section: the actual session Section. Missing values are omitted;
  the renderer does not guess a classroom from a shared material or roster.
- Teacher/session administrator: the existing session teacher's stored name.
- Selected count: length of the same session.student_ids list used previously.
  Completed and missed counts/lists: the original caller-supplied lists, with
  each learner's stored custom_id included when available.
- Completion rate: completed / selected x 100, rounded to one decimal; zero
  selected gives zero. Supporting text explicitly describes participation,
  rather than reading accuracy or proficiency. Missing learner records are not
  converted into completed/missed results.
- Session status: the actual persisted status, independent of participation.
- Duration: elapsed time between aware, ordered start_at and ends_at values on
  an ended/cancelled session, including pauses. Omitted for multi-batch or
  inconsistent batch metadata because start_at may refer only to the most
  recent batch. It is never inferred from creation time or student timers.
- No individual reading score or CRLA classification was added.

## Email layout and fallbacks

The 660px maximum-width layout uses presentation tables, inline essential
styles, safe font fallbacks and explicit image dimensions. Mobile media queries
stack information fields and participation panels. Rounded cards and gradients
have solid-color fallbacks. The completion bar and book/group motifs use HTML
cells; no SVG, JavaScript, external CSS framework or external illustration is
required. Long names and titles wrap, and participation lists have no fixed
height or student truncation.

## Reproduce validation

```powershell
python pabasa_site/manage.py check
python pabasa_site/manage.py test pabasa_app.tests_live_assessment_email pabasa_app.tests_email_backend pabasa_app.tests_live_crla_export pabasa_app.tests.LiveAssessmentCloseAndSaveTests
python tools/generate_live_summary_email_previews.py
node tools/inspect_live_summary_email_previews.cjs
```

Use the existing local Python 3.13 environment. The browser script uses
`playwright-core` (or `PABASA_PLAYWRIGHT_PATH`) and headless Chrome. It opens only
local synthetic HTML previews and requires no accounts or application server.

The preview generator uses the production template with clearly labeled
fictional data. It does not open a database or send email. It emits one-student,
all-completed, mixed, maximum ten-student batch, zero-selected, missing-field and
long-text examples in the git-ignored `output/email/live-summary/` directory.
Logo bytes are embedded directly in local previews; production uses the same
bytes as MIME CID content.

Validation includes desktop (960px) and mobile (390px and 320px) previews, logo
loading/aspect ratio, equal KPI heights, horizontal overflow and completion-text
overlap. An additional preview disables head styles, gradients, shadows,
rounded corners and images to inspect the basic fallback. Mail tests use
in-memory delivery or mocked SMTP, including primary rejection and backup
delivery of the HTML/text alternatives and embedded logo. The end-session test
checks the original queue, recipient, plain-text counts and duplicate-send guard.

These are local browser and MIME/backend checks, not native Gmail or Outlook
inbox tests. Actual student data was not used in previews; no live message,
database record modification or deployment was performed.
