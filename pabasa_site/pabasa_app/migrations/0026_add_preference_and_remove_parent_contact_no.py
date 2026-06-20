from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0025_material_assigned_week_integer'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='preference',
            field=models.JSONField(default=dict, blank=True),
        ),
        migrations.RemoveField(
            model_name='user',
            name='parent_contact_no',
        ),
    ]
