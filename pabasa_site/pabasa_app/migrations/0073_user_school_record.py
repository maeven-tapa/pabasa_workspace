from django.db import migrations, models
import django.db.models.deletion


def backfill_user_schools(apps, schema_editor):
    User = apps.get_model("pabasa_app", "User")
    Section = apps.get_model("pabasa_app", "Section")
    Enrollment = apps.get_model("pabasa_app", "Enrollment")
    School = apps.get_model("pabasa_app", "School")

    for user in User.objects.filter(school_record__isnull=True):
        school_ids = set(
            Section.objects.filter(teacher_id=user.id, school__isnull=False)
            .values_list("school_id", flat=True)
        )
        school_ids.update(
            Enrollment.objects.filter(student_id=user.id, section__school__isnull=False)
            .values_list("section__school_id", flat=True)
        )
        if len(school_ids) == 1:
            user.school_record_id = next(iter(school_ids))
            user.save(update_fields=["school_record"])
            continue

        legacy_name = (user.school or "").strip()
        if legacy_name:
            matches = list(School.objects.filter(name__iexact=legacy_name).values_list("id", flat=True)[:2])
            if len(matches) == 1:
                user.school_record_id = matches[0]
                user.save(update_fields=["school_record"])


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0072_remove_global_section_uniqueness"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="school_record",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="users",
                to="pabasa_app.school",
            ),
        ),
        migrations.RunPython(backfill_user_schools, migrations.RunPython.noop),
    ]
