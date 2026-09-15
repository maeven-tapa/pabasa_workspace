from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0002_practice_debug_settings')]
    operations = [
        migrations.CreateModel(
            name='StudentActivityProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activity_key', models.CharField(max_length=100)),
                ('current_index', models.PositiveIntegerField(default=0)),
                ('completed_items', models.PositiveIntegerField(default=0)),
                ('correct_items', models.PositiveIntegerField(default=0)),
                ('total_items', models.PositiveIntegerField(default=0)),
                ('activity_completed', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_progress', to='pabasa_app.user')),
            ],
            options={'db_table': 'student_activity_progress'},
        ),
        migrations.AddConstraint(
            model_name='studentactivityprogress',
            constraint=models.UniqueConstraint(fields=('student', 'activity_key'), name='unique_student_activity_progress'),
        ),
    ]
