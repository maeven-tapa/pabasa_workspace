import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import JsonResponse
from django.test import SimpleTestCase
from django.test import TestCase
from django.urls import reverse

from .models import Material, School, Section, StudentActivityProgress, User
from .prescribed_activity_catalog import PRESCRIBED_ACTIVITIES, active_prescribed_activities
from .prescribed_workbook import ACTIVITIES, apply_event, get_activity, initial_state, normalize_l22_c_state, search_paths


class WorkbookStateTests(SimpleTestCase):
    def test_exact_scope_and_searches(self):
        self.assertEqual(len(ACTIVITIES), len(set(ACTIVITIES)))
        for a in ACTIVITIES.values():
            self.assertIn(a['session'], (8, 9))
            self.assertIn(a['printed_page'], range(38, 50))
            if a['interaction_type'] == 'search':
                for item in a['items']:
                    self.assertTrue(search_paths(a, item['text']), (a['activity_key'], item['text']))

    def test_three_readings_three_listens_repeat_and_gate(self):
        a = get_activity('aral-l22-g5-f-word-search')
        state = initial_state()
        with self.assertRaises(ValueError):
            apply_event(a, state, {'action': 'answer', 'answer': search_paths(a, 'freezer')[0]})
        for _ in range(2):
            for _ in range(3):
                apply_event(a, state, {'action': 'reading'}, False)
            self.assertEqual(state['oral']['item-1']['phase'], 'listen')
            with self.assertRaises(ValueError):
                apply_event(a, state, {'action': 'reading'}, True)
            for _ in range(3):
                apply_event(a, state, {'action': 'listened'})
            self.assertEqual(state['oral']['item-1']['attempts'], 0)
        apply_event(a, state, {'action': 'reading'}, True)
        self.assertEqual(state['index'], 0)
        with self.assertRaises(ValueError):
            apply_event(a, state, {'action': 'finish'})
        apply_event(a, state, {'action': 'answer', 'answer': search_paths(a, 'freezer')[0]})
        self.assertEqual(state['index'], 1)

    def test_builder_needs_written_word_after_every_syllable(self):
        a = get_activity('aral-l22-g4-f-syllable-builder')
        s = initial_state()
        for i in range(len(a['items'])):
            apply_event(a, s, {'action': 'reading'}, True)
            if i < len(a['items']) - 1:
                apply_event(a, s, {'action': 'answer'})
        with self.assertRaises(ValueError):
            apply_event(a, s, {'action': 'answer', 'answer': []})
        apply_event(a, s, {'action': 'answer', 'answer': [['item-1', 'item-8']]})
        self.assertFalse(s['completed'])
        apply_event(a, s, {'action': 'finish'})
        self.assertTrue(s['completed'])

    def test_lesson22_gawain1_preserves_big_box_and_requires_both_phases(self):
        a = get_activity('aral-l22-g1-c-syllable-builder')
        self.assertEqual(a['title'], 'Letrang Cc')
        self.assertEqual(a['instruction'], 'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita mula rito.')
        self.assertEqual(a['rows'], [
            ['cac', 'ce', 'ca'], ['bu', 'com', 'pu'], ['ga', 'tus', 'ter'],
            ['yan', 'Car', 'do'], ['bi', 'ca', 'net'], ['te', 'Ce', 'les'],
        ])
        self.assertEqual(a['bigbox_cells'][1], [
            ['item-4'], ['item-5'], ['item-6'],
        ])
        box_piece_by_id = {item['id']: item['text'] for item in a['items']}
        self.assertEqual(
            [[box_piece_by_id[item_id] for item_id in cell] for cell in a['bigbox_cells'][1]],
            [['bu'], ['com'], ['pu']],
        )
        self.assertEqual(len(a['items']), 18)
        s = initial_state()
        with self.assertRaisesMessage(ValueError, 'Basahin muna'):
            apply_event(a, s, {'action': 'build_word', 'parts': ['item-1', 'item-8']})
        apply_event(a, s, {'action': 'reading_started'})
        with self.assertRaisesMessage(ValueError, 'Hindi nakuha'):
            apply_event(a, s, {'action': 'reading_attempt'}, False)
        apply_event(a, s, {'action': 'reading_attempt'}, True)
        apply_event(a, s, {'action': 'build_word', 'parts': ['item-1', 'item-4']})
        self.assertEqual(s['found_words'], [])
        self.assertEqual(s['pending_words'][0]['word'], 'cacbu')
        self.assertTrue(s['last_feedback'].startswith('Subukan muli.'))
        with self.assertRaisesMessage(ValueError, 'Bumuo muna'):
            apply_event(a, s, {'action': 'finish'})
        apply_event(a, s, {'action': 'build_word', 'parts': ['item-1', 'item-8']})
        with self.assertRaisesMessage(ValueError, 'ibang salita'):
            apply_event(a, s, {'action': 'build_word', 'parts': ['item-1', 'item-8']})
        apply_event(a, s, {'action': 'finish'})
        self.assertTrue(s['completed'])
        self.assertEqual(s['found_words'], ['cactus'])

    def test_lesson22_gawain1_com_is_one_big_box_piece(self):
        a = get_activity('aral-l22-g1-c-syllable-builder')
        self.assertEqual(a['items'][4], {'id': 'item-5', 'text': 'com'})
        self.assertNotIn('m', [item['text'] for item in a['items']])
        s = initial_state()
        apply_event(a, s, {'action': 'reading_started'})
        apply_event(a, s, {'action': 'reading_attempt'}, True)
        apply_event(a, s, {'action': 'build_word', 'parts': ['item-5']})
        self.assertEqual(s['found_words'], ['com'])

    def test_lesson22_gawain1_advances_only_the_verified_current_syllable(self):
        a = get_activity('aral-l22-g1-c-syllable-builder')
        s = initial_state()
        apply_event(a, s, {'action': 'reading_started'})
        apply_event(a, s, {'action': 'reading_syllable_attempt'}, True)
        self.assertEqual(s['index'], 1)
        self.assertFalse(s['read_aloud_completed'])
        apply_event(a, s, {'action': 'reading_syllable_attempt'}, False)
        self.assertEqual(s['index'], 1)
        self.assertEqual(s['last_feedback'], 'Subukan muli.')
        for _ in range(len(a['items']) - 1):
            apply_event(a, s, {'action': 'reading_syllable_attempt'}, True)
        self.assertEqual(s['index'], len(a['items']))
        self.assertTrue(s['read_aloud_completed'])

    def test_lesson22_gawain1_restores_partial_reading_at_the_next_unread_syllable(self):
        a = get_activity('aral-l22-g1-c-syllable-builder')
        s = initial_state()
        apply_event(a, s, {'action': 'reading_started'})
        for _ in range(4):
            apply_event(a, s, {'action': 'reading_syllable_attempt'}, True)
        apply_event(a, s, {'action': 'reading_syllable_attempt'}, False)
        self.assertEqual(s['index'], 4)
        self.assertFalse(s['read_aloud_completed'])
        self.assertEqual(s['reading_phase'], 'read')
        restored = normalize_l22_c_state(dict(s))
        self.assertEqual(restored['index'], 4)
        self.assertFalse(restored['read_aloud_completed'])
        self.assertFalse(restored['found_words'])

    def test_lesson22_gawain1_completion_unlocks_word_building_without_resetting_reading(self):
        a = get_activity('aral-l22-g1-c-syllable-builder')
        s = initial_state()
        apply_event(a, s, {'action': 'reading_started'})
        for _ in a['items']:
            apply_event(a, s, {'action': 'reading_syllable_attempt'}, True)
        self.assertEqual(s['index'], len(a['items']))
        self.assertTrue(s['read_aloud_completed'])
        apply_event(a, s, {'action': 'build_word', 'parts': ['item-1', 'item-8']})
        self.assertEqual(s['found_words'], ['cactus'])
        self.assertEqual(s['index'], len(a['items']))

    def test_lesson22_gawain1_migrates_legacy_co_m_selection_to_com(self):
        a = get_activity('aral-l22-g1-c-syllable-builder')
        legacy = {
            'index': 19, 'completed': False, 'read_aloud_completed': True,
            'draft': {'builder': ['item-5', 'item-19']},
        }
        apply_event(a, legacy, {'action': 'draft', 'draft': {'builder': ['item-5', 'item-19']}})
        self.assertEqual(legacy['draft']['builder'], ['item-5'])


