from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0051_system_owned_crla_assessments"),
    ]

    operations = [
        migrations.AddField(
            model_name="assessmentwindowsetting",
            name="active_period",
            field=models.CharField(choices=[("bosy", "Beginning of School Year"), ("mosy", "Middle of School Year"), ("eosy", "End of School Year")], default="bosy", max_length=10),
        ),
        migrations.AddField(
            model_name="assessmentwindowsetting",
            name="active_phase",
            field=models.CharField(choices=[("pretest", "Pre-Test"), ("posttest", "Post-Test")], default="pretest", max_length=10),
        ),
        migrations.AddField(
            model_name="material",
            name="system_assessment_period",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="material",
            name="system_assessment_phase",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="assessment",
            name="system_assessment_period",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="assessment",
            name="system_assessment_phase",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
    ]
