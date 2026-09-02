from django.db import migrations


def mark_five_w_materials(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    for material in Material.objects.filter(item_type='paragraph'):
        content = material.content_json if isinstance(material.content_json, dict) else {}
        template_values = {
            str(content.get(key) or '').strip().lower()
            for key in ('template_title', 'template_type', 'template_activity_name')
        }
        if "5w's story questions" not in template_values:
            continue
        if content.get('activity_variant') == 'five_w_story_questions':
            continue
        content['activity_variant'] = 'five_w_story_questions'
        material.content_json = content
        material.save(update_fields=['content_json'])


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0097_storyresponsesubmission')]
    operations = [migrations.RunPython(mark_five_w_materials, migrations.RunPython.noop)]
