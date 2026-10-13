from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0031_optional_email_default_password')]

    operations = [
        migrations.AlterField(
            model_name='user', name='password_hash',
            field=models.CharField(max_length=255),
        ),
    ]
