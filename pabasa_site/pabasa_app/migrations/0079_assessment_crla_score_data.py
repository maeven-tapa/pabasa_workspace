from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pabasa_app", "0078_user_must_change_password")]

    operations = [
        migrations.AddField(
            model_name="assessment",
            name="crla_score_data",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
