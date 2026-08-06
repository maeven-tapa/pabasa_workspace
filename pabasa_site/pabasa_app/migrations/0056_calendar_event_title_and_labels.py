from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0055_remove_assessmentwindowsetting_active_window_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendarevent',
            name='title',
            field=models.CharField(
                max_length=150,
                default='',
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='calendarevent',
            name='event_type',
            field=models.CharField(
                max_length=30,
                choices=[
                    ('school_opening', 'School Opening'),
                    ('school_closing', 'School Closing'),
                    ('pre_assessment', 'Pre-Assessment Week'),
                    ('post_assessment', 'Post-Assessment Week'),
                    ('holiday', 'Holiday'),
                    ('examination', 'Examination Week'),
                    ('other', 'Other Activity'),
                ],
            ),
        ),
    ]