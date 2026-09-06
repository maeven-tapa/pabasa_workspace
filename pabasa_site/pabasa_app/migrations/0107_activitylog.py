from django.db import migrations, models
import django.db.models.deletion
import pabasa_app.system_clock


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0106_systemtimeoverride')]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('notification', 'Notification'), ('system_time_debug', 'System Time Debug')], max_length=32)),
                ('title', models.CharField(max_length=150)),
                ('message', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(db_index=True, default=pabasa_app.system_clock.real_now, editable=False)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='activity_log_entries', to='pabasa_app.user')),
            ],
            options={'db_table': 'activity_logs', 'ordering': ['-created_at', '-id']},
        ),
    ]
