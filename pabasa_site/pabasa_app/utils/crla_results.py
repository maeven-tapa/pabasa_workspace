"""Authoritative selection of persisted official CRLA result rows."""

from django.db.models import Q

from pabasa_app.models import Assessment
from pabasa_app.scoring import CRLA_CLASSIFICATIONS


OFFICIAL_CRLA_KEYS = (
    "bosy_crla_pretest",
    "midline_crla_midtest",
    "eosy_crla_posttest",
)
VALID_CRLA_CLASSIFICATIONS = tuple(label for _threshold, label in CRLA_CLASSIFICATIONS)


def official_crla_result_queryset():
    """Finalized rows that are identifiable as official CRLA assessments.

    System ownership alone is deliberately insufficient.  A row must carry an
    official CRLA system key, or be linked to material explicitly identified as
    CRLA assessment content.  System ownership alone is never sufficient.
    """
    return Assessment.objects.filter(
        attempt_status="completed",
        completed_at__isnull=False,
        crla_classification__in=VALID_CRLA_CLASSIFICATIONS,
        student__isnull=False,
    ).filter(
        Q(system_assessment_key__in=OFFICIAL_CRLA_KEYS)
        | Q(source_assessment__system_assessment_key__in=OFFICIAL_CRLA_KEYS)
        | Q(material__assessment_kind="crla")
        | Q(
            source_assessment__materials__assessment_kind="crla",
        )
    ).select_related("student", "teacher", "section", "section__teacher", "material", "source_assessment", "source_assessment__material").distinct()


def latest_completed_official_crla_results(student_ids=None, source_assessment=None):
    """Latest valid official CRLA result per student, deterministically."""
    results = official_crla_result_queryset()
    if student_ids is not None:
        results = results.filter(student_id__in=student_ids)
    if source_assessment is not None:
        results = results.filter(source_assessment=source_assessment)

    latest = {}
    for result in results.order_by("student_id", "-completed_at", "-updated_at", "-id"):
        latest.setdefault(result.student_id, result)
    return latest
