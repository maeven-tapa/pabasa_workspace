from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0098_mark_five_w_story_questions'),
    ]

    operations = [
        migrations.AddField(
            model_name='liveassessmentsession',
            name='batch_assignments',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='liveassessmentsession',
            name='batch_size',
            field=models.IntegerField(default=10),
        ),
        migrations.AddField(
            model_name='liveassessmentsession',
            name='current_batch',
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name='liveassessmentsession',
            name='total_batches',
            field=models.IntegerField(default=0),
        ),
    ]