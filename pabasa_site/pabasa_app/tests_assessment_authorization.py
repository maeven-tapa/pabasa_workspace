from django.test import TestCase
from django.contrib.auth.hashers import make_password

from .models import Assessment, Material, School, Section, User
from .views import _student_can_complete_assessment


class AssessmentCompletionAuthorizationTests(TestCase):
    def setUp(self):
        self.school_a = School.objects.create(name='School A', code='AUTH-A')
        self.school_b = School.objects.create(name='School B', code='AUTH-B')
        self.teacher_a = User.objects.create(
            custom_id='AUTH-TA', role='teacher', first_name='Teacher', last_name='A',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1,
            birth_year=1990, email='auth-ta@example.com',
            password_hash=make_password('password'), school_record=self.school_a,
        )
        self.teacher_b = User.objects.create(
            custom_id='AUTH-TB', role='teacher', first_name='Teacher', last_name='B',
            middle_initial='', suffix='', sex='male', birth_month=1, birth_day=2,
            birth_year=1990, email='auth-tb@example.com',
            password_hash=make_password('password'), school_record=self.school_b,
        )
        self.student = User.objects.create(
            custom_id='AUTH-STU', role='student', first_name='Student', last_name='A',
            middle_initial='', suffix='', sex='female', birth_month=2, birth_day=3,
            birth_year=2012, email='auth-stu@example.com',
            password_hash=make_password('password'), school_record=self.school_a,
        )
        self.section_a = Section.objects.create(
            school=self.school_a, teacher=self.teacher_a, class_code='AUTH-A-1',
            class_name='A 1', subject='Reading', is_active=True,
        )
        self.section_b = Section.objects.create(
            school=self.school_b, teacher=self.teacher_b, class_code='AUTH-B-1',
            class_name='B 1', subject='Reading', is_active=True,
        )
        self.section_a.add_student(self.student)
        self.assessment_a = Assessment.objects.create(
            title='Own assessment', code='AUTH-ASSESS-A', assessment_type='word',
            teacher=self.teacher_a, section=self.section_a,
        )
        self.assessment_b = Assessment.objects.create(
            title='Other assessment', code='AUTH-ASSESS-B', assessment_type='word',
            teacher=self.teacher_b, section=self.section_b,
        )

    def test_active_enrollment_authorizes_own_section_assessment(self):
        self.assertTrue(_student_can_complete_assessment(self.student, self.assessment_a))

    def test_other_school_and_unrelated_section_assessments_are_rejected(self):
        self.assertFalse(_student_can_complete_assessment(self.student, self.assessment_b))
        unrelated = Section.objects.create(
            school=self.school_a, teacher=self.teacher_a, class_code='AUTH-A-2',
            class_name='A 2', subject='Reading', is_active=True,
        )
        unrelated_assessment = Assessment.objects.create(
            title='Unrelated assessment', code='AUTH-ASSESS-C', assessment_type='word',
            teacher=self.teacher_a, section=unrelated,
        )
        self.assertFalse(_student_can_complete_assessment(self.student, unrelated_assessment))

    def test_inactive_enrollment_does_not_authorize(self):
        self.section_a.deactivate_student(self.student)
        self.assertFalse(_student_can_complete_assessment(self.student, self.assessment_a))

    def test_attempt_rows_are_not_source_assessments(self):
        attempt = Assessment.objects.create(
            title='Attempt', code='AUTH-ATTEMPT', assessment_type='word',
            teacher=self.teacher_a, section=self.section_a,
            source_assessment=self.assessment_a, student=self.student,
        )
        self.assertFalse(_student_can_complete_assessment(self.student, attempt))

    def test_material_assignment_uses_active_enrollment(self):
        material = Material.objects.create(
            title='Assigned material', item_type='word', type='assessment',
            teacher=self.teacher_b, status='published', is_active=True,
        )
        material.assigned_sections.add(self.section_a)
        self.assertTrue(_student_can_complete_assessment(self.student, material=material))

    def test_unrelated_material_is_rejected(self):
        material = Material.objects.create(
            title='Unrelated material', item_type='word', type='assessment',
            teacher=self.teacher_b, section=self.section_b, status='published', is_active=True,
        )
        self.assertFalse(_student_can_complete_assessment(self.student, material=material))
