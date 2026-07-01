from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0026_add_preference_and_remove_parent_contact_no'),
    ]

    operations = [
        migrations.AddField(
            model_name='material',
            name='source_type',
            field=models.CharField(choices=[('personal', 'Personal'), ('shared', 'Shared')], default='personal', max_length=20),
        ),
    ]