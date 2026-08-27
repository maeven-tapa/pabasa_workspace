from django.db import migrations


def classify_known_admin_practice(apps, schema_editor):
    Material = apps.get_model("pabasa_app", "Material")
    Material.objects.filter(
        id=5,
        title="Free Easy Level 1",
        type="practice",
        section__isnull=True,
        teacher__isnull=True,
        source_type="personal",
        is_system_owned=False,
        difficulty_level="easy",
        language="English",
        content_json__mode="free",
        content_json__difficulty="easy",
        content_json__level="level_1",
    ).update(is_system_owned=True, source_type="shared")


class Migration(migrations.Migration):
    dependencies = [("pabasa_app", "0083_course_school")]

    operations = [
        migrations.RunPython(classify_known_admin_practice, migrations.RunPython.noop),
    ]
