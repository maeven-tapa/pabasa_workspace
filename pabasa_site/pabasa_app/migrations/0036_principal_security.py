from django.db import migrations, models
import django.db.models.deletion


def scope_existing_notifications(apps, schema_editor):
    Notification = apps.get_model('pabasa_app', 'Notification')
    # Only infer provable ownership. Unknown/global legacy Principal notices
    # stay unscoped and are quarantined by Principal readers, never broadcast.
    for notice in Notification.objects.filter(recipient__role='principal').select_related('created_by', 'recipient').iterator():
        actor_school = getattr(notice.created_by, 'school_record_id', None)
        if actor_school and actor_school == notice.recipient.school_record_id:
            Notification.objects.filter(pk=notice.pk).update(school_id=actor_school)


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0035_lesson29_recording_scope')]
    operations = [
        migrations.AddField(model_name='user', name='principal_password_expires_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='notification', name='school', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='pabasa_app.school')),
        migrations.RunPython(scope_existing_notifications, migrations.RunPython.noop),
    ]
