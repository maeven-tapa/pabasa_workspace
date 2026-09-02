from django.db import migrations

from pabasa_app.section_configuration import SALAWAG_GRADE_TWO_SECTIONS


def seed_salawag_grade_two_sections(apps, schema_editor):
    School = apps.get_model("pabasa_app", "School")
    SchoolCalendar = apps.get_model("pabasa_app", "SchoolCalendar")
    Section = apps.get_model("pabasa_app", "Section")

    school, _ = School.objects.get_or_create(
        name="Salawag Elementary School",
        defaults={
            "code": "107912",
            "address": "4114 Paliparan Road Dasmariñas Calabarzon",
            "status": "active",
            "is_active": True,
        },
    )
    active_calendar = SchoolCalendar.objects.filter(is_active=True).order_by("-updated_at", "-created_at").first()
    if not active_calendar:
        return

    existing_names = {
        str(name).upper()
        for name in Section.objects.filter(
            school=school,
            school_calendar=active_calendar,
            grade_level__iexact="Grade 2",
        ).values_list("section", flat=True)
    }
    for position, name in enumerate(SALAWAG_GRADE_TWO_SECTIONS, start=1):
        if name in existing_names:
            continue
        Section.objects.create(
            school=school,
            school_calendar=active_calendar,
            class_code=f"SAL-G2-{position:02d}",
            class_name=f"Grade 2 - {name}",
            subject="Reading",
            grade_level="Grade 2",
            section=name,
            is_active=True,
        )


class Migration(migrations.Migration):
    dependencies = [("pabasa_app", "0092_school_year_learning_records")]

    operations = [migrations.RunPython(seed_salawag_grade_two_sections, migrations.RunPython.noop)]
