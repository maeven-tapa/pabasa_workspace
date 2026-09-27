import json
import uuid

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import School, StudentActivityProgress, User


class PrescribedLesson19Gawain4RestartTests(TestCase):
    key = 'session-7-lesson-19-gawain-4'

    def setUp(self):
        token = uuid.uuid4().hex
        school = School.objects.create(name=f'Lesson 19 {token}', code=f'L19-{token}')
        self.student = User.objects.create(
            custom_id=f'STU-{token}', role='student', first_name='Lesson 19', last_name='Learner',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1,
            birth_year=2018, email=f'lesson19-g4-{token}@example.com', password_hash='hashed',
            school_record=school,
        )
        session = self.client.session
        session.update({'user_id': self.student.id, 'user_role': 'student', 'email': self.student.email})
        session.save()
        self.student.active_session_key = session.session_key
        self.student.last_activity = timezone.now()
        self.student.save(update_fields=['active_session_key', 'last_activity', 'updated_at'])
        self.url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.key})

    def post(self, body):
        return self.client.post(self.url, data=json.dumps(body), content_type='application/json')

    def test_restart_returns_activity_to_intro_even_after_saved_progress(self):
        progressed = self.post({
            'state': {'phase': 'oral_reading', 'completed_oral_reads': [0], 'state_version': 1},
        })
        self.assertEqual(progressed.status_code, 200)
        self.assertEqual(progressed.json()['progress']['state']['phase'], 'letter_ordering')

        restarted = self.post({'reset': True})

        self.assertEqual(restarted.status_code, 200)
        payload = restarted.json()['progress']
        self.assertFalse(payload['activity_completed'])
        self.assertEqual(payload['completed_items'], 0)
        self.assertEqual(payload['state']['phase'], 'intro')
        self.assertEqual(payload['state']['current_item_index'], 0)
        self.assertEqual(payload['state']['completed_oral_reads'], [])
        self.assertEqual(payload['state']['selected_tile_order'], [])
        self.assertEqual(payload['state']['completed_correct_words'], [])
        saved = StudentActivityProgress.objects.get(student=self.student, activity_key=self.key)
        self.assertFalse(saved.activity_completed)
        self.assertEqual(saved.current_index, 0)
        self.assertEqual(saved.completed_items, 0)
