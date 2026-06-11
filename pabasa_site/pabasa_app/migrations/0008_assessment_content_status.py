# Generated migration for Assessment model: add content, status, scheduled_at fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0007_user_teacher_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='assessment',
            name='content',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='assessment',
            name='status',
            field=models.CharField(
                choices=[('published', 'Published'), ('draft', 'Draft'), ('scheduled', 'Scheduled')],
                default='published',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='assessment',
            name='scheduled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
