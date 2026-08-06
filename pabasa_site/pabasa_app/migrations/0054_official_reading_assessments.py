# Generated manually because the local Django command runner is missing an installed dependency.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0053_schoolcalendar_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='material',
            name='status',
            field=models.CharField(choices=[('published', 'Published'), ('draft', 'Draft'), ('archived', 'Archived'), ('scheduled', 'Scheduled')], default='published', max_length=20),
        ),
        migrations.AddField(
            model_name='material',
            name='is_official_reading',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='material',
            name='official_term',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='material',
            name='official_pdf',
            field=models.FileField(blank=True, null=True, upload_to='official_readings/'),
        ),
    ]
