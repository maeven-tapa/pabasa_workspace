from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0071_school_and_school_scoped_sections"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="section",
            name="unique_canonical_grade_section",
        ),
    ]
