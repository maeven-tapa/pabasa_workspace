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
from ..scoring import crla_reading_profile, crla_sentence_score
from .crla_results import latest_completed_official_crla_results


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
    # Share the dashboard's authoritative final-result selection exactly.
    return latest_completed_official_crla_results(source_assessment=assessment)


def _valid_section_teacher(section):
    """Return a current section teacher only when it is a valid assignment."""
    teacher = getattr(section, "teacher", None)
    if (
        teacher
        and getattr(teacher, "role", None) == "teacher"
        and not getattr(teacher, "is_archived", False)
    ):
        return teacher
    return None


def _attempt_section_context(attempt):
    """Return the persisted class context for one exported result attempt.

    Official CRLA result rows commonly have no direct ``section`` because the
    system-owned material is shared.  Their enrollment preserves the class in
    which the learner completed the assessment, so it is the authoritative
    fallback.  The assessment/result owner is deliberately never metadata.
    """
    enrollment = getattr(attempt, "enrollment", None)
    section = getattr(attempt, "section", None) or getattr(enrollment, "section", None)
    if not section:
        return None

    school = getattr(enrollment, "school", None) or getattr(section, "school", None)
    return {
        "section": section,
        "school": school,
        "teacher": _valid_section_teacher(section),
    }


def _export_metadata_context(assessment, latest_attempts):
    """Resolve one truthful class context for the workbook header.

    A single CRLA workbook header cannot represent different sections or
    schools.  In that case, or when any exported result has no class context,
    return blanks rather than borrowing metadata from an assessment owner.
    """
    if assessment.section_id and assessment.section:
        context = {
            "section": assessment.section,
            "school": getattr(assessment.section, "school", None),
            "teacher": _valid_section_teacher(assessment.section),
        }
        return context

    contexts = []
    for attempt in latest_attempts.values():
        context = _attempt_section_context(attempt)
        if context is None:
            return {"section": None, "school": None, "teacher": None}
        contexts.append(context)

    if not contexts:
        return {"section": None, "school": None, "teacher": None}

    context_keys = {
        (context["section"].id, getattr(context["school"], "id", None))
        for context in contexts
    }
    if len(context_keys) != 1:
        return {"section": None, "school": None, "teacher": None}
    return contexts[0]


def _state_material_id(value):
    match = re.search(r"(\d+)$", str(value or "").strip())
    return int(match.group(1)) if match else None


def _assessment_material_ids(assessment, latest_attempts):
    ids = set(assessment.materials.values_list("id", flat=True))
    ids.update(attempt.material_id for attempt in latest_attempts.values() if attempt.material_id)
    return ids


def _student_end_state(student, material_ids):
    preference = student.preference if isinstance(student.preference, dict) else {}
    workflow = preference.get("reading_assessment_state")
    workflow = workflow if isinstance(workflow, dict) else {}
    result_states = workflow.get("crla_result_states")
    result_states = result_states if isinstance(result_states, dict) else {}
    for material_id in material_ids:
        persisted = result_states.get(str(material_id))
        if isinstance(persisted, dict):
            return persisted
    state = workflow.get("student_end_assessment_state")
    state = state if isinstance(state, dict) else {}
    state_material_id = _state_material_id(state.get("material_id"))
    if material_ids and state_material_id not in material_ids:
        return {}
    return state


def _attempt_end_state(student, attempt):
    """Return CRLA workflow state only when it belongs to this exact result material.

    A student's last generic end-state may describe a different CRLA phase or
    a prior retake.  It must never be used as evidence for the attempt being
    exported.
    """
    material_id = getattr(attempt, "material_id", None)
    if not material_id:
        return {}

    preference = student.preference if isinstance(student.preference, dict) else {}
    workflow = preference.get("reading_assessment_state")
    workflow = workflow if isinstance(workflow, dict) else {}
    result_states = workflow.get("crla_result_states")
    result_states = result_states if isinstance(result_states, dict) else {}
    persisted = result_states.get(str(material_id))
    if isinstance(persisted, dict):
        return persisted

    # Compatibility for a material-scoped state saved before crla_result_states
    # was introduced.  Do not accept an unscoped state here.
    state = workflow.get("student_end_assessment_state")
    state = state if isinstance(state, dict) else {}
    return state if _state_material_id(state.get("material_id")) == material_id else {}


