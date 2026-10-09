from django.db import IntegrityError
from django.test import TestCase

from .models import PrescribedReadingAttempt, SchoolCalendar, User


class PrescribedReadingAttemptModelTests(TestCase):
    def setUp(self):
        self.calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=1)
        self.student = User.objects.create(
            custom_id='READ-TEST-1', role='student', first_name='Test', last_name='Reader',
            sex='U', birth_month=1, birth_day=1, birth_year=2018,
            email='reading-attempt-test@example.com', password_hash='test',
        )

    def test_attempt_history_keeps_distinct_attempt_numbers(self):
        base = dict(
            student=self.student, school_calendar=self.calendar, term=1,
            activity_key='session-5-lesson-14-gawain-4', item_index=0,
            expected_text='kuko', audio_file='activity_recordings/test.webm',
        )
        first = PrescribedReadingAttempt.objects.create(attempt_number=1, **base)
        second = PrescribedReadingAttempt.objects.create(attempt_number=2, **base)
        self.assertNotEqual(first.attempt_id, second.attempt_id)
        self.assertEqual(PrescribedReadingAttempt.objects.filter(item_index=0).count(), 2)

    def test_duplicate_attempt_number_is_rejected(self):
        base = dict(
            student=self.student, school_calendar=self.calendar, term=1,
            activity_key='session-5-lesson-14-gawain-4', item_index=0,
            attempt_number=1, expected_text='kuko',
            audio_file='activity_recordings/test.webm',
        )
        PrescribedReadingAttempt.objects.create(**base)
        with self.assertRaises(IntegrityError):
            PrescribedReadingAttempt.objects.create(**base)
