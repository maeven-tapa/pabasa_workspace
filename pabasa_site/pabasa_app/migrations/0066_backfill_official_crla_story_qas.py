from django.db import migrations


def backfill_official_crla_story_qas(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')

    try:
        from pabasa_app.management.commands.seed_official_crla_assessments import OFFICIAL_CRLA_CONTENT
    except Exception:
        OFFICIAL_CRLA_CONTENT = {}

    if not OFFICIAL_CRLA_CONTENT:
        return

    seed_by_key = {}
    for key, payload in OFFICIAL_CRLA_CONTENT.items():
        story_qas = []
        for item in payload.get('story_qas') or []:
            if not isinstance(item, dict):
                continue
            story_title = str(item.get('story_title') or '').strip()
            question = str(item.get('question') or '').strip()
            answer = str(item.get('answer') or '').strip()
            if story_title and question and answer:
                story_qas.append({
                    'story_title': story_title,
                    'question': question,
                    'answer': answer,
                })
        seed_by_key[key] = story_qas

    for material in Material.objects.filter(is_official_reading=True):
        content_json = material.content_json or {}
        if not isinstance(content_json, dict):
            continue
        if content_json.get('story_qas'):
            continue
        assessment_key = str(content_json.get('assessment_key') or getattr(material, 'system_assessment_key', '') or '').strip().lower()
        story_qas = seed_by_key.get(assessment_key)
        if not story_qas:
            continue
        updated_content_json = dict(content_json)
        updated_content_json['story_qas'] = story_qas
        material.content_json = updated_content_json
        material.save(update_fields=['content_json', 'updated_at'])


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0065_remove_preadded_accounts'),
    ]

    operations = [
        migrations.RunPython(backfill_official_crla_story_qas, noop_reverse),
    ]
