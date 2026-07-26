"""Account-level reader classification based on completed assessment types.

Reader classification is intentionally independent from the assessment score.
Paragraph levels use the cumulative number of fully correct paragraph items
over all paragraph items read by the student.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional


LOW_EMERGING = "Low Emerging Readers"
HIGH_EMERGING = "High Emerging Readers"
DEVELOPING = "Developing Readers"
TRANSITIONING = "Transitioning Readers"
AT_GRADE_LEVEL = "Readers at Grade Level"


def _non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def classify_reader(attempts: Iterable[Mapping[str, Any]]) -> Optional[str]:
    """Return a classification from an account's completed assessments.

    Paragraph attempts take precedence. A paragraph item is correct only when
    it was recorded in ``correct_items``; ``items_completed`` is the number of
    paragraph items read.
    """
    completed_types: set[str] = set()
    correct_paragraphs = 0
    total_paragraphs = 0

    for attempt in attempts or []:
        if str(attempt.get("status", "completed")).strip().lower() != "completed":
            continue
        assessment_type = str(attempt.get("assessment_type") or "").strip().lower()
        if not assessment_type:
            continue
        completed_types.add(assessment_type)
        if assessment_type == "paragraph":
            # Legacy rows created before correct-item tracking cannot safely be
            # interpreted as zero-correct paragraph attempts.
            if attempt.get("correct_items") is None:
                continue
            total = _non_negative_int(attempt.get("items_completed"))
            correct = min(total, _non_negative_int(attempt.get("correct_items")))
            total_paragraphs += total
            correct_paragraphs += correct

    if total_paragraphs:
        percentage = (correct_paragraphs / total_paragraphs) * 100
        if percentage < 50:
            return DEVELOPING
        if percentage <= 75:
            return TRANSITIONING
        return AT_GRADE_LEVEL

    if "word" in completed_types and "sentence" in completed_types:
        return HIGH_EMERGING
    if "word" in completed_types:
        return LOW_EMERGING
    return None


def completed_assessments_for_student(student: Any) -> list[dict[str, Any]]:
    """Load the completed assessment history used to classify one account."""
    from .models import Assessment

    rows = Assessment.objects.filter(
        student=student,
        source_assessment__isnull=False,
        attempt_status="completed",
    ).select_related("source_assessment")
    return [
        {
            "status": row.attempt_status,
            "assessment_type": row.source_assessment.assessment_type,
            "correct_items": row.correct_items,
            "items_completed": row.items_completed,
        }
        for row in rows
    ]


def classify_student_account(
    student: Any,
    current_attempt: Optional[Mapping[str, Any]] = None,
) -> Optional[str]:
    """Classify a student from saved history plus an optional new attempt."""
    attempts = completed_assessments_for_student(student)
    if current_attempt:
        attempts.append(dict(current_attempt))
    return classify_reader(attempts)
