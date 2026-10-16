# Student achievements

The dashboard renders 12 badges from saved student records. Browser-local
`pabasa_seen_material_ids` and `pabasa_practice_progress_v1` do not award badges.
The card shows six badges at a time in two rows. Previous/next controls at the
top right switch between the original six badges and the six additions, without
changing the card height or making a server request. Hidden badges are excluded
from keyboard navigation; the page indicator announces changes.
Each badge is a button that opens an achievement details dialog with its name,
icon, unlock requirement, and earned/locked status. The dialog supports keyboard
activation, Escape, backdrop dismissal, Close, and Got it. Closing restores focus
to the badge and preserves the selected page.

| Badge | Requirement |
| --- | --- |
| First Steps | One completed assessment |
| Book Explorer | Three different completed assessments; retries count once |
| Reading Streak | Reading or practice evidence on seven consecutive local dates |
| Rising Reader | At least half of the required prescribed activities completed |
| Practice Star | All 45 mode/difficulty/level combinations in one language |
| Reading Champion | Every required prescribed activity across Sessions 1–15 |
| Session Starter | Every required activity in one prescribed session |
| Session Explorer | Every required activity in five prescribed sessions |
| Activity Achiever | Ten different prescribed activities |
| Star Collector | At least 100 lifetime stars, including spent stars |
| Color Champion | All five Easy Color Mode levels in one language |
| Word Hunter | All five Easy Hunt Mode levels in one language |

## Evidence and scope

Prescribed progress uses the active catalog plus the legacy session activities.
Superseded entries are excluded. Session 2's older progress alias is counted
once; a canonical reset takes precedence over an older alias. Activities count
only when their saved `activity_completed` flag is true. Submissions still
awaiting teacher approval do not count. Session Journey uses the same rules.
Prescribed totals never combine school calendars, terms, or students.

Assessment milestones use completed result rows with completion dates, not
views, browser flags, started attempts, or practice results. A class CRLA
finalization without an actual student submission does not qualify. Results
for the same material/source assessment count once.

Practice badges use the student's saved completion snapshots on systemwide
practice materials. Different languages cannot be combined to complete a mode.
Lifetime stars combine saved progression stars across languages and use the
greater of that sum and credited/stored lifetime totals;
the available wallet balance is not the unlock criterion. Profile's Star
Collector uses the same 100-star award as the dashboard.

Learning days use the configured application timezone (Asia/Manila). Multiple
activities on one date count as one day. Dates with gaps do not form a streak;
future dates are excluded. Teacher review dates do not replace recording
submission dates. Completion events record days and milestones before the
student next opens the dashboard. Refresh also reconstructs historical days
from dated assessment/practice results and recorded reading evidence.
Historical activities without trustworthy dated evidence do not invent days.

`StudentAchievement` persists earned awards, so new content, term changes,
resets, and spending stars do not relock them. Old browser-only badge states
are not imported as verified awards. Unique constraints make repeated refreshes
and concurrent awards idempotent. No student-supplied achievement endpoint exists.

## Migration and verification

Migration `0033_student_achievement_awards` adds only the achievement and learning
day tables. The app's existing AutoField default and the later Supplementary
assignment table's BigAutoField are explicit to avoid unrelated primary-key
schema changes under Django 6.

For deployment, follow AGENTS.md: check migration readiness, back up the
database, and migrate with the release image before directing traffic to it.
The local SQLite migration was applied after readiness and a consistent backup.

```powershell
.\.venv\Scripts\python.exe pabasa_site/manage.py test pabasa_app.tests_achievements pabasa_app.tests.DashboardAchievementBadgeTests
.\.venv\Scripts\python.exe pabasa_site/manage.py makemigrations --check --dry-run
node tools/test_student_achievements.cjs
```

The browser test renders actual templates/scripts with synthetic student data
and intercepted requests. It checks all seven themes at desktop, narrow desktop,
mobile, and dark desktop sizes, server-selected unlocks despite fabricated browser
completion flags, badge text bounds, lock positioning, and keyboard labels. It
does not create sessions against the real local or production database.

The implementation also serializes practice completion timestamps before saving
the JSON snapshot. Previously a datetime payload could prevent completion and
its badge from being saved. Empty session summaries are emitted as JSON arrays
and guarded before rendering the journey.

Local verification: 112 of 122 Django tests passed, including all 29 focused
achievement/template cases and the prescribed/supplementary term, database,
practice visibility/selection/debug, and progression checks. The pagination
follow-up passed 56 browser page layouts across seven themes, including stable
card height, six visible badges, a single-line heading with top-right controls,
and keyboard paging. Two focused Django template checks also passed. System,
schema-drift, and migration checks passed.
The details-modal follow-up also passed 350 dialog checks across seven themes:
all 12 badges, earned/locked text, viewport bounds, click/Enter/Space activation,
Close/Got it/Escape/backdrop dismissal, and focus restoration to the triggering
badge. Both achievement pages retain their layout and selected page afterward.

The ten remaining cases are pre-existing failures in
`PracticeReaderMaterialTests`: five old Hunt star API fixtures omit the current
attempt/award contract, and five material listing/progression expectations
disagree with current behavior. In a disposable test process, restoring the
original practice-completion function and disconnecting the new achievement
signals reproduced those failures plus three timestamp-related failures. The
timestamp fix resolves the latter three; the final run adds no failures to that
baseline. These older expectations have not been weakened to make the suite pass.

## Save-flow conflict fixes

Assessment and Material result helpers now apply their complete payload before
the first result save. Achievement hooks therefore see exclusion remarks and
final metadata together, preventing permanent awards for an intermediate,
apparently completed result that is subsequently excluded.

Replacing an existing recording refreshes `submitted_at`, including callers
that save only selected fields. The previous submission date is retained as a
learning-day fact before the new date is recorded. Teacher review and metadata
updates do not refresh the submission date. Same-name replacement uploads are
also treated as genuine new recordings.

Profile, Practice, Theme Shop wallet synchronization, and Star Collector now
share the `practice_summary` lifetime-star calculation. English and Filipino
progression are considered consistently, alongside credited/stored lifetime
totals. Spending does not reduce lifetime stars, and repeated wallet sync does
not credit the same progression twice.

Verification: all 36 focused achievement/template cases passed, including seven
new regressions covering both result helpers, recording retries, preservation of
old dates, review metadata, language consistency, and wallet spending. The real
profile response was also checked for the Filipino 105-star reproduction.
Related recording, term lifecycle, reading-report, course-progress, scoring, and
workflow checks passed 49 of 59 cases. The ten scoring/workflow failures reproduce
with the original result helpers, original wallet helper, and achievement hooks
disconnected in an isolated test database; there are no additional failures.
The existing scoring rules and tests were preserved. Schema checks find no new
migration needed for these method-only fixes.

The bilingual lifetime-star regression also verifies that 60 English stars plus
60 Filipino stars report 120, unlock Star Collector on the dashboard and Profile,
and credit only the missing 60 stars after an earlier English-only wallet sync.
Previously spent stars remain spent, repeat syncs do not deposit again, and
larger credited/imported lifetime totals are retained without adding progression
twice. Practice completion badges still require their levels in one language.

This follow-up passed all 37 focused achievement/template tests. The broader
practice progression, visibility, and Hunt run passed 45 of 47 tests; its two
failures assert Hunt frontend strings in files unchanged from HEAD. Django's
system check and `git diff --check` also passed.
