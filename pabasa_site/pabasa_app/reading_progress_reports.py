"""Structured data collection for parent-facing reading progress reports."""

import json
from collections import defaultdict

from django.db.models import Q

from .aral_activity_catalog import ACTIVITIES, COMPETENCIES, resolve_activity
from .models import Assessment, Enrollment, Material, StoryReadingProgress, StoryResponseSubmission
from .utils.crla_results import latest_completed_official_crla_results


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


def _performance_from_result(result, activity_id, definition):
    details = _parse_prefixed_json(result.remarks)
    return {
        "activity_id": activity_id,
        "activity_name": definition["name"],
        "competencies": list(definition["competencies"]),
        "material_id": result.material_id,
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
            "material_id": progress.material_id,
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
            "material_id": submission.material_id,
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


def _recommendations(crla, activities):
    recommendations = []
    if not crla.get("available"):
        recommendations.append("Complete an official CRLA assessment to establish a reading baseline.")
    if not activities:
        recommendations.append("Continue assigned ARAL reading activities and review results with the teacher.")
    if any(row.get("accuracy") is not None and row["accuracy"] < 80 for row in activities):
        recommendations.append("Continue guided practice with the activities that have lower recorded accuracy.")
    if any(row.get("wpm") is not None for row in activities):
        recommendations.append("Continue short, regular oral-reading practice and review automated fluency results with the teacher.")
    return recommendations or ["Continue regular reading practice and teacher-guided support."]


def build_student_reading_progress_report(student, sections=None, course=None):
    """Collect persisted CRLA and ARAL data without applying new scoring rules."""
    scoped_sections = _scope_sections(student, sections=sections, course=course)
    crla = _collect_crla(student)
    activities = _collect_aral(student, scoped_sections, course=course)
    competencies = []
    by_competency = defaultdict(list)
    for activity in activities:
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
    report.update({
        "crla": crla,
        "aral_activities": activities,
        "competencies": competencies,
        "recent_progress": activities[:10],
        "recommendations": _recommendations(crla, activities),
        "has_completed_assessment": bool(crla.get("available") or activities),
    })
    return report
