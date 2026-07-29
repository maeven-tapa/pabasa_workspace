"""Export Pabasa assessment results into the official CRLA workbook."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
import math
import re
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from openpyxl import load_workbook

from pabasa_app.models import Assessment, User

from .crla_mapping import (
    FORMULA_COLUMNS,
    SCHOOL_CELLS,
    SHEET_NAME,
    STUDENT_COLUMNS,
    STUDENT_END_ROW,
    STUDENT_START_ROW,
)


TEMPLATE_FILENAME = "CRLA3_Grade2TagalogScoresheet_v3.xlsx"


def _first_value(*values):
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _bounded_integer(value, minimum, maximum):
    number = _number(value)
    if number is None:
        return None
    return max(minimum, min(maximum, int(round(number))))


def _full_name(user):
    if not user:
        return ""
    parts = [
        user.first_name,
        f"{user.middle_initial}." if user.middle_initial else "",
        user.last_name,
        user.suffix,
    ]
    return " ".join(str(part).strip() for part in parts if str(part or "").strip())


def _profile_value(user, *keys):
    preference = getattr(user, "preference", None) or {}
    if isinstance(preference, dict):
        for key in keys:
            value = preference.get(key)
            if value not in (None, ""):
                return value
    return ""


def _safe_filename(value):
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(value or "Assessment"))
    cleaned = re.sub(r"\s+", "_", cleaned).strip(" ._")
    return cleaned[:120] or "Assessment"


def _attempt_sort_key(attempt):
    completed = attempt.completed_at or attempt.started_at or attempt.updated_at or attempt.created_at
    if completed and timezone.is_naive(completed):
        completed = timezone.make_aware(completed, timezone.get_default_timezone())
    return completed or datetime.min.replace(tzinfo=timezone.get_default_timezone())


def _latest_attempts(assessment):
    attempts = (
        Assessment.objects.filter(source_assessment=assessment, student__isnull=False)
        .select_related("student")
        .order_by("student_id", "attempt_number", "created_at", "id")
    )
    latest = {}
    for attempt in attempts:
        current = latest.get(attempt.student_id)
        if current is None or _attempt_sort_key(attempt) >= _attempt_sort_key(current):
            latest[attempt.student_id] = attempt
    return latest


def _assessment_students(assessment, latest_attempts):
    students = []
    seen = set()
    section = assessment.section
    if section:
        enrolled_ids = []
        for entry in section.get_enrolled_students(active_only=True):
            try:
                enrolled_ids.append(int(entry.get("student_id")))
            except (TypeError, ValueError, AttributeError):
                continue
        by_id = {
            student.id: student
            for student in User.objects.filter(id__in=enrolled_ids, role="student", is_archived=False)
        }
        for student_id in enrolled_ids:
            student = by_id.get(student_id)
            if student and student.id not in seen:
                students.append(student)
                seen.add(student.id)

    for student_id, attempt in latest_attempts.items():
        if student_id not in seen and attempt.student:
            students.append(attempt.student)
            seen.add(student_id)
    return students


def _observation_level(attempt):
    if not attempt:
        return None
    score = _number(_first_value(attempt.fluency_score, attempt.total_score, attempt.accuracy))
    if score is None:
        return None
    if score <= 25:
        return "Level 1"
    if score <= 50:
        return "Level 2"
    if score <= 75:
        return "Level 3"
    return "Level 4"


def _student_values(student, attempt):
    duration = _bounded_integer(getattr(attempt, "duration_seconds", None), 0, 24 * 60 * 60)
    minutes, seconds = (divmod(duration, 60) if duration is not None else (None, None))

    words_read = _bounded_integer(getattr(attempt, "word_count", None), 0, 100000)
    accuracy = _number(getattr(attempt, "accuracy", None))
    miscues = None
    if words_read is not None and accuracy is not None and 0 < accuracy <= 100:
        estimated_total = int(round(words_read / (accuracy / 100)))
        miscues = max(0, estimated_total - words_read)

    correct_items = _first_value(
        getattr(attempt, "correct_items", None),
        getattr(attempt, "items_completed", None),
    )
    total_score = getattr(attempt, "total_score", None)
    task_1_score = _bounded_integer(correct_items, 0, 10)
    if task_1_score is None and total_score is not None:
        task_1_score = _bounded_integer(_number(total_score) / 10, 0, 10)

    completed_at = None
    if attempt:
        completed_at = attempt.completed_at or attempt.started_at or attempt.created_at
        if completed_at:
            completed_at = timezone.localtime(completed_at).date() if timezone.is_aware(completed_at) else completed_at.date()

    learner_rating = None
    if total_score is not None:
        learner_rating = _bounded_integer(math.ceil(max(0, _number(total_score) or 0) / 20), 1, 5)

    raw_sex = str(student.sex or "").strip().lower()
    sex = {"m": "Male", "male": "Male", "f": "Female", "female": "Female"}.get(raw_sex, "")

    return {
        # LRN is an official learner identifier. Never substitute an internal
        # database/user/custom ID when the learner has no stored LRN.
        "lrn": student.lrn or "",
        "learner_name": _full_name(student),
        "sex": sex,
        "assessment_date": completed_at,
        "task_1_score": task_1_score,
        "task_2l_score": None,
        "task_2h_score": None,
        "story_number": 1 if attempt else None,
        "miscues": miscues,
        "reading_minutes": minutes,
        "reading_seconds": seconds,
        "comprehension_score": _bounded_integer(correct_items, 0, 6),
        "learner_experience_rating": learner_rating,
        "observation_level": _observation_level(attempt),
        "remarks": getattr(attempt, "remarks", "") if attempt else "",
    }


def export_crla_excel(assessment_id):
    """Return an in-memory CRLA workbook for a root assessment.

    The returned ``BytesIO`` is positioned at byte zero and has a ``name``
    attribute containing the download filename.
    """
    assessment = (
        Assessment.objects.select_related("teacher", "section", "section__teacher")
        .get(pk=assessment_id)
    )
    if assessment.source_assessment_id:
        assessment = (
            Assessment.objects.select_related("teacher", "section", "section__teacher")
            .get(pk=assessment.source_assessment_id)
        )

    template_path = Path(settings.BASE_DIR) / "templates" / TEMPLATE_FILENAME
    if not template_path.is_file():
        raise FileNotFoundError(f"CRLA template not found: {template_path}")

    workbook = load_workbook(template_path)
    worksheet = workbook[SHEET_NAME]
    workbook.calculation.calcMode = "auto"
    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True

    latest_attempts = _latest_attempts(assessment)
    students = _assessment_students(assessment, latest_attempts)
    if len(students) > (STUDENT_END_ROW - STUDENT_START_ROW + 1):
        raise ValueError("The official CRLA template supports at most 100 learners.")

    teacher = assessment.teacher
    section = assessment.section
    male_count = sum(str(student.sex or "").strip().lower() == "male" for student in students)
    female_count = sum(str(student.sex or "").strip().lower() == "female" for student in students)
    school_values = {
        # C3 is the CRLA administration period, not Pabasa's content type
        # (word/sentence/paragraph). Default to BoSY when no school preference
        # has been configured.
        "assessment_type": _profile_value(
            teacher,
            "crla_assessment_type",
            "crla_assessment_period",
        ) or "BoSY",
        "school_id": _profile_value(teacher, "school_id", "schoolId"),
        "school_name": teacher.school or "",
        "teacher": _full_name(teacher),
        "male_enrollment": male_count,
        "female_enrollment": female_count,
        "section": section.class_name if section else "",
    }
    for field, cell in SCHOOL_CELLS.items():
        worksheet[cell] = school_values[field]

    for offset, student in enumerate(students):
        row = STUDENT_START_ROW + offset
        values = _student_values(student, latest_attempts.get(student.id))
        for field, column in STUDENT_COLUMNS.items():
            if column in FORMULA_COLUMNS:
                raise RuntimeError(f"Refusing to overwrite formula column {column}.")
            worksheet[f"{column}{row}"] = values[field]

    output = BytesIO()
    output.name = f"CRLA_{_safe_filename(assessment.title)}.xlsx"
    workbook.save(output)
    output.seek(0)
    return output
