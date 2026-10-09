import uuid
from django.db import IntegrityError
from django.db import transaction
from django.test import TestCase
from .models import User, PrescribedReadingAttempt, PrescribedReadingValidationLabel

class ValidationWorkflowTests(TestCase):
    def setUp(self):
        def make(custom_id, role):
            return User.objects.create(custom_id=custom_id, role=role, first_name='Validation', last_name=custom_id, sex='X', birth_month=1, birth_day=1, birth_year=2015, email=f'{custom_id}@example.test', password_hash='x')
        self.student = make('VAL-STUDENT', 'student')
        self.reviewer = make('VAL-REVIEWER', 'teacher')
        self.other = make('VAL-OTHER', 'teacher')
        self.attempt = PrescribedReadingAttempt.objects.create(student=self.student, activity_key='session-5-lesson-14-gawain-4', item_index=8, attempt_id=uuid.uuid4(), expected_text='sa bahay', audio_file='activity_recordings/test.webm')

    def test_independent_duplicate_prevention_and_labels(self):
        PrescribedReadingValidationLabel.objects.create(attempt=self.attempt, reviewer=self.reviewer, label='YELLOW')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PrescribedReadingValidationLabel.objects.create(attempt=self.attempt, reviewer=self.reviewer, label='GREEN')
        PrescribedReadingValidationLabel.objects.create(attempt=self.attempt, reviewer=self.other, label='GREEN')
        self.assertEqual(self.attempt.validation_labels.count(), 2)
