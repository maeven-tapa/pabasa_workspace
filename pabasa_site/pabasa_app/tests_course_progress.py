from django.test import TestCase
from django.urls import reverse

from .models import Material, School, Section, User


class TeacherCourseProgressTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='Course Progress School', code='COURSE-PROGRESS')
        self.teacher = User.objects.create(
            custom_id='TCH-COURSE-PROGRESS', role='teacher',
            first_name='Course', last_name='Teacher',
            sex='female', birth_month=1, birth_day=1, birth_year=1990,
            email='course.progress.teacher@example.com', password_hash='hashed-password',
        )
        self.student = User.objects.create(
            custom_id='STD-COURSE-PROGRESS', role='student',
            first_name='Course', last_name='Student',
            sex='male', birth_month=1, birth_day=1, birth_year=2015,
            email='course.progress.student@example.com', password_hash='hashed-password',
        )
        self.section = Section.objects.create(
            school=self.school, teacher=self.teacher, class_code='COURSE-PROGRESS-1',
            class_name='Course Progress', header='Reading', subject='Reading',
        )
        self.section.add_student(self.student)
        self.material_one = Material.objects.create(
            title='Activity one', item_type='word', type='practice', status='published',
            is_active=True, section=self.section, teacher=self.teacher,
        )
        self.material_two = Material.objects.create(
            title='Activity two', item_type='word', type='practice', status='published',
            is_active=True, section=self.section, teacher=self.teacher,
        )
        session = self.client.session
        session['user_id'] = self.teacher.id
        session['user_role'] = 'teacher'
        session.save()

    def test_section_backed_course_reports_completed_activity_progress(self):
        # Use the same persistence method the student activity completion API uses.
        self.material_one.record_assessment_result(
            self.student, status='completed', items_completed=1, total_practice_items=1,
        )

        response = self.client.get(reverse('get_teacher_courses_api'))

        self.assertEqual(response.status_code, 200)
        course = response.json()['courses'][0]
        self.assertEqual(course['id'], f'section-{self.section.id}')
        self.assertEqual(course['metrics']['average_progress'], 50.0)
