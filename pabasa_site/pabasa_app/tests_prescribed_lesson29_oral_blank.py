import json
import uuid
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import School, Section, StudentActivityProgress, User
from .prescribed_activity_catalog import prescribed_activity
from .views import _local_prescribed_audio_file, reading_transcribe_api


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
        from .prescribed_test_fixtures import prescribed_term_fixture
        prescribed_term_fixture(self.student)
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
        self.assertEqual(payload['items'][0]['answer'], 'list')
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

    def test_sentence_reading_keeps_the_current_item_until_the_full_sentence_is_read(self):
        word_result = self.post_action(action='answer', item_index=0, heard='list')
        self.assertTrue(word_result.json()['accepted'])

        incomplete_result = self.post_action(
            action='sentence_reading', item_index=0, heard='Matt is on list',
        )
        self.assertFalse(incomplete_result.json()['accepted'])
        incomplete_state = incomplete_result.json()['progress']['state']
        self.assertEqual(incomplete_state['phase'], 'sentence_reading')
        self.assertEqual(incomplete_result.json()['progress']['completed_items'], 0)

        complete_result = self.post_action(
            action='sentence_reading', item_index=0, heard='Math is on the list',
        )
        self.assertTrue(complete_result.json()['accepted'])
        self.assertEqual(complete_result.json()['progress']['completed_items'], 1)

    def test_sentence_reading_rejects_mad_but_keeps_mat_and_math_for_matt(self):
        for index in (0, 1, 3):
            item = prescribed_activity('lesson-29-gawain-1')['items'][index]
            sentence = f"{item['before']}{item['answer']}{item['after']}"
            for name in ('mad', 'mat', 'math', 'Matt'):
                with self.subTest(item=index, name=name):
                    StudentActivityProgress.objects.filter(student=self.student).delete()
                    StudentActivityProgress.objects.create(
                        student=self.student, activity_key='lesson-29-gawain-1',
                        current_index=index, completed_items=index, correct_items=index, total_items=5,
                        state={'current_item': index, 'completed_items': index, 'phase': 'sentence_reading'},
                    )
                    result = self.post_action(
                        action='sentence_reading', item_index=index, heard=sentence.replace('Matt', name),
                    ).json()
                    self.assertEqual(result['accepted'], name != 'mad')
                    self.assertEqual(result['progress']['completed_items'], index + (name != 'mad'))

    def test_mill_accepts_the_common_meal_transcription(self):
        progress = StudentActivityProgress.objects.create(
            student=self.student,
            activity_key='lesson-29-gawain-1',
            current_index=3,
            completed_items=3,
            correct_items=3,
            total_items=5,
            state={'current_item': 3, 'completed_items': 3, 'phase': 'answering'},
        )
        response = self.post_action(action='answer', item_index=3, heard='meal')
        self.assertTrue(response.json()['accepted'])
        progress.refresh_from_db()
        self.assertEqual(progress.state['phase'], 'sentence_reading')

    def test_word_phase_rejects_complete_sentences_for_every_item(self):
        for index, item in enumerate(prescribed_activity('lesson-29-gawain-1')['items']):
            with self.subTest(item=index):
                StudentActivityProgress.objects.filter(student=self.student).delete()
                StudentActivityProgress.objects.create(
                    student=self.student, activity_key='lesson-29-gawain-1',
                    current_index=index, completed_items=index, correct_items=index, total_items=5,
                    state={'current_item': index, 'completed_items': index, 'phase': 'answering'},
                )
                sentence = f"{item['before']}{item['answer']}{item['after']}"
                response = self.post_action(action='answer', item_index=index, heard=sentence)
                self.assertEqual(response.status_code, 200)
                result = response.json()
                self.assertFalse(result['accepted'])
                self.assertEqual(result['progress']['state']['phase'], 'answering')
                self.assertEqual(result['progress']['completed_items'], index)
                word_response = self.post_action(action='answer', item_index=index, heard=item['answer'])
                self.assertTrue(word_response.json()['accepted'])
                self.assertEqual(word_response.json()['progress']['state']['phase'], 'sentence_reading')

    def test_word_phase_rejects_extra_words_and_repeated_answers(self):
        for heard in ('the list', 'list please', 'list list', 'Matt is on the list', 'last'):
            with self.subTest(heard=heard):
                result = self.post_action(action='answer', item_index=0, heard=heard).json()
                self.assertFalse(result['accepted'])
                self.assertEqual(result['progress']['state']['phase'], 'answering')

    def test_word_phase_accepts_case_spacing_and_punctuation(self):
        for heard in ('list', 'LIST!', '  List?  '):
            with self.subTest(heard=heard):
                self.post_action(reset=True)
                result = self.post_action(action='answer', item_index=0, heard=heard).json()
                self.assertTrue(result['accepted'])
                self.assertEqual(result['progress']['state']['phase'], 'sentence_reading')

    def test_completion_feedback_uses_the_existing_local_audio_file(self):
        audio_file = _local_prescribed_audio_file(
            'lesson-29-gawain-1', 'Great job! You completed all the sentences.',
        )
        self.assertIsNotNone(audio_file)
        self.assertEqual(audio_file.name, 'Great job! You completed Fill in the Blank..mp3')

    def test_correct_word_then_sentence_reading_advances_each_item_and_completes_activity(self):
        early = self.client.post(self.complete_url, data='{}', content_type='application/json')
        self.assertEqual(early.status_code, 400)
        items = [
            ('list', 'Matt is on the list.'),
            ('last', 'The last man is Matt.'),
            ('stem', 'The stem is green.'),
            ('mill', 'Matt sets the grain mill.'),
            ('fog', 'The city is covered in fog.'),
        ]
        for index, (answer, sentence) in enumerate(items):
            word_result = self.post_action(action='answer', item_index=index, heard=answer)
            self.assertEqual(word_result.status_code, 200)
            self.assertTrue(word_result.json()['accepted'])
            word_state = word_result.json()['progress']['state']
            self.assertEqual(word_state['phase'], 'sentence_reading')
            self.assertEqual(word_result.json()['progress']['completed_items'], index)

            sentence_result = self.post_action(action='sentence_reading', item_index=index, heard=sentence)
            self.assertEqual(sentence_result.status_code, 200)
            self.assertTrue(sentence_result.json()['accepted'])
            self.assertEqual(sentence_result.json()['progress']['completed_items'], index + 1)
        progress = StudentActivityProgress.objects.get(student=self.student, activity_key='lesson-29-gawain-1')
        self.assertTrue(progress.activity_completed)
        self.assertEqual(progress.completed_items, 5)
        completion = self.client.post(self.complete_url, data='{}', content_type='application/json')
        self.assertEqual(completion.status_code, 200)
        self.assertEqual(completion.json()['result']['items_completed'], 5)


