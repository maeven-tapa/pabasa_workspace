import django.db.models.deletion
from django.db import migrations, models
from django.db.models.functions import Lower


def prepare_canonical_sections_and_enrollments(apps, schema_editor):
    Section = apps.get_model("pabasa_app", "Section")
    Enrollment = apps.get_model("pabasa_app", "Enrollment")
    User = apps.get_model("pabasa_app", "User")

    # Normalize only the newly introduced canonical identity fields. Legacy rows
    # with no reliable Grade + Section mapping deliberately remain unclassified.
    claimed_identities = set()
    for section in Section.objects.order_by("id").iterator():
        grade_level = (section.grade_level or "").strip()
        section_name = (section.section or "").strip()
        identity = (grade_level.casefold(), section_name.casefold())
        if grade_level and section_name and identity in claimed_identities:
            # Preserve the complete legacy class row and every FK pointing at it.
            # Clearing only its untrusted canonical labels allows an admin to
            # resolve the collision explicitly without merging assessment data.
            grade_level = ""
            section_name = ""
        elif grade_level and section_name:
            claimed_identities.add(identity)
        Section.objects.filter(pk=section.pk).update(
            grade_level=grade_level,
            section=section_name,
        )

        entries = section.students if isinstance(section.students, list) else []
        seen_student_ids = set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            raw_student_id = entry.get("student_id")
            student = None
            if raw_student_id is not None:
                try:
                    student = User.objects.filter(pk=int(raw_student_id), role="student").first()
                except (TypeError, ValueError):
                    student = None
            if student is None and entry.get("custom_id"):
                student = User.objects.filter(custom_id=entry["custom_id"], role="student").first()
            if student is None or student.pk in seen_student_ids:
                continue
            seen_student_ids.add(student.pk)
            enrollment, _ = Enrollment.objects.get_or_create(
                student_id=student.pk,
                section_id=section.pk,
                defaults={"is_active": bool(entry.get("is_active", True))},
            )
            desired_active = bool(entry.get("is_active", True))
            if enrollment.is_active != desired_active:
                Enrollment.objects.filter(pk=enrollment.pk).update(is_active=desired_active)


class Migration(migrations.Migration):
    dependencies = [("pabasa_app", "0069_section_grade_level_section")]

    operations = [
        migrations.AlterField(
            model_name="section",
            name="teacher",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sections",
                to="pabasa_app.user",
            ),
        ),
        migrations.CreateModel(
            name="Enrollment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("is_active", models.BooleanField(default=True)),
                ("section", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="enrollments", to="pabasa_app.section")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="enrollments", to="pabasa_app.user")),
            ],
            options={"db_table": "class_enrollments", "ordering": ["-joined_at"]},
        ),
        migrations.AddConstraint(
            model_name="enrollment",
            constraint=models.UniqueConstraint(fields=("student", "section"), name="unique_student_section_enrollment"),
        ),
        migrations.RunPython(prepare_canonical_sections_and_enrollments, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="section",
            constraint=models.UniqueConstraint(
                Lower("grade_level"),
                Lower("section"),
                condition=models.Q(grade_level__gt="", section__gt=""),
                name="unique_canonical_grade_section",
            ),
        ),
    ]
