from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0099_liveassessmentsession_batches')]

    operations = [
        migrations.AddField(
            model_name='user', name='active_session_key',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='user', name='active_session_created_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user', name='last_activity',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='assessment', name='attempt_session_key',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
    ]
