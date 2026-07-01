from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0027_add_practice_material'),
    ]

    operations = [
        migrations.AddField(
            model_name='material',
            name='source_type',
            field=models.CharField(
                choices=[('personal', 'Personal'), ('shared', 'Shared')],
                default='personal',
                max_length=20,
            ),
        ),
    ]
