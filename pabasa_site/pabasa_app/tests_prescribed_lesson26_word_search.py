import json
import uuid
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import School, Section, StudentActivityProgress, User
from .prescribed_activity_catalog import prescribed_activity
from .reading_stt import analyze_reading


class PrescribedLesson26WordSearchTests(TestCase):
    activity_key = 'lesson-26-gawain-1'

    def setUp(self):
        suffix = uuid.uuid4().hex.upper()
        school = School.objects.create(name=f'Lesson 26 Word Search {suffix}', code=f'L26W-{suffix}')
        teacher = User.objects.create(
            custom_id=f'TCH-{suffix}', role='teacher', first_name='Teacher', last_name='WordSearch',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1, birth_year=1990,
            email=f'teacher-{suffix}@example.com', password_hash='hashed', teacher_role='Teacher',
            school_record=school,
        )
        self.student = User.objects.create(
            custom_id=f'STU-{suffix}', role='student', first_name='Learner', last_name='WordSearch',
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
        self.progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.activity_key})
        self.activity2_key = 'lesson-26-gawain-2'
        self.activity2_progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.activity2_key})
        self.lesson27_key = 'lesson-27-gawain-1'
        self.lesson27_progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.lesson27_key})
        self.lesson28_activity1_key = 'lesson-28-gawain-1'
        self.lesson28_activity2_key = 'lesson-28-gawain-2'
        self.lesson28_activity1_progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.lesson28_activity1_key})
        self.lesson28_activity2_progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.lesson28_activity2_key})
        self.lesson29_activity1_key = 'lesson-29-gawain-1'
        self.lesson29_activity2_key = 'lesson-29-gawain-2'
        self.lesson29_activity1_progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.lesson29_activity1_key})
        self.lesson29_activity2_progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.lesson29_activity2_key})
        self.lesson30_activity2_key = 'lesson-30-gawain-2'
        self.lesson30_activity2_progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.lesson30_activity2_key})
        self.lesson30_activity1_key = 'lesson-30-gawain-1'
        self.lesson30_activity1_progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.lesson30_activity1_key})
        self.lesson30_activity3_key = 'lesson-30-gawain-3'
        self.lesson30_activity3_progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.lesson30_activity3_key})
        self.lesson31_activity1_key = 'lesson-31-gawain-1'
        self.lesson31_activity1_progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.lesson31_activity1_key})
        self.lesson31_activity2_key = 'lesson-31-gawain-2'
        self.lesson31_activity2_progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.lesson31_activity2_key})
        self.lesson31_activity3_key = 'lesson-31-gawain-3'
        self.lesson31_activity3_progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.lesson31_activity3_key})
        self.lesson31_activity4_key = 'lesson-31-gawain-4'
        self.lesson31_activity4_progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.lesson31_activity4_key})

    def test_activity_page_exposes_existing_english_transcription_route(self):
        response = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.activity_key}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pabasa_app/prescribed_word_search_activity_page.html')
        self.assertContains(response, 'id="lesson26-start"')
        self.assertContains(response, 'id="lesson26-start-button"')
        self.assertContains(response, 'id="lesson26-later-button"')
        self.assertContains(response, 'Find the words on the grid.')
        self.assertEqual(
            response.context['prescribed_activity_data']['transcribe_url'],
            reverse('reading_transcribe_api'),
        )
        self.assertEqual(
            response.context['prescribed_activity_data']['read_aloud_url'],
            reverse('reading_read_aloud_api'),
        )
        script = Path(settings.BASE_DIR, 'pabasa_app/static/pabasa_app/js/prescribed_word_search.js').read_text(encoding='utf-8')
        self.assertIn("form.append('language', 'English')", script)
        self.assertIn('result.raw_transcript || result.transcript', script)
        self.assertNotIn('result.complete &&', script)
        self.assertIn('acceptedWords.includes(normalizedWord(token))', script)
        self.assertIn('Word Search. Find the words on the grid.', script)
        self.assertIn('addEventListener(\'click\', () => readAloud(targetWord))', script)
        self.assertIn("target === 'mat' ? ['mat', 'math'] : [target]", script)
        self.assertIn('lesson26-complete-message', script)
        self.assertIn('JSON.stringify({reset: true})', script)

    def test_back_reset_clears_only_this_students_lesson26_progress(self):
        progress = StudentActivityProgress.objects.create(
            student=self.student,
            activity_key=self.activity_key,
            current_index=2,
            completed_items=2,
            total_items=5,
            state={'matches': {'0': {'start': [0, 0], 'end': [0, 2]}}, 'reading': {'0': True}},
        )
        response = self.client.post(
            self.progress_url,
            data=json.dumps({'reset': True}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertFalse(StudentActivityProgress.objects.filter(pk=progress.pk).exists())

    def test_spoken_word_analysis_accepts_exact_lesson_words_and_rejects_substrings(self):
        for word in prescribed_activity(self.activity_key)['words']:
            self.assertTrue(analyze_reading(word, 0, word, 'en-PH')['complete'], word)
        self.assertFalse(analyze_reading('mat', 0, 'matter', 'en-PH')['complete'])

    def test_successful_read_unlocks_only_that_word_for_grid_search(self):
        response = self.client.post(
            self.progress_url,
            data=json.dumps({'word_index': 0, 'reading_result': True}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        progress = StudentActivityProgress.objects.get(student=self.student, activity_key=self.activity_key)
        self.assertTrue(progress.state['reading']['0'])
        self.assertFalse(progress.state['reading'].get('1', False))

    def test_activity2_uses_its_own_english_lesson26_ui_and_google_read_aloud_route(self):
        response = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.activity2_key}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pabasa_app/prescribed_fill_blank_lesson26_activity2_page.html')
        self.assertEqual(response.context['prescribed_activity_data']['read_aloud_url'], reverse('reading_read_aloud_api'))
        self.assertEqual(response.context['prescribed_activity_data']['transcribe_url'], reverse('reading_transcribe_api'))
        script = Path(settings.BASE_DIR, 'pabasa_app/static/pabasa_app/js/prescribed_fill_blank_lesson26_activity2.js').read_text(encoding='utf-8')
        self.assertIn("playTts('Fill in the Blanks. Read the words, then fill in the blanks.')", script)
        self.assertIn("target === 'mat' ? ['mat','math'] : target === 'hat' ? ['hat','hot'] : [target]", script)
        self.assertIn("replace(/\\bhot\\b/g, 'hat')", script)
        self.assertNotIn('speechSynthesis', script)
        self.assertIn('word-chip:hover:not(:disabled)', response.content.decode())
        self.assertIn('outline:0;border-color:var(--teal)', response.content.decode())

    def test_activity2_back_reset_clears_its_saved_progress(self):
        progress = StudentActivityProgress.objects.create(
            student=self.student, activity_key=self.activity2_key,
            current_index=1, completed_items=1, total_items=4,
            state={'phase': 'sentence', 'completed_items': 1, 'placements': {'0': 'cat'}},
        )
        response = self.client.post(
            self.activity2_progress_url, data=json.dumps({'reset': True}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertFalse(StudentActivityProgress.objects.filter(pk=progress.pk).exists())

    def test_lesson27_activity1_uses_its_own_english_ui_and_speech_apis(self):
        response = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.lesson27_key}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pabasa_app/prescribed_rhyming_verses_lesson27_activity1_page.html')
        activity_data = response.context['prescribed_activity_data']
        self.assertEqual(activity_data['read_aloud_url'], reverse('reading_read_aloud_api'))
        self.assertEqual(activity_data['transcribe_url'], reverse('reading_transcribe_api'))
        self.assertContains(response, 'SESSION 11 · LESSON 27 · ACTIVITY 1')
        template = response.content.decode()
        self.assertIn('lesson27-word:hover:not(:disabled)', template)
        self.assertIn('outline:3px solid var(--line)', template)
        script = Path(settings.BASE_DIR, 'pabasa_app/static/pabasa_app/js/prescribed_rhyming_verses_lesson27_activity1.js').read_text(encoding='utf-8')
        self.assertIn('Rhyming Verses. Read each verse', script)
        self.assertIn("replace(/\\bhot\\b/g, 'hat').replace(/\\bmath\\b/g, 'mat').replace(/\\bwar\\b/g, 'wore').replace(/\\bbutt\\b/g, 'bat').replace(/\\blove\\b/g, 'loved')", script)
        self.assertNotIn('speechSynthesis', script)

    def test_lesson27_back_reset_clears_only_its_saved_progress(self):
        progress = StudentActivityProgress.objects.create(
            student=self.student, activity_key=self.lesson27_key,
            current_index=1, completed_items=1, total_items=4,
            state={'phase': 'reading', 'item_index': 1, 'verse_index': 2},
        )
        response = self.client.post(
            self.lesson27_progress_url, data=json.dumps({'reset': True}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertFalse(StudentActivityProgress.objects.filter(pk=progress.pk).exists())

    def test_lesson28_activities_use_dedicated_english_ui_and_google_speech_routes(self):
        activity1 = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.lesson28_activity1_key}))
        self.assertEqual(activity1.status_code, 200)
        self.assertTemplateUsed(activity1, 'pabasa_app/prescribed_missing_letter_lesson28_activity1_page.html')
        self.assertEqual(activity1.context['prescribed_activity_data']['read_aloud_url'], reverse('reading_read_aloud_api'))
        self.assertEqual(activity1.context['prescribed_activity_data']['transcribe_url'], reverse('reading_transcribe_api'))
        self.assertContains(activity1, 'SESSION 12 · LESSON 28 · ACTIVITY 1')
        activity2 = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.lesson28_activity2_key}))
        self.assertEqual(activity2.status_code, 200)
        self.assertTemplateUsed(activity2, 'pabasa_app/prescribed_word_identifying_lesson28_activity2_page.html')
        self.assertEqual(activity2.context['prescribed_activity_data']['read_aloud_url'], reverse('reading_read_aloud_api'))
        self.assertEqual(activity2.context['prescribed_activity_data']['transcribe_url'], reverse('reading_transcribe_api'))
        self.assertContains(activity2, 'SESSION 12 · LESSON 28 · ACTIVITY 2')
        for script_name in ('prescribed_missing_letter_lesson28_activity1.js', 'prescribed_word_identifying_lesson28_activity2.js'):
            script = Path(settings.BASE_DIR, 'pabasa_app/static/pabasa_app/js', script_name).read_text(encoding='utf-8')
            self.assertIn("language:'English'", script)
            self.assertNotIn('speechSynthesis', script)
            self.assertIn('{reset:true}', script)

    def test_lesson28_back_reset_clears_only_its_activity_progress(self):
        for key, url in ((self.lesson28_activity1_key, self.lesson28_activity1_progress_url),
                         (self.lesson28_activity2_key, self.lesson28_activity2_progress_url)):
            progress = StudentActivityProgress.objects.create(
                student=self.student, activity_key=key, current_index=1, completed_items=1,
                total_items=5, state={'current_item': 1, 'phase': 'reading'},
            )
            response = self.client.post(url, data=json.dumps({'reset': True}), content_type='application/json')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['success'])
            self.assertFalse(StudentActivityProgress.objects.filter(pk=progress.pk).exists())

    def test_lesson28_activity2_accepts_a_recognized_target_word_with_surrounding_transcript_text(self):
        started = self.client.post(
            self.lesson28_activity2_progress_url,
            data=json.dumps({'action': 'begin', 'item_index': 0}), content_type='application/json',
        )
        self.assertEqual(started.status_code, 200)
        target = started.json()['progress']['state']['target_word']
        response = self.client.post(
            self.lesson28_activity2_progress_url,
            data=json.dumps({'action': 'answer', 'item_index': 0, 'heard': f'I said {target}'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['accepted'])

    def test_lesson29_activities_use_dedicated_english_ui_and_google_speech_routes(self):
        activity1 = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.lesson29_activity1_key}))
        self.assertEqual(activity1.status_code, 200)
        self.assertTemplateUsed(activity1, 'pabasa_app/prescribed_oral_sentence_blank_lesson29_activity1_page.html')
        self.assertEqual(activity1.context['prescribed_activity_data']['read_aloud_url'], reverse('reading_read_aloud_api'))
        self.assertEqual(activity1.context['prescribed_activity_data']['transcribe_url'], reverse('reading_transcribe_api'))
        activity2 = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.lesson29_activity2_key}))
        self.assertEqual(activity2.status_code, 200)
        self.assertTemplateUsed(activity2, 'pabasa_app/prescribed_spot_word_lesson29_activity2_page.html')
        self.assertEqual(activity2.context['prescribed_activity_data']['read_aloud_url'], reverse('reading_read_aloud_api'))
        for script_name in ('prescribed_oral_sentence_blank_lesson29_activity1.js', 'prescribed_spot_word_lesson29_activity2.js'):
            script = Path(settings.BASE_DIR, 'pabasa_app/static/pabasa_app/js', script_name).read_text(encoding='utf-8')
            self.assertIn("language:'English'", script)
            self.assertNotIn('speechSynthesis', script)
            self.assertIn('{reset:true}', script)

    def test_lesson29_back_reset_clears_only_its_activity_progress(self):
        for key, url in ((self.lesson29_activity1_key, self.lesson29_activity1_progress_url),
                         (self.lesson29_activity2_key, self.lesson29_activity2_progress_url)):
            progress = StudentActivityProgress.objects.create(
                student=self.student, activity_key=key, current_index=1, completed_items=1,
                total_items=5, state={'current_item': 1, 'phase': 'answering'},
            )
            response = self.client.post(url, data=json.dumps({'reset': True}), content_type='application/json')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['success'])
            self.assertFalse(StudentActivityProgress.objects.filter(pk=progress.pk).exists())

    def test_lesson29_activity2_accepts_consecutive_word_choices(self):
        begin = self.client.post(
            self.lesson29_activity2_progress_url,
            data=json.dumps({'action': 'begin', 'item_index': 0}), content_type='application/json',
        )
        self.assertEqual(begin.status_code, 200)
        first_target = begin.json()['progress']['state']['target_word']
        first = self.client.post(
            self.lesson29_activity2_progress_url,
            data=json.dumps({'action': 'choose', 'item_index': 0, 'word': first_target}),
            content_type='application/json',
        )
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()['accepted'])
        next_target = first.json()['progress']['state']['target_word']
        second = self.client.post(
            self.lesson29_activity2_progress_url,
            data=json.dumps({'action': 'choose', 'item_index': 1, 'word': next_target}),
            content_type='application/json',
        )
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()['accepted'])
        self.assertEqual(second.json()['progress']['completed_items'], 2)

    def test_lesson30_story_time_uses_dedicated_line_by_line_speech_flow(self):
        response = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.lesson30_activity2_key}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pabasa_app/prescribed_story_time_lesson30_activity2_page.html')
        data = response.context['prescribed_activity_data']
        self.assertEqual(data['read_aloud_url'], reverse('reading_read_aloud_api'))
        self.assertEqual(data['transcribe_url'], reverse('reading_transcribe_api'))
        self.assertEqual(data['story_title'], 'Ben and the Little Pet')
        self.assertEqual(len(data['lines']), 6)
        script = Path(settings.BASE_DIR, 'pabasa_app/static/pabasa_app/js/prescribed_story_time_lesson30_activity2.js').read_text(encoding='utf-8')
        self.assertIn("action:'line_read'", script)
        self.assertIn('{reset:true}', script)
        self.assertIn("language:'English'", script)
        self.assertNotIn('speechSynthesis', script)

    def test_lesson30_match_it_has_its_own_english_activity_screen_and_reset(self):
        response = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.lesson30_activity1_key}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pabasa_app/prescribed_match_it_lesson30_activity1_page.html')
        self.assertContains(response, 'Read the word aloud first. Then choose the matching picture.')
        self.assertIn('csrftoken', response.cookies)
        script = Path(settings.BASE_DIR, 'pabasa_app/static/pabasa_app/js/prescribed_match_it_lesson30_activity1.js').read_text(encoding='utf-8')
        self.assertIn("language:'English'", script)
        self.assertIn('id="listen">🔊 Listen</button>', script)
        self.assertIn("setTimeout(()=>play(target).catch", script)
        self.assertIn('reset:true', script)
        self.assertNotIn('speechSynthesis', script)
        StudentActivityProgress.objects.create(
            student=self.student, activity_key=self.lesson30_activity1_key,
            current_index=1, completed_items=1, total_items=5,
            state={'phase': 'oral_reading', 'state_version': 1},
        )
        reset = self.client.post(
            self.lesson30_activity1_progress_url,
            data=json.dumps({'reset': True}), content_type='application/json',
        )
        self.assertEqual(reset.status_code, 200)
        self.assertTrue(reset.json()['success'])
        self.assertFalse(StudentActivityProgress.objects.filter(student=self.student, activity_key=self.lesson30_activity1_key).exists())

    def test_lesson30_match_it_requires_rereading_after_three_wrong_pictures(self):
        activity = prescribed_activity(self.lesson30_activity1_key)
        target = activity['word_bank'][0]
        read_once = self.client.post(
            self.lesson30_activity1_progress_url,
            data=json.dumps({'state': {
                'phase': 'matching', 'current_oral_word_index': 0,
                'unlocked_oral_words': [target], 'matches': {}, 'state_version': 1,
            }}), content_type='application/json',
        )
        self.assertEqual(read_once.status_code, 200)
        reread = self.client.post(
            self.lesson30_activity1_progress_url,
            data=json.dumps({'state': {
                'phase': 'oral_reading', 'current_oral_word_index': 0,
                'unlocked_oral_words': [target], 'matches': {},
                'picture_attempts': {target: 3}, 'needs_reread': True, 'state_version': 2,
            }}), content_type='application/json',
        )
        self.assertEqual(reread.status_code, 200)
        state = reread.json()['progress']['state']
        self.assertEqual(state['phase'], 'oral_reading')
        self.assertTrue(state['needs_reread'])
        self.assertEqual(state['picture_attempts'][target], 3)

    def test_lesson30_story_time_saves_line_progress_and_resets_it(self):
        response = self.client.post(
            self.lesson30_activity2_progress_url,
            data=json.dumps({'action': 'line_read', 'line_index': 0, 'success': True}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        progress = response.json()['progress']
        self.assertTrue(response.json()['accepted'])
        self.assertEqual(progress['completed_items'], 1)
        self.assertEqual(progress['state']['current_line'], 1)
        reset = self.client.post(
            self.lesson30_activity2_progress_url,
            data=json.dumps({'reset': True}), content_type='application/json',
        )
        self.assertEqual(reset.status_code, 200)
        self.assertTrue(reset.json()['success'])
        self.assertFalse(StudentActivityProgress.objects.filter(student=self.student, activity_key=self.lesson30_activity2_key).exists())

    def test_lesson30_comprehension_check_reads_questions_and_validates_choices(self):
        page = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.lesson30_activity3_key}))
        self.assertEqual(page.status_code, 200)
        self.assertTemplateUsed(page, 'pabasa_app/prescribed_comprehension_lesson30_activity3_page.html')
        data = page.context['prescribed_activity_data']
        self.assertEqual(len(data['questions']), 5)
        self.assertEqual(data['questions'][0]['question'], 'Who has a pet?')
        self.assertNotIn('answer', data['questions'][0])
        incorrect = self.client.post(
            self.lesson30_activity3_progress_url,
            data=json.dumps({'action': 'choose', 'item_index': 0, 'choice': 'b'}),
            content_type='application/json',
        )
        self.assertEqual(incorrect.status_code, 200)
        self.assertFalse(incorrect.json()['accepted'])
        correct = self.client.post(
            self.lesson30_activity3_progress_url,
            data=json.dumps({'action': 'choose', 'item_index': 0, 'choice': 'a'}),
            content_type='application/json',
        )
        self.assertEqual(correct.status_code, 200)
        self.assertTrue(correct.json()['accepted'])
        self.assertEqual(correct.json()['progress']['completed_items'], 1)
        reset = self.client.post(
            self.lesson30_activity3_progress_url,
            data=json.dumps({'reset': True}), content_type='application/json',
        )
        self.assertEqual(reset.status_code, 200)
        self.assertTrue(reset.json()['success'])

    def test_lesson31_circle_right_word_requires_reading_all_choices_before_picture_choice(self):
        page = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.lesson31_activity1_key}))
        self.assertEqual(page.status_code, 200)
        self.assertTemplateUsed(page, 'pabasa_app/prescribed_circle_right_word_lesson31_activity1_page.html')
        data = page.context['prescribed_activity_data']
        self.assertEqual(len(data['items']), 5)
        self.assertEqual(data['items'][0]['choices'], ['pet', 'mat', 'sit'])
        self.assertNotIn('answer', data['items'][0])
        self.assertEqual(data['read_aloud_url'], reverse('reading_read_aloud_api'))
        self.assertEqual(data['transcribe_url'], reverse('reading_transcribe_api'))
        premature = self.client.post(
            self.lesson31_activity1_progress_url,
            data=json.dumps({'action': 'choose', 'item_index': 0, 'choice': 'pet'}),
            content_type='application/json',
        )
        self.assertEqual(premature.status_code, 400)
        for choice_index, word in enumerate(('pet', 'math', 'sit')):
            response = self.client.post(
                self.lesson31_activity1_progress_url,
                data=json.dumps({'action': 'read_choice', 'item_index': 0, 'choice_index': choice_index, 'heard': word}),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['accepted'])
        wrong = self.client.post(
            self.lesson31_activity1_progress_url,
            data=json.dumps({'action': 'choose', 'item_index': 0, 'choice': 'mat'}),
            content_type='application/json',
        )
        self.assertEqual(wrong.status_code, 200)
        self.assertFalse(wrong.json()['accepted'])
        self.assertEqual(wrong.json()['progress']['state']['current_item'], 0)
        correct = self.client.post(
            self.lesson31_activity1_progress_url,
            data=json.dumps({'action': 'choose', 'item_index': 0, 'choice': 'pet'}),
            content_type='application/json',
        )
        self.assertEqual(correct.status_code, 200)
        self.assertTrue(correct.json()['accepted'])
        self.assertEqual(correct.json()['progress']['state']['current_item'], 1)
        StudentActivityProgress.objects.update_or_create(
            student=self.student, activity_key=self.lesson31_activity1_key,
            defaults={'current_index': 3, 'completed_items': 3, 'correct_items': 3, 'total_items': 5,
                      'state': {'current_item': 3, 'choice_index': 0, 'phase': 'reading_choices'}},
        )
        bat_alias = self.client.post(
            self.lesson31_activity1_progress_url,
            data=json.dumps({'action': 'read_choice', 'item_index': 3, 'choice_index': 0, 'heard': 'butt'}),
            content_type='application/json',
        )
        self.assertEqual(bat_alias.status_code, 200)
        self.assertTrue(bat_alias.json()['accepted'])

    def test_lesson31_fill_blank_requires_reading_then_dragging_then_sentence_reading(self):
        page = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.lesson31_activity2_key}))
        self.assertEqual(page.status_code, 200)
        self.assertTemplateUsed(page, 'pabasa_app/prescribed_drag_blank_lesson31_activity2_page.html')
        self.assertEqual(page.context['prescribed_activity_data']['word_choices'], ['pet', 'sit', 'sip', 'lit', 'mat'])
        for index, word in enumerate(['pet', 'sit', 'sip', 'lit', 'math']):
            result = self.client.post(self.lesson31_activity2_progress_url, data=json.dumps({
                'action': 'read_choice', 'choice_index': index, 'heard': word,
            }), content_type='application/json')
            self.assertEqual(result.status_code, 200)
            self.assertTrue(result.json()['accepted'])
        listened = self.client.post(self.lesson31_activity2_progress_url, data=json.dumps({'action': 'sentence_played'}), content_type='application/json')
        self.assertEqual(listened.status_code, 200)
        wrong = self.client.post(self.lesson31_activity2_progress_url, data=json.dumps({'action': 'place_word', 'word': 'sit'}), content_type='application/json')
        self.assertFalse(wrong.json()['accepted'])
        placed = self.client.post(self.lesson31_activity2_progress_url, data=json.dumps({'action': 'place_word', 'word': 'pet'}), content_type='application/json')
        self.assertTrue(placed.json()['accepted'])
        read = self.client.post(self.lesson31_activity2_progress_url, data=json.dumps({'action': 'read_sentence', 'heard': 'The pet is on the mat'}), content_type='application/json')
        self.assertTrue(read.json()['accepted'])
        self.assertEqual(read.json()['progress']['completed_items'], 1)

    def test_lesson31_fix_sentence_requires_reading_arranging_and_sentence_reading(self):
        page = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.lesson31_activity3_key}))
        self.assertEqual(page.status_code, 200)
        self.assertTemplateUsed(page, 'pabasa_app/prescribed_fix_sentence_lesson31_activity3_page.html')
        item = page.context['prescribed_activity_data']['items'][0]
        self.assertEqual(item['jumbled_words'], ['pet', 'the', 'pat'])
        for index, word in enumerate(item['jumbled_words']):
            result = self.client.post(self.lesson31_activity3_progress_url, data=json.dumps({
                'action': 'read_word', 'word_index': index, 'heard': word,
            }), content_type='application/json')
            self.assertTrue(result.json()['accepted'])
        wrong = self.client.post(self.lesson31_activity3_progress_url, data=json.dumps({
            'action': 'place_word', 'slot': 0, 'word': 'pet',
        }), content_type='application/json')
        self.assertFalse(wrong.json()['accepted'])
        for slot, word in enumerate(['pat', 'the', 'pet']):
            placed = self.client.post(self.lesson31_activity3_progress_url, data=json.dumps({
                'action': 'place_word', 'slot': slot, 'word': word,
            }), content_type='application/json')
            self.assertTrue(placed.json()['accepted'])
        read = self.client.post(self.lesson31_activity3_progress_url, data=json.dumps({
            'action': 'read_sentence', 'heard': 'Pat the pet',
        }), content_type='application/json')
        self.assertTrue(read.json()['accepted'])
        self.assertEqual(read.json()['progress']['completed_items'], 1)

    def test_lesson31_say_circle_requires_picture_reading_and_rereading_after_wrong_choice(self):
        page = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.lesson31_activity4_key}))
        self.assertEqual(page.status_code, 200)
        self.assertTemplateUsed(page, 'pabasa_app/prescribed_say_circle_lesson31_activity4_page.html')
        item = page.context['prescribed_activity_data']['items'][0]
        self.assertEqual(item['word'], 'bell')
        spoken = self.client.post(self.lesson31_activity4_progress_url, data=json.dumps({
            'action': 'read_word', 'heard': 'bell',
        }), content_type='application/json')
        self.assertTrue(spoken.json()['accepted'])
        wrong = self.client.post(self.lesson31_activity4_progress_url, data=json.dumps({
            'action': 'choose', 'choice': 'ball',
        }), content_type='application/json')
        self.assertFalse(wrong.json()['accepted'])
        self.assertEqual(wrong.json()['progress']['state']['phase'], 'reading')
        spoken_again = self.client.post(self.lesson31_activity4_progress_url, data=json.dumps({
            'action': 'read_word', 'heard': 'bell',
        }), content_type='application/json')
        self.assertTrue(spoken_again.json()['accepted'])
        correct = self.client.post(self.lesson31_activity4_progress_url, data=json.dumps({
            'action': 'choose', 'choice': 'bell',
        }), content_type='application/json')
        self.assertTrue(correct.json()['accepted'])
        self.assertEqual(correct.json()['progress']['completed_items'], 1)
