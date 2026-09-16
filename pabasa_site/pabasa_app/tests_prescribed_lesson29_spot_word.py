import json
import uuid

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import School, Section, StudentActivityProgress, User
from .prescribed_activity_catalog import prescribed_activity


class PrescribedLesson29SpotWordTests(TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex.upper()
        school = School.objects.create(name=f"Lesson 29 Spot School {suffix}", code=f"L29S-{suffix}")
        teacher = User.objects.create(
            custom_id=f"TCH-{suffix}", role="teacher", first_name="Teacher", last_name="SpotWord",
            middle_initial="", suffix="", sex="female", birth_month=1, birth_day=1, birth_year=1990,
            email=f"teacher-{suffix}@example.com", password_hash="hashed", teacher_role="Teacher",
            school_record=school,
        )
        self.student = User.objects.create(
            custom_id=f"STU-{suffix}", role="student", first_name="Learner", last_name="SpotWord",
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
        self.progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': 'lesson-29-gawain-2'})
        self.complete_url = reverse('prescribed_activity_complete', kwargs={'activity_key': 'lesson-29-gawain-2'})

    def post_action(self, **payload):
        return self.client.post(self.progress_url, data=json.dumps(payload), content_type='application/json')

    def test_reference_grid_words_and_session_metadata(self):
        activity = prescribed_activity('lesson-29-gawain-2')
        self.assertEqual((activity['session_number'], activity['lesson_number'], activity['gawain_number']), (13, 29, 2))
        self.assertEqual(activity['words'], ['mat', 'sell', 'lit', 'till', 'last', 'stem', 'list', 'tell', 'sit'])
        response = self.client.get(reverse(
            'prescribed_activity_page', kwargs={'activity_key': 'lesson-29-gawain-2'},
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['prescribed_activity_data']['words'], activity['words'])

    def test_words_are_spoken_in_random_order_and_wrong_choice_retries_same_prompt(self):
        started = self.post_action(action='begin', item_index=0)
        self.assertEqual(started.status_code, 200)
        first = started.json()['target_word']
        state = started.json()['progress']['state']
        self.assertIn(first, prescribed_activity('lesson-29-gawain-2')['words'])
        self.assertEqual(state['word_order'][0], first)

        wrong_word = next(word for word in prescribed_activity('lesson-29-gawain-2')['words'] if word != first)
        wrong = self.post_action(action='choose', item_index=0, word=wrong_word)
        self.assertFalse(wrong.json()['accepted'])
        self.assertEqual(wrong.json()['wrong_word'], wrong_word)
        self.assertEqual(wrong.json()['progress']['completed_items'], 0)
        self.assertEqual(wrong.json()['target_word'], first)

        correct = self.post_action(action='choose', item_index=0, word=first)
        self.assertTrue(correct.json()['accepted'])
        self.assertEqual(correct.json()['progress']['state']['selected_words'], [first])
        self.assertEqual(correct.json()['progress']['completed_items'], 1)

    def test_all_words_must_be_correct_before_completion(self):
        early = self.client.post(self.complete_url, data='{}', content_type='application/json')
        self.assertEqual(early.status_code, 400)
        order = None
        for index in range(9):
            started = self.post_action(action='begin', item_index=index)
            self.assertEqual(started.status_code, 200)
            order = started.json()['progress']['state']['word_order']
            chosen = self.post_action(action='choose', item_index=index, word=order[index])
            self.assertTrue(chosen.json()['accepted'])
        self.assertEqual(set(order), set(prescribed_activity('lesson-29-gawain-2')['words']))
        progress = StudentActivityProgress.objects.get(student=self.student, activity_key='lesson-29-gawain-2')
        self.assertTrue(progress.activity_completed)
        self.assertEqual(progress.completed_items, 9)
        complete = self.client.post(self.complete_url, data='{}', content_type='application/json')
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(complete.json()['result']['items_completed'], 9)
