import json
import uuid
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.contrib.staticfiles import finders
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from .models import Material, School, Section, StudentActivityProgress, User
from .prescribed_activity_catalog import prescribed_activity
from .prescribed_test_fixtures import prescribed_term_fixture


class PrescribedLesson16ActivityTests(TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex.upper()
        self.school = School.objects.create(name=f"Lesson 16 School {suffix}", code=f"L16-{suffix}")
        self.teacher = User.objects.create(
            custom_id=f"TCH-{suffix}", role="teacher", first_name="Teacher", last_name="Sixteen",
            middle_initial="", suffix="", sex="female", birth_month=1, birth_day=1, birth_year=1990,
            email=f"teacher-{suffix}@example.com", password_hash="hashed", teacher_role="Teacher",
            school_record=self.school,
        )
        self.student = User.objects.create(
            custom_id=f"STU-{suffix}", role="student", first_name="Learner", last_name="Sixteen",
            middle_initial="", suffix="", sex="male", birth_month=1, birth_day=1, birth_year=2018,
            email=f"student-{suffix}@example.com", password_hash="hashed", school_record=self.school,
        )
        self.section = Section.objects.create(
            school=self.school, class_code=f"CLASS-{suffix}", class_name="Grade 2", header="Reading",
            description="", teacher=self.teacher, subject="Filipino", is_active=True,
        )
        self.section.add_student(self.student)
        prescribed_term_fixture(self.student, teacher=self.teacher, section=self.section)

    def login_student(self):
        session = self.client.session
        session.update({'user_id': self.student.id, 'user_role': 'student', 'email': self.student.email})
        session.save()
        self.student.active_session_key = session.session_key
        self.student.last_activity = timezone.now()
        self.student.save(update_fields=['active_session_key', 'last_activity', 'updated_at'])

    def login_teacher(self):
        session = self.client.session
        session.update({'user_id': self.teacher.id, 'user_role': 'teacher', 'email': self.teacher.email})
        session.save()

    def make_material(self, key='lesson-16-gawain-1'):
        content = prescribed_activity(key)
        content.update({
            'template_source': 'prescribed', 'template_title': content['title'],
            'template_lesson': 'Lesson 16', 'activity_type': 'prescribed_missing_syllable',
            'language': 'Filipino', 'instructions': content['instruction'],
        })
        material = Material.objects.create(
            teacher=self.teacher, section=self.section,
            title=f"Lesson 16: Gawain {content['gawain_number']} — {content['title']}",
            item_type='word', content_text='\n'.join(item['word'] for item in content['items']),
            content_json=content, language='Filipino', type='assessment', assessment_kind='regular',
            source_type='template', status='published', is_active=True, student_access=True,
            assigned_week=6, assigned_weeks=[6],
        )
        material.assigned_sections.add(self.section)
        return material

    def test_published_page_uses_the_key_without_course_assignment(self):
        self.login_student()
        response = self.client.get(
            reverse('prescribed_activity_page', kwargs={'activity_key': 'lesson-16-gawain-1'}),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.context['prescribed_activity_data']
        self.assertEqual(payload['activity_key'], 'lesson-16-gawain-1')
        self.assertEqual([item['word'] for item in payload['items']], ['gumamela', 'banga', 'gusali', 'ngiti', 'gata'])
        self.assertNotIn('answer', payload['items'][0])

    def test_progress_resumes_and_completion_requires_all_items(self):
        material = self.make_material('lesson-16-gawain-2')
        self.login_student()
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': 'lesson-16-gawain-2'})
        complete_url = reverse('prescribed_activity_complete', kwargs={'activity_key': 'lesson-16-gawain-2'})
        partial = self.client.post(progress_url, data=json.dumps({
            'material_id': material.id, 'current_index': 2, 'answers': ['gu', 'ba'],
        }), content_type='application/json')
        self.assertEqual(partial.status_code, 200)
        saved = StudentActivityProgress.objects.get(student=self.student, activity_key='lesson-16-gawain-2')
        self.assertEqual(saved.completed_items, 2)
        self.assertFalse(saved.activity_completed)
        rejected = self.client.post(complete_url, data=json.dumps({
            'material_id': material.id, 'answers': ['gu', 'ba'],
        }), content_type='application/json')
        self.assertEqual(rejected.status_code, 400)
        completed = self.client.post(complete_url, data=json.dumps({
            'material_id': material.id, 'answers': ['gu', 'ba', 'gu', 'ngi', 'ga'], 'duration_seconds': 14,
        }), content_type='application/json')
        self.assertEqual(completed.status_code, 200)
        saved.refresh_from_db()
        self.assertTrue(saved.activity_completed)
        self.assertEqual(saved.correct_items, 5)
        self.assertTrue(material.assessment_results.filter(student=self.student, attempt_status='completed').exists())

    def test_directly_published_activity_saves_without_a_course_material(self):
        self.login_student()
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': 'lesson-16-gawain-1'})
        complete_url = reverse('prescribed_activity_complete', kwargs={'activity_key': 'lesson-16-gawain-1'})
        incorrect = self.client.post(progress_url, data=json.dumps({
            'current_index': 0, 'answers': [], 'candidate_answer': 'ga',
            'state': {'phase': 'written', 'written_attempts': 1, 'state_version': 1},
        }), content_type='application/json')
        self.assertEqual(incorrect.status_code, 200)
        self.assertFalse(incorrect.json()['accepted'])
        self.assertEqual(incorrect.json()['progress']['completed_items'], 0)
        self.assertEqual(incorrect.json()['progress']['state']['phase'], 'written')
        self.assertEqual(incorrect.json()['progress']['state']['written_attempts'], 1)
        response = self.client.post(progress_url, data=json.dumps({
            'current_index': 0, 'answers': [], 'candidate_answer': 'gu',
            'state': {'phase': 'written', 'state_version': 2},
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['accepted'])
        self.assertEqual(response.json()['progress']['state']['phase'], 'oral')
        response = self.client.post(complete_url, data=json.dumps({
            'answers': ['gu', 'ba', 'gu', 'ngi', 'ga'],
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        saved = StudentActivityProgress.objects.get(student=self.student, activity_key='lesson-16-gawain-1')
        self.assertTrue(saved.activity_completed)
        self.assertEqual(saved.correct_items, 5)
        self.assertIsNone(saved.state['material_id'])

    def test_catalog_preserves_workbook_order_and_direct_image_paths(self):
        activity = prescribed_activity('lesson-16-gawain-1')
        self.assertEqual([item['word'] for item in activity['items']], ['gumamela', 'banga', 'gusali', 'ngiti', 'gata'])
        self.assertEqual(
            [item['image_path'] for item in activity['items']],
            [
                'pabasa_app/images/lesson_16/gumamela.png',
                'pabasa_app/images/lesson_16/banga.png',
                'pabasa_app/images/lesson_16/gusali.png',
                'pabasa_app/images/lesson_16/ngiti.png',
                'pabasa_app/images/lesson_16/gata.png',
            ],
        )
        for item in activity['items']:
            self.assertIsNotNone(finders.find(item['image_path']))

    def test_all_lesson_16_cards_use_the_session_6_key(self):
        self.login_student()
        response = self.client.get(reverse('assessment'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                card['activity_key']: card['session_key']
                for card in response.context['prescribed_activity_cards']
                if card['activity_key'].startswith('lesson-16-')
            },
            {
                'lesson-16-gawain-1': 'session-6',
                'lesson-16-gawain-2': 'session-6',
                'lesson-16-gawain-3': 'session-6',
                'session-6-lesson-16-gawain-4': 'session-6',
            },
        )

    def test_gawain_4_uses_fixed_workbook_order_and_available_assets(self):
        activity = prescribed_activity('session-6-lesson-16-gawain-4')
        self.assertEqual(activity['session_key'], 'session-6')
        self.assertEqual(activity['interaction'], 'picture_word_write')
        self.assertEqual(
            [item['answer'] for item in activity['items']],
            ['gamot', 'bunga', 'panga', 'goma', 'sanga'],
        )
        self.assertEqual([item['letter_count'] for item in activity['items']], [5, 5, 5, 4, 5])
        for item in activity['items']:
            self.assertIsNotNone(finders.find(item['image_path']))

    def test_gawain_4_is_present_in_the_teacher_catalog_from_the_same_definition(self):
        self.login_teacher()
        response = self.client.get(reverse('course_teacher_view'))
        self.assertEqual(response.status_code, 200)
        catalog_activity = next(
            activity for activity in response.context['prescribed_lesson_16_activities']
            if activity['activity_key'] == 'session-6-lesson-16-gawain-4'
        )
        self.assertEqual(catalog_activity, prescribed_activity('session-6-lesson-16-gawain-4'))

    def test_gawain_4_page_has_scoped_step_progress_and_scroll_safe_visuals(self):
        self.login_student()
        response = self.client.get(reverse('prescribed_activity_page', kwargs={
            'activity_key': 'session-6-lesson-16-gawain-4',
        }))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('class="steps"', html)
        self.assertIn('class="step ${index<answers.length?', html)
        self.assertIn("index===answers.length?'active'", html)
        self.assertIn('min-height:2.8em', html)
        self.assertIn('grid-template-columns:minmax(280px,.95fr)', html)
        self.assertIn('@media(max-width:820px)', html)
        scoped_css = html.split('/* Lesson 16', 1)[1].split('</style>', 1)[0]
        self.assertNotIn('height:100dvh', scoped_css)
        self.assertNotIn('overflow:hidden', scoped_css)
        self.assertNotIn('!important', scoped_css)
        self.assertNotIn('top:calc(-1', scoped_css)
        self.assertIn('width:100%;height:clamp(250px,32vw,390px)', scoped_css)
        self.assertIn('progress_url', html)
        self.assertIn('completion_url', html)
        self.assertIn('activity_completed', html)

    def test_gawain_4_persists_correct_items_and_requires_all_for_completion(self):
        self.login_student()
        key = 'session-6-lesson-16-gawain-4'
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        complete_url = reverse('prescribed_activity_complete', kwargs={'activity_key': key})
        blocked = self.client.post(progress_url, data=json.dumps({
            'candidate_answer': 'gamot', 'state': {'started': True, 'state_version': 1},
        }), content_type='application/json')
        self.assertEqual(blocked.status_code, 400)
        oral_state = {'started': True, 'phase': 'written', 'completed_oral_reads': [0, 1, 2, 3, 4],
                      'stt_attempts': {}, 'tts_plays': {}}
        incorrect = self.client.post(progress_url, data=json.dumps({
            'candidate_answer': 'gamutx', 'state': {**oral_state, 'state_version': 2},
        }), content_type='application/json')
        self.assertEqual(incorrect.status_code, 200)
        self.assertFalse(incorrect.json()['accepted'])
        self.assertEqual(incorrect.json()['progress']['state']['attempts'], {'0': 1})
        first = self.client.post(progress_url, data=json.dumps({
            'candidate_answer': ' GAMOT ', 'state': {**oral_state, 'state_version': 3},
        }), content_type='application/json')
        self.assertTrue(first.json()['accepted'])
        self.assertEqual(first.json()['progress']['completed_items'], 1)
        page = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': key}))
        self.assertTemplateUsed(page, 'pabasa_app/prescribed_picture_word_write_page.html')
        self.assertEqual(page.context['prescribed_activity_data']['progress']['current_index'], 1)
        self.assertNotIn('answer', page.context['prescribed_activity_data']['items'][0])
        self.assertEqual(self.client.post(complete_url, data='{}', content_type='application/json').status_code, 400)
        for state_version, answer in enumerate(['bunga', 'panga', 'goma', 'sanga'], start=4):
            response = self.client.post(progress_url, data=json.dumps({
                'candidate_answer': answer, 'state': {**oral_state, 'state_version': state_version},
            }), content_type='application/json')
            self.assertTrue(response.json()['accepted'])
        self.assertEqual(self.client.post(complete_url, data='{}', content_type='application/json').status_code, 200)
        saved = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
        self.assertTrue(saved.activity_completed)
        self.assertEqual(saved.completed_items, 5)

    def test_gawain_4_page_uses_saved_progress_steps_and_scroll_safe_activity_styles(self):
        template = Path(__file__).parent / 'templates' / 'pabasa_app' / 'prescribed_picture_word_write_page.html'
        source = template.read_text(encoding='utf-8')
        style = source.split('/* Gawain 4 visual system.', 1)[1].split('</style>', 1)[0]
        self.assertIn("'Isulat ang wastong salita para sa larawan'", source)
        self.assertIn('Session 6 · Lesson 16 · Gawain 4', source)
        self.assertIn('index<answers.length', source)
        self.assertIn('index===answers.length', source)
        self.assertNotIn('${Math.min(answers.length+1,items.length)} / ${items.length}', source)
        self.assertNotIn('height:100dvh', style)
        self.assertNotIn('overflow:hidden', style)
        self.assertNotIn('max-height:', style)
        self.assertNotRegex(style, r'(?<![a-z-])top\s*:')
        self.assertNotIn('!important', style)
        self.assertIn('grid-template-columns:minmax(280px,1fr) minmax(340px,1fr)', style)
        self.assertIn('grid-template-columns:1fr', style)
        self.assertIn('min-height:3.2em', style)
        self.assertIn('min-height:4.5em', style)
        self.assertIn('min-height:68px', style)

    def test_gawain_4_recovers_a_saved_final_answer_when_completion_was_interrupted(self):
        self.login_student()
        key = 'session-6-lesson-16-gawain-4'
        StudentActivityProgress.objects.create(
            student=self.student, activity_key=key, current_index=5, completed_items=5,
            correct_items=5, total_items=5, activity_completed=False,
            state={'answers': ['gamot', 'bunga', 'panga', 'goma', 'sanga'],
                   'attempts': {}, 'started': True, 'completed_oral_reads': [0, 1, 2, 3, 4],
                   'stt_attempts': {}, 'tts_plays': {}, 'state_version': 7},
        )
        response = self.client.post(
            reverse('prescribed_activity_progress', kwargs={'activity_key': key}),
            data=json.dumps({'candidate_answer': 'sanga', 'state': {'started': True, 'completed_oral_reads': [0, 1, 2, 3, 4], 'state_version': 8}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['progress']['activity_completed'])
        saved = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
        self.assertTrue(saved.activity_completed)

    def test_gawain_3_uses_the_workbook_word_bank_and_placeholder_paths(self):
        activity = prescribed_activity('lesson-16-gawain-3')
        self.assertEqual(activity['interaction'], 'picture_word_match')
        self.assertEqual(activity['word_bank'], ['panga', 'gamot', 'sanga', 'bunga', 'goma'])
        self.assertEqual([item['word'] for item in activity['items']], ['sanga', 'goma', 'bunga', 'panga', 'gamot'])
        self.assertEqual(
            [item['image_path'] for item in activity['items']],
            [
                'pabasa_app/images/lesson_16/sanga.png',
                'pabasa_app/images/lesson_16/goma.png',
                'pabasa_app/images/lesson_16/bunga.png',
                'pabasa_app/images/lesson_16/panga.png',
                'pabasa_app/images/lesson_16/gamot.png',
            ],
        )

    def test_gawain_3_hides_answers_from_the_student_page(self):
        self.login_student()
        response = self.client.get(
            reverse('prescribed_activity_page', kwargs={'activity_key': 'lesson-16-gawain-3'}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pabasa_app/lesson_16_gawain_3_page.html')
        payload = response.context['prescribed_activity_data']
        self.assertEqual(payload['title'], 'Piliin ang Larawang Katugma ng Salita')
        self.assertEqual(payload['screen']['picture_choices'], [])
        self.assertNotIn('word_bank', payload)
        self.assertNotIn('items', payload)
        self.assertNotIn('matches', payload['progress'])
        self.assertNotIn('picture_order', payload['progress']['state'])
        self.assertContains(response, 'lesson_16_gawain_3.css')
        self.assertContains(response, 'session6_intro_modal.js')
        self.assertNotContains(response, 'activityStart')
        generic_template = Path(__file__).parent / 'templates' / 'pabasa_app' / 'prescribed_picture_word_matching_page.html'
        generic_source = generic_template.read_text(encoding='utf-8')
        self.assertNotIn('lesson-16-gawain-3', generic_source)
        self.assertNotIn('lesson16Gawain3', generic_source)
        script_path = Path(finders.find('pabasa_app/js/lesson_16_gawain_3.js'))
        script = script_path.read_text(encoding='utf-8')
        self.assertIn('00_activity_intro.mp3', script)
        self.assertIn('16_feedback_completion.mp3', script)
        self.assertIn("window.addEventListener('lesson-start-ready', startOrResume)", script)
        self.assertNotIn('activityStart', script)
        self.assertIn('aria-label="Larawan ${i+1}"', script)
        self.assertIn("i === current ? 'is-current'", script)
        started = self.client.post(reverse('prescribed_activity_progress', kwargs={'activity_key': 'lesson-16-gawain-3'}),
                                   data=json.dumps({'action': 'start'}), content_type='application/json')
        self.assertEqual(started.json()['screen']['current_word'], 'sanga')
        self.assertTrue(started.json()['screen']['oral_image_url'].endswith('/sanga.png'))

    def test_gawain_3_rejects_client_oral_index_and_requires_signed_one_use_proof(self):
        self.login_student()
        key = 'lesson-16-gawain-3'
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        start = self.client.post(progress_url, data=json.dumps({'action': 'start'}), content_type='application/json')
        self.assertEqual(start.status_code, 200)
        self.assertEqual(start.json()['progress']['state']['oral_index'], 0)
        forged_progress = self.client.post(progress_url, data=json.dumps({
            'state': {'phase': 'matching', 'oral_index': 5, 'oral_verified_count': 5},
        }), content_type='application/json')
        self.assertEqual(forged_progress.status_code, 400)
        row = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
        nonce = uuid.uuid4().hex
        row.state['pending_reading_nonce'] = nonce
        row.save(update_fields=['state', 'updated_at'])
        wrong_item = signing.dumps({'student': self.student.pk, 'activity': key, 'progress': row.pk,
                                   'item': 1, 'nonce': nonce}, salt='lesson16-gawain3-reading')
        self.assertEqual(self.client.post(progress_url, data=json.dumps({
            'action': 'advance_oral', 'verification_token': wrong_item,
        }), content_type='application/json').status_code, 400)
        token = signing.dumps({'student': self.student.pk, 'activity': key, 'progress': row.pk, 'item': 0, 'nonce': nonce}, salt='lesson16-gawain3-reading')
        forged = self.client.post(progress_url, data=json.dumps({
            'action': 'advance_oral', 'verification_token': token + 'forged',
        }), content_type='application/json')
        self.assertEqual(forged.status_code, 400)
        advance = self.client.post(progress_url, data=json.dumps({'action': 'advance_oral', 'verification_token': token}), content_type='application/json')
        self.assertEqual(advance.status_code, 200)
        self.assertEqual(advance.json()['progress']['state']['oral_index'], 1)
        replay = self.client.post(progress_url, data=json.dumps({'action': 'advance_oral', 'verification_token': token}), content_type='application/json')
        self.assertEqual(replay.status_code, 400)

    def test_gawain_3_rejects_expired_reading_verification(self):
        class ExpiredSigner(signing.TimestampSigner):
            def timestamp(self):
                return '1'

        self.login_student()
        key = 'lesson-16-gawain-3'
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        self.client.post(progress_url, data=json.dumps({'action': 'start'}), content_type='application/json')
        row = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
        nonce = uuid.uuid4().hex
        row.state['pending_reading_nonce'] = nonce
        row.save(update_fields=['state', 'updated_at'])
        with patch('django.core.signing.time.time', return_value=1):
            token = signing.dumps({'student': self.student.pk, 'activity': key, 'progress': row.pk,
                                   'item': 0, 'nonce': nonce}, salt='lesson16-gawain3-reading')
        expired = self.client.post(progress_url, data=json.dumps({
            'action': 'advance_oral', 'verification_token': token,
        }), content_type='application/json')
        self.assertEqual(expired.status_code, 400)
        row.refresh_from_db()
        self.assertEqual(row.state['oral_index'], 0)

    @patch('pabasa_app.views.analyze_reading', return_value={'complete': False})
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=('sanganga', 'chirp_3', None))
    @patch('pabasa_app.views.uses_knowlez_stt', return_value=False)
    @patch('pabasa_app.views._local_api_key_stt_fallback', return_value=False)
    def test_gawain_3_rejects_substring_transcript_without_authoritative_completion(self, *_mocks):
        self.login_student()
        key = 'lesson-16-gawain-3'
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        self.client.post(progress_url, data=json.dumps({'action': 'start'}), content_type='application/json')
        response = self.client.post(reverse('reading_transcribe_api'), {
            'audio': SimpleUploadedFile('reading.webm', b'voice', content_type='audio/webm'),
            'target_text': 'sanga', 'language': 'Filipino', 'mode': 'reading',
            'prescribed_activity_key': key,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['complete'])
        self.assertNotIn('verification_token', response.json())
        row = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
        self.assertEqual(row.state['oral_index'], 0)

    @patch('pabasa_app.views.analyze_reading', return_value={'complete': True})
    @patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=('sanga', 'chirp_3', None))
    @patch('pabasa_app.views.uses_knowlez_stt', return_value=False)
    @patch('pabasa_app.views._local_api_key_stt_fallback', return_value=False)
    def test_gawain_3_issues_attempt_bound_verification_token_from_authoritative_result(self, *_mocks):
        self.login_student()
        key = 'lesson-16-gawain-3'
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        self.client.post(progress_url, data=json.dumps({'action': 'start'}), content_type='application/json')
        response = self.client.post(reverse('reading_transcribe_api'), {
            'audio': SimpleUploadedFile('reading.webm', b'voice', content_type='audio/webm'),
            'target_text': 'sanga', 'language': 'Filipino', 'mode': 'reading',
            'prescribed_activity_key': key,
        })
        self.assertEqual(response.status_code, 200)
        token = response.json()['verification_token']
        proof = signing.loads(token, salt='lesson16-gawain3-reading', max_age=300)
        row = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
        self.assertEqual(proof['student'], self.student.pk)
        self.assertEqual(proof['progress'], row.pk)
        self.assertEqual(proof['item'], 0)
        self.assertEqual(proof['nonce'], row.state['pending_reading_nonce'])
        advanced = self.client.post(progress_url, data=json.dumps({'action': 'advance_oral', 'verification_token': token}), content_type='application/json')
        self.assertEqual(advanced.status_code, 200)
        self.assertEqual(advanced.json()['progress']['state']['oral_index'], 1)

    def test_gawain_3_matching_is_server_checked_persisted_and_completion_is_authoritative(self):
        self.login_student()
        key = 'lesson-16-gawain-3'
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        complete_url = reverse('prescribed_activity_complete', kwargs={'activity_key': key})
        started = self.client.post(progress_url, data=json.dumps({'action': 'start'}), content_type='application/json').json()
        row = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
        order = list(row.state['picture_order'])
        row.state.update({'oral_index': 5, 'oral_verified_count': 5, 'phase': 'matching'})
        row.save(update_fields=['state', 'updated_at'])
        wrong = self.client.post(progress_url, data=json.dumps({'action': 'match_picture', 'picture_id': 'picture-1'}), content_type='application/json')
        self.assertEqual(wrong.status_code, 200)
        self.assertFalse(wrong.json()['accepted'])
        correct_picture_id = next(item['id'] for item in prescribed_activity(key)['items'] if item['word'] == 'panga')
        correct_id = next(token for token, picture_id in row.state['choice_tokens'].items() if picture_id == correct_picture_id)
        correct = self.client.post(progress_url, data=json.dumps({'action': 'match_picture', 'picture_id': correct_id}), content_type='application/json')
        self.assertEqual(correct.status_code, 200)
        self.assertTrue(correct.json()['accepted'])
        self.assertNotIn('matches', correct.json()['progress'])
        self.assertNotIn(correct_id, correct.json()['progress']['state'].get('matched_picture_ids', []))
        self.assertNotIn(correct_picture_id, json.dumps(correct.json()))
        self.assertEqual(correct.json()['progress']['state']['matching_index'], 1)
        row.refresh_from_db()
        self.assertEqual(row.state['picture_order'], order)
        self.assertEqual(row.state['matching_index'], 1)
        row.state['matching_index'] = 0
        row.save(update_fields=['state', 'updated_at'])
        restored = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': key}))
        restored_data = restored.context['prescribed_activity_data']
        self.assertEqual(restored_data['progress']['state']['matching_index'], 1)
        self.assertEqual(restored_data['screen']['current_word'], 'gamot')
        self.assertEqual([choice['id'] for choice in restored_data['screen']['picture_choices']],
                         [token for token, picture_id in row.state['choice_tokens'].items()
                          if picture_id in order and picture_id != correct_picture_id])
        incomplete = self.client.post(complete_url, data='{}', content_type='application/json')
        self.assertEqual(incomplete.status_code, 400)
        row.state.update({
            'oral_index': 5, 'oral_verified_count': 5, 'phase': 'matching',
            'matching_index': 0, 'matched_picture_ids': [item['id'] for item in prescribed_activity(key)['items']],
        })
        row.save(update_fields=['state', 'updated_at'])
        completed = self.client.post(complete_url, data='{}', content_type='application/json')
        self.assertEqual(completed.status_code, 200)
        row.refresh_from_db()
        self.assertTrue(row.activity_completed)
        reset = self.client.post(progress_url, data=json.dumps({'reset': True}), content_type='application/json')
        self.assertEqual(reset.status_code, 200)
        row = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
        self.assertEqual(row.state['matching_index'], 0)
        self.assertEqual(row.state['oral_index'], 0)

    def test_gawain_3_restart_rotates_picture_order_and_invalidates_old_read_token(self):
        self.login_student()
        key = 'lesson-16-gawain-3'
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        shuffle_round = [0]
        def shuffle_for_attempt(values):
            if shuffle_round[0] == 0:
                values[:] = values[1:] + values[:1]
            else:
                values.reverse()
            shuffle_round[0] += 1
        with patch('pabasa_app.views.random.shuffle', side_effect=shuffle_for_attempt):
            self.client.post(progress_url, data=json.dumps({'action': 'start'}), content_type='application/json')
            row = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
            first_order = list(row.state['picture_order'])
            nonce = uuid.uuid4().hex
            row.state['pending_reading_nonce'] = nonce
            row.save(update_fields=['state', 'updated_at'])
            stale = signing.dumps({'student': self.student.pk, 'activity': key, 'progress': row.pk,
                                   'item': 0, 'nonce': nonce}, salt='lesson16-gawain3-reading')
            reset = self.client.post(progress_url, data=json.dumps({'reset': True}), content_type='application/json')
            self.assertEqual(reset.status_code, 200)
            row = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
            self.assertNotEqual(row.state['picture_order'], first_order)
            rejected = self.client.post(progress_url, data=json.dumps({'action': 'advance_oral', 'verification_token': stale}), content_type='application/json')
            self.assertEqual(rejected.status_code, 400)

    def test_gawain_3_layout_uses_scoped_non_scrolling_responsive_shell(self):
        css_path = Path(finders.find('pabasa_app/css/lesson_16_gawain_3.css'))
        css = css_path.read_text(encoding='utf-8')
        self.assertIn('body.l16g3-page', css)
        self.assertIn('@media(max-width:850px)', css)
        self.assertIn('@media(max-width:560px)', css)
        self.assertIn('max-width:calc(100vw - 190px)', css)
        self.assertNotIn('overflow:auto', css)
        self.assertNotRegex(css, r'\.l16g3-card\s*\{[^}]*overflow\s*:')

    def test_gawain_3_uses_required_serial_audio_order_and_picture_only_controls(self):
        script = Path(finders.find('pabasa_app/js/lesson_16_gawain_3.js')).read_text(encoding='utf-8')
        for filename in (
            '00_activity_intro.mp3', '01_item_01_sanga_match_prompt.mp3',
            '03_item_02_goma_match_prompt.mp3', '05_item_03_bunga_match_prompt.mp3',
            '07_item_04_panga_match_prompt.mp3', '09_item_05_gamot_match_prompt.mp3',
            '02_item_01_sanga_word.mp3', '04_item_02_goma_word.mp3',
            '06_item_03_bunga_word.mp3', '08_item_04_panga_word.mp3',
            '10_item_05_gamot_word.mp3', '11_feedback_reading_correct.mp3',
            '12_feedback_reading_retry.mp3', '13_matching_start_prompt.mp3',
            '14_feedback_matching_correct.mp3', '15_feedback_matching_retry.mp3',
            '16_feedback_completion.mp3',
        ):
            self.assertIn(filename, script)
        self.assertIn("[audioBase+'00_activity_intro.mp3',audioBase+readPrompts[0]]", script)
        self.assertIn("[audioBase+'12_feedback_reading_retry.mp3',retryCue,audioBase+wordAudio[", script)
        self.assertIn("[audioBase+'11_feedback_reading_correct.mp3',audioBase+readPrompts[next]]", script)

    def test_gawain_3_cancels_stale_work_and_keeps_correct_choice_until_feedback_ends(self):
        script = Path(finders.find('pabasa_app/js/lesson_16_gawain_3.js')).read_text(encoding='utf-8')
        self.assertIn('controller?.abort()', script)
        self.assertIn('stream?.getTracks().forEach(track => track.stop())', script)
        self.assertIn('window.Basahin?.cancelAll?.()', script)
        self.assertIn("controller?.signal", script)
        self.assertIn("signal:controller.signal", script)
        self.assertIn("event.detail?.reason === 'pause'", script)
        self.assertIn("event.detail?.reason === 'restart'", script)
        self.assertIn('if (gen !== generation) return;', script)
        self.assertIn("button?.classList.add('is-correct')", script)
        self.assertLess(script.index("button?.classList.add('is-correct')"),
                        script.index("await play(audioBase+'14_feedback_matching_correct.mp3',gen)"))
        feedback_after_correct = script.index("await play(audioBase+'14_feedback_matching_correct.mp3',gen)",
                                              script.index("button?.classList.add('is-correct')"))
        next_render = script.index('render();', feedback_after_correct)
        self.assertLess(feedback_after_correct, next_render)
        self.assertIn("await play(audioBase+'13_matching_start_prompt.mp3',gen)", script)
        matching = script.split('async function submitPicture', 1)[1].split('async function finishCompletion', 1)[0]
        self.assertNotIn('readPrompts', matching)
        self.assertIn('aria-label="Larawan ${i+1}"', script)
        self.assertIn('alt="" aria-hidden="true"', script)
        self.assertIn("role=\"status\" aria-live=\"polite\"", script)

    def test_lesson_17_18_gawain_5_requires_saved_oral_reading_before_matching(self):
        self.login_student()
        key = 'lesson-17-18-gawain-5'
        activity = prescribed_activity(key)
        self.assertEqual(activity['activity_key'], key)
        self.assertEqual([item['id'] for item in activity['items']], ['robot', 'payong', 'pitaka', 'riles', 'puso'])
        page = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': key}))
        self.assertTemplateUsed(page, 'pabasa_app/prescribed_picture_syllable_matching_page.html')
        self.assertEqual(page.context['prescribed_activity_data']['read_aloud_url'], reverse('reading_read_aloud_api'))
        self.assertContains(page, "phase='oral_reading';try{await save();renderOral()}")
        stale = StudentActivityProgress.objects.create(
            student=self.student,
            activity_key=key,
            current_index=5,
            completed_items=0,
            correct_items=0,
            total_items=len(activity['items']),
            activity_completed=False,
            state={'matches': {}, 'phase': 'matching', 'oral_index': 5, 'state_version': 9},
        )
        stale_page = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': key}))
        self.assertEqual(stale_page.context['prescribed_activity_data']['progress']['state']['phase'], 'intro')
        stale.delete()
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        blocked = self.client.post(progress_url, data=json.dumps({
            'matches': {}, 'candidate_match': {'target_id': 'robot', 'word': 'ro'},
            'state': {'phase': 'oral_reading', 'oral_index': 0, 'state_version': 1},
        }), content_type='application/json')
        self.assertEqual(blocked.status_code, 400)
        resumed = self.client.post(progress_url, data=json.dumps({
            'matches': {}, 'state': {'phase': 'matching', 'oral_index': 5, 'stt_attempts': {'0': 2}, 'tts_plays': {}, 'state_version': 2},
        }), content_type='application/json')
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.json()['progress']['state']['oral_index'], 0)
        self.assertEqual(resumed.json()['progress']['state']['phase'], 'intro')

        # Oral progress is earned one item at a time. A client cannot jump
        # directly from the intro to the matching phase by claiming index 5.
        for oral_index in range(1, len(activity['items']) + 1):
            advanced = self.client.post(progress_url, data=json.dumps({
                'matches': {},
                'state': {
                    'phase': 'matching' if oral_index == len(activity['items']) else 'oral_reading',
                    'oral_index': oral_index,
                    'oral_verified_count': oral_index - 1,
                    'state_version': 2 + oral_index,
                },
            }), content_type='application/json')
            self.assertEqual(advanced.status_code, 200)
            expected_phase = 'matching' if oral_index == len(activity['items']) else 'oral_reading'
            self.assertEqual(advanced.json()['progress']['state']['oral_index'], oral_index)
            self.assertEqual(advanced.json()['progress']['state']['phase'], expected_phase)

    def test_remaining_session6_activities_have_full_page_intro_states(self):
        self.login_student()
        scenarios = {
            'lesson-16-gawain-1': ('prescribed_missing_syllable_page.html', 'oral'),
            'lesson-16-gawain-2': ('prescribed_missing_syllable_page.html', 'oral'),
            'lesson-16-gawain-3': ('lesson_16_gawain_3_page.html', 'oral_reading'),
            'lesson-17-18-gawain-5': ('prescribed_picture_syllable_matching_page.html', 'oral_reading'),
        }
        for key, (template, first_phase) in scenarios.items():
            with self.subTest(activity_key=key):
                response = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': key}))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, f'pabasa_app/{template}')
                payload = response.context['prescribed_activity_data']
                self.assertTrue(payload['intro_enabled'])
                self.assertEqual(payload['progress']['state']['phase'], 'intro')
                self.assertContains(response, 'session6_intro_modal.js')
                self.assertContains(response, 'session6-modal-handoff-1')
                if key != 'lesson-16-gawain-3':
                    self.assertContains(response, 'SIMULAN')
                    self.assertContains(response, 'lesson-start-ready')
                if key == 'lesson-16-gawain-1':
                    self.assertContains(response, '04_item_01_gumamela_missing_syllable_prompt.mp3')
                    self.assertContains(response, 'const audioKey = itemAudio?.word;')
                    self.assertNotContains(response, 'const audioKey = itemAudio?.prompt;')
                elif key == 'lesson-16-gawain-2':
                    self.assertContains(response, '04_item_01_gumamela_missing_syllable_prompt.mp3')
                    self.assertContains(response, 'const audioKey = itemAudio?.word;')
                    self.assertNotContains(response, 'const audioKey = itemAudio?.prompt;')
                elif key == 'lesson-16-gawain-3':
                    self.assertContains(response, 'lesson_16_gawain_3.js')
                    self.assertContains(response, 'session6_intro_modal.js')
                    self.assertNotContains(response, 'activityStart')

                progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
                state = (
                    {'phase': first_phase, 'state_version': 1}
                    if first_phase == 'oral' else
                    {'phase': first_phase, 'oral_index': 0, 'state_version': 1}
                )
                body = {'state': state}
                if first_phase == 'oral':
                    body['answers'] = []
                else:
                    body['matches'] = {}
                if key == 'lesson-16-gawain-3':
                    body = {'action': 'start'}
                started = self.client.post(progress_url, data=json.dumps(body), content_type='application/json')
                self.assertEqual(started.status_code, 200)
                self.assertEqual(started.json()['progress']['state']['phase'], first_phase)

    def test_remaining_session6_intro_resumes_reset_and_stays_out_of_completed_state(self):
        self.login_student()
        keys = (
            'lesson-16-gawain-1', 'lesson-16-gawain-2', 'lesson-17-18-gawain-5',
        )
        for key in keys:
            with self.subTest(activity_key=key):
                activity = prescribed_activity(key)
                is_matching = activity['interaction'] in {'picture_word_match', 'picture_syllable_match'}
                if is_matching:
                    state = {'phase': 'oral_reading', 'oral_index': 1, 'state_version': 2}
                    saved = {'matches': {}, **state}
                else:
                    state = {'phase': 'oral', 'state_version': 2}
                    saved = {'answers': [], **state}
                StudentActivityProgress.objects.update_or_create(
                    student=self.student, activity_key=key,
                    defaults={'current_index': 1, 'completed_items': 0, 'correct_items': 0,
                              'total_items': len(activity['items']), 'activity_completed': False,
                              'state': saved},
                )
                resumed = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': key}))
                self.assertNotEqual(resumed.context['prescribed_activity_data']['progress']['state']['phase'], 'intro')

                progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
                reset = self.client.post(progress_url, data=json.dumps({'reset': True}), content_type='application/json')
                self.assertEqual(reset.status_code, 200)
                self.assertEqual(reset.json()['progress']['state']['phase'], 'intro')
                self.assertFalse(StudentActivityProgress.objects.filter(student=self.student, activity_key=key).exists())

                if is_matching:
                    completed_state = {
                        'matches': {item['id']: item['word'] for item in activity['items']},
                        'phase': 'matching', 'oral_index': len(activity['items']),
                        'oral_verified_count': len(activity['items']), 'state_version': 3,
                    }
                    completed_items = len(activity['items'])
                else:
                    completed_state = {
                        'answers': [item['answer'] for item in activity['items']],
                        'phase': 'oral', 'state_version': 3,
                    }
                    completed_items = len(activity['items'])
                StudentActivityProgress.objects.create(
                    student=self.student, activity_key=key, current_index=completed_items,
                    completed_items=completed_items, correct_items=completed_items,
                    total_items=completed_items, activity_completed=True, state=completed_state,
                )
                completed = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': key}))
                payload = completed.context['prescribed_activity_data']
                self.assertTrue(payload['progress']['activity_completed'])
                self.assertNotEqual(payload['progress']['state']['phase'], 'intro')

    @patch('pabasa_app.views.synthesize_read_aloud_audio', return_value='encoded-audio')
    def test_session_6_activities_use_the_prescribed_filipino_google_voice(self, synthesize):
        self.login_student()
        for key in ('lesson-16-gawain-3', 'session-6-lesson-16-gawain-4', 'lesson-17-18-gawain-5'):
            with self.subTest(activity_key=key):
                response = self.client.post(reverse('reading_read_aloud_api'), {
                    'target_text': 'gamot', 'language': '', 'mode': 'reading',
                    'prescribed_activity_key': key,
                })
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()['tts_language'], 'fil-PH')
                self.assertEqual(response.json()['voice_name'], 'fil-PH-Wavenet-A')
                self.assertEqual(synthesize.call_args.args[2], 'fil-PH')
                self.assertEqual(synthesize.call_args.kwargs['voice_gender'], 'FEMALE')
