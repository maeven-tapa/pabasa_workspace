# Parent report recommendations

The parent PDF uses workbook and supplementary results collected for that student.
Official CRLA status is checked before activity recommendations. P0 and P5 are
exclusive: they suppress P1-P4 advice about ARAL work that is not applicable to
the student's assessment status. CRLA accuracy and WPM do not directly select
P1-P4 support codes; the saved official classification determines P5.

| Code | Triggering evidence | Meaning |
| --- | --- | --- |
| P0 | No qualifying official CRLA result for the verified report period, or a class-finalized result without a student submission | Coordinate with the teacher to complete the official assessment or confirm its result. Practice Mode may be used while waiting. No ARAL continuation advice is generated. |
| P1 | Incomplete verified workbook programme (including activities without records), ongoing activity, pending evaluation, or requested retry | Continue workbook work or review it with the teacher. Missing work and retries do not establish incorrect scores. |
| P2 | Explicit incorrect answer records, or a teacher-reviewed recording score of zero | Practice the specific activity with teacher guidance. No universal workbook accuracy threshold is applied. |
| P3 | A catalog-identified oral-reading task with recording submissions or reviewed oral support needs | Continue oral practice and review recordings or teacher feedback. Workbook WPM is not inferred. |
| P4 | No other support or workflow rule applies | Continue regular reading practice and teacher support. This is not a mastery classification. |
| P5 | Qualifying official CRLA classification is Reading At Grade Level | Continue reading through Practice Mode to maintain and strengthen skills. ARAL completion, error, and recording rules do not apply. |

P0 replaces the former P1 CRLA-baseline reminder. Missing activity records do not
add P1 while the official CRLA result is unavailable. P5 uses the shared official
classification canonicalizer, including recognized legacy grade-level spellings.
Neither accuracy alone nor a supplementary activity classification establishes P5.

The existing CRLA section and history remain intact. `recommendation_crla` records
the official result used for advice: within a verified school year and dated
current term, it selects the matching BoSY/Midline/EoSY history row. An older
period or school year cannot supply P5 while the current result is unavailable.
Without a dated current term, the latest available verified assessment period in
the report year is used; without a verified report calendar, the existing latest
official student-result selector supplies the context. Class-finalized results
without a student submission do not establish an available result for advice.

Workbook judgments require an active, verified report calendar and the currently
dated term resolved by the same term-block helper as the student workbook flow.
The stored calendar `current_term` display value is not used as a fallback.
Historical and unverified workbook rows remain in the PDF, but cannot establish
current workbook performance or suppress the no-current-results P1 reminder.

The collector also retains `workbook.program`, using the same active prescribed
sequence as the learner and teacher dashboard. It currently contains 93 canonical
activities; the count is computed, not hard-coded. A dated active calendar, term,
and active school-year enrollment are required. Verified current-term workbook
records establish participation, or the workbook flow's existing current-term
CRLA eligibility check can establish it before any work is recorded. A verified
grade-level exemption prevents reporting from assigning the entire programme.

Completion is compared with that sequence within the same calendar and term.
Activities without records remain in the expected sequence, without creating
database rows or inventing scores. Unfinished programme work adds P1 even if all
recorded workbook work is completed and supplementary results are perfect.
Existing P1 continuation/review text is preserved and enriched once with the
programme completion count; it is not repeated as another generic P1 entry.
P2/P3 evidence remains independent, and P4 is available only if no trigger applies.

Pending grading never supplies a failed teacher score. Explicit answer results in
a workbook submission awaiting teacher judgment are excluded from recommendation
scoring until that pending state clears. Default counters, completion percentages,
and success after retries cannot establish low accuracy. Previously reviewed zero
scores on other items can still trigger P2 while additional recordings await review.

Supplementary accuracy below 80% still triggers P2. Recorded supplementary WPM,
including zero, retains the existing P3 trigger; it does not establish low speed.
Advice mentions automated fluency only when the collected result indicates speech
analysis. Supplementary and workbook recommendations can coexist.

`build_student_reading_progress_report` collects workbook data once. It retains:

- `recommendations`: plain message strings consumed by the PDF renderer.
- `recommendation_details`: corresponding code, text, activity identity/period,
  reason, and evidence sources/record IDs. The general baseline and fallback
  recommendations have no single activity.
- `workbook.rows[].evidence`: structured completion, answer, submission and review
  facts; the rules do not parse the PDF table's display strings.
- `workbook.program`: verified calendar/term, enrollment, active sequence keys,
  completion count and remaining/unrecorded keys. The recommendation's programme
  evidence retains the expected keys and actual completion record references.

For expected-versus-actual testing, compare codes plus activity and evidence, not
codes alone. Multiple recommendations may share a code for different activities.
Duplicate snapshots of the same activity do not repeat the same advice. This
metadata describes a generated report; it is not a new persistent recommendation
history table. Preserve the generated output when auditing historical sends.

Section 09 (Next Steps / Parent recommendations) displays the matching P-code
beside each recommendation and a compact P0-P5 key. Codes come only from matching
structured metadata; older text-only payloads retain numbered advice without
guessing a code. The key explains all six families; it does not assign them all
to the student.

Section 07 (Reading Progress) charts saved prescribed workbook activity counts
by verified term within the report's school calendar. Completed, ongoing,
awaiting review, and completion-unrecorded categories are separate. Recording
review counts are shown separately, including when a completed activity still
has pending recordings. Unverified records remain in Section 05 but are excluded
from the chart. The denominator is saved activity records, never all assigned
work; term counts cannot establish improvement in reading proficiency.

Recent supplementary accuracy is charted separately on a 0-100% scale, retaining
dates, WPM, miscues, and automated-analysis context. Missing accuracy is labeled
as unavailable, not zero. Recent records not verified as supplementary remain
under their own heading. The chart does not combine different scoring systems
or infer workbook accuracy/WPM from completion or retries.

Validate using Python 3.13 with the repository requirements and a disposable local
test database:

```powershell
python pabasa_site/manage.py test pabasa_app.tests_reading_recommendations pabasa_app.tests_reading_progress_reports
```
