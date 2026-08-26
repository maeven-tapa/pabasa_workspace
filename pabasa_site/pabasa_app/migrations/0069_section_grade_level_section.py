from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pabasa_app", "0068_assessment_official_term")]
    operations = [
        migrations.AddField(model_name="section", name="grade_level", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="section", name="section", field=models.CharField(blank=True, max_length=50)),
    ]
