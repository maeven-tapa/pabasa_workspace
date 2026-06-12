from django.db import migrations, models


def renumber_material_order(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    # Get distinct (section_id, item_type) pairs
    pairs = Material.objects.values('section_id', 'item_type').distinct()
    for pair in pairs:
        sec_id = pair['section_id']
        itype = pair['item_type']
        qs = Material.objects.filter(section_id=sec_id, item_type=itype).order_by('created_at', 'id')
        idx = 1
        for m in qs:
            if m.order_index != idx:
                m.order_index = idx
                m.save(update_fields=['order_index'])
            idx += 1


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0010_make_material_created_at_aware'),
    ]

    operations = [
        migrations.RunPython(renumber_material_order, reverse_code=migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='material',
            name='unique_assessment_item_order',
        ),
        migrations.AddConstraint(
            model_name='material',
            constraint=models.UniqueConstraint(fields=['section', 'item_type', 'order_index'], name='unique_section_item_order'),
        ),
        migrations.AlterModelOptions(
            name='material',
            options={'ordering': ['section', 'order_index'], 'db_table': 'materials'},
        ),
    ]