@override_settings(GOOGLE_STT_API_KEY='', GOOGLE_CLOUD_PROJECT_ID='test-project')
class Lesson29WordCaptureTranscriptTests(SimpleTestCase):
    def test_word_capture_keeps_the_full_provider_transcript_for_activity_validation(self):
        for heard in ('list', 'Matt is on the list.', 'the list', 'meal'):
            with self.subTest(heard=heard), \
                 patch('pabasa_app.views._check_auth', return_value=True), \
                 patch('pabasa_app.views._enforce_student_access_for_request', return_value=None), \
                 patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=(heard, 'chirp_3', '')):
                request = RequestFactory().post('/api/reading/transcribe/', {
                    'audio': SimpleUploadedFile('word.webm', b'audio', content_type='audio/webm'),
                    'target_text': 'mill' if heard == 'meal' else 'list',
                    'language': 'English', 'mode': 'word',
                }, HTTP_X_PABASA_STT_MODEL='chirp_3', HTTP_X_PABASA_STT_PROVIDER='google')
                request._dont_enforce_csrf_checks = True
                response = reading_transcribe_api(request)
                self.assertEqual(response.status_code, 200, response.content)
                result = json.loads(response.content)
                self.assertEqual(result['raw_transcript'], heard)
                self.assertEqual(result['transcript'], heard)
