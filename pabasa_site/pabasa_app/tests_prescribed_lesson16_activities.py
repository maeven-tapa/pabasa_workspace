import json
import uuid

from django.test import TestCase
from django.urls import reverse
from django.contrib.staticfiles import finders
from django.utils import timezone

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
        self.student.active_session_key = session.session_key
        self.student.last_activity = timezone.now()
        self.student.save(update_fields=['active_session_key', 'last_activity', 'updated_at'])

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

    def test_all_lesson_16_cards_use_the_session_6_key(self):
        self.login_student()
        response = self.client.get(reverse('assessment'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                card['activity_key']: card['session_key']
                for card in response.context['prescribed_activity_cards']
                if card['activity_key'].startswith('lesson-16-')
            },
            {
                'lesson-16-gawain-1': 'session-6',
                'lesson-16-gawain-2': 'session-6',
                'lesson-16-gawain-3': 'session-6',
                'session-6-lesson-16-gawain-4': 'session-6',
            },
        )

    def test_gawain_4_uses_fixed_workbook_order_and_available_assets(self):
        activity = prescribed_activity('session-6-lesson-16-gawain-4')
        self.assertEqual(activity['session_key'], 'session-6')
        self.assertEqual(activity['interaction'], 'picture_word_write')
        self.assertEqual(
            [item['answer'] for item in activity['items']],
            ['gamot', 'bunga', 'panga', 'goma', 'sanga'],
        )
        self.assertEqual([item['letter_count'] for item in activity['items']], [5, 5, 5, 4, 5])
        for item in activity['items']:
            self.assertIsNotNone(finders.find(item['image_path']))

    def test_gawain_4_is_present_in_the_teacher_catalog_from_the_same_definition(self):
        self.login_teacher()
        response = self.client.get(reverse('course_teacher_view'))
        self.assertEqual(response.status_code, 200)
        catalog_activity = next(
            activity for activity in response.context['prescribed_lesson_16_activities']
            if activity['activity_key'] == 'session-6-lesson-16-gawain-4'
        )
        self.assertEqual(catalog_activity, prescribed_activity('session-6-lesson-16-gawain-4'))

    def test_gawain_4_persists_correct_items_and_requires_all_for_completion(self):
        self.login_student()
        key = 'session-6-lesson-16-gawain-4'
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        complete_url = reverse('prescribed_activity_complete', kwargs={'activity_key': key})
        incorrect = self.client.post(progress_url, data=json.dumps({
            'candidate_answer': 'gamutx', 'state': {'started': True, 'state_version': 1},
        }), content_type='application/json')
        self.assertEqual(incorrect.status_code, 200)
        self.assertFalse(incorrect.json()['accepted'])
        self.assertEqual(incorrect.json()['progress']['state']['attempts'], {'0': 1})
        first = self.client.post(progress_url, data=json.dumps({
            'candidate_answer': ' GAMOT ', 'state': {'started': True, 'state_version': 2},
        }), content_type='application/json')
        self.assertTrue(first.json()['accepted'])
        self.assertEqual(first.json()['progress']['completed_items'], 1)
        page = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': key}))
        self.assertTemplateUsed(page, 'pabasa_app/prescribed_picture_word_write_page.html')
        self.assertEqual(page.context['prescribed_activity_data']['progress']['current_index'], 1)
        self.assertNotIn('answer', page.context['prescribed_activity_data']['items'][0])
        self.assertEqual(self.client.post(complete_url, data='{}', content_type='application/json').status_code, 400)
        for state_version, answer in enumerate(['bunga', 'panga', 'goma', 'sanga'], start=3):
            response = self.client.post(progress_url, data=json.dumps({
                'candidate_answer': answer, 'state': {'started': True, 'state_version': state_version},
            }), content_type='application/json')
            self.assertTrue(response.json()['accepted'])
        self.assertEqual(self.client.post(complete_url, data='{}', content_type='application/json').status_code, 200)
        saved = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
        self.assertTrue(saved.activity_completed)
        self.assertEqual(saved.completed_items, 5)

    def test_gawain_4_recovers_a_saved_final_answer_when_completion_was_interrupted(self):
        self.login_student()
        key = 'session-6-lesson-16-gawain-4'
        StudentActivityProgress.objects.create(
            student=self.student, activity_key=key, current_index=5, completed_items=5,
            correct_items=5, total_items=5, activity_completed=False,
            state={'answers': ['gamot', 'bunga', 'panga', 'goma', 'sanga'],
                   'attempts': {}, 'started': True, 'state_version': 7},
        )
        response = self.client.post(
            reverse('prescribed_activity_progress', kwargs={'activity_key': key}),
            data=json.dumps({'candidate_answer': 'sanga', 'state': {'started': True, 'state_version': 8}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['progress']['activity_completed'])
        saved = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
        self.assertTrue(saved.activity_completed)

    def test_gawain_3_uses_the_workbook_word_bank_and_placeholder_paths(self):
        activity = prescribed_activity('lesson-16-gawain-3')
        self.assertEqual(activity['interaction'], 'picture_word_match')
        self.assertEqual(activity['word_bank'], ['panga', 'gamot', 'sanga', 'bunga', 'goma'])
        self.assertEqual([item['word'] for item in activity['items']], ['sanga', 'goma', 'bunga', 'panga', 'gamot'])
        self.assertEqual(
            [item['image_path'] for item in activity['items']],
            [
                'pabasa_app/images/lesson_16/sanga.png',
                'pabasa_app/images/lesson_16/goma.png',
                'pabasa_app/images/lesson_16/bunga.png',
                'pabasa_app/images/lesson_16/panga.png',
                'pabasa_app/images/lesson_16/gamot.png',
            ],
        )

    def test_gawain_3_hides_answers_from_the_student_page(self):
        self.login_student()
        response = self.client.get(
            reverse('prescribed_activity_page', kwargs={'activity_key': 'lesson-16-gawain-3'}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pabasa_app/prescribed_picture_word_matching_page.html')
        payload = response.context['prescribed_activity_data']
        self.assertEqual(payload['word_bank'], ['panga', 'gamot', 'sanga', 'bunga', 'goma'])
        self.assertEqual([item['id'] for item in payload['items']], [
            'picture-1', 'picture-2', 'picture-3', 'picture-4', 'picture-5',
        ])
        self.assertNotIn('word', payload['items'][0])

    def test_gawain_3_validates_matches_and_restores_partial_progress(self):
        self.login_student()
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': 'lesson-16-gawain-3'})
        complete_url = reverse('prescribed_activity_complete', kwargs={'activity_key': 'lesson-16-gawain-3'})
        incorrect = self.client.post(progress_url, data=json.dumps({
            'matches': {}, 'candidate_match': {'target_id': 'picture-1', 'word': 'panga'},
            'state': {'match_attempts': 1, 'state_version': 1},
        }), content_type='application/json')
        self.assertEqual(incorrect.status_code, 200)
        self.assertFalse(incorrect.json()['accepted'])
        self.assertEqual(incorrect.json()['progress']['completed_items'], 0)

        correct = self.client.post(progress_url, data=json.dumps({
            'matches': {}, 'candidate_match': {'target_id': 'picture-4', 'word': 'panga'},
            'state': {'match_attempts': 2, 'state_version': 2},
        }), content_type='application/json')
        self.assertEqual(correct.status_code, 200)
        self.assertTrue(correct.json()['accepted'])
        self.assertEqual(correct.json()['progress']['matches'], {'picture-4': 'panga'})
        saved = StudentActivityProgress.objects.get(student=self.student, activity_key='lesson-16-gawain-3')
        self.assertEqual(saved.completed_items, 1)
        self.assertEqual(saved.state['matches'], {'picture-4': 'panga'})

        page = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': 'lesson-16-gawain-3'}))
        self.assertEqual(page.context['prescribed_activity_data']['progress']['matches'], {'picture-4': 'panga'})
        rejected = self.client.post(complete_url, data=json.dumps({'matches': {'picture-4': 'panga'}}), content_type='application/json')
        self.assertEqual(rejected.status_code, 400)

        completed = self.client.post(complete_url, data=json.dumps({'matches': {
            'picture-1': 'sanga', 'picture-2': 'goma', 'picture-3': 'bunga',
            'picture-4': 'panga', 'picture-5': 'gamot',
        }}), content_type='application/json')
        self.assertEqual(completed.status_code, 200)
        saved.refresh_from_db()
        self.assertTrue(saved.activity_completed)
        self.assertEqual(saved.correct_items, 5)
