"""Period-aware additions to the parent report; never apply new scoring rules."""

import re
from collections import Counter

from django.db.models import Q

from .models import Enrollment, StudentActivityProgress, StudentActivityRecordingSubmission
from .prescribed_activity_catalog import (
    LEGACY_SESSION_PROGRESS_ACTIVITIES, LEGACY_SESSION_PROGRESS_ALIASES,
    PRESCRIBED_ACTIVITIES, PRESCRIBED_WORKBOOK_ACTIVITIES,
)
from .scoring import canonical_crla_classification
from .utils.crla_results import official_crla_result_queryset


SINGLE_CRLA_PERIOD_NOTICE = (
    "Only one CRLA assessment period is currently available. Progress comparisons "
    "will be provided once results from additional assessment periods become available."
)
FINALIZED_WITHOUT_SUBMISSION = "Finalized without a submitted CRLA assessment."
CRLA_PERIODS = {
    "bosy_crla_pretest": "BoSY",
    "midline_crla_midtest": "Midline",
    "eosy_crla_posttest": "EoSY",
}

# These catalog interactions explicitly include reading aloud. Recording a
# drawing, tracing task, or picture-choice answer alone does not establish it.
ORAL_READING_INTERACTIONS = frozenset({
    "teacher_word_decode_preview", "teacher_sentence_decode_preview",
    "teacher_reading_checklist", "rhyming_verses", "oral_story_line",
    "oral_sentence_blank", "oral_drag_sentence", "oral_jumbled_sentence",
    "word_identifying_oral", "missing_letter_image_oral", "spot_word_oral",
    "oral_then_starting_syllable", "session7_oral_missing_syllable",
    "session7_oral_circle_word", "session7_oral_letter_ordering",
    "session7_oral_cluster_syllabification", "session7_oral_picture_word_connection",
    "session7_oral_cluster_word_circle", "oral_then_picture_word_match",
    "oral_then_picture_word_write",
})


def report_calendar(student, sections):
    """Use school-year ownership, never infer a year from the completion date."""
    calendars = {section.school_calendar_id: section.school_calendar
                 for section in sections if section.school_calendar_id}
    enrollments = Enrollment.objects.filter(student=student, is_active=True)
    if sections:
        enrollments = enrollments.filter(section_id__in=[section.pk for section in sections])
    for enrollment in enrollments.select_related("school_calendar"):
        if enrollment.school_calendar_id:
            calendars[enrollment.school_calendar_id] = enrollment.school_calendar
    return next(iter(calendars.values())) if len(calendars) == 1 else None


def _crla_period(result):
    source = result.source_assessment
    for owner in (result, source):
        if owner and owner.system_assessment_key in CRLA_PERIODS:
            return CRLA_PERIODS[owner.system_assessment_key]
    for owner in (result, source):
        if not owner:
            continue
        for value in (owner.system_assessment_period, owner.system_assessment_phase):
            normalized = re.sub(r"[^a-z]", "", str(value).lower())
            period = {"bosy": "BoSY", "pretest": "BoSY", "midline": "Midline",
                      "midtest": "Midline", "eosy": "EoSY", "posttest": "EoSY"}.get(normalized)
            if period:
                return period
    return None


def collect_crla_history(student, calendar):
    history = {"school_year": calendar.school_year if calendar else "", "rows": []}
    if not calendar:
        history["message"] = "CRLA progress history is unavailable because the report's school year could not be verified."
        return history
    results = official_crla_result_queryset().filter(student=student).select_related(
        "enrollment__section", "enrollment__school_calendar",
    ).order_by("-completed_at", "-updated_at", "-id")
    latest = {}
    for result in results:
        enrollment = result.enrollment
        if enrollment and enrollment.student_id != student.pk:
            continue
        # Conflicting ownership is not sufficient evidence for a comparison.
        years = {owner.school_calendar_id for owner in (
            enrollment, enrollment.section if enrollment else None, result.section,
        ) if owner and owner.school_calendar_id}
        if years != {calendar.pk}:
            continue
        classification = canonical_crla_classification(result.crla_classification or result.classification)
        period = _crla_period(result)
        if (not classification or not period or period in latest
                or FINALIZED_WITHOUT_SUBMISSION in str(result.remarks or "")):
            continue
        data = result.crla_score_data if isinstance(result.crla_score_data, dict) else {}
        correct = next((data[key] for key in ("comprehension_correct", "correct_answers")
                        if data.get(key) is not None), None)
        total = next((data[key] for key in ("comprehension_total", "total_questions")
                      if data.get(key) is not None), None)
        comprehension = "Not recorded"
        if correct is not None:
            comprehension = f"{correct} correct"
            if (isinstance(correct, (int, float)) and isinstance(total, (int, float))
                    and 0 <= correct <= total and total > 0):
                comprehension = f"{correct}/{total} correct"
        latest[period] = {
            "period": period, "assessment_id": result.pk,
            "completed_at": result.completed_at.isoformat(), "classification": classification,
            "accuracy": result.accuracy, "wpm": result.wpm, "comprehension": comprehension,
        }
    history["rows"] = [latest[period] for period in CRLA_PERIODS.values() if period in latest]
    if len(latest) == 1:
        history["message"] = SINGLE_CRLA_PERIOD_NOTICE
    elif not latest:
        history["message"] = "No verified official student CRLA assessment results are available for this school year."
    return history


