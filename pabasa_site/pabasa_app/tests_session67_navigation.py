import json
import uuid

from django.test import TestCase
from django.urls import reverse

from .models import School, StudentActivityProgress, User
from .prescribed_activity_catalog import prescribed_activity
from .prescribed_test_fixtures import prescribed_term_fixture
from .views import _normalized_starting_syllable_state


class Session7Lesson19RestartTests(TestCase):
    def test_gawain1_restart_clears_completed_progress_and_attempts(self):
        token = uuid.uuid4().hex
        school = School.objects.create(name=f'Restart {token}', code=f'R-{token}')
        student = User.objects.create(
            custom_id=f'STU-{token}', role='student', first_name='Test', last_name='Reader',
            sex='female', birth_month=1, birth_day=1, birth_year=2018,
            email=f'restart-{token}@example.com', password_hash='hashed', school_record=school,
        )
        prescribed_term_fixture(student)
        session = self.client.session
        session.update({'user_id': student.id, 'user_role': 'student', 'email': student.email})
        session.save()
        key = 'session-7-lesson-19-gawain-1'
        activity = prescribed_activity(key)
        # Seed a completed activity through the endpoint, using its normal
        # ordered reading/answer transitions rather than editing progress rows.
        url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        state = _normalized_starting_syllable_state(activity, {})
        for index, item in enumerate(activity['items']):
            state.update(phase='oral_reading', current_item_index=index,
                         completed_oral_reads=list(range(index + 1)))
            reading = self.client.post(url, json.dumps({'state': state}), content_type='application/json')
            self.assertEqual(reading.status_code, 200)
            state = reading.json()['progress']['state']
            answer = self.client.post(url, json.dumps({'state': state, 'candidate_answer': item['answer']}),
                                      content_type='application/json')
            self.assertEqual(answer.status_code, 200)
            self.assertTrue(answer.json()['accepted'])
            state = answer.json()['progress']['state']
        completion = self.client.post(reverse('prescribed_activity_complete', kwargs={'activity_key': key}),
                                      '{}', content_type='application/json')
        self.assertEqual(completion.status_code, 200)

        reset = self.client.post(url, json.dumps({'reset': True}), content_type='application/json')
        self.assertEqual(reset.status_code, 200)
        progress = StudentActivityProgress.objects.get(student=student, activity_key=key)
        self.assertFalse(progress.activity_completed)
        self.assertEqual((progress.current_index, progress.completed_items, progress.correct_items), (0, 0, 0))
        self.assertEqual(progress.state['phase'], 'intro')
        self.assertEqual(progress.state['correct_answers'], [])
        self.assertEqual(progress.state['completed_oral_reads'], [])
        self.assertFalse(any(progress.state['stt_attempts'].values()))
        self.assertFalse(any(progress.state['tts_plays'].values()))
