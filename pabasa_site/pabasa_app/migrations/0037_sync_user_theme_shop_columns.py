from django.db import migrations, models

import pabasa_app.models


def add_missing_user_theme_columns(apps, schema_editor):
    User = apps.get_model("pabasa_app", "User")
    table_name = User._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(
                cursor,
                table_name,
            )
        }

    fields = [
        ("available_stars", models.PositiveIntegerField(default=0)),
        ("theme_stars_credited", models.PositiveIntegerField(default=0)),
        (
            "unlocked_themes",
            models.JSONField(
                blank=True,
                default=pabasa_app.models.default_unlocked_themes,
            ),
        ),
        ("equipped_theme", models.CharField(default="sky", max_length=30)),
    ]

    for name, field in fields:
        if name in existing_columns:
            continue

        field.set_attributes_from_name(name)
        schema_editor.add_field(User, field)


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0036_user_theme_shop_fields"),
    ]

    operations = [
        migrations.RunPython(
            add_missing_user_theme_columns,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