def _story_reading_evidence(state):
    """Return true only for material-scoped, persisted Story Reading work.

    Part 1 completions also have elapsed time.  They are not Story Reading
    duration and must not populate the Part 2 columns of the CRLA workbook.
    """
    if not isinstance(state, dict):
        return False
    if str(state.get("stage") or "").strip().lower() not in {
        "story_reading", "story_comprehension", "learner_experience", "completed",
    }:
        return False
    selected_story = str(state.get("selected_story") or "").strip()
    total_words = _bounded_integer(
        _first_value(state.get("story_total_words"), state.get("total_story_words")), 1, 100000
    )
    words_read = _bounded_integer(
        _first_value(state.get("words_read"), state.get("total_words_read")), 0, 100000
    )
    duration = _bounded_integer(state.get("duration_seconds"), 1, 24 * 60 * 60)
    return bool(selected_story and total_words is not None and words_read is not None and duration is not None)


def _crla_score_data(attempt):
    score_data = getattr(attempt, "crla_score_data", None)
    return score_data if isinstance(score_data, dict) else {}


def _reading_profile(part_1_total, story_number, percent, correct_answers):
    """Return Column U using the shared official CRLA formula.

    The workbook's Reading Profile is the final classification.  It is never
    replaced by a stale persisted label or by a separate export-only rule.
    """
    return crla_reading_profile(part_1_total, story_number, percent, correct_answers)


def _part_1_reading_level(part_1_total):
    if part_1_total is None:
        return None
    if part_1_total <= 10:
        return "Full Refresher"
    if part_1_total <= 16:
        return "Moderate Refresher"
    if part_1_total <= 26:
        return "Light Refresher"
    return "Grade Ready"


def _observation_level(profile):
    normalized = str(profile or "").strip().lower()
    return {
        "high emerging reader": "Level 1",
        "developing reader": "Level 2",
        "transitioning reader": "Level 3",
        "reading at grade level": "Level 4",
        "reader at grade level": "Level 4",
    }.get(normalized)


def _reading_profile_remark(profile):
    """Return the prescribed remark for an already-derived CRLA profile."""
    normalized = str(profile or "").strip().lower()
    return {
        "low emerging reader": "Needs intensive reading intervention",
        "high emerging reader": "Needs intensive reading support",
        "developing reader": "Needs targeted reading support",
        "transitioning reader": "Needs continued reading practice",
        "reading at grade level": "No additional intervention required",
        "reader at grade level": "No additional intervention required",
    }.get(normalized)


def _story_number(score_data, state):
    selected = str(
        score_data.get("story_number")
        or score_data.get("story_key")
        or score_data.get("story_title")
        or score_data.get("selected_story")
        or state.get("selected_story")
        or ""
    ).strip()
    if not selected:
        return None
    normalized = selected.casefold()
    if normalized in {"si pagong at kuneho", "ang pagong at ang kuneho", "ang pagong at kuneho"}:
        return 1
    if normalized == "isang kakaibang araw":
        return 2
    if normalized in {"filipino-set-1", "story-1", "story1", "1"}:
        return 1
    if normalized in {"filipino-set-2", "story-2", "story2", "2"}:
        return 2
    return None


def _row_formulas(row):
    return {
        "I": f'=IF(AND(F{row}="",G{row}="",H{row}=""),"",SUM(F{row}:H{row}))',
        "J": f'=IF(I{row}="","",IF(I{row}<=10,"Full Refresher",IF(I{row}<17,"Moderate Refresher",IF(I{row}<27,"Light Refresher","Grade Ready"))))',
        "P": f'=IF(AND(M{row}>0,OR(N{row}>0,O{row}>0)),(M{row}/((N{row}*60)+O{row}))*60,"")',
        # A blank Part 2 row must remain blank in Excel.  Without this guard,
        # a blank M cell is treated as zero and produces a misleading 0%.
        "Q": f'=IF(AND(K{row}<>"",M{row}>0),IFERROR(M{row}/IF(K{row}=2,$P$7,$M$7),""),"")',
    }


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


