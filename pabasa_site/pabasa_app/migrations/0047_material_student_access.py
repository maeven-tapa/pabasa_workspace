from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0046_material_language"),
    ]

    operations = [
        migrations.AddField(
            model_name="material",
            name="student_access",
            field=models.BooleanField(default=False),
        ),
    ]
