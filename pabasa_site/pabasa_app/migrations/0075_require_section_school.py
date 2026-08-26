from django.core.exceptions import ValidationError
from django.db import migrations, models
import django.db.models.deletion


def reject_unowned_sections(apps, schema_editor):
    Section = apps.get_model("pabasa_app", "Section")
    if Section.objects.filter(school_id__isnull=True).exists():
        raise ValidationError(
            "Cannot require Section.school while unowned Sections still exist. "
            "Assign each Section to a School explicitly first."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("pabasa_app", "0074_migrate_salawag_default_school"),
    ]

    operations = [
        migrations.RunPython(reject_unowned_sections, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="section",
            name="school",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="sections",
                to="pabasa_app.school",
            ),
        ),
    ]
