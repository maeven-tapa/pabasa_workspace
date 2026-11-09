"""Structured data collection for parent-facing reading progress reports."""

import json
from collections import defaultdict

from django.db.models import Q

from .aral_activity_catalog import ACTIVITIES, COMPETENCIES, WORKBOOK_ACTIVITIES, resolve_activity
from .models import Assessment, Enrollment, Material, StoryReadingProgress, StoryResponseSubmission
from .utils.crla_results import OFFICIAL_CRLA_KEYS, latest_completed_official_crla_results
from .reading_report_details import collect_crla_history, collect_workbook_performance, report_calendar
from .scoring import canonical_crla_classification


FINALIZED_CRLA_REMARK = "Finalized without a submitted CRLA assessment."


def _parse_prefixed_json(value):
    text = str(value or "")
    separator = text.find(":")
    if separator < 0:
        return {}
    try:
        parsed = json.loads(text[separator + 1:])
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _material_week_values(material):
    weeks = getattr(material, "assigned_weeks", None)
    if isinstance(weeks, list):
        values = []
        for week in weeks:
            try:
                number = int(week)
            except (TypeError, ValueError):
                continue
            if number not in values:
                values.append(number)
        if values:
            return values
    assigned_week = getattr(material, "assigned_week", None)
    try:
        return [int(assigned_week)] if assigned_week not in (None, "") else []
    except (TypeError, ValueError):
        return []


def _scope_sections(student, sections=None, course=None):
    if sections is not None:
        return [section for section in sections if section]
    if course is not None:
        return list(course.sections.filter(is_active=True))
    enrollments = (
        Enrollment.objects.filter(student=student, is_active=True)
        .select_related("section", "assigned_teacher", "school_calendar")
    )
    return [enrollment.section for enrollment in enrollments if enrollment.section]


def _section_ids(sections):
    return [section.pk for section in sections if getattr(section, "pk", None)]


def _scoped_materials(sections, course=None):
    section_ids = _section_ids(sections)
    filters = Q()
    if section_ids:
        filters |= Q(section_id__in=section_ids) | Q(assigned_sections__id__in=section_ids)
    if course is not None:
        filters |= Q(courses=course)
    if not filters:
        return Material.objects.none()
    return Material.objects.filter(filters, is_active=True).distinct()


def _student_context(student, sections, course=None):
    enrollment = (
        Enrollment.objects.filter(student=student, is_active=True)
        .select_related("section", "assigned_teacher", "school_calendar")
        .order_by("-joined_at", "-id")
        .first()
    )
    section = sections[0] if sections else getattr(enrollment, "section", None)
    teacher = getattr(section, "teacher", None) or getattr(enrollment, "assigned_teacher", None)
    school_calendar = getattr(section, "school_calendar", None) or getattr(enrollment, "school_calendar", None)
    section_label = ""
    if section:
        section_label = getattr(section, "class_name", "") or getattr(section, "class_code", "") or ""
    return {
        "student_name": f"{student.first_name} {student.last_name}".strip() or student.custom_id or "Student",
        "student_id": getattr(student, "custom_id", "") or "",
        "grade_level": getattr(student, "grade_level", "") or getattr(enrollment, "grade_level", "") or "",
        "section": section_label,
        "teacher_name": (
            f"{teacher.first_name} {teacher.last_name}".strip()
            if teacher else ""
        ),
        "school_year": getattr(school_calendar, "school_year", "") or "",
        "course_name": getattr(course, "title", "") or "",
        "course_code": getattr(course, "code", "") or "",
        "email": getattr(student, "email", "") or "",
    }


