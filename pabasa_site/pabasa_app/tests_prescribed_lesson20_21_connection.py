import json
import uuid

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import School, StudentActivityProgress, User
from .prescribed_activity_catalog import prescribed_activity


class PrescribedLesson2021ConnectionTests(TestCase):
    key = 'session-7-lesson-20-21-gawain-3'

    def setUp(self):
        token = uuid.uuid4().hex
        school = School.objects.create(name=f'Connection {token}', code=f'CN-{token}')
        self.student = User.objects.create(
            custom_id=f'STU-{token}', role='student', first_name='Connection', last_name='Learner',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1, birth_year=2018,
            email=f'connection-{token}@example.com', password_hash='hashed', school_record=school,
        )
        session = self.client.session
        session.update({'user_id': self.student.id, 'user_role': 'student', 'email': self.student.email})
        session.save()
        self.student.active_session_key = session.session_key
        self.student.last_activity = timezone.now()
        self.student.save(update_fields=['active_session_key', 'last_activity', 'updated_at'])
        self.progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.key})
        self.complete_url = reverse('prescribed_activity_complete', kwargs={'activity_key': self.key})

    def post(self, body):
        return self.client.post(self.progress_url, data=json.dumps(body), content_type='application/json')

    def test_workbook_order_example_and_student_payload(self):
        activity = prescribed_activity(self.key)
        self.assertEqual(activity['total_items'], 4)
        self.assertEqual([item['word'] for item in activity['items']], ['tsek', 'tsokolate', 'kutsara', 'kotse', 'pitsel'])
        self.assertTrue(activity['items'][0]['worked_example'])
        self.assertTrue(all(item['image_path'].startswith('pabasa_app/prescribed/session_7/lesson_20_21/gawain_3/') for item in activity['items']))

        response = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.key}))
        self.assertTemplateUsed(response, 'pabasa_app/session7_picture_word_connection_page.html')
        payload = response.context['prescribed_activity_data']
        self.assertEqual(payload['progress']['total_items'], 4)
        self.assertEqual(payload['worked_example']['word'], 'tsek')
        self.assertNotIn('answer', payload['items'][0])

    def test_reading_gate_retry_and_saved_correct_connection(self):
        blocked = self.post({'candidate_answer': 'tsokolate', 'state': {'phase': 'connection', 'selected_answer': 'tsokolate'}})
        self.assertEqual(blocked.status_code, 400)

        oral = self.post({'state': {'phase': 'connection', 'completed_oral_reads': [0]}})
        self.assertEqual(oral.status_code, 200)
        state = oral.json()['progress']['state']
        state.update({'phase': 'connection', 'selected_answer': 'kendi'})
        wrong = self.post({'candidate_answer': 'kendi', 'state': state})
        self.assertEqual(wrong.status_code, 200)
        self.assertFalse(wrong.json()['accepted'])
        self.assertEqual(wrong.json()['progress']['completed_items'], 0)

        state = wrong.json()['progress']['state']
        state.update({'phase': 'connection', 'selected_answer': 'tsokolate'})
        accepted = self.post({'candidate_answer': 'tsokolate', 'state': state})
        self.assertTrue(accepted.json()['accepted'])
        progress = StudentActivityProgress.objects.get(student=self.student, activity_key=self.key)
        self.assertEqual((progress.completed_items, progress.correct_items, progress.total_items), (1, 1, 4))
        self.assertEqual(progress.state['connected_answers'], {'tsokolate': 'tsokolate'})
        self.assertEqual(self.client.post(self.complete_url, data='{}', content_type='application/json').status_code, 400)
