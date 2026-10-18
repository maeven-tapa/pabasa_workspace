from django.test import TestCase

from .models import Enrollment, School, Section, User
from .views import _student_enrolled_sections


class StudentSectionLookupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name='Lookup School', code='LOOKUP')
        cls.other_school = School.objects.create(name='Other Lookup School', code='LOOKUP-OTHER')
        def user(code, role='student', school=None):
            return User.objects.create(custom_id=code,role=role,first_name='Synthetic',last_name='Lookup',
                middle_initial='',suffix='',sex='female',birth_month=1,birth_day=1,birth_year=2012,
                password_hash='!unused',school_record=school or cls.school)
        cls.student = user('LOOKUP-STUDENT')
        cls.other_student = user('LOOKUP-OTHER-STUDENT',school=cls.other_school)
        cls.teacher = user('LOOKUP-TEACHER','teacher')
        cls.sections = []
        for index in range(20):
            section = Section.objects.create(school=cls.school if index < 10 else cls.other_school,
                teacher=cls.teacher,class_code=f'LOOKUP-{index}',class_name=f'Lookup {index}',subject='Reading',
                is_active=index != 3,students=[{'student_id':cls.student.pk}])
            cls.sections.append(section)
        cls.allowed = cls.sections[0]
        Enrollment.objects.create(section=cls.allowed,student=cls.student,status='active',is_active=True)
        Enrollment.objects.create(section=cls.sections[1],student=cls.student,status='dropped',is_active=True)
        inactive = Enrollment.objects.create(section=cls.sections[2],student=cls.student,status='active')
        # Represent a historical inactive row without save() normalizing the flag.
        Enrollment.objects.filter(pk=inactive.pk).update(is_active=False)
        Enrollment.objects.create(section=cls.sections[3],student=cls.student,status='active',is_active=True)
        Enrollment.objects.create(section=cls.sections[10],student=cls.other_student,status='active',is_active=True)

    def test_lookup_matches_active_enrollment_authority_in_one_query(self):
        expected = {s.pk for s in self.sections if s.is_active and s.has_student(self.student,active_only=True)}
        with self.assertNumQueries(1):
            actual = {s.pk for s in _student_enrolled_sections(self.student).select_related('teacher')}
        self.assertEqual(actual, expected)
        self.assertEqual(actual, {self.allowed.pk})

    def test_missing_user_and_teacher_never_receive_student_sections(self):
        with self.assertNumQueries(0):
            self.assertEqual(list(_student_enrolled_sections(None)), [])
            self.assertEqual(list(_student_enrolled_sections(self.teacher)), [])
