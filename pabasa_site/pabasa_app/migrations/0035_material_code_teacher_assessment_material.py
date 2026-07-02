import uuid

import django.db.models.deletion
from django.db import migrations, models


def _material_code(Material, preferred=None):
    base = (preferred or "").strip()
    if base and not Material.objects.filter(code=base).exists():
        return base
    candidate = "MAT" + uuid.uuid4().hex[:8].upper()
    while Material.objects.filter(code=candidate).exists():
        candidate = "MAT" + uuid.uuid4().hex[:8].upper()
    return candidate


def populate_material_metadata(apps, schema_editor):
    Material = apps.get_model("pabasa_app", "Material")
    Assessment = apps.get_model("pabasa_app", "Assessment")

    for material in Material.objects.select_related("assessment", "section").all().iterator():
        preferred_code = ""
        teacher_id = None
        if material.assessment_id:
            try:
                preferred_code = material.assessment.code
                teacher_id = material.assessment.teacher_id
            except Assessment.DoesNotExist:
                pass
        if teacher_id is None and material.section_id:
            teacher_id = material.section.teacher_id

        updates = {}
        if not material.code:
            updates["code"] = _material_code(Material, preferred_code)
        if material.teacher_id is None and teacher_id is not None:
            updates["teacher_id"] = teacher_id
        if updates:
            Material.objects.filter(pk=material.pk).update(**updates)

    for assessment in Assessment.objects.filter(material__isnull=True).iterator():
        parent_id = assessment.source_assessment_id or assessment.id
        material = Material.objects.filter(assessment_id=parent_id).order_by("id").first()
        if material:
            Assessment.objects.filter(pk=assessment.pk).update(material_id=material.id)


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0034_remove_assessment_attempt_history_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="material",
            name="code",
            field=models.CharField(blank=True, max_length=30, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="material",
            name="teacher",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="materials", to="pabasa_app.user"),
        ),
        migrations.AddField(
            model_name="assessment",
            name="material",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assessment_results", to="pabasa_app.material"),
        ),
        migrations.RunPython(populate_material_metadata, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="material",
            name="code",
            field=models.CharField(blank=True, default="", max_length=30, unique=True),
        ),
    ]
