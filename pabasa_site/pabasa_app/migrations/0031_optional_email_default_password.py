from django.db import migrations, models
import pabasa_app.account_defaults


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0030_otp_debug_settings')]

    operations = [
        migrations.AlterField(
            model_name='user', name='email',
            field=models.EmailField(blank=True, max_length=254, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='user', name='password_hash',
            field=models.CharField(default=pabasa_app.account_defaults.default_new_account_password_hash, max_length=255),
        ),
    ]
