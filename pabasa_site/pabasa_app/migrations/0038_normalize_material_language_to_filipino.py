from django.db import migrations


def normalize_material_language_to_filipino(apps, schema_editor):
    Material = apps.get_model("pabasa_app", "Material")

    for material in Material.objects.all():
        content_json = material.content_json or {}
        if not isinstance(content_json, dict):
            continue

        updated = False
        normalized_content_json = dict(content_json)
        for key in ("language", "language_context", "languageContext"):
            value = normalized_content_json.get(key)
            if not isinstance(value, str):
                continue

            text = value.strip()
            lowered = text.lower()
            if lowered in {"tagalog", "tl", "tag", "tagalog language"}:
                normalized_content_json[key] = "Filipino"
                updated = True
            elif lowered in {"filipino", "fil", "filipina", "filipino language"}:
                normalized_content_json[key] = "Filipino"
                updated = True

        if updated:
            material.content_json = normalized_content_json
            material.save(update_fields=["content_json", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("pabasa_app", "0037_sync_user_theme_shop_columns"),
    ]

    operations = [
        migrations.RunPython(normalize_material_language_to_filipino, migrations.RunPython.noop),
    ]
