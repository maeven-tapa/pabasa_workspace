import uuid
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import School, StudentActivityProgress, User


class Session4Gawain5CompletionCardTests(TestCase):
    def setUp(self):
        token = uuid.uuid4().hex
        school = School.objects.create(name=f'S4 G5 {token}', code=f'S4G5-{token}')
        self.student = User.objects.create(
            custom_id=f'STU-{token}', role='student', first_name='Test', last_name='Learner',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1,
            birth_year=2018, email=f's4g5-{token}@example.test', password_hash='hashed',
            school_record=school,
        )
        session = self.client.session
        session.update({'user_id': self.student.id, 'user_role': 'student', 'email': self.student.email})
        session.save()

    def test_completed_activity_renders_completion_card_instead_of_redirecting(self):
        StudentActivityProgress.objects.create(
            student=self.student,
            activity_key='session-4-gawain-5',
            current_index=4,
            completed_items=4,
            correct_items=4,
            total_items=4,
            activity_completed=True,
            state={'current_item': 4, 'traces': [[]] * 12, 'phase': 'complete'},
        )

        with patch('pabasa_app.views._enforce_prescribed_activity_sequence', return_value=None), \
                patch('pabasa_app.views._dashboard_context', return_value={}):
            response = self.client.get(reverse('session_4_gawain_5_page'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tapos na ang gawain! 🎉')
        self.assertContains(response, 'Mahusay! Nakumpleto mo na ang aktibidad.')
        self.assertContains(response, 'BALIK SA AKING ARALIN')
        self.assertContains(response, 'data.progress?.activity_completed')