def _workbook_key(key):
    return LEGACY_SESSION_PROGRESS_ALIASES.get(key, key)


def _workbook_definitions():
    definitions = {_workbook_key(key): value for key, value in PRESCRIBED_ACTIVITIES.items()}
    for entry in LEGACY_SESSION_PROGRESS_ACTIVITIES:
        key = _workbook_key(entry["activity_key"])
        match = re.fullmatch(r"lesson-(\d+)-gawain-(\d+)", key)
        if match:
            definitions.setdefault(key, {
                **entry, "lesson_number": match[1], "gawain_number": match[2],
                "title": f"Lesson {match[1]}: Gawain {match[2]}",
            })
    return definitions


def _workbook_row(key, definition, calendar_id, school_year, term):
    period = f"{school_year or 'School year unverified'} / {f'Term {term}' if term else 'Term unverified'}"
    workbook = PRESCRIBED_WORKBOOK_ACTIVITIES.get(definition.get("activity_key"), {})
    oral_reading = (bool(workbook.get("oral_flow")) if workbook else
                    definition.get("interaction") in ORAL_READING_INTERACTIONS)
    return {
        "activity_key": key, "session": definition.get("session_number"),
        "lesson": definition.get("lesson_number"),
        "gawain": definition.get("display_gawain_number", definition.get("gawain_number")),
        "title": definition.get("title") or definition.get("display_title") or "Workbook activity",
        "period": period, "period_verified": bool(calendar_id and term in (1, 2, 3, 4)),
        "school_calendar_id": calendar_id, "term": term,
        "completed": False, "completion_status": "Completion not recorded",
        "items": "Not recorded", "completion_percent": None, "results": [],
        "review_status": "No teacher evaluation recorded", "_recordings": {},
        "evidence": {
            "progress_id": None, "completion_recorded": False,
            "pending_review": False, "retry_requested": False, "teacher_checked": False,
            "submitted": False, "scored_answers": [], "recordings": [],
            "oral_reading": oral_reading,
        },
    }


def _current_workbook_term(calendar):
    if not calendar or not calendar.is_active:
        return None
    # Reuse the student's dated term resolution rather than the calendar's
    # potentially stale current_term display field. Imported at call time to
    # avoid the views/report collector import cycle.
    from .views import _calendar_current_term
    term = _calendar_current_term(calendar)
    return term if term in (1, 2, 3) else None