def _collect_crla(student):
    result = latest_completed_official_crla_results(student_ids=[student.pk]).get(student.pk)
    if not result:
        return {
            "available": False,
            "status": "not_available",
            "message": "An official completed CRLA result is not available.",
        }

    score_data = result.crla_score_data if isinstance(result.crla_score_data, dict) else {}
    remarks_data = _parse_prefixed_json(result.remarks)
    miscues = score_data.get("miscues")
    if miscues is None:
        miscues = remarks_data.get("miscues")
    finalized = FINALIZED_CRLA_REMARK in str(result.remarks or "")
    return {
        "available": True,
        "status": "finalized_without_submission" if finalized else "completed",
        "finalized_without_submission": finalized,
        "message": (
            "CRLA assessment was finalized for the class without a submitted student assessment."
            if finalized else "Official completed CRLA result."
        ),
        "assessment_id": result.pk,
        "assessment_title": result.source_assessment.title if result.source_assessment_id and result.source_assessment else result.title,
        "assessment_period": result.system_assessment_period or getattr(result.source_assessment, "system_assessment_period", ""),
        "assessment_phase": result.system_assessment_phase or getattr(result.source_assessment, "system_assessment_phase", ""),
        "official_term": result.official_term,
        "reading_profile": result.crla_classification or result.classification or "",
        "total_score": result.total_score,
        "accuracy": result.accuracy,
        "wpm": result.wpm,
        "miscues": miscues,
        "duration_seconds": result.duration_seconds,
        "task_results": score_data,
        "part2_results": {
            key: score_data.get(key)
            for key in (
                "story_number", "story_read_percent", "passage_accuracy_percent",
                "correct_answers", "comprehension_correct", "part1_total_score",
            )
            if score_data.get(key) is not None
        },
        "completed_at": result.completed_at.isoformat() if result.completed_at else "",
    }


def _is_supplementary_skill_activity(material, activity_id, result=None):
    """Keep the skills-practiced summary separate from workbook/CRLA results."""
    if activity_id in WORKBOOK_ACTIVITIES:
        return False
    source = result.source_assessment if result and result.source_assessment_id else None
    for owner in (material, result, source):
        if owner is None:
            continue
        if (getattr(owner, 'assessment_kind', '') == 'crla'
                or getattr(owner, 'assessment_set', '') == 'crla'
                or getattr(owner, 'system_assessment_key', '') in OFFICIAL_CRLA_KEYS
                or (getattr(owner, 'is_system_owned', False) and getattr(owner, 'is_official_reading', False))):
            return False
    return True


def _performance_from_result(result, activity_id, definition):
    details = _parse_prefixed_json(result.remarks)
    return {
        "activity_id": activity_id,
        "activity_name": definition["name"],
        "competencies": list(definition["competencies"]),
        "supplementary_skill_activity": _is_supplementary_skill_activity(result.material, activity_id, result),
        "material_id": result.material_id,
        "record_id": result.pk,
        "evidence_source": "Assessment",
        "assigned_weeks": _material_week_values(result.material),
        "status": "completed",
        "completed": True,
        "completed_at": result.completed_at.isoformat() if result.completed_at else "",
        "score": result.total_score,
        "accuracy": result.accuracy,
        "correct_items": result.correct_items,
        "total_items": result.items_completed,
        "duration_seconds": result.duration_seconds,
        "passed": result.passed,
        "wpm": result.wpm,
        "miscues": details.get("miscues"),
        "transcript": result.transcript if activity_id == "fluency_reading" else "",
        "automated_speech_analysis": bool(result.speech_recognition_used),
        "item_results": details,
    }


