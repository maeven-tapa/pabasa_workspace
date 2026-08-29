from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pabasa_app", "0087_storyreadingscore"),
    ]

    operations = [
        migrations.AddField(
            model_name="storyreadingprogress",
            name="correct_words",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="storyreadingprogress",
            name="miscues",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="storyreadingprogress",
            name="accuracy",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="storyreadingprogress",
            name="wpm",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="storyreadingprogress",
            name="word_alignment",
            field=models.JSONField(default=list, blank=True),
        ),
    ]
