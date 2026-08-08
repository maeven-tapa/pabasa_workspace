# Generated manually to align the override request model with link-based supporting documentation.

import json
from django.db import migrations, models


def _convert_supporting_documentation(apps, schema_editor):
    OverrideRequest = apps.get_model('pabasa_app', 'OfficialReadingIntegrityOverrideRequest')
    with schema_editor.connection.cursor() as cursor:
        for request in OverrideRequest.objects.all().only('id', 'supporting_documentation'):
            value = request.supporting_documentation
            if isinstance(value, list):
                json_value = json.dumps(value)
            elif value in (None, ''):
                json_value = json.dumps([])
            else:
                json_value = json.dumps([str(value).strip()])
            safe_json = json_value.replace("'", "''")
            cursor.execute(
                f"UPDATE official_reading_integrity_override_requests SET supporting_documentation = '{safe_json}' WHERE id = {request.id}"
            )


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0058_official_reading_integrity_override_workflow'),
    ]

    operations = [
        migrations.RunPython(_convert_supporting_documentation, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='officialreadingintegrityoverriderequest',
            name='supporting_documentation',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
