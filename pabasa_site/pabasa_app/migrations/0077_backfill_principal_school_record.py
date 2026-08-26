from django.db import migrations


def forwards(apps, schema_editor):
    User = apps.get_model("pabasa_app", "User")
    School = apps.get_model("pabasa_app", "School")

    schools = {
        school.name.casefold(): school
        for school in School.objects.exclude(name="Default School")
    }
    for user in User.objects.filter(role="principal", school_record__isnull=True):
        legacy_name = str(user.school or "").strip().casefold()
        school = schools.get(legacy_name)
        if school is None:
            continue
        if User.objects.filter(
            role="principal",
            school_record=school,
            is_archived=False,
        ).exists():
            # Do not guess which duplicate active account should own the School.
            continue
        user.school_record_id = school.id
        user.school = school.name
        user.save(update_fields=["school_record", "school"])


class Migration(migrations.Migration):
    dependencies = [
        ("pabasa_app", "0076_unique_active_principal_per_school"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
