import json
import uuid

from django.test import TestCase
from django.urls import reverse
from django.contrib.staticfiles import finders

from .models import Material, School, Section, StudentActivityProgress, User
from .prescribed_activity_catalog import prescribed_activity


class PrescribedLesson16ActivityTests(TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex.upper()
        self.school = School.objects.create(name=f"Lesson 16 School {suffix}", code=f"L16-{suffix}")
        self.teacher = User.objects.create(
            custom_id=f"TCH-{suffix}", role="teacher", first_name="Teacher", last_name="Sixteen",
            middle_initial="", suffix="", sex="female", birth_month=1, birth_day=1, birth_year=1990,
            email=f"teacher-{suffix}@example.com", password_hash="hashed", teacher_role="Teacher",
            school_record=self.school,
        )
        self.student = User.objects.create(
            custom_id=f"STU-{suffix}", role="student", first_name="Learner", last_name="Sixteen",
            middle_initial="", suffix="", sex="male", birth_month=1, birth_day=1, birth_year=2018,
            email=f"student-{suffix}@example.com", password_hash="hashed", school_record=self.school,
        )
        self.section = Section.objects.create(
            school=self.school, class_code=f"CLASS-{suffix}", class_name="Grade 2", header="Reading",
            description="", teacher=self.teacher, subject="Filipino", is_active=True,
        )
        self.section.add_student(self.student)

    def login_student(self):
        session = self.client.session
        session.update({'user_id': self.student.id, 'user_role': 'student', 'email': self.student.email})
        session.save()

    def login_teacher(self):
        session = self.client.session
        session.update({'user_id': self.teacher.id, 'user_role': 'teacher', 'email': self.teacher.email})
        session.save()

    def make_material(self, key='lesson-16-gawain-1'):
        content = prescribed_activity(key)
        content.update({
            'template_source': 'prescribed', 'template_title': content['title'],
            'template_lesson': 'Lesson 16', 'activity_type': 'prescribed_missing_syllable',
            'language': 'Filipino', 'instructions': content['instruction'],
        })
        material = Material.objects.create(
            teacher=self.teacher, section=self.section,
            title=f"Lesson 16: Gawain {content['gawain_number']} — {content['title']}",
            item_type='word', content_text='\n'.join(item['word'] for item in content['items']),
            content_json=content, language='Filipino', type='assessment', assessment_kind='regular',
            source_type='template', status='published', is_active=True, student_access=True,
            assigned_week=6, assigned_weeks=[6],
        )
        material.assigned_sections.add(self.section)
        return material

    def test_published_page_uses_the_key_without_course_assignment(self):
        self.login_student()
        response = self.client.get(
            reverse('prescribed_activity_page', kwargs={'activity_key': 'lesson-16-gawain-1'}),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.context['prescribed_activity_data']
        self.assertEqual(payload['activity_key'], 'lesson-16-gawain-1')
        self.assertEqual([item['word'] for item in payload['items']], ['gumamela', 'banga', 'gusali', 'ngiti', 'gata'])
        self.assertNotIn('answer', payload['items'][0])

    def test_progress_resumes_and_completion_requires_all_items(self):
        material = self.make_material('lesson-16-gawain-2')
        self.login_student()
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': 'lesson-16-gawain-2'})
        complete_url = reverse('prescribed_activity_complete', kwargs={'activity_key': 'lesson-16-gawain-2'})
        partial = self.client.post(progress_url, data=json.dumps({
            'material_id': material.id, 'current_index': 2, 'answers': ['gu', 'ba'],
        }), content_type='application/json')
        self.assertEqual(partial.status_code, 200)
        saved = StudentActivityProgress.objects.get(student=self.student, activity_key='lesson-16-gawain-2')
        self.assertEqual(saved.completed_items, 2)
        self.assertFalse(saved.activity_completed)
        rejected = self.client.post(complete_url, data=json.dumps({
            'material_id': material.id, 'answers': ['gu', 'ba'],
        }), content_type='application/json')
        self.assertEqual(rejected.status_code, 400)
        completed = self.client.post(complete_url, data=json.dumps({
            'material_id': material.id, 'answers': ['gu', 'ba', 'gu', 'ngi', 'ga'], 'duration_seconds': 14,
        }), content_type='application/json')
        self.assertEqual(completed.status_code, 200)
        saved.refresh_from_db()
        self.assertTrue(saved.activity_completed)
        self.assertEqual(saved.correct_items, 5)
        self.assertTrue(material.assessment_results.filter(student=self.student, attempt_status='completed').exists())

    def test_directly_published_activity_saves_without_a_course_material(self):
        self.login_student()
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': 'lesson-16-gawain-1'})
        complete_url = reverse('prescribed_activity_complete', kwargs={'activity_key': 'lesson-16-gawain-1'})
        incorrect = self.client.post(progress_url, data=json.dumps({
            'current_index': 0, 'answers': [], 'candidate_answer': 'ga',
            'state': {'phase': 'written', 'written_attempts': 1, 'state_version': 1},
        }), content_type='application/json')
        self.assertEqual(incorrect.status_code, 200)
        self.assertFalse(incorrect.json()['accepted'])
        self.assertEqual(incorrect.json()['progress']['completed_items'], 0)
        self.assertEqual(incorrect.json()['progress']['state']['phase'], 'written')
        self.assertEqual(incorrect.json()['progress']['state']['written_attempts'], 1)
        response = self.client.post(progress_url, data=json.dumps({
            'current_index': 0, 'answers': [], 'candidate_answer': 'gu',
            'state': {'phase': 'written', 'state_version': 2},
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['accepted'])
        self.assertEqual(response.json()['progress']['state']['phase'], 'oral')
        response = self.client.post(complete_url, data=json.dumps({
            'answers': ['gu', 'ba', 'gu', 'ngi', 'ga'],
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        saved = StudentActivityProgress.objects.get(student=self.student, activity_key='lesson-16-gawain-1')
        self.assertTrue(saved.activity_completed)
        self.assertEqual(saved.correct_items, 5)
        self.assertIsNone(saved.state['material_id'])

    def test_catalog_preserves_workbook_order_and_direct_image_paths(self):
        activity = prescribed_activity('lesson-16-gawain-1')
        self.assertEqual([item['word'] for item in activity['items']], ['gumamela', 'banga', 'gusali', 'ngiti', 'gata'])
        self.assertEqual(
            [item['image_path'] for item in activity['items']],
            [
                'pabasa_app/images/lesson_16/gumamela.png',
                'pabasa_app/images/lesson_16/banga.png',
                'pabasa_app/images/lesson_16/gusali.png',
                'pabasa_app/images/lesson_16/ngiti.png',
                'pabasa_app/images/lesson_16/gata.png',
            ],
        )
        for item in activity['items']:
            self.assertIsNotNone(finders.find(item['image_path']))
