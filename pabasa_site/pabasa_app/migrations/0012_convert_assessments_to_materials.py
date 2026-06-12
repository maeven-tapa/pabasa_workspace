from django.db import migrations


def convert_assessments_to_materials(apps, schema_editor):
    import re
    from django.db import transaction
    from django.db.models import Max

    Assessment = apps.get_model('pabasa_app', 'Assessment')
    Material = apps.get_model('pabasa_app', 'Material')

    for asm in Assessment.objects.filter(section__isnull=False):
        # Skip if materials already linked to this assessment
        if Material.objects.filter(assessment_id=asm.id).exists():
            continue

        content = (asm.content or '').strip()
        if not content:
            continue

        if asm.assessment_type == 'word':
            tokens = re.findall(r"\b[\w']+\b", content, flags=re.UNICODE)
        elif asm.assessment_type == 'sentence':
            tokens = [s.strip() for s in re.split(r'(?<=[.!?])\s+', content) if s.strip()]
        elif asm.assessment_type == 'paragraph':
            tokens = [p.strip() for p in re.split(r'\n{2,}', content) if p.strip()]
        else:
            tokens = [content]

        if not tokens:
            continue

        # compute starting index for this section+type
        max_idx = Material.objects.filter(section_id=asm.section_id, item_type=asm.assessment_type).aggregate(m=Max('order_index'))['m'] or 0
        next_index = int(max_idx) + 1

        with transaction.atomic():
            for token in tokens:
                Material.objects.create(
                    assessment_id=asm.id,
                    section_id=asm.section_id,
                    item_type=asm.assessment_type,
                    prompt_text=token,
                    order_index=next_index,
                    expected_answer=None,
                    difficulty_level='',
                    audio_url=None,
                    is_active=asm.is_active,
                )
                next_index += 1


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0011_change_material_constraint_and_ordering'),
    ]

    operations = [
        migrations.RunPython(convert_assessments_to_materials, reverse_code=migrations.RunPython.noop),
    ]
