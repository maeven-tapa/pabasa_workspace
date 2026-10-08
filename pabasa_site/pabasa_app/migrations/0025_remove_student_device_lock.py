from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('pabasa_app', '0024_remove_session_timeout_fields'),
    ]

    operations = [
        migrations.RemoveField(model_name='user', name='active_session_key'),
        migrations.RemoveField(model_name='user', name='active_session_created_at'),
    ]
