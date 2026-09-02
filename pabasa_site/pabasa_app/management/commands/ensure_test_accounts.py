from django.core.management.base import BaseCommand

from pabasa_app.test_accounts import (
    DEFAULT_TEST_ACCOUNTS,
    ensure_default_test_accounts,
)
from pabasa_app.models import Enrollment, Section, User


class Command(BaseCommand):
    help = "Ensure default teacher and student accounts exist."

    def handle(self, *args, **options):
        results = ensure_default_test_accounts()
        teacher = User.objects.get(custom_id="TCH-9999")
        student = User.objects.get(custom_id="G2-9999")
        section = Section.objects.filter(
            section__iexact="Aguinaldo",
            grade_level="Grade 2",
            is_active=True,
        ).first()
        if section:
            section.teacher = teacher
            section.save(update_fields=["teacher", "updated_at"])
            Enrollment.objects.update_or_create(
                student=student,
                section=section,
                defaults={
                    "school": section.school,
                    "school_calendar": section.school_calendar,
                    "grade_level": section.grade_level or "Grade 2",
                    "status": "active",
                    "is_active": True,
                    "assigned_teacher": teacher,
                },
            )
            student.section = section.section
            student.grade_level = section.grade_level or "Grade 2"
            student.school_record = section.school
            student.school_calendar = section.school_calendar
            student.save(update_fields=["section", "grade_level", "school_record", "school_calendar", "updated_at"])
        for custom_id, created in results:
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created test account: {custom_id}"))
            else:
                self.stdout.write(f"Test account already exists: {custom_id}")

        self.stdout.write("")
        self.stdout.write("Default test credentials:")
        for account in DEFAULT_TEST_ACCOUNTS:
            self.stdout.write(
                f"  {account['custom_id']} / {account['password']} ({account['role']})"
            )
