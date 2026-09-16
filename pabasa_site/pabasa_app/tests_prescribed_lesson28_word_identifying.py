import json
import uuid

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import School, Section, StudentActivityProgress, User
from .prescribed_activity_catalog import prescribed_activity
from .views import _prescribed_activity_thumbnail_path


class PrescribedLesson28WordIdentifyingTests(TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex.upper()
        self.school = School.objects.create(name=f"Lesson 28 School {suffix}", code=f"L28-{suffix}")
        self.teacher = User.objects.create(
            custom_id=f"TCH-{suffix}", role="teacher", first_name="Teacher", last_name="TwentyEight",
            middle_initial="", suffix="", sex="female", birth_month=1, birth_day=1, birth_year=1990,
            email=f"teacher-{suffix}@example.com", password_hash="hashed", teacher_role="Teacher",
            school_record=self.school,
        )
        self.student = User.objects.create(
            custom_id=f"STU-{suffix}", role="student", first_name="Learner", last_name="TwentyEight",
            middle_initial="", suffix="", sex="male", birth_month=1, birth_day=1, birth_year=2018,
            email=f"student-{suffix}@example.com", password_hash="hashed", school_record=self.school,
        )
        section = Section.objects.create(
            school=self.school, class_code=f"CLASS-{suffix}", class_name="Grade 2", header="Reading",
            description="", teacher=self.teacher, subject="English", is_active=True,
        )
        section.add_student(self.student)
        session = self.client.session
        session.update({'user_id': self.student.id, 'user_role': 'student', 'email': self.student.email})
        session.save()
        self.student.active_session_key = session.session_key
        self.student.last_activity = timezone.now()
        self.student.save(update_fields=['active_session_key', 'last_activity', 'updated_at'])
        self.url = reverse('prescribed_activity_progress', kwargs={'activity_key': 'lesson-28-gawain-2'})

    def post_action(self, **payload):
        return self.client.post(self.url, data=json.dumps(payload), content_type='application/json')

    def test_catalog_matches_all_five_reference_rows_and_has_no_images(self):
        activity = prescribed_activity('lesson-28-gawain-2')
        self.assertEqual(activity['session_number'], 12)
        self.assertEqual(activity['lesson_number'], 28)
        self.assertEqual(activity['gawain_number'], 2)
        self.assertEqual([item['choices'] for item in activity['items']], [
            ['sun', 'sit'], ['set', 'let'], ['sat', 'met'], ['set', 'set'], ['lit', 'let'],
        ])
        self.assertEqual(_prescribed_activity_thumbnail_path(activity), '')

    def test_student_page_exposes_text_choices_without_picture_elements(self):
        response = self.client.get(reverse(
            'prescribed_activity_page', kwargs={'activity_key': 'lesson-28-gawain-2'},
        ))
        self.assertEqual(response.status_code, 200)
        payload = response.context['prescribed_activity_data']
        self.assertEqual([item['choices'] for item in payload['items']], [
            ['sun', 'sit'], ['set', 'let'], ['sat', 'met'], ['set', 'set'], ['lit', 'let'],
        ])
        self.assertNotContains(response, '<img')

    def test_word_is_randomized_retried_and_progresses_after_correct_speech(self):
        started = self.post_action(action='begin', item_index=0)
        self.assertEqual(started.status_code, 200)
        target = started.json()['target_word']
        self.assertIn(target, {'sun', 'sit'})

        wrong_word = 'sit' if target == 'sun' else 'sun'
        wrong = self.post_action(action='answer', item_index=0, heard=wrong_word)
        self.assertFalse(wrong.json()['accepted'])
        self.assertNotEqual(wrong.json()['target_word'], target)

        resumed = self.post_action(action='begin', item_index=0)
        self.assertEqual(resumed.json()['target_word'], wrong.json()['target_word'])
        correct = self.post_action(action='answer', item_index=0, heard=resumed.json()['target_word'])
        self.assertTrue(correct.json()['accepted'])
        self.assertEqual(correct.json()['progress']['completed_items'], 1)
        self.assertIn(correct.json()['target_word'], {'set', 'let'})

        for item_index in range(1, 5):
            current = self.post_action(action='begin', item_index=item_index)
            target = current.json()['target_word']
            response = self.post_action(action='answer', item_index=item_index, heard=target)
            self.assertTrue(response.json()['accepted'])

        progress = StudentActivityProgress.objects.get(student=self.student, activity_key='lesson-28-gawain-2')
        self.assertTrue(progress.activity_completed)
        self.assertEqual(progress.completed_items, 5)
        completion = self.client.post(
            reverse('prescribed_activity_complete', kwargs={'activity_key': 'lesson-28-gawain-2'}),
            data='{}', content_type='application/json',
        )
        self.assertEqual(completion.status_code, 200)