def _workbook_program_progress(student, calendar, term, rows):
    """Resolve the active whole-program sequence against this term's records.

    Reuse the learner/dashboard sequence, not a hard-coded catalogue size or
    only the unlocked entries. An absent record supplies no correctness score.
    """
    program = {"verified": False, "activity_keys": []}
    if not calendar or not calendar.is_active or term not in (1, 2, 3):
        return program
    enrollment = Enrollment.objects.filter(
        student=student, school_calendar=calendar, is_active=True, status="active",
    ).first()
    if not enrollment:
        return program
    current = [row for row in rows if row["period_verified"]
               and row["school_calendar_id"] == calendar.pk and row["term"] == term]
    # Use the same eligibility check as the workbook flow. Existing verified
    # term records also establish participation when its CRLA link is legacy.
    from .views import _current_term_crla_result, _prescribed_activity_order
    eligibility = _current_term_crla_result(student, calendar, term)
    if eligibility["reading_at_grade_level"] or not (current or eligibility["aral_eligible"]):
        return program
    keys = list(dict.fromkeys(_workbook_key(key) for key in _prescribed_activity_order()))
    recorded = {row["activity_key"] for row in current}
    completed = {row["activity_key"] for row in current if row["completed"]}
    return {
        "verified": True, "source": "active_prescribed_sequence",
        "school_calendar_id": calendar.pk, "school_year": calendar.school_year,
        "term": term, "enrollment_id": enrollment.pk, "activity_keys": keys,
        "total_count": len(keys), "completed_count": len(completed.intersection(keys)),
        "remaining_activity_keys": [key for key in keys if key not in completed],
        "unrecorded_activity_keys": [key for key in keys if key not in recorded],
    }


def collect_workbook_performance(student, calendar):
    """One row per canonical activity and saved period, merging recording items."""
    definitions = _workbook_definitions()
    rows = {}
    progress = StudentActivityProgress.objects.filter(student=student)
    recordings = StudentActivityRecordingSubmission.objects.filter(student=student)
    if calendar:
        scope = Q(school_calendar=calendar) | Q(school_calendar__isnull=True)
        progress = progress.filter(scope)
        recordings = recordings.filter(scope)

    def row_for(record):
        key = _workbook_key(record.activity_key)
        if key not in definitions:
            return None
        identity = (record.school_calendar_id, record.term, key)
        if identity not in rows:
            rows[identity] = _workbook_row(
                key, definitions[key], record.school_calendar_id,
                record.school_calendar.school_year if record.school_calendar_id else "", record.term,
            )
        return rows[identity]

    # Newest canonical/legacy duplicate wins; do not sum resumable snapshots.
    for record in progress.select_related("school_calendar").order_by("-updated_at", "-id"):
        row = row_for(record)
        if row is None or row.get("_has_progress"):
            continue
        row["_has_progress"] = True
        state = record.state if isinstance(record.state, dict) else {}
        pending = bool(state.get("pending_review") or state.get("awaiting_teacher_verdict"))
        evidence = row["evidence"]
        evidence.update(
            progress_id=record.pk, completion_recorded=True,
            pending_review=pending, retry_requested=bool(state.get("retry_requested")),
            teacher_checked=state.get("checked") is True and not pending,
            submitted=bool(state.get("submitted") or pending),
        )
        row["completed"] = bool(record.activity_completed and not pending)
        row["completion_status"] = "Completed" if row["completed"] else "Ongoing"
        if pending:
            row["completion_status"] = "Submitted; awaiting teacher review"
            row["review_status"] = "Pending teacher review"
        elif state.get("checked") is True:
            row["review_status"] = "Teacher checked"
        elif state.get("retry_requested") is True:
            row["review_status"] = "Retry requested"
        completed, total = record.completed_items, record.total_items
        if total > 0 and 0 <= completed <= total:
            row["items"] = f"{completed}/{total} items"
            row["completion_percent"] = round(completed / total * 100, 1)
        elif completed:
            row["items"] = f"{completed} items recorded; required total unverified"
        answers = state.get("answer_records")
        if (isinstance(answers, list) and answers
                and all(isinstance(answer, dict) and isinstance(answer.get("correct"), bool) for answer in answers)):
            row["results"].append(f"Submitted answers: {sum(answer['correct'] for answer in answers)}/{len(answers)} correct")
            if not pending:
                evidence["scored_answers"] = [
                    {"item_id": answer.get("item_id", answer.get("id", index)),
                     "correct": answer["correct"]}
                    for index, answer in enumerate(answers)
                ]
        elif record.correct_items > 0:
            row["results"].append(f"Practice items marked successful: {record.correct_items} (may include retries)")

    for record in recordings.select_related("school_calendar").order_by("-updated_at", "-id"):
        row = row_for(record)
        if row is not None:
            row["_recordings"].setdefault((record.item_index, record.substep), record)

    for row in rows.values():
        submissions = list(row.pop("_recordings").values())
        row.pop("_has_progress", None)
        if not submissions:
            continue
        status = Counter()
        reviewed_scores = []
        classifications = Counter()
        for submission in submissions:
            reviewed = (submission.review_status != "pending" and submission.status != "retry"
                        and (submission.status == "checked" or submission.review_status == "reviewed"))
            row["evidence"]["recordings"].append({
                "submission_id": submission.pk, "item_index": submission.item_index,
                "substep": submission.substep, "has_recording": bool(submission.audio_file),
                "status": submission.status, "review_status": submission.review_status,
                "teacher_reviewed": reviewed,
                "teacher_score": submission.teacher_score if reviewed else None,
                "classification": submission.fluency_classification if reviewed else "",
                "classification_source": submission.classification_source if reviewed else "",
            })
            if submission.status == "retry":
                status["retry requested"] += 1
            elif submission.review_status == "pending":
                status["pending teacher review"] += 1
            elif submission.status == "checked" or submission.review_status == "reviewed":
                status["teacher checked"] += 1
                if submission.teacher_score in (0, 1):
                    reviewed_scores.append(submission.teacher_score)
                if submission.classification_source == "teacher" and submission.fluency_classification in {"GREEN", "YELLOW", "RED"}:
                    classifications[submission.fluency_classification.title()] += 1
            else:
                status["submitted; awaiting teacher review"] += 1
        row["review_status"] = "; ".join(f"{count} {label}" for label, count in status.items())
        if reviewed_scores:
            row["results"] = [value for value in row["results"]
                              if not value.startswith("Practice items marked successful:")]
            row["results"].append(f"Teacher score: {sum(reviewed_scores)}/{len(reviewed_scores)} reviewed recording items")
        if classifications:
            row["results"].append("Teacher evaluation: " + ", ".join(f"{label}: {count}" for label, count in classifications.items()))
        if row["completion_status"] == "Completion not recorded":
            row["completion_status"] = "Recording submitted; activity completion not recorded"

    activities = sorted(rows.values(), key=lambda row: (row["period"], str(row["session"] or "").zfill(2), str(row["lesson"] or "").zfill(2), str(row["gawain"] or ""), row["activity_key"]))
    current_term = _current_workbook_term(calendar)
    return {
        "school_year": calendar.school_year if calendar else "School year unverified",
        "school_calendar_id": calendar.pk if calendar else None,
        "current_term": current_term,
        "program": _workbook_program_progress(student, calendar, current_term, activities),
        "rows": activities, "completed_count": sum(row["completed"] for row in activities),
        "ongoing_count": sum(row["completion_status"] == "Ongoing" for row in activities),
        "other_count": sum(not row["completed"] and row["completion_status"] != "Ongoing" for row in activities),
        "unverified_count": sum(not row["period_verified"] for row in activities),
    }


