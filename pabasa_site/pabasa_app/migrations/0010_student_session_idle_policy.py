from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0009_activityrecordingreviewstate')]
    operations = [
        migrations.AddField(
            model_name='user', name='active_session_last_seen',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='user', name='active_session_learning',
            field=models.BooleanField(default=False),
        ),
    ]