def _student_values(student, attempt, state, assessment):
    score_data = _crla_score_data(attempt)
    story_state = _attempt_end_state(student, attempt)
    has_story_reading = _story_reading_evidence(story_state)
    duration = _bounded_integer(story_state.get("duration_seconds"), 1, 24 * 60 * 60) if has_story_reading else None
    story_number = _story_number({}, story_state) if has_story_reading else None
    minutes, seconds = divmod(duration, 60) if duration is not None else (None, None)

    task_1_score = _bounded_integer(score_data.get("task1_score"), 0, 10)
    task_2_score = _bounded_integer(score_data.get("task2_score"), 0, 10)
    task_2_type = str(score_data.get("task2_type") or "").lower()
    rhyme_score = task_2_score if "l" in task_2_type else None
    sentence_score = task_2_score if "h" in task_2_type else None

    if "h" in task_2_type:
        sentence_count = score_data.get("sentences_read")
        if sentence_count is None:
            sentence_count = min(task_2_score or 0, 4)
        sentence_score = crla_sentence_score(sentence_count)

    if task_1_score is not None:
        if 0 <= task_1_score <= 6:
            rhyme_score = _bounded_integer(task_2_score, 0, 10)
            sentence_score = None
        elif 7 <= task_1_score <= 10:
            sentence_score = crla_sentence_score(
                score_data.get("sentences_read")
                if score_data.get("sentences_read") is not None
                else min(task_2_score or 0, 4)
            )
            rhyme_score = None

    part_1_total = None
    if task_1_score is not None and (rhyme_score is not None or sentence_score is not None):
        part_1_total = task_1_score + (rhyme_score or 0) + (sentence_score or 0)

    story_words_read = _bounded_integer(
        _first_value(story_state.get("words_read"), story_state.get("total_words_read")), 0, 100000,
    ) if has_story_reading else None
    miscues = _bounded_integer(story_state.get("miscues"), 0, 100000) if has_story_reading else None
    percent = _number(_first_value(
        story_state.get("passage_accuracy_percent"), story_state.get("story_read_percent"),
    )) if has_story_reading else None
    correct_answers = _bounded_integer(
        score_data.get("comprehension_correct"),
        0,
        6,
    )
    profile = _reading_profile(part_1_total, story_number, percent, correct_answers)

    completed_at = None
    if attempt:
        completed_at = attempt.completed_at or attempt.started_at or attempt.created_at
        if completed_at:
            completed_at = timezone.localtime(completed_at).date() if timezone.is_aware(completed_at) else completed_at.date()

    learner_rating = _bounded_integer(
        _first_value(state.get("learner_experience_rating"), state.get("learner_experience")), 1, 5
    ) if _first_value(state.get("learner_experience_rating"), state.get("learner_experience")) is not None else None

    raw_sex = str(student.sex or "").strip().lower()
    sex = {"m": "Male", "male": "Male", "f": "Female", "female": "Female"}.get(raw_sex, "")

    words_per_minute = _number(story_state.get("wpm")) if has_story_reading else None

    return {
        # LRN is an official learner identifier. Never substitute an internal
        # database/user/custom ID when the learner has no stored LRN.
        "lrn": student.lrn or "",
        "learner_name": _full_name(student),
        "sex": sex,
        "assessment_date": completed_at,
        "task_1_score": task_1_score,
        "task_2l_score": rhyme_score,
        "task_2h_score": sentence_score,
        "part_1_total": part_1_total,
        "part_1_reading_level": _part_1_reading_level(part_1_total),
        "story_number": story_number,
        "miscues": miscues,
        "total_words_read": story_words_read,
        "reading_minutes": minutes,
        "reading_seconds": seconds,
        "words_per_minute": words_per_minute,
        "correct_words_percentage": (percent / 100) if percent is not None else None,
        "comprehension_score": correct_answers,
        "learner_experience_rating": learner_rating,
        "observation_level": _observation_level(profile),
        "reading_profile": profile or None,
        "remarks": _reading_profile_remark(profile),
    }


def export_crla_excel(assessment_id):
    """Return an in-memory CRLA workbook for a root assessment.

    The returned ``BytesIO`` is positioned at byte zero and has a ``name``
    attribute containing the download filename.
    """
    assessment = (
        Assessment.objects.select_related("teacher", "section", "section__teacher", "section__school")
        .get(pk=assessment_id)
    )
    if assessment.source_assessment_id:
        assessment = (
            Assessment.objects.select_related("teacher", "section", "section__teacher", "section__school")
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

    metadata = _export_metadata_context(assessment, latest_attempts)
    teacher = metadata["teacher"]
    section = metadata["section"]
    school = metadata["school"]
    material_ids = _assessment_material_ids(assessment, latest_attempts)
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
        "school_id": getattr(school, "code", "") or "",
        "school_name": getattr(school, "name", "") or "",
        "teacher": _full_name(teacher),
        "male_enrollment": male_count,
        "female_enrollment": female_count,
        "section": section.class_name if section else "",
    }
    for field, cell in SCHOOL_CELLS.items():
        worksheet[cell] = school_values[field]

    for offset, student in enumerate(students):
        row = STUDENT_START_ROW + offset
        values = _student_values(
            student,
            latest_attempts.get(student.id),
            _student_end_state(student, material_ids),
            assessment,
        )
        for field, column in STUDENT_COLUMNS.items():
            if column in FORMULA_COLUMNS:
                worksheet[f"{column}{row}"] = _row_formulas(row)[column]
                continue
            worksheet[f"{column}{row}"] = values[field]

    output = BytesIO()
    output.name = f"CRLA_{_safe_filename(assessment.title)}.xlsx"
    workbook.save(output)
    output.seek(0)
    return output