def summarize_workbook_progress(workbook):
    """Count saved activity snapshots by verified term, without inferring grades.

    The collector has already canonicalized aliases and merged recording items.
    A denominator for all assigned/required activities is not available here.
    Recording review counts remain separate from activity completion counts.
    """
    periods, seen = {}, set()
    excluded = 0
    calendar_id = workbook.get("school_calendar_id")
    for row in workbook.get("rows") or []:
        if (not calendar_id or not row.get("period_verified")
                or row.get("school_calendar_id") != calendar_id
                or row.get("term") not in (1, 2, 3, 4)):
            excluded += 1
            continue
        identity = (calendar_id, row["term"], row.get("activity_key"))
        if row.get("activity_key") and identity in seen:
            continue
        seen.add(identity)
        period = periods.setdefault(row["term"], {
            "term": row["term"], "completed": 0, "ongoing": 0,
            "awaiting_review": 0, "completion_unrecorded": 0,
            "recordings_reviewed": 0, "recordings_pending": 0, "recordings_retry": 0,
        })
        facts = row.get("evidence") or {}
        if row.get("completed"):
            period["completed"] += 1
        elif facts.get("completion_recorded"):
            period["awaiting_review" if facts.get("pending_review") else "ongoing"] += 1
        else:
            period["completion_unrecorded"] += 1
        for recording in facts.get("recordings") or []:
            if recording.get("status") == "retry":
                period["recordings_retry"] += 1
            elif recording.get("teacher_reviewed"):
                period["recordings_reviewed"] += 1
            else:
                period["recordings_pending"] += 1
    return {"periods": [periods[term] for term in sorted(periods)],
            "excluded_count": excluded, "school_year": workbook.get("school_year")}
