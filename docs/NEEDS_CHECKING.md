# Needs Checking

The teacher dashboard and sidebar open `/dashboard/teacher/needs-checking/`.
The workspace combines nine explicitly registered prescribed activities with
Response to Story and Retell the Story. Session 8 results remain available from
the dashboard's existing prescribed-results link.

## Source of truth

`pabasa_app/review_queue.py` projects one task per student, activity, calendar,
and term. It reads existing progress, recording, reading-attempt, and story
submission tables in batches. There is no duplicated review-task table.

- Incomplete practice and missing recordings do not become review tasks.
- Lesson 1 and Trace & Say allow submitted attempts before teacher approval.
- Binary scores include zero as reviewed. Session 4 Gawain 2 includes only its
  two manual letter-sound stages, excluding its automatic blending stage.
- Fluency skips are excluded. Lesson 15 follows the exact immutable attempt
  referenced by progress state, including retained clips for long passages.
- Drawings require the stored teacher verdict. Trace & Say remains pending
  until its final teacher verdict, even after all recordings have been scored.
- Retellings can be marked reviewed independently of their optional 0–5 score.
  Existing graded retellings already count as reviewed. Story responses still
  require a numerical score. Existing score locking and completion behavior
  are preserved.
- Retry requests leave Needs checking; resubmissions return. The status filter
  also exposes reviewed work and work awaiting resubmission.

The current active enrollment, teacher, school, school calendar, current term,
publication, and selected-student assignment constrain visibility. Historical
periods do not silently become current tasks. Older unscoped recordings require
an explicit current-attempt link or a submission date within the current
progress record's lifetime. New uploads record their calendar and term.

## Evaluation and consistency

The inbox contains no grading form or grading dialog. Review links open the
existing Course → Students' Progress interface with the authorized student and
activity selected. Session 9 drawings open the existing prescribed-review page.
Back to inbox restores the teacher's filters; Next pending uses those filters
to select the next submission. Retelling's Mark Reviewed control is on the
existing student-progress card and works from either entry point.

The scoped detail endpoint adapts current evidence to the existing progress
renderer. The same evaluation handlers are used by normal course navigation
and inbox links. Task versions detect changed evidence for inbox actions.
Writes lock the student and relevant submission/progress records before
revalidating authorization and version. Audio requests independently validate
the current task and recording identity before using existing audio responses.
Drawing and story-score writes are atomic, including when opened from the
existing teacher screens.

## Updates and notifications

`review_inbox.js` refreshes a compact summary every 30 seconds while visible,
on returning to the page, and after review actions. The workspace fetches a
paginated list with search, source, class, activity, calendar, term, status, and
sorting filters. It preserves its filters in the URL and supports direct task
links, previous/next review navigation, and keyboard dismissal. Polls do not
replace an open review or interrupt audio playback.

`TeacherReviewInbox` is only a notification-delivery cursor. It stores observed
current evidence tokens and a link to one grouped `Notification`. Newly observed
work creates or updates that alert; ordinary polling and partial grading do not
make it unread again. New evidence can make it unread again. Reading or clearing
the alert never removes work from the queue. The first refresh on a teacher's
return discovers submissions made while they were away. No background worker,
WebSocket service, or email delivery is introduced. In-app notification
preferences are respected without hiding the queue.

## Schema and release

Migration `0037_teacher_review_inbox` adds the delivery cursor and nullable
`reviewed_at`/`reviewed_by` fields to story submissions. It does not modify grades
or require a data rewrite. Follow the repository's migration readiness, backup,
and release-job requirements before activating a production image. Existing
startup readiness and migration guards are unchanged.

## Validation

Use Python 3.13 and the repository requirements. Run against an explicitly chosen
local SQLite configuration, not a production database:

```powershell
python pabasa_site/manage.py check
python pabasa_site/manage.py makemigrations --check --dry-run
python pabasa_site/manage.py test pabasa_app.tests_review_queue
python pabasa_site/manage.py test pabasa_app.tests_review_queue_browser --settings=pabasa_site.browser_test_settings
```

The browser test requires Playwright Core and an installed Chromium browser.
`PABASA_PLAYWRIGHT_PATH` can identify its Node module;
`PABASA_BROWSER_CHANNEL=chrome` selects installed Chrome when needed. It uses a
disposable Django test server, synthetic students, and temporary audio, with no
live-site sessions. Screenshots are written to ignored `tmp/review-screens/`.
The browser settings use a temporary file-backed database so concurrent polling
and grading requests have independent database connections.

The queue tests cover all registered activities, partial and final review,
zero scores, retries, replacement evidence, old periods, publication allow-lists,
cross-teacher access, CSRF, notification preferences, read/clear behavior,
pagination, and a batch-query check with **20 distinct students**. That query
check is not a concurrent classroom capacity benchmark.

Validated on November 13, 2026 with Python 3.13: 43 focused workflow tests and four
browser tests passed after consolidating the review interface. The browser checks exercise inbox routing and all
seven existing compact course review layouts, real audio playback and review
writes, score confirmation, retries, final verdicts, keyboard navigation, and
desktop/tablet/mobile layouts. Django system checks, migration drift checks,
JavaScript syntax checks, and whitespace checks passed. Migration readiness was
checked only against a disposable fresh local database. No live database or
Cloud Run changes were made.
