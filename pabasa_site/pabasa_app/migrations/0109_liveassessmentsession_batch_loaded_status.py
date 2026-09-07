from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0108_backfill_crla_reading_profile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='liveassessmentsession',
            name='status',
            field=models.CharField(
                choices=[
                    ('waiting', 'Waiting'),
                    ('batch_loaded', 'Batch Loaded'),
                    ('countdown', 'Countdown'),
                    ('started', 'Started'),
                    ('paused', 'Paused'),
                    ('ended', 'Ended'),
                    ('cancelled', 'Cancelled'),
                ],
                default='waiting',
                max_length=20,
            ),
        ),
    ]
