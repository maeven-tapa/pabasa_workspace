# Generated manually because the local Django command runner is unavailable in this environment.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0059_supporting_documentation_links_json'),
    ]

    operations = [
        migrations.CreateModel(
            name='OfficialReadingOverrideSecurityLockout',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('failed_attempt_count', models.PositiveSmallIntegerField(default=0)),
                ('last_failed_at', models.DateTimeField(blank=True, null=True)),
                ('lockout_expires_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('audit_payload', models.JSONField(blank=True, default=dict)),
                ('reviewer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='official_override_security_lockout', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'official_reading_override_security_lockouts',
            },
        ),
    ]
