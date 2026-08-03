from django.db import migrations, models


def backfill_practice_language(apps, schema_editor):
    Material = apps.get_model("pabasa_app", "Material")
    Material.objects.filter(type="practice").update(language="English")


class Migration(migrations.Migration):
    dependencies = [
        ("pabasa_app", "0045_user_lrn"),
    ]

    operations = [
        migrations.AddField(
            model_name="material",
            name="language",
            field=models.CharField(blank=True, default="English", max_length=20),
        ),
        migrations.RunPython(backfill_practice_language, migrations.RunPython.noop),
    ]
