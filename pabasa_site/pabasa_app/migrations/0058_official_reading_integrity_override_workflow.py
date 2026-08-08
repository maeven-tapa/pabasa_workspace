# Generated manually because the local Django command runner is unavailable in this environment.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0057_calendarevent_term'),
    ]

    operations = [
        migrations.CreateModel(
            name='OfficialReadingIntegrityOverrideRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_id', models.CharField(max_length=40, unique=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('expired', 'Expired'), ('used', 'Used')], default='pending', max_length=20)),
                ('deped_reference', models.TextField()),
                ('material_change', models.TextField()),
                ('justification', models.TextField()),
                ('supporting_documentation', models.TextField(blank=True, default='')),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_decision', models.CharField(blank=True, default='', max_length=20)),
                ('rejection_reason', models.TextField(blank=True, default='')),
                ('authorized_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('audit_payload', models.JSONField(blank=True, default=dict)),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='official_override_requests', to='pabasa_app.material')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='official_override_requests', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_official_override_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'official_reading_integrity_override_requests',
                'ordering': ['-submitted_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='OfficialReadingIntegrityAuthorization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('authorized_at', models.DateTimeField()),
                ('expires_at', models.DateTimeField()),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('audit_payload', models.JSONField(blank=True, default=dict)),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='official_integrity_authorizations', to='pabasa_app.material')),
                ('authorized_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='official_integrity_authorizations', to=settings.AUTH_USER_MODEL)),
                ('request', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='authorization', to='pabasa_app.officialreadingintegrityoverriderequest')),
            ],
            options={
                'db_table': 'official_reading_integrity_authorizations',
            },
        ),
    ]
