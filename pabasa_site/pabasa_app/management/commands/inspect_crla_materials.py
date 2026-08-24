from django.core.management.base import BaseCommand

from pabasa_app.models import Material
from pabasa_app.views import _official_reading_assessment_type, _official_reading_materials_queryset


CRLA_KEYS = [
    "bosy_crla_pretest",
    "midline_crla_midtest",
    "eosy_crla_posttest",
]


def _fmt(value):
    if value is None:
        return ""
    return str(value)


def _print_record(material):
    self = material
    print("=" * 40)
    print(f"CRLA MATERIAL: {_fmt(self.system_assessment_key)}")
    print("=" * 40)
    print(f"ID: {_fmt(self.id)}")
    print(f"System Key: {_fmt(self.system_assessment_key)}")
    print(f"Code: {_fmt(self.code)}")
    print(f"Title: {_fmt(self.title)}")
    print(f"Period: {_fmt(self.system_assessment_period)}")
    print(f"Phase: {_fmt(self.system_assessment_phase)}")
    print(f"Assessment Type: {_fmt(_official_reading_assessment_type(self))}")
    print(f"System Owned: {_fmt(self.is_system_owned)}")
    print(f"Official Reading: {_fmt(self.is_official_reading)}")
    print(f"Assessment Set: {_fmt(self.assessment_set)}")
    print(f"Assessment Kind: {_fmt(self.assessment_kind)}")
    print(f"Type: {_fmt(self.type)}")
    print(f"Source Type: {_fmt(self.source_type)}")
    print(f"Status: {_fmt(self.status)}")
    print(f"Student Access: {_fmt(self.student_access)}")
    print(f"Active: {_fmt(self.is_active)}")
    print(f"Teacher: {_fmt(self.teacher_id)}")
    print(f"Section: {_fmt(self.section_id)}")


class Command(BaseCommand):
    help = "Inspect persisted CRLA materials and the official reading admin queryset."

    def handle(self, *args, **options):
        materials = list(
            Material.objects.filter(system_assessment_key__in=CRLA_KEYS).order_by("system_assessment_key")
        )
        materials_by_key = {str(material.system_assessment_key): material for material in materials}

        self.stdout.write("PERSISTED CRLA MATERIALS")
        for key in CRLA_KEYS:
            material = materials_by_key.get(key)
            if not material:
                self.stdout.write("=" * 40)
                self.stdout.write(f"CRLA MATERIAL: {key}")
                self.stdout.write("=" * 40)
                self.stdout.write("NOT FOUND")
                continue
            _print_record(material)

        official_qs = _official_reading_materials_queryset()
        official_key_set = {
            str(value)
            for value in official_qs.filter(system_assessment_key__in=CRLA_KEYS).values_list(
                "system_assessment_key", flat=True
            )
        }
        self.stdout.write("")
        self.stdout.write("OFFICIAL QUERY MATCHES")
        for key in CRLA_KEYS:
            self.stdout.write(f"{key}: {'YES' if key in official_key_set else 'NO'}")

        self.stdout.write("")
        self.stdout.write("ADMIN ACTIVE MATERIAL SELECTION")
        self.stdout.write("Run the admin page after seeding to confirm the current active material selection.")
