import json
import uuid

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import School, Section, StudentActivityProgress, User
from .prescribed_activity_catalog import prescribed_activity


class PrescribedLesson29OralBlankTests(TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex.upper()
        school = School.objects.create(name=f"Lesson 29 School {suffix}", code=f"L29-{suffix}")
        teacher = User.objects.create(
            custom_id=f"TCH-{suffix}", role="teacher", first_name="Teacher", last_name="TwentyNine",
            middle_initial="", suffix="", sex="female", birth_month=1, birth_day=1, birth_year=1990,
            email=f"teacher-{suffix}@example.com", password_hash="hashed", teacher_role="Teacher",
            school_record=school,
        )
        self.student = User.objects.create(
            custom_id=f"STU-{suffix}", role="student", first_name="Learner", last_name="TwentyNine",
            middle_initial="", suffix="", sex="male", birth_month=1, birth_day=1, birth_year=2018,
            email=f"student-{suffix}@example.com", password_hash="hashed", school_record=school,
        )
        section = Section.objects.create(
            school=school, class_code=f"CLASS-{suffix}", class_name="Grade 2", header="Reading",
            description="", teacher=teacher, subject="English", is_active=True,
        )
        section.add_student(self.student)
        session = self.client.session
        session.update({'user_id': self.student.id, 'user_role': 'student', 'email': self.student.email})
        session.save()
        self.student.active_session_key = session.session_key
        self.student.last_activity = timezone.now()
        self.student.save(update_fields=['active_session_key', 'last_activity', 'updated_at'])
        self.progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': 'lesson-29-gawain-1'})
        self.complete_url = reverse('prescribed_activity_complete', kwargs={'activity_key': 'lesson-29-gawain-1'})

    def post_action(self, **payload):
        return self.client.post(self.progress_url, data=json.dumps(payload), content_type='application/json')

    def test_catalog_matches_reference_sentence_and_image_order(self):
        activity = prescribed_activity('lesson-29-gawain-1')
        self.assertEqual((activity['session_number'], activity['lesson_number'], activity['gawain_number']), (13, 29, 1))
        self.assertEqual([item['answer'] for item in activity['items']], ['list', 'last', 'stem', 'mill', 'fog'])
        self.assertEqual([item['image_path'].rsplit('/', 1)[-1] for item in activity['items']],
                         ['list.png', 'last.png', 'stem.png', 'mill.png', 'fog.png'])

    def test_student_page_shows_one_sentence_without_answer_key(self):
        response = self.client.get(reverse(
            'prescribed_activity_page', kwargs={'activity_key': 'lesson-29-gawain-1'},
        ))
        self.assertEqual(response.status_code, 200)
        payload = response.context['prescribed_activity_data']
        self.assertEqual(len(payload['items']), 5)
        self.assertEqual(payload['items'][0]['before'], 'Matt is on the ')
        self.assertNotIn('answer', str(payload))
        self.assertNotContains(response, 'Matt is on the list')

    def test_hints_reveal_one_letter_every_two_misses_then_offer_audio(self):
        expected_hints = ['', 'l', 'l', 'li', 'li', 'lis', 'lis', 'list', 'list', 'list']
        expected_audio = [False] * 9 + [True]
        for attempt, (hint, audio) in enumerate(zip(expected_hints, expected_audio), start=1):
            response = self.post_action(action='answer', item_index=0, heard='wrong')
            self.assertEqual(response.status_code, 200)
            state = response.json()['progress']['state']
            self.assertEqual(state['hint'], hint, f'attempt {attempt}')
            self.assertEqual(state['help_visible'], audio, f'attempt {attempt}')
            self.assertEqual(state['help_word'], 'list' if audio else '', f'attempt {attempt}')

    def test_correct_answers_advance_each_item_and_complete_activity(self):
        early = self.client.post(self.complete_url, data='{}', content_type='application/json')
        self.assertEqual(early.status_code, 400)
        for index, answer in enumerate(['list', 'last', 'stem', 'mill', 'fog']):
            result = self.post_action(action='answer', item_index=index, heard=answer)
            self.assertEqual(result.status_code, 200)
            self.assertTrue(result.json()['accepted'])
            self.assertEqual(result.json()['progress']['completed_items'], index + 1)
        progress = StudentActivityProgress.objects.get(student=self.student, activity_key='lesson-29-gawain-1')
        self.assertTrue(progress.activity_completed)
        self.assertEqual(progress.completed_items, 5)
        completion = self.client.post(self.complete_url, data='{}', content_type='application/json')
        self.assertEqual(completion.status_code, 200)
        self.assertEqual(completion.json()['result']['items_completed'], 5)
