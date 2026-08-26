from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("pabasa_app", "0075_require_section_school"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                fields=("school_record",),
                condition=Q(role="principal", is_archived=False, school_record__isnull=False),
                name="unique_active_principal_per_school",
            ),
        ),
    ]
