import json

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Assessment, ClassCrlaFinalization, Material, School, SchoolCalendar, Section, User
from .scoring import crla_reading_profile


class ClassCrlaFinalizationTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='Finalization School', code='CFL')
        self.calendar = SchoolCalendar.objects.create(school_year='Finalization Year', current_term=1, is_active=True)
        self.teacher = self._user('final-teacher', 'teacher')
        self.other_teacher = self._user('final-other', 'teacher')
        self.section = Section.objects.create(
            school=self.school, school_calendar=self.calendar, teacher=self.teacher,
            class_code='FIN-A', class_name='FIN-A', subject='Reading',
        )
        self.other_section = Section.objects.create(
            school=self.school, school_calendar=self.calendar, teacher=self.other_teacher,
            class_code='FIN-B', class_name='FIN-B', subject='Reading',
        )
        self.completed_student = self._user('final-completed', 'student')
        self.missing_student = self._user('final-missing', 'student')
        self.section.add_student(self.completed_student)
        self.section.add_student(self.missing_student)
        self.material = Material.objects.get(system_assessment_key='bosy_crla_pretest')

    def _user(self, custom_id, role):
        return User.objects.create(
            custom_id=custom_id, role=role, first_name=custom_id, last_name='User',
            middle_initial='', suffix='', sex='N/A', birth_month=1, birth_day=1, birth_year=1990,
            email=f'{custom_id}@example.com', password_hash=make_password('password'), school_record=self.school,
        )

    def _login(self, user):
        session = self.client.session
        session.update({'user_id': user.id, 'user_role': user.role, 'email': user.email})
        session.save()

    def _finalize(self, section=None, material=None):
        return self.client.post(reverse('finalize_class_crla_assessment'), data=json.dumps({
            'section_id': (section or self.section).id,
            'material_id': (material or self.material).id,
        }), content_type='application/json')

    def test_finalize_preserves_completed_result_and_creates_authoritative_zero(self):
        self.material.record_assessment_result(
            self.completed_student, status='completed', completed_at=timezone.now(), total_score=28,
            crla_classification='Reading At Grade Level', classification='Reading At Grade Level',
        )
        original = Assessment.objects.get(student=self.completed_student, material=self.material)
        self._login(self.teacher)
        response = self._finalize()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['missing_students_processed'], 1)
        original.refresh_from_db()
        self.assertEqual(original.total_score, 28)
        zero = Assessment.objects.get(student=self.missing_student, material=self.material)
        self.assertEqual(zero.total_score, 0)
        self.assertEqual(zero.crla_classification, crla_reading_profile(0, None, None, None))
        self.assertTrue(ClassCrlaFinalization.objects.filter(section=self.section, material=self.material).exists())

    def test_finalize_no_completed_students_is_idempotent(self):
        self._login(self.teacher)
        self.assertEqual(self._finalize().status_code, 200)
        again = self._finalize()
        self.assertEqual(again.status_code, 200)
        self.assertTrue(again.json()['already_finalized'])
        self.assertEqual(Assessment.objects.filter(material=self.material, student__isnull=False).count(), 2)

    def test_finalize_all_completed_students_creates_no_zero_results(self):
        for student, score, classification in (
            (self.completed_student, 20, 'Developing Reader'),
            (self.missing_student, 30, 'Reading At Grade Level'),
        ):
            self.material.record_assessment_result(
                student, status='completed', completed_at=timezone.now(), total_score=score,
                crla_classification=classification, classification=classification,
            )
        self._login(self.teacher)
        response = self._finalize()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['missing_students_processed'], 0)
        self.assertEqual(Assessment.objects.filter(material=self.material, student__isnull=False).count(), 2)

    def test_wrong_teacher_and_wrong_class_are_rejected(self):
        self._login(self.other_teacher)
        self.assertEqual(self._finalize().status_code, 403)

    def test_invalid_assessment_is_rejected(self):
        invalid = Material.objects.create(
            code='FINAL-NON-CRLA', title='Regular assessment', teacher=self.teacher,
            item_type='word', type='assessment', status='published', is_active=True,
        )
        self._login(self.teacher)
        self.assertEqual(self._finalize(material=invalid).status_code, 400)

    def test_export_is_rejected_before_finalization(self):
        root = Assessment.objects.create(
            teacher=self.teacher, title='CRLA root', code='FINAL-ROOT', assessment_type='paragraph',
        )
        self._login(self.teacher)
        response = self.client.get(reverse('export_crla_assessment', args=[root.id]), {
            'source': 'student-directory', 'section_id': self.section.id, 'material_id': self.material.id,
        })
        self.assertIn(response.status_code, {302, 403})
