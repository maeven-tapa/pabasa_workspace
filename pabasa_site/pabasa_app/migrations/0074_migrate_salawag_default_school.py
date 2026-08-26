from django.db import migrations


SALAWAG_NAME = "Salawag Elementary School"
LEGACY_DEFAULT_NAME = "Default School"


def forwards(apps, schema_editor):
    School = apps.get_model("pabasa_app", "School")
    Section = apps.get_model("pabasa_app", "Section")
    User = apps.get_model("pabasa_app", "User")
    Enrollment = apps.get_model("pabasa_app", "Enrollment")
    Material = apps.get_model("pabasa_app", "Material")
    Assessment = apps.get_model("pabasa_app", "Assessment")

    salawag = School.objects.filter(name=SALAWAG_NAME).first()
    if not salawag:
        salawag = School.objects.create(
            name=SALAWAG_NAME,
            code="SALAWAG-ES",
            status="active",
            is_active=True,
        )

    default_school = School.objects.filter(name=LEGACY_DEFAULT_NAME).first()
    if not default_school:
        return

    clearly_salawag_sections = set(
        Section.objects.filter(school=default_school, teacher_id__isnull=False).values_list("id", flat=True)
    )
    clearly_salawag_sections.update(
        Enrollment.objects.filter(section__school=default_school, is_active=True)
        .values_list("section_id", flat=True)
    )
    clearly_salawag_sections.update(
        Material.objects.filter(section__school=default_school, section__isnull=False)
        .values_list("section_id", flat=True)
    )
    clearly_salawag_sections.update(
        Assessment.objects.filter(section__school=default_school, section__isnull=False)
        .values_list("section_id", flat=True)
    )

    clearly_salawag_sections.discard(None)

    migrated_sections = Section.objects.filter(id__in=clearly_salawag_sections, school=default_school)
    migrated_section_ids = list(migrated_sections.values_list("id", flat=True))
    migrated_sections.update(school=salawag)

    migrated_teacher_ids = set(
        Section.objects.filter(id__in=migrated_section_ids, teacher_id__isnull=False).values_list("teacher_id", flat=True)
    )
    migrated_student_ids = set(
        Enrollment.objects.filter(section_id__in=migrated_section_ids).values_list("student_id", flat=True)
    )

    migrated_user_ids = migrated_teacher_ids | migrated_student_ids
    migrated_user_ids.update(
        User.objects.filter(school__iexact=SALAWAG_NAME).values_list("id", flat=True)
    )

    for user in User.objects.filter(id__in=migrated_user_ids):
        updates = []
        if user.school_record_id != salawag.id:
            user.school_record_id = salawag.id
            updates.append("school_record")
        if user.school != SALAWAG_NAME:
            user.school = SALAWAG_NAME
            updates.append("school")
        if updates:
            user.save(update_fields=updates)

    # Leave ambiguous Default School sections untouched so we do not guess
    # ownership for any rows that lack direct Salawag evidence.


def backwards(apps, schema_editor):
    School = apps.get_model("pabasa_app", "School")
    Section = apps.get_model("pabasa_app", "Section")
    User = apps.get_model("pabasa_app", "User")

    salawag = School.objects.filter(name=SALAWAG_NAME).first()
    default_school = School.objects.filter(name=LEGACY_DEFAULT_NAME).first()
    if not salawag or not default_school:
        return

    Section.objects.filter(school=salawag).update(school=default_school)
    User.objects.filter(school_record=salawag).update(school_record=default_school)


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0073_user_school_record"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
