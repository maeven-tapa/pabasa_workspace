from django.db import migrations


OFFICIAL_CRLA_TERMS = {
    "bosy_crla_pretest": 1,
    "midline_crla_midtest": 2,
    "eosy_crla_posttest": 3,
}


def backfill_official_crla_terms(apps, schema_editor):
    Material = apps.get_model("pabasa_app", "Material")
    for assessment_key, term in OFFICIAL_CRLA_TERMS.items():
        Material.objects.filter(
            system_assessment_key=assessment_key,
            is_official_reading=True,
        ).update(official_term=term)


def clear_official_crla_terms(apps, schema_editor):
    Material = apps.get_model("pabasa_app", "Material")
    Material.objects.filter(
        system_assessment_key__in=OFFICIAL_CRLA_TERMS,
        is_official_reading=True,
    ).update(official_term=None)


class Migration(migrations.Migration):
    dependencies = [
        ("pabasa_app", "0066_backfill_official_crla_story_qas"),
    ]

    operations = [
        migrations.RunPython(backfill_official_crla_terms, clear_official_crla_terms),
    ]
