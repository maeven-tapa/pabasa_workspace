import json

from django.contrib.sessions.backends.db import SessionStore
from django.db import connection
from django.test import TestCase, RequestFactory
from django.test.utils import CaptureQueriesContext

from .models import Enrollment, School, Section, User
from .views import get_student_joined_classes


class StudentClassesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name='Class listing school', code='CLASS-LIST')
        cls.other_school = School.objects.create(name='Other school', code='CLASS-OTHER')
        cls.teacher = cls.user('LIST-TEACHER', role='teacher')
        cls.section = cls.make_section('LIST-CLASS', cls.school, cls.teacher)
        cls.students = [cls.user(f'LIST-STUDENT-{index}') for index in range(20)]
        for student in cls.students:
            Enrollment.objects.create(student=student, section=cls.section)

    @staticmethod
    def user(custom_id, role='student'):
        return User.objects.create(
            custom_id=custom_id, role=role, first_name='Fixture', last_name='User',
            email=f'{custom_id.lower()}@example.com', password_hash='unused',
            sex='female', birth_month=1, birth_day=1, birth_year=2012,
        )

    @staticmethod
    def make_section(code, school, teacher=None, is_active=True):
        return Section.objects.create(
            school=school, class_code=code, class_name=code, subject='Reading',
            teacher=teacher, is_active=is_active,
        )

    def request(self, user=None, role=None):
        request = RequestFactory().get('/api/student/classes/', HTTP_ACCEPT='application/json')
        request.session = SessionStore()
        if user is not None:
            request.session.update({'user_id': user.pk, 'user_role': role or user.role})
        return request

    def classes(self, user=None):
        response = get_student_joined_classes(self.request(user or self.students[0]))
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)['classes']

    def test_twenty_students_receive_their_own_enrolled_class_and_roster_count(self):
        other = self.make_section('UNENROLLED', self.other_school)
        for student in self.students:
            with self.subTest(student_id=student.id):
                classes = self.classes(student)
                self.assertEqual([item['section_id'] for item in classes], [self.section.id])
                self.assertEqual(classes[0]['student_count'], 20)
                self.assertEqual(classes[0]['teacher_id'], self.teacher.custom_id)
                self.assertFalse(classes[0]['official_crla_completed'])
                self.assertNotEqual(classes[0]['section_id'], other.id)

    def test_dropped_enrollment_and_inactive_section_are_excluded(self):
        dropped = self.make_section('DROPPED', self.school)
        inactive = self.make_section('INACTIVE', self.school, is_active=False)
        Enrollment.objects.create(student=self.students[0], section=dropped, status='dropped')
        Enrollment.objects.create(student=self.students[0], section=inactive)
        self.assertEqual([item['section_id'] for item in self.classes()], [self.section.id])

    def test_roster_count_and_membership_refresh_after_enrollment_changes(self):
        enrollment = Enrollment.objects.get(student=self.students[0], section=self.section)
        enrollment.status = 'dropped'
        enrollment.save(update_fields=['status', 'is_active'])
        self.assertEqual(self.classes(self.students[0]), [])
        self.assertEqual(self.classes(self.students[1])[0]['student_count'], 19)

    def test_unassigned_teacher_is_supported(self):
        self.section.teacher = None
        self.section.save(update_fields=['teacher'])
        item = self.classes()[0]
        self.assertIsNone(item['teacher_id'])
        self.assertEqual(item['teacher_name'], '')

    def test_teacher_name_follows_current_section_assignment(self):
        enrollment = Enrollment.objects.get(student=self.students[0], section=self.section)
        self.assertEqual(self.classes()[0]['teacher_name'], 'Fixture User')

        self.section.teacher = None
        self.section.save(update_fields=['teacher'])
        self.assertEqual(enrollment.assigned_teacher_id, self.teacher.id)
        self.assertEqual(self.classes()[0]['teacher_name'], '')

        new_teacher = self.user('LIST-NEW-TEACHER', role='teacher')
        new_teacher.first_name = 'New'
        new_teacher.last_name = 'Teacher'
        new_teacher.save(update_fields=['first_name', 'last_name'])
        self.section.teacher = new_teacher
        self.section.save(update_fields=['teacher'])
        self.assertEqual(self.classes()[0]['teacher_name'], 'New Teacher')

    def test_query_count_does_not_grow_with_unrelated_sections(self):
        with CaptureQueriesContext(connection) as before:
            original = self.classes()
        for index in range(20):
            self.make_section(f'OTHER-{index}', self.other_school, self.teacher)
        with CaptureQueriesContext(connection) as after:
            expanded = self.classes()
        self.assertEqual(original, expanded)
        membership_tables = [connection.ops.quote_name(model._meta.db_table) for model in (Section, Enrollment)]
        def membership_query_count(queries):
            return sum(any(table in query['sql'] for table in membership_tables) for query in queries)
        self.assertEqual(membership_query_count(before), membership_query_count(after))
        # Includes authentication, CRLA/calendar resolution, and an occasional
        # system-clock override cache refresh unrelated to class membership.
        self.assertLessEqual(len(after), 12)

    def test_anonymous_and_wrong_roles_cannot_fetch_student_classes(self):
        self.assertEqual(get_student_joined_classes(self.request()).status_code, 401)
        self.assertEqual(get_student_joined_classes(self.request(self.teacher)).status_code, 403)
        self.assertEqual(get_student_joined_classes(self.request(self.teacher, role='student')).status_code, 403)

    def test_archived_students_cannot_fetch_classes(self):
        student = self.students[0]
        student.is_archived = True
        student.save(update_fields=['is_archived'])
        self.assertEqual(get_student_joined_classes(self.request(student)).status_code, 403)
