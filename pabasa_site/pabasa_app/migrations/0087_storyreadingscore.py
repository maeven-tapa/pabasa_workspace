from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pabasa_app", "0086_storyreadingplayerprogress")]

    operations = [
        migrations.AddField(
            model_name="storyreadingprogress",
            name="correct_sentences",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="storyreadingprogress",
            name="reading_score",
            field=models.FloatField(default=0),
        ),
    ]