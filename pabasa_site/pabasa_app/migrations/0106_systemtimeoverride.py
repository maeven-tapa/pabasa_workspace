from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0105_liveassessmentsession_state_version')]

    operations = [
        migrations.CreateModel(
            name='SystemTimeOverride',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ('enabled', models.BooleanField(default=False)),
                ('reference_time', models.DateTimeField(blank=True, null=True)),
                ('configured_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={'db_table': 'system_time_override'},
        ),
    ]
