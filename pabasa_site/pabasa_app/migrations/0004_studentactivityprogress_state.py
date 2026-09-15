from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0003_studentactivityprogress')]
    operations = [migrations.AddField(model_name='studentactivityprogress', name='state', field=models.JSONField(blank=True, default=dict))]
