from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0019_remove_section_grade_level"),
    ]

    operations = [
        migrations.AddField(
            model_name='material',
            name='assigned_week',
            field=models.CharField(max_length=20, blank=True, default=''),
        ),
    ]
