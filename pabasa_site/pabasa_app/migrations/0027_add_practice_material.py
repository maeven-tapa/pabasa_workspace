from django.db import migrations, models


def _create_practice_materials(apps, schema_editor):
    Practice = apps.get_model('pabasa_app', 'Practice')
    Material = apps.get_model('pabasa_app', 'Material')

    for practice in Practice.objects.all():
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


def _remove_practice_materials(apps, schema_editor):
    Practice = apps.get_model('pabasa_app', 'Practice')

    for practice in Practice.objects.filter(material__isnull=False):
        practice.material = None
        practice.save(update_fields=['material'])


class Migration(migrations.Migration):
    dependencies = [
        ('pabasa_app', '0026_add_preference_and_remove_parent_contact_no'),
    ]

    operations = [
        migrations.AddField(
            model_name='practice',
            name='material',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name='practice_result',
                to='pabasa_app.Material',
            ),
        ),
        migrations.RunPython(_create_practice_materials, _remove_practice_materials),
    ]
