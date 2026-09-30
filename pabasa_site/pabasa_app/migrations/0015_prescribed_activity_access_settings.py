from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0014_recording_substep')]
    operations = [migrations.CreateModel(name='PrescribedActivityAccessSettings', fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('unlock_all_activities', models.BooleanField(default=False)),
        ('updated_at', models.DateTimeField(auto_now=True)),
    ], options={'db_table': 'prescribed_activity_access_settings'})]
