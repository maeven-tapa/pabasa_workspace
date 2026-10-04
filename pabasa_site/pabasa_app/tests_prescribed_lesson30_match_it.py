import json
import uuid
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import School, Section, StudentActivityProgress, User
from .prescribed_activity_catalog import prescribed_activity
from .prescribed_test_fixtures import prescribed_term_fixture
from .views import _local_prescribed_audio_file


class PrescribedLesson30MatchItTests(TestCase):
    activity_key = 'lesson-30-gawain-1'

    def setUp(self):
        suffix = uuid.uuid4().hex.upper()
        school = School.objects.create(name=f'Lesson 30 Match School {suffix}', code=f'L30M-{suffix}')
        teacher = User.objects.create(
            custom_id=f'TCH-{suffix}', role='teacher', first_name='Teacher', last_name='MatchIt',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1, birth_year=1990,
            email=f'teacher-{suffix}@example.com', password_hash='hashed', teacher_role='Teacher',
            school_record=school,
        )
        self.student = User.objects.create(
            custom_id=f'STU-{suffix}', role='student', first_name='Learner', last_name='MatchIt',
            middle_initial='', suffix='', sex='male', birth_month=1, birth_day=1, birth_year=2018,
            email=f'student-{suffix}@example.com', password_hash='hashed', school_record=school,
        )
        section = Section.objects.create(
            school=school, class_code=f'CLASS-{suffix}', class_name='Grade 2', header='Reading',
            description='', teacher=teacher, subject='English', is_active=True,
        )
        section.add_student(self.student)
        session = self.client.session
        session.update({'user_id': self.student.id, 'user_role': 'student', 'email': self.student.email})
        session.save()
        self.student.active_session_key = session.session_key
        self.student.last_activity = timezone.now()
        self.student.save(update_fields=['active_session_key', 'last_activity', 'updated_at'])
        prescribed_term_fixture(self.student, teacher=teacher, section=section)
        self.progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.activity_key})
        self.complete_url = reverse('prescribed_activity_complete', kwargs={'activity_key': self.activity_key})

    def post_state(self, state):
        return self.client.post(self.progress_url, data=json.dumps({'state': state}), content_type='application/json')

    def test_reference_content_and_student_page(self):
        activity = prescribed_activity(self.activity_key)
        self.assertEqual((activity['session_number'], activity['lesson_number'], activity['gawain_number']), (14, 30, 1))
        self.assertEqual(activity['word_bank'], ['pet', 'mat', 'pat', 'little', 'happy'])
        self.assertEqual([item['word'] for item in activity['items']], ['mat', 'happy', 'pet', 'pat', 'little'])
        response = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.activity_key}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pabasa_app/prescribed_match_it_lesson30_activity1_page.html')
        self.assertEqual(response.context['prescribed_activity_data']['progress']['total_items'], 5)
        self.assertEqual(response.context['prescribed_activity_data']['picture_attempt_limit'], 2)

    def test_second_wrong_picture_advances_without_requiring_a_reread(self):
        skipped = self.post_state({
            'phase': 'oral_reading',
            'unlocked_oral_words': ['pet'],
            'matches': {},
            'picture_attempts': {'pet': 2},
            'skipped_picture_words': ['pet'],
            'state_version': 0,
        })
        self.assertEqual(skipped.status_code, 200, skipped.content)
        progress = skipped.json()['progress']
        self.assertEqual(progress['completed_items'], 1)
        self.assertEqual(progress['correct_items'], 0)
        self.assertEqual(progress['state']['skipped_picture_words'], ['pet'])
        self.assertEqual(progress['state']['phase'], 'oral_reading')
        self.assertFalse(progress['state']['needs_reread'])

    def test_picture_cannot_be_skipped_before_two_wrong_attempts(self):
        skipped = self.post_state({
            'phase': 'oral_reading',
            'unlocked_oral_words': ['pet'],
            'matches': {},
            'picture_attempts': {'pet': 1},
            'skipped_picture_words': ['pet'],
            'state_version': 0,
        })
        self.assertEqual(skipped.status_code, 400)

    def test_must_read_then_match_in_order_and_retry_wrong_picture(self):
        read_first = self.post_state({'phase': 'matching', 'unlocked_oral_words': ['pet'], 'matches': {}})
        self.assertEqual(read_first.status_code, 200)
        read_state = read_first.json()['progress']['state']
        no_read = self.post_state({'phase': 'matching', 'unlocked_oral_words': [], 'matches': {'pet': 'pet'}})
        self.assertEqual(no_read.status_code, 200)
        self.assertEqual(no_read.json()['progress']['completed_items'], 0)
        self.assertEqual(no_read.json()['progress']['state']['matches'], {})

        # Continue from server-issued version; browsers do the same when saving.
        read_state['state_version'] = no_read.json()['progress']['state']['state_version']
        matched = self.post_state({'phase': 'oral_reading', 'unlocked_oral_words': ['pet'], 'matches': {'pet': 'pet'},
                                   'state_version': read_state['state_version']})
        self.assertEqual(matched.status_code, 200)
        self.assertEqual(matched.json()['progress']['completed_items'], 1)
        self.assertEqual(matched.json()['progress']['state']['current_oral_word_index'], 1)

        next_read = self.post_state({
            'phase': 'matching', 'unlocked_oral_words': ['pet', 'mat'], 'matches': {'pet': 'pet'},
            'state_version': matched.json()['progress']['state']['state_version'],
        })
        self.assertEqual(next_read.status_code, 200)
        self.assertEqual(next_read.json()['progress']['state']['current_oral_word_index'], 1)

    def test_completion_requires_every_word_and_picture(self):
        response = self.client.post(self.complete_url, data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 400)

        activity = prescribed_activity(self.activity_key)
        state = {'phase': 'oral_reading', 'unlocked_oral_words': [], 'matches': {}, 'state_version': 0}
        for word in activity['word_bank']:
            state['phase'] = 'matching'
            state['unlocked_oral_words'].append(word)
            read = self.post_state(state)
            self.assertEqual(read.status_code, 200, read.content)
            item = next(item for item in activity['items'] if item['word'] == word)
            state = read.json()['progress']['state']
            state['phase'] = 'oral_reading'
            state['unlocked_oral_words'].append(word) if word not in state['unlocked_oral_words'] else None
            state['matches'][item['id']] = word
            matched = self.post_state(state)
            self.assertEqual(matched.status_code, 200, matched.content)
            state = matched.json()['progress']['state']

        progress = StudentActivityProgress.objects.get(student=self.student, activity_key=self.activity_key)
        self.assertEqual(progress.completed_items, 5)
        response = self.client.post(self.complete_url, data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 200)
        progress.refresh_from_db()
        self.assertTrue(progress.activity_completed)
        self.assertEqual(progress.total_items, 5)

    def test_completion_feedback_uses_the_existing_match_it_audio(self):
        script = Path(
            settings.BASE_DIR,
            'pabasa_app/static/pabasa_app/js/prescribed_match_it_lesson30_activity1.js',
        ).read_text(encoding='utf-8')
        self.assertIn("announce('Great job! You completed the activity.');", script)
        audio_file = _local_prescribed_audio_file(
            self.activity_key, 'Great job! You completed the activity.',
        )
        self.assertIsNotNone(audio_file)
        self.assertEqual(audio_file.name, 'Great job! You completed Match It..mp3')

    def test_second_wrong_picture_uses_the_next_word_audio(self):
        script = Path(
            settings.BASE_DIR,
            'pabasa_app/static/pabasa_app/js/prescribed_match_it_lesson30_activity1.js',
        ).read_text(encoding='utf-8')
        self.assertIn('announce("Let\'s move to the next word.")', script)
        audio_file = _local_prescribed_audio_file(self.activity_key, "Let's move to the next word.")
        self.assertIsNotNone(audio_file)
        self.assertEqual(audio_file.name, "Let's move to the next word..mp3")
        self.assertIn(
            "new Set([...Object.values(s.matches||{}),...(s.skipped_picture_words||[])]).size===words.length",
            script,
        )

    def test_stage_uses_prominent_instructions_without_a_game_title(self):
        script = Path(
            settings.BASE_DIR,
            'pabasa_app/static/pabasa_app/js/prescribed_match_it_lesson30_activity1.js',
        ).read_text(encoding='utf-8')
        self.assertNotIn('<h1 class="title">Match It!</h1>', script)
        self.assertIn('Choose the picture that matches the word.', script)
        self.assertIn('Read the word aloud first. Then choose the matching picture.', script)

    def test_matching_phase_places_word_beside_original_size_picture_choices(self):
        script = Path(
            settings.BASE_DIR,
            'pabasa_app/static/pabasa_app/js/prescribed_match_it_lesson30_activity1.js',
        ).read_text(encoding='utf-8')
        template = Path(
            settings.BASE_DIR,
            'pabasa_app/templates/pabasa_app/prescribed_match_it_lesson30_activity1_page.html',
        ).read_text(encoding='utf-8')
        self.assertIn('.matching-layout{--choice-size:', template)
        self.assertIn('display:grid;grid-template-columns:', template)
        self.assertIn('.matching-layout .pictures{grid-template-columns:1fr;', template)
        self.assertIn('class="instruction matching-instruction">Choose the picture that matches the word.</p>', script)
        self.assertIn('.stage.matching-phase{top:calc(50% + 24px);width:min(1000px,calc(100% - 32px));height:min(840px,calc(100dvh - 112px))}', template)
        self.assertIn('.matching-layout .word{position:absolute;top:50%;', template)
        self.assertIn('.matching-layout .matching-instruction{position:absolute;', template)
        self.assertIn('transform:translateX(clamp(48px,6vw,80px))', template)
        self.assertIn('--choice-size:min(clamp(130px,17vh,165px),calc((100dvh - 340px)/5))', template)
        self.assertIn('.matching-layout .picture{width:var(--choice-size);min-width:var(--choice-size);height:var(--choice-size);', template)
        self.assertIn('padding:8px;overflow:hidden}', template)
        self.assertIn('.matching-layout .picture img{width:82%;height:82%;', template)
