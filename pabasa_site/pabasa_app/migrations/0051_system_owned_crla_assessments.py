from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0050_material_assessment_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="assessment",
            name="is_system_owned",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="assessment",
            name="system_assessment_key",
            field=models.CharField(blank=True, choices=[("", "Teacher Owned"), ("bosy_crla_pretest", "BoSY CRLA Pre-Test"), ("eosy_crla_posttest", "EoSY CRLA Post-Test")], default="", max_length=40),
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
        migrations.AddField(
            model_name="material",
            name="is_system_owned",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="material",
            name="system_assessment_key",
            field=models.CharField(blank=True, default=None, max_length=40, null=True),
        ),
        migrations.AlterField(
            model_name="material",
            name="system_assessment_key",
            field=models.CharField(blank=True, default=None, max_length=40, null=True, unique=True),
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
    ]
