from django.core.validators import RegexValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pabasa_app", "0044_alter_liveassessmentsession_status_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="lrn",
            field=models.CharField(
                blank=True,
                max_length=12,
                null=True,
                unique=True,
                validators=[RegexValidator(regex=r"^\d{12}$", message="LRN must contain exactly 12 digits.")],
                verbose_name="Learner Reference Number",
            ),
        ),
    ]
