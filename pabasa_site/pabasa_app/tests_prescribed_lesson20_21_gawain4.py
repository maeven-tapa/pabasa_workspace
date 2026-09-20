import json
import uuid

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import School, StudentActivityProgress, User
from .prescribed_activity_catalog import prescribed_activity


class PrescribedLesson2021Gawain4Tests(TestCase):
    key = 'session-7-lesson-20-21-gawain-4'

    def setUp(self):
        token = uuid.uuid4().hex
        school = School.objects.create(name=f'Gawain 4 {token}', code=f'G4-{token}')
        self.student = User.objects.create(
            custom_id=f'STU-{token}', role='student', first_name='Gawain', last_name='Learner',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1, birth_year=2018,
            email=f'gawain4-{token}@example.com', password_hash='hashed', school_record=school,
        )
        self.teacher = User.objects.create(
            custom_id=f'TCH-{token}', role='teacher', first_name='Gawain', last_name='Teacher',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1, birth_year=1990,
            email=f'gawain4-teacher-{token}@example.com', password_hash='hashed', teacher_role='Teacher',
            school_record=school,
        )

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

    def test_catalog_is_the_exact_five_workbook_rows(self):
        activity = prescribed_activity(self.key)
        self.assertEqual(activity['display_title'], 'Lesson 20 at 21: Gawain 4')
        self.assertEqual(activity['title'], 'Bilugan ang Salitang May Klaster')
        self.assertEqual(activity['instruction'], 'Basahin ang bawat pangkat ng salita. Bilugan ang salitang may klaster.')
        self.assertEqual([item['words'] for item in activity['items']], [
            ['pato', 'plato', 'dagat', 'pera'],
            ['grupo', 'ganda', 'masa', 'tasa'],
            ['Enero', 'Pebrero', 'Mayo', 'Agosto'],
            ['krayola', 'parola', 'tinola', 'bola'],
            ['tono', 'trono', 'maso', 'baso'],
        ])
        self.assertEqual([item['answer'] for item in activity['items']], ['plato', 'grupo', 'Pebrero', 'krayola', 'trono'])
        self.assertTrue(activity['thumbnail'].startswith('pabasa_app/prescribed/session_7/lesson_20_21/gawain_4/'))

    def test_progress_requires_four_ordered_readings_then_resumes_and_completes(self):
        self.login_student()
        page = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.key}))
        self.assertTemplateUsed(page, 'pabasa_app/session7_cluster_word_circle_page.html')
        payload = page.context['prescribed_activity_data']
        self.assertNotIn('answer', payload['items'][0])
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.key})
        denied = self.client.post(progress_url, data=json.dumps({
            'candidate_answer': 'plato', 'state': {'phase': 'word_selection', 'state_version': 1},
        }), content_type='application/json')
        self.assertEqual(denied.status_code, 400)

        state = {'phase': 'oral_reading', 'state_version': 1, 'orally_completed_words': {'0': [0]}}
        for reading_index in range(4):
            state['orally_completed_words'] = {'0': list(range(reading_index + 1))}
            saved = self.client.post(progress_url, data=json.dumps({'state': state}), content_type='application/json')
            self.assertEqual(saved.status_code, 200)
            state = saved.json()['progress']['state']
        self.assertEqual(state['current_reading_index'], 4)
        saved = StudentActivityProgress.objects.get(student=self.student, activity_key=self.key)
        self.assertEqual(saved.completed_items, 0)
        self.assertEqual(saved.state['orally_completed_words']['0'], [0, 1, 2, 3])

        wrong = self.client.post(progress_url, data=json.dumps({
            'candidate_answer': 'pato', 'state': state,
        }), content_type='application/json')
        self.assertFalse(wrong.json()['accepted'])
        state = wrong.json()['progress']['state']
        correct = self.client.post(progress_url, data=json.dumps({
            'candidate_answer': 'plato', 'state': state,
        }), content_type='application/json')
        self.assertTrue(correct.json()['accepted'])
        saved.refresh_from_db()
        self.assertEqual(saved.completed_items, 1)
        self.assertEqual(saved.state['current_row_index'], 1)
        self.assertEqual(saved.state['selected_words'], ['plato'])

        completion_url = reverse('prescribed_activity_complete', kwargs={'activity_key': self.key})
        incomplete = self.client.post(completion_url, data='{}', content_type='application/json')
        self.assertEqual(incomplete.status_code, 400)
        for row, answer in enumerate(['grupo', 'Pebrero', 'krayola', 'trono'], start=1):
            state['phase'] = 'oral_reading'
            for reading_index in range(4):
                state['orally_completed_words'][str(row)] = list(range(reading_index + 1))
                saved = self.client.post(progress_url, data=json.dumps({'state': state}), content_type='application/json')
                self.assertEqual(saved.status_code, 200)
                state = saved.json()['progress']['state']
            completed_row = self.client.post(progress_url, data=json.dumps({
                'candidate_answer': answer, 'state': state,
            }), content_type='application/json')
            self.assertTrue(completed_row.json()['accepted'])
            state = completed_row.json()['progress']['state']
        complete = self.client.post(completion_url, data='{}', content_type='application/json')
        self.assertTrue(complete.json()['success'])
        saved.refresh_from_db()
        self.assertTrue(saved.activity_completed)
        self.assertEqual((saved.completed_items, saved.correct_items, saved.total_items), (5, 5, 5))

    def test_teacher_catalog_and_assessment_card_use_the_registered_label(self):
        self.login_teacher()
        teacher_page = self.client.get(reverse('course_teacher_view'))
        activities = teacher_page.context['prescribed_lesson_20_21_activities']
        activity = next(entry for entry in activities if entry['activity_key'] == self.key)
        self.assertEqual(activity['card_label'], 'Lesson 20 at 21: Gawain 4')
        self.assertContains(teacher_page, 'session-7-lesson-20-21-gawain-4')
        self.assertContains(teacher_page, 'lesson20-gawain4-preview')