def _collect_aral(student, sections, course=None):
    materials = _scoped_materials(sections, course=course)
    material_ids = list(materials.values_list("id", flat=True))
    if not material_ids:
        return []
    material_map = {material.id: material for material in materials}
    rows = []

    results = (
        Assessment.objects.filter(
            student=student,
            material_id__in=material_ids,
            attempt_status="completed",
            completed_at__isnull=False,
            is_active=True,
        )
        .select_related("material", "source_assessment")
        .order_by("completed_at", "id")
    )
    for result in results:
        activity_id, definition = resolve_activity(result.material.content_json)
        if not activity_id:
            continue
        rows.append(_performance_from_result(result, activity_id, definition))

    progress_rows = (
        StoryReadingProgress.objects.filter(
            student=student,
            material_id__in=material_ids,
            completed=True,
            completed_at__isnull=False,
        )
        .select_related("material")
        .order_by("completed_at", "id")
    )
    existing_story_materials = {row["material_id"] for row in rows if row["activity_id"] == "story_reading"}
    for progress in progress_rows:
        activity_id, definition = resolve_activity(progress.material.content_json)
        if activity_id != "story_reading" or progress.material_id in existing_story_materials:
            continue
        rows.append({
            "activity_id": activity_id,
            "activity_name": definition["name"],
            "competencies": list(definition["competencies"]),
            "supplementary_skill_activity": _is_supplementary_skill_activity(progress.material, activity_id),
            "material_id": progress.material_id,
            "record_id": progress.pk,
            "evidence_source": "StoryReadingProgress",
            "assigned_weeks": _material_week_values(progress.material),
            "status": "completed",
            "completed": True,
            "completed_at": progress.completed_at.isoformat(),
            "score": progress.reading_score,
            "accuracy": progress.accuracy,
            "correct_items": progress.correct_words,
            "total_items": progress.total_words,
            "duration_seconds": progress.duration_seconds,
            "passed": None,
            "wpm": progress.wpm,
            "miscues": progress.miscues,
            "transcript": "",
            "automated_speech_analysis": bool(progress.word_alignment),
            "item_results": {"progress_percent": progress.progress_percent},
        })

    submissions = (
        StoryResponseSubmission.objects.filter(
            student=student,
            material_id__in=material_ids,
            submitted_at__isnull=False,
        )
        .select_related("material")
        .order_by("submitted_at", "id")
    )
    for submission in submissions:
        activity_id, definition = resolve_activity(submission.material.content_json)
        if activity_id not in {"story_response", "retell_story", "five_w_story_questions"}:
            continue
        rows.append({
            "activity_id": activity_id,
            "activity_name": definition["name"],
            "competencies": list(definition["competencies"]),
            "supplementary_skill_activity": _is_supplementary_skill_activity(submission.material, activity_id),
            "material_id": submission.material_id,
            "record_id": submission.pk,
            "evidence_source": "StoryResponseSubmission",
            "assigned_weeks": _material_week_values(submission.material),
            # Keep the persisted review state visible; submission itself is the
            # completion event and must not be mistaken for teacher grading.
            "status": submission.status or "pending",
            "completed": True,
            "completed_at": submission.submitted_at.isoformat(),
            "score": submission.grade,
            "accuracy": None,
            "correct_items": None,
            "total_items": None,
            "duration_seconds": submission.duration_seconds,
            "passed": None,
            "wpm": None,
            "miscues": None,
            "transcript": "",
            "automated_speech_analysis": False,
            "item_results": {"grade": submission.grade, "grading_status": submission.status},
        })

    return sorted(rows, key=lambda row: row.get("completed_at") or "", reverse=True)


def _recommendation_crla(crla, history, workbook):
    """Use a verified report-year/period result without changing the CRLA display."""
    if not workbook.get("school_calendar_id"):
        return crla
    term = workbook.get("current_term")
    period = {1: "BoSY", 2: "Midline", 3: "EoSY"}.get(term)
    rows = history.get("rows") or []
    selected = (next((row for row in rows if row["period"] == period), None)
                if period else (rows[-1] if rows else None))
    return {
        "available": bool(selected), "assessment_id": selected["assessment_id"] if selected else None,
        "reading_profile": selected["classification"] if selected else "",
        "school_calendar_id": workbook["school_calendar_id"], "school_year": workbook.get("school_year"),
        "official_term": term, "assessment_period": period or (selected["period"] if selected else ""),
    }


