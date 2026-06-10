# Generated manually to bridge the profile/class schema to the unified User schema.

import django.db.models.deletion
from django.db import migrations, models


def _append_profile_tag(user, key, profile_data):
    tags = user.tags or []
    if not isinstance(tags, list):
        tags = [tags]

    for index, entry in enumerate(tags):
        if isinstance(entry, dict) and key in entry:
            tags[index] = {key: profile_data}
            break
    else:
        tags.append({key: profile_data})

    user.tags = tags
    user.save(update_fields=["tags"])


def copy_profiles_to_users(apps, schema_editor):
    User = apps.get_model("pabasa_app", "User")
    TeacherProfile = apps.get_model("pabasa_app", "TeacherProfile")
    StudentProfile = apps.get_model("pabasa_app", "StudentProfile")

    for profile in TeacherProfile.objects.select_related("user").iterator():
        _append_profile_tag(
            profile.user,
            "teacher_profile",
            {
                "teacher_code": profile.teacher_code,
                "teacher_role": profile.teacher_role,
                "school": profile.school,
                "department": profile.department,
                "is_active": profile.is_active,
            },
        )

    for profile in StudentProfile.objects.select_related("user").iterator():
        _append_profile_tag(
            profile.user,
            "student_profile",
            {
                "student_code": profile.student_code,
                "grade_level": profile.grade_level,
                "section": profile.section,
                "reading_level": profile.reading_level,
                "wpm": profile.wpm,
                "accuracy": str(profile.accuracy),
                "parent_contact_no": profile.parent_contact_no,
                "is_active": profile.is_active,
            },
        )

    # Keep static analysis quiet for historical apps import paths.
    User.objects.exists()


def repoint_profile_foreign_keys(apps, schema_editor):
    quoted = schema_editor.quote_name

    def update_fk(table, column, profile_table):
        schema_editor.execute(
            f"""
            UPDATE {quoted(table)}
            SET {quoted(column)} = (
                SELECT {quoted("user_id")}
                FROM {quoted(profile_table)}
                WHERE {quoted(profile_table)}.{quoted("id")} = {quoted(table)}.{quoted(column)}
            )
            WHERE {quoted(column)} IS NOT NULL
            """
        )

    update_fk("class_enrollments", "student_id", "student_profiles")
    update_fk("assessments", "teacher_id", "teacher_profiles")
    update_fk("teacher_notes", "teacher_id", "teacher_profiles")
    update_fk("teacher_notes", "student_id", "student_profiles")


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0004_user_middle_initial_user_suffix"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="profile_picture",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="tags",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(copy_profiles_to_users, migrations.RunPython.noop),
        migrations.DeleteModel(
            name="AssessmentResult",
        ),
        migrations.DeleteModel(
            name="AssessmentAttempt",
        ),
        migrations.AddField(
            model_name="assessment",
            name="attempts",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RenameModel(
            old_name="ReadingClass",
            new_name="Section",
        ),
        migrations.RenameModel(
            old_name="ClassEnrollment",
            new_name="Enrollment",
        ),
        migrations.RenameModel(
            old_name="AssessmentItem",
            new_name="Material",
        ),
        migrations.RenameModel(
            old_name="TeacherNote",
            new_name="Note",
        ),
        migrations.RemoveConstraint(
            model_name="enrollment",
            name="unique_student_class_enrollment",
        ),
        migrations.RenameField(
            model_name="assessment",
            old_name="reading_class",
            new_name="section",
        ),
        migrations.RenameField(
            model_name="enrollment",
            old_name="reading_class",
            new_name="section",
        ),
        migrations.RunPython(repoint_profile_foreign_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="section",
            name="teacher",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sections",
                to="pabasa_app.user",
            ),
        ),
        migrations.AlterField(
            model_name="enrollment",
            name="student",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="enrollments",
                to="pabasa_app.user",
            ),
        ),
        migrations.AlterField(
            model_name="enrollment",
            name="section",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="enrollments",
                to="pabasa_app.section",
            ),
        ),
        migrations.AlterField(
            model_name="assessment",
            name="teacher",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="assessments",
                to="pabasa_app.user",
            ),
        ),
        migrations.AlterField(
            model_name="assessment",
            name="section",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="assessments",
                to="pabasa_app.section",
            ),
        ),
        migrations.AlterField(
            model_name="note",
            name="teacher",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notes",
                to="pabasa_app.user",
            ),
        ),
        migrations.AlterField(
            model_name="note",
            name="student",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="teacher_notes",
                to="pabasa_app.user",
            ),
        ),
        migrations.AlterField(
            model_name="material",
            name="assessment",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="materials",
                to="pabasa_app.assessment",
            ),
        ),
        migrations.AddConstraint(
            model_name="enrollment",
            constraint=models.UniqueConstraint(
                fields=("student", "section"),
                name="unique_student_section_enrollment",
            ),
        ),
        migrations.AlterModelTable(
            name="section",
            table="sections",
        ),
        migrations.AlterModelTable(
            name="material",
            table="materials",
        ),
        migrations.AlterModelTable(
            name="note",
            table="notes",
        ),
        migrations.AlterModelOptions(
            name="section",
            options={"ordering": ["class_name"]},
        ),
        migrations.AlterModelOptions(
            name="enrollment",
            options={"ordering": ["-joined_at"]},
        ),
        migrations.AlterModelOptions(
            name="material",
            options={"ordering": ["assessment", "order_index"]},
        ),
        migrations.AlterModelOptions(
            name="note",
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddField(
            model_name="section",
            name="students",
            field=models.ManyToManyField(
                related_name="enrolled_sections",
                through="pabasa_app.Enrollment",
                to="pabasa_app.user",
            ),
        ),
        migrations.DeleteModel(
            name="TeacherProfile",
        ),
        migrations.DeleteModel(
            name="StudentProfile",
        ),
    ]
