from django.db import migrations


def create_practice_materials(apps, schema_editor):
    Practice = apps.get_model('pabasa_app', 'Practice')
    Material = apps.get_model('pabasa_app', 'Material')

    for practice in Practice.objects.filter(material__isnull=True):
        material = Material.objects.create(
            title=practice.title or '',
            item_type=practice.practice_type or 'word',
            prompt_text=practice.prompt_text or '',
            content_text=practice.contents or '',
            content_json={},
            type='practice',
            status=practice.status or 'draft',
            difficulty_level=practice.difficulty_type or '',
            section=practice.section,
            is_active=practice.is_active,
        )
        practice.material = material
        practice.save(update_fields=['material'])


class Migration(migrations.Migration):
    dependencies = [
        ('pabasa_app', '0028_add_material_source_type'),
    ]

    operations = [
        migrations.RunPython(create_practice_materials, reverse_code=migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='practice',
            name='practice_type',
        ),
        migrations.RemoveField(
            model_name='practice',
            name='difficulty_type',
        ),
        migrations.RemoveField(
            model_name='practice',
            name='contents',
        ),
        migrations.RemoveField(
            model_name='practice',
            name='prompt_text',
        ),
    ]