class PrescribedWorkbookFlowTests(TestCase):
    def setUp(self):
        active_student_session = patch('pabasa_app.middleware.student_session_is_active', return_value=True)
        active_student_session.start()
        self.addCleanup(active_student_session.stop)
        school = School.objects.create(name='Workbook Flow School', code='WFS')
        self.student = User.objects.create(
            custom_id='WF-STUDENT', role='student', first_name='Test', last_name='Student',
            email='workbook-student@example.com', password_hash='test', sex='N/A',
            birth_month=1, birth_day=1, birth_year=2016, school_record=school,
        )
        self.teacher = User.objects.create(
            custom_id='WF-TEACHER', role='teacher', first_name='Test', last_name='Teacher',
            email='workbook-teacher@example.com', password_hash='test', sex='N/A',
            birth_month=1, birth_day=1, birth_year=1990, school_record=school,
        )
        self.section = Section.objects.create(
            school=school, class_code='WF-1', class_name='Workbook Flow', subject='Reading',
            teacher=self.teacher, is_active=True,
        )
        self.section.add_student(self.student)
        self.session_student(self.student)

    def session_student(self, user):
        session = self.client.session
        session.update({'user_id': user.pk, 'user_role': user.role, 'email': user.email})
        session.save()

    def test_catalog_has_one_prescribed_entry_per_workbook_key(self):
        keys = [key for key, value in PRESCRIBED_ACTIVITIES.items() if value.get('interaction') == 'prescribed_workbook']
        self.assertCountEqual(keys, ACTIVITIES.keys())
        session_8 = [value for value in PRESCRIBED_ACTIVITIES.values() if value.get('session_number') == 8]
        self.assertEqual(len(session_8), 22)
        lesson_22_gawain_1 = [value for value in session_8 if value.get('activity_key') == 'aral-l22-g1-c-syllable-builder']
        self.assertEqual(len(lesson_22_gawain_1), 1)
        self.assertEqual(lesson_22_gawain_1[0]['session_key'], 'session-8')
        self.assertEqual(lesson_22_gawain_1[0]['lesson_number'], 22)
        self.assertEqual(lesson_22_gawain_1[0]['gawain_number'], '1')
        for activity in ACTIVITIES.values():
            entry = PRESCRIBED_ACTIVITIES[activity['activity_key']]
            self.assertEqual(entry['session_number'], activity['session'])
            self.assertEqual(entry['lesson_number'], activity['lesson'] or '')

    def test_active_catalog_has_exact_workbook_sessions_8_to_11(self):
        active = active_prescribed_activities()
        groups = {
            session: [activity for activity in active if activity.get('session_key') == f'session-{session}']
            for session in (8, 9, 10, 11)
        }
        self.assertEqual([len(groups[session]) for session in (8, 9, 10, 11)], [22, 2, 2, 1])
        self.assertTrue(all(activity['lesson_number'] in (22, 23, 24) for activity in groups[8]))
        self.assertEqual([activity['activity_key'] for activity in groups[10]], ['lesson-26-gawain-1', 'lesson-26-gawain-2'])
        self.assertEqual([activity['activity_key'] for activity in groups[11]], ['lesson-27-gawain-1'])
        self.assertEqual(
            [activity['lesson_number'] for activity in groups[8]],
            [22] * 6 + [23] * 7 + [24] * 9,
        )

    def test_teacher_picker_uses_the_same_current_workbook_entries(self):
        self.session_student(self.teacher)
        response = self.client.get(reverse('course_teacher_view'))
        self.assertEqual(response.status_code, 200, response.content)
        workbook = active_prescribed_activities()
        groups = {
            session: [activity for activity in workbook if activity.get('session_key') == f'session-{session}']
            for session in (8, 9, 10, 11)
        }
        self.assertEqual([len(groups[session]) for session in (8, 9, 10, 11)], [22, 2, 2, 1])
        self.assertCountEqual(
            [activity['activity_key'] for activity in response.context['prescribed_lesson_26_activities']],
            ['lesson-26-gawain-1', 'lesson-26-gawain-2'],
        )
        self.assertEqual(
            [activity['activity_key'] for activity in response.context['prescribed_lesson_27_activities']],
            ['lesson-27-gawain-1'],
        )

    def test_legacy_material_copy_is_excluded_from_class_material_feed(self):
        Material.objects.create(
            teacher=self.teacher, section=self.section, title='Legacy duplicate',
            content_json={'activity_type': 'prescribed_workbook', 'activity_key': 'aral-l22-g2-c-word-reading'},
            item_type='word', type='assessment', source_type='template', status='published',
            student_access=True,
        )
        response = self.client.get(reverse('get_class_materials'), {'section_id': self.section.pk})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(any(item.get('title') == 'Legacy duplicate' for item in response.json().get('all_materials', [])))

    def test_teacher_preview_and_student_progress_use_shared_prescribed_routes(self):
        key = 'aral-l22-g1-c-syllable-builder'
        activity_url = reverse('prescribed_activity_page', kwargs={'activity_key': key})
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})

        self.session_student(self.teacher)
        preview = self.client.get(activity_url, {'preview': '1'})
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.context['workbook_payload']['preview'])
        self.assertEqual(preview.context['workbook_payload']['progress_url'], progress_url)
        self.assertEqual(preview.context['workbook_payload']['read_aloud_url'], reverse('reading_read_aloud_api'))

        self.session_student(self.student)
        page = self.client.get(activity_url)
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('material_id', page.context['workbook_payload'])
        state = page.context['workbook_payload']['state']
        response = self.client.post(progress_url, json.dumps({'action': 'reading_started', 'revision': state['revision']}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        state = response.json()['state']
        with patch('pabasa_app.views.reading_transcribe_api', return_value=JsonResponse({
            'success': True, 'transcript': 'cac', 'complete': True,
        })) as speech:
            response = self.client.post(progress_url, {
                'action': 'reading_syllable_attempt', 'revision': state['revision'],
                'audio': SimpleUploadedFile('reading.webm', b'audio', content_type='audio/webm'),
            })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(speech.called)
        state = response.json()['state']
        self.assertEqual(state['index'], 1)
        self.assertFalse(state['read_aloud_completed'])
        with patch('pabasa_app.views.reading_transcribe_api', return_value=JsonResponse({
            'success': True, 'transcript': 'wrong', 'complete': False,
        })):
            response = self.client.post(progress_url, {
                'action': 'reading_syllable_attempt', 'revision': state['revision'],
                'audio': SimpleUploadedFile('reading.webm', b'audio', content_type='audio/webm'),
            })
        self.assertEqual(response.status_code, 200, response.content)
        state = response.json()['state']
        self.assertEqual(state['index'], 1)
        self.assertEqual(state['last_feedback'], 'Subukan muli.')
        with patch('pabasa_app.views.reading_transcribe_api', return_value=JsonResponse({
            'success': True, 'transcript': 'cac ce ca', 'complete': False,
        })) as speech:
            response = self.client.post(progress_url, {
                'action': 'reading_attempt', 'revision': state['revision'],
                'audio': SimpleUploadedFile('reading.webm', b'audio', content_type='audio/webm'),
            })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(speech.called)
        state = response.json()['state']
        self.assertTrue(state['read_aloud_completed'])
        response = self.client.post(progress_url, json.dumps({
            'action': 'build_word', 'parts': ['item-1', 'item-8'], 'revision': state['revision'],
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        state = response.json()['state']
        self.assertEqual(state['found_words'], ['cactus'])
        response = self.client.post(progress_url, json.dumps({'action': 'finish', 'revision': state['revision']}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        progress = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
        self.assertTrue(progress.activity_completed)
        self.assertTrue(progress.state['completed'])
        self.assertEqual(progress.current_index, 1)

    def test_workbook_progress_returns_json_for_an_expired_student_session(self):
        key = 'aral-l22-g1-c-syllable-builder'
        self.client.session.flush()
        response = self.client.post(
            reverse('prescribed_activity_progress', kwargs={'activity_key': key}),
            {'action': 'reading_started', 'revision': 0},
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response['Content-Type'].split(';', 1)[0], 'application/json')
        self.assertEqual(response.json(), {'success': False, 'error': 'Authentication required'})

    def test_each_new_workbook_activity_keeps_its_workbook_route(self):
        for key, expected_session in (
            ('aral-l22-g1-c-syllable-builder', 8),
            ('aral-s9-a1-family-drawing', 9),
        ):
            with self.subTest(activity_key=key):
                response = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': key}))
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.context['workbook_payload']['activity']['session'], expected_session)
