from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pabasa_app", "0085_storyreadingprogress")]

    operations = [
        migrations.AddField(model_name="storyreadingprogress", name="story_key", field=models.CharField(blank=True, default="", max_length=100)),
        migrations.AddField(model_name="storyreadingprogress", name="current_scene", field=models.PositiveSmallIntegerField(default=1)),
        migrations.AddField(model_name="storyreadingprogress", name="current_time_seconds", field=models.FloatField(default=0)),
    ]