from django.db import migrations, models


def copy_enrollments_to_section_students(apps, schema_editor):
    Section = apps.get_model("pabasa_app", "Section")
    Enrollment = apps.get_model("pabasa_app", "Enrollment")

    section_students = {}
    enrollments = Enrollment.objects.select_related("student", "section").iterator()
    for enrollment in enrollments:
        student = enrollment.student
        section_students.setdefault(enrollment.section_id, []).append(
            {
                "student_id": student.id,
                "custom_id": student.custom_id,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "email": student.email,
                "joined_at": enrollment.joined_at.isoformat() if enrollment.joined_at else None,
                "is_active": enrollment.is_active,
            }
        )

    for section_id, students in section_students.items():
        Section.objects.filter(id=section_id).update(students=students)


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0005_user_section_enrollment_model_update"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="section",
            name="students",
        ),
        migrations.AddField(
            model_name="section",
            name="students",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(copy_enrollments_to_section_students, migrations.RunPython.noop),
        migrations.DeleteModel(
            name="Enrollment",
        ),
    ]