def _recommendations(crla, supplementary_activities, workbook=None):
    """Return auditable advice; completion is never a correctness score.

    P0/P5 take precedence; P1-P4 use evidence only for applicable ARAL support.
    Workbook judgments require the report's verified current calendar AND term.
    """
    recommendations = []
    seen = {}

    def add(code, text, activity, reason, evidence):
        identity = (code, activity.get("source"), activity.get("activity_key"),
                    activity.get("activity_id"), activity.get("school_calendar_id"),
                    activity.get("term"), reason)
        if identity in seen:
            retained = seen[identity]["evidence"]
            retained.extend(item for item in evidence if item not in retained)
            return
        entry = {"code": code, "text": text, "activity": activity or None,
                 "reason": reason, "evidence": evidence}
        seen[identity] = entry
        recommendations.append(entry)

    crla_evidence = {"source": "Assessment", "record_id": crla.get("assessment_id"),
                     "school_calendar_id": crla.get("school_calendar_id"),
                     "term": crla.get("official_term"), "period": crla.get("assessment_period")}
    if not crla.get("available") or crla.get("finalized_without_submission"):
        period = crla.get("assessment_period")
        scope = f" for {period}, school year {crla['school_year']}" if period and crla.get("school_year") else ""
        add("P0", f"An official CRLA result is not yet available{scope}. Please coordinate with the teacher to complete the assessment or confirm its official result. Your child may use Practice Mode for reading practice while awaiting the official result.", {},
            "No qualifying official CRLA result is available.",
            [{**crla_evidence, "field": "official_crla_result", "available": False,
              "finalized_without_submission": bool(crla.get("finalized_without_submission"))}])
        return recommendations

    profile = canonical_crla_classification(crla.get("reading_profile"))
    if profile == "Reading At Grade Level":
        add("P5", "Your child's official CRLA classification is Reading At Grade Level. Continue regular reading practice using Practice Mode to maintain and strengthen reading skills.", {},
            "The qualifying official CRLA result classifies the learner as Reading At Grade Level.",
            [{**crla_evidence, "field": "crla_classification", "value": profile}])
        return recommendations

    workbook = workbook or {}
    calendar_id, term = workbook.get("school_calendar_id"), workbook.get("current_term")
    current = [row for row in workbook.get("rows", [])
               if calendar_id and term in (1, 2, 3) and row.get("period_verified")
               and row.get("school_calendar_id") == calendar_id and row.get("term") == term]
    if not supplementary_activities and not current:
        add("P1", "Continue assigned ARAL reading activities and review results with the teacher.", {},
            "No supplementary results or verified current-period workbook records are available.",
            [{"source": "report_scope", "school_calendar_id": calendar_id, "term": term}])

    grouped = defaultdict(list)
    for row in supplementary_activities:
        grouped[row["activity_id"]].append(row)
    for activity_id, rows in grouped.items():
        name = rows[0]["activity_name"]
        activity = {"source": "supplementary", "activity_id": activity_id, "title": name}

        def sources(results, field):
            return [{"source": row.get("evidence_source", "Assessment"),
                     "record_id": row.get("record_id"), "material_id": row.get("material_id"),
                     "field": field, "value": row.get(field)} for row in results]

        lower = [row for row in rows if row.get("accuracy") is not None and row["accuracy"] < 80]
        if lower:
            add("P2", f"Continue guided practice with the activities that have lower recorded accuracy. Activity: {name}.",
                activity, "Supplementary activity accuracy is below 80%.", sources(lower, "accuracy"))
        fluency = [row for row in rows if row.get("wpm") is not None]
        if fluency:
            automated = any(row.get("automated_speech_analysis") for row in fluency)
            description = "automated fluency results" if automated else "recorded fluency results"
            add("P3", f"Continue short, regular oral-reading practice and review {description} with the teacher. Activity: {name}.",
                activity, "A supplementary oral-reading rate is recorded.", sources(fluency, "wpm"))

    for row in current:
        facts = row.get("evidence") or {}
        recordings = facts.get("recordings") or []
        labels = [f"{label} {row[key]}" for label, key in (
            ("Session", "session"), ("Lesson", "lesson"), ("Gawain", "gawain"),
        ) if row.get(key) not in (None, "")]
        label = ", ".join(labels)
        if label and row["title"].casefold() not in {part.casefold() for part in labels}:
            label = f"{label} ({row['title']})"
        elif not label:
            label = row["title"]
        activity = {key: row.get(key) for key in (
            "activity_key", "title", "session", "lesson", "gawain", "school_calendar_id", "term",
        )}
        activity["source"] = "workbook"
        progress_source = {"source": "StudentActivityProgress", "record_id": facts.get("progress_id")}
        pending = [r for r in recordings if r["review_status"] == "pending" or
                   (r["status"] == "submitted" and not r["teacher_reviewed"])]
        retries = [r for r in recordings if r["status"] == "retry"]
        status_evidence = []
        if facts.get("progress_id"):
            status_evidence.append({**progress_source, "field": "completion_and_review",
                                    "completed": row.get("completed", False),
                                    "pending_review": facts.get("pending_review", False),
                                    "retry_requested": facts.get("retry_requested", False)})
        status_evidence.extend({"source": "StudentActivityRecordingSubmission",
                                "record_id": r["submission_id"], "field": "review_status",
                                "status": r["status"], "review_status": r["review_status"]}
                               for r in pending + retries)
        if facts.get("pending_review") or pending:
            add("P1", f"Review submitted work in {label} with the teacher; evaluation is pending.", activity,
                "Workbook work is awaiting teacher review.", status_evidence)
        elif facts.get("retry_requested") or retries:
            add("P1", f"Repeat {label} as requested by the teacher and review the new work together.", activity,
                "A workbook retry was requested.", status_evidence)
        elif not row.get("completed") and facts.get("completion_recorded"):
            add("P1", f"Continue {label} and review the results with the teacher.", activity,
                "A workbook activity is ongoing.", status_evidence)

        incorrect = ([] if facts.get("pending_review") else
                     [answer for answer in facts.get("scored_answers", []) if answer["correct"] is False])
        zeros = [r for r in recordings if r["teacher_reviewed"] and r["teacher_score"] == 0]
        difficulty = []
        if incorrect:
            difficulty.append({**progress_source, "field": "state.answer_records",
                               "incorrect_item_ids": [answer["item_id"] for answer in incorrect]})
        difficulty.extend({"source": "StudentActivityRecordingSubmission", "record_id": r["submission_id"],
                           "field": "teacher_score", "value": 0, "teacher_reviewed": True} for r in zeros)
        if difficulty:
            add("P2", f"Practice the items needing support in {label} with teacher guidance.", activity,
                "Scored workbook answers or teacher-reviewed items identify specific errors.", difficulty)

        oral_evidence = [r for r in recordings if r["has_recording"] or
                         (r["teacher_reviewed"] and (r["teacher_score"] == 0 or
                          (r["classification_source"] == "teacher" and r["classification"] in {"YELLOW", "RED"})))]
        if facts.get("oral_reading") and oral_evidence:
            add("P3", f"Continue oral reading practice using {label} and review the recordings or teacher feedback with the teacher.",
                activity, "A verified workbook oral-reading activity has recorded submissions or reviewed support needs.",
                [{"source": "StudentActivityRecordingSubmission", "record_id": r["submission_id"],
                  "field": "oral_reading_submission", "has_recording": r["has_recording"],
                  "teacher_reviewed": r["teacher_reviewed"], "teacher_score": r["teacher_score"],
                  "classification": r["classification"], "classification_source": r["classification_source"]}
                 for r in oral_evidence])

    program = workbook.get("program") or {}
    if (program.get("verified") and calendar_id and term in (1, 2, 3)
            and program.get("school_calendar_id") == calendar_id and program.get("term") == term):
        required = list(dict.fromkeys(program.get("activity_keys") or []))
        completed = {row["activity_key"] for row in current if row.get("completed")}.intersection(required)
        remaining = [key for key in required if key not in completed]
        if remaining:
            count = len(required) - len(remaining)
            text = (f"Workbook progress: {count} of {len(required)} prescribed activities are recorded as completed "
                    f"for Term {term}. Continue the remaining workbook activities with the teacher.")
            evidence = {
                "source": "active_prescribed_sequence", "field": "remaining_workbook_activities",
                "school_calendar_id": calendar_id, "term": term,
                "enrollment_id": program.get("enrollment_id"), "required_activity_keys": required,
                "completed_activity_keys": [key for key in required if key in completed],
                "remaining_activity_keys": remaining,
                "completion_records": [{"source": "StudentActivityProgress",
                    "record_id": row.get("evidence", {}).get("progress_id"),
                    "activity_key": row["activity_key"]} for row in current
                    if row["activity_key"] in completed],
            }
            continuation = next((item for item in recommendations if item["code"] == "P1" and (
                (item["activity"] or {}).get("source") == "workbook"
                or (not item["activity"] and any(fact.get("source") == "report_scope"
                                               for fact in item["evidence"]))
            )), None)
            if continuation:
                # Keep the existing named activity/review advice and add the
                # missing programme context once, rather than duplicate P1.
                continuation["text"] += " " + text
                continuation["reason"] += " The verified prescribed workbook sequence is incomplete."
                continuation["evidence"].append(evidence)
            else:
                add("P1", text, {"source": "workbook_program", "title": "ARAL Workbook",
                                "school_calendar_id": calendar_id, "term": term},
                    "The verified prescribed workbook sequence includes unfinished or unrecorded activities.",
                    [evidence])

    if not recommendations:
        fallback_evidence = [{"source": "report_scope", "school_calendar_id": calendar_id, "term": term}]
        fallback_evidence.extend({"source": "StudentActivityProgress",
                                  "record_id": row["evidence"]["progress_id"],
                                  "activity_key": row["activity_key"], "completed": row["completed"],
                                  "teacher_checked": row["evidence"]["teacher_checked"]}
                                 for row in current if row.get("evidence", {}).get("progress_id"))
        fallback_evidence.extend({"source": row.get("evidence_source", "Assessment"),
                                  "record_id": row.get("record_id"), "material_id": row.get("material_id"),
                                  "accuracy": row.get("accuracy"), "wpm": row.get("wpm")}
                                 for row in supplementary_activities)
        add("P4", "Continue regular reading practice and teacher-guided support.", {},
            "No unfinished work, pending review, or specific support trigger is recorded in the recommendation inputs.",
            fallback_evidence)
    return recommendations


