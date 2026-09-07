from django.db import migrations
from django.db.models import Q


OFFICIAL_CRLA_KEYS = (
    "bosy_crla_pretest",
    "midline_crla_midtest",
    "eosy_crla_posttest",
)


def _profile_input(score_data):
    data = score_data if isinstance(score_data, dict) else {}
    part1_total = data.get("part1_total_score")
    if part1_total in (None, ""):
        task1 = data.get("task1_score", data.get("task1_correct_words"))
        task2 = data.get("task2_score")
        try:
            task1 = int(task1)
            task2 = int(task2)
        except (TypeError, ValueError):
            task1 = task2 = None
        if task1 is not None and task2 is not None:
            # Task 2H stores completed sentences; Column H uses 0/3/5/7/10.
            if "h" in str(data.get("task2_type") or "").lower():
                task2 = (0, 3, 5, 7, 10)[max(0, min(4, int(data.get("sentences_read", task2) or 0)))]
            part1_total = task1 + task2
    return (
        part1_total,
        data.get("story_number"),
        data.get("passage_accuracy_percent", data.get("story_read_percent")),
        data.get("comprehension_correct", data.get("correct_answers")),
    )


def backfill_final_crla_profiles(apps, schema_editor):
    # Import the one canonical Column-U implementation rather than preserving
    # a second scoring rule in this migration.
    from pabasa_app.scoring import crla_reading_profile

    Assessment = apps.get_model("pabasa_app", "Assessment")
    candidates = Assessment.objects.filter(
        student__isnull=False,
        attempt_status="completed",
        completed_at__isnull=False,
    ).filter(
        Q(source_assessment__system_assessment_key__in=OFFICIAL_CRLA_KEYS)
        | Q(material__assessment_kind="crla", material__is_official_reading=True)
    )
    for attempt in candidates.iterator():
        profile = crla_reading_profile(*_profile_input(attempt.crla_score_data))
        if profile and attempt.crla_classification != profile:
            Assessment.objects.filter(pk=attempt.pk).update(crla_classification=profile)


class Migration(migrations.Migration):
    dependencies = [("pabasa_app", "0107_activitylog")]

    operations = [
        migrations.RunPython(backfill_final_crla_profiles, migrations.RunPython.noop),
    ]
