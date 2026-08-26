from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q
from django.db.models.functions import Lower


def forwards(apps, schema_editor):
    School = apps.get_model("pabasa_app", "School")
    Section = apps.get_model("pabasa_app", "Section")

    school = School.objects.filter(name="Default School").first()
    if not school:
        school = School.objects.create(name="Default School", code="DEFAULT-SCHOOL", status="active", is_active=True)

    Section.objects.filter(school__isnull=True).update(school=school)


def backwards(apps, schema_editor):
    Section = apps.get_model("pabasa_app", "Section")
    School = apps.get_model("pabasa_app", "School")
    default_school = School.objects.filter(name="Default School").first()
    if default_school:
        Section.objects.filter(school=default_school).update(school=None)
        default_school.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0070_canonical_sections_and_enrollments"),
    ]

    operations = [
        migrations.CreateModel(
            name="School",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, unique=True)),
                ("code", models.CharField(blank=True, default="", max_length=50, unique=True)),
                ("address", models.TextField(blank=True, default="")),
                ("contact_information", models.TextField(blank=True, default="")),
                ("logo", models.CharField(blank=True, max_length=255, null=True)),
                ("status", models.CharField(choices=[("active", "Active"), ("archived", "Archived")], default="active", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "schools",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="section",
            name="school",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sections", to="pabasa_app.school"),
        ),
        migrations.AddConstraint(
            model_name="section",
            constraint=models.UniqueConstraint(
                models.F("school"),
                Lower("grade_level"),
                Lower("section"),
                condition=Q(grade_level__gt="", section__gt=""),
                name="unique_school_canonical_grade_section",
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