def build_student_reading_progress_report(student, sections=None, course=None):
    """Collect persisted CRLA and ARAL data without applying new scoring rules."""
    scoped_sections = _scope_sections(student, sections=sections, course=course)
    crla = _collect_crla(student)
    activities = _collect_aral(student, scoped_sections, course=course)
    competencies = []
    by_competency = defaultdict(list)
    for activity in activities:
        if not activity.get("supplementary_skill_activity"):
            continue
        for competency in activity["competencies"]:
            by_competency[competency].append(activity)
    for competency in COMPETENCIES:
        completed = by_competency.get(competency, [])
        competencies.append({
            "name": competency,
            "activities": completed,
            "completed_count": len(completed),
        })

    report = _student_context(student, scoped_sections, course=course)
    calendar = report_calendar(student, scoped_sections)
    workbook = collect_workbook_performance(student, calendar)
    history = collect_crla_history(student, calendar)
    recommendation_crla = _recommendation_crla(crla, history, workbook)
    recommendations = _recommendations(recommendation_crla, activities, workbook)
    report.update({
        "crla": crla,
        "crla_history": history,
        "recommendation_crla": recommendation_crla,
        "workbook": workbook,
        "aral_activities": activities,
        "competencies": competencies,
        "recent_progress": activities[:10],
        "recommendations": [item["text"] for item in recommendations],
        "recommendation_details": recommendations,
        "has_completed_assessment": bool(crla.get("available") or activities),
    })
    return report
