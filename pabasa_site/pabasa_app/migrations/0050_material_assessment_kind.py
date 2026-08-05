from django.db import migrations, models


def set_existing_materials_regular(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    Material.objects.filter(assessment_kind__isnull=True).update(assessment_kind='regular')


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0049_assessmentwindowsetting_material_assessment_set'),
    ]

    operations = [
        migrations.AddField(
            model_name='material',
            name='assessment_kind',
            field=models.CharField(choices=[('regular', 'Regular Reading Material'), ('crla', 'CRLA Assessment')], default='regular', max_length=20),
        ),
        migrations.RunPython(set_existing_materials_regular, migrations.RunPython.noop),
    ]
