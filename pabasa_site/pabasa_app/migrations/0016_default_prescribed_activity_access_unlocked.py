from django.db import migrations, models


def enable_unlock_all_for_existing_settings(apps, schema_editor):
    Settings = apps.get_model('pabasa_app', 'PrescribedActivityAccessSettings')
    Settings.objects.filter(pk=1).update(unlock_all_activities=True)


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0015_prescribed_activity_access_settings')]

    operations = [
        migrations.AlterField(
            model_name='prescribedactivityaccesssettings',
            name='unlock_all_activities',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(enable_unlock_all_for_existing_settings, migrations.RunPython.noop),
    ]
