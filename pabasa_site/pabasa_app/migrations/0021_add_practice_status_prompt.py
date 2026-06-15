# Generated migration to add status and prompt_text to Practice
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0020_add_assigned_week'),
    ]

    operations = [
        migrations.AddField(
            model_name='practice',
            name='prompt_text',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='practice',
            name='status',
            field=models.CharField(choices=[('published', 'Published'), ('draft', 'Draft'), ('scheduled', 'Scheduled')], default='published', max_length=20),
        ),
    ]
