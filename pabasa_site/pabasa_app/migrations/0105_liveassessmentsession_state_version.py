from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0104_alter_section_assessment_week_enabled_not_null'),
    ]

    operations = [
        migrations.AddField(
            model_name='liveassessmentsession',
            name='state_version',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
