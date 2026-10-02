import uuid
from pathlib import Path

from django.test import TestCase
from django.urls import reverse

from .prescribed_workbook import (
    L22_G4_F_WORDS,
    apply_event,
    get_activity,
    initial_l22_g4_state,
    l22_g4_pronunciation_match,
    normalize_l22_g4_state,
)


class PrescribedLesson22Gawain4Tests(TestCase):
    key = 'aral-l22-g4-f-syllable-builder'

    def test_workbook_content_and_approved_words_are_exact(self):
        activity = get_activity(self.key)
        self.assertEqual(activity['instruction'], 'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng salita mula rito.')
        self.assertEqual([item['text'] for item in activity['items']], ['free', 'fries', 'Fi', 'Fe', 'na', 'li', 'lix', 'zer', 'pe'])
        self.assertEqual(L22_G4_F_WORDS, ('freezer', 'fries', 'Fina', 'Filipino', 'Felix'))

    def test_reading_is_ordered_and_phase_two_stays_locked(self):
        activity = get_activity(self.key)
        state = initial_l22_g4_state()
        with self.assertRaises(ValueError):
            apply_event(activity, state, {'action': 'build_word', 'parts': ['item-1', 'item-8']})
        for index, item in enumerate(activity['items']):
            apply_event(activity, state, {'action': 'reading_started'})
            apply_event(activity, state, {'action': 'reading_attempt', 'transcript': item['text']}, True)
            self.assertEqual(state['reading_index'], index + 1)
            self.assertIn(index, state['completed_reading'])
        self.assertEqual(state['reading_phase'], 'complete')

    def test_reading_highlight_tracks_the_single_authoritative_target(self):
        script = (Path(__file__).resolve().parent / 'static/pabasa_app/js/prescribed_l22_g4_f_builder.js').read_text(encoding='utf-8')
        css = (Path(__file__).resolve().parent / 'static/pabasa_app/css/prescribed_l22_g4_f_builder_refinement.css').read_text(encoding='utf-8')
        self.assertIn("const target=items[Math.min(n,8)]||items[8]", script)
        self.assertIn("tile.classList.toggle('active',locked&&i===n)", script)
        self.assertIn('.tile.active', css)
        self.assertIn(".tile.active::before", css)
        self.assertIn("content:'BASAHIN ITO'", css)

        activity = get_activity(self.key)
        state = initial_l22_g4_state()
        apply_event(activity, state, {'action': 'reading_started'})
        apply_event(activity, state, {'action': 'reading_attempt', 'transcript': 'wrong'}, False)
        self.assertEqual(state['reading_index'], 0)
        self.assertEqual(state['completed_reading'], [])
        apply_event(activity, state, {'action': 'reading_attempt', 'transcript': 'free'}, True)
        self.assertEqual(state['reading_index'], 1)
        self.assertEqual(state['completed_reading'], [0])

    def test_wrong_and_unclear_readings_have_correct_attempt_behavior(self):
        activity = get_activity(self.key)
        state = initial_l22_g4_state()
        apply_event(activity, state, {'action': 'reading_started'})
        for expected in (1, 2, 3):
            apply_event(activity, state, {'action': 'reading_attempt', 'transcript': 'unrelated'}, False)
            self.assertEqual(state['reading_attempts'], expected)
        self.assertEqual(state['reading_phase'], 'help')
        before = state['reading_attempts']
        state['reading_phase'] = 'read'
        apply_event(activity, state, {'action': 'reading_attempt', 'transcript': ''}, None)
        self.assertEqual(state['reading_attempts'], before)

    def test_help_retry_and_duplicate_build_protection(self):
        activity = get_activity(self.key)
        state = initial_l22_g4_state()
        state['completed_reading'] = list(range(9)); state['reading_index'] = 9
        normalize_l22_g4_state(state)
        apply_event(activity, state, {'action': 'build_word', 'parts': ['item-1', 'item-8']})
        self.assertEqual(state['built_words'], ['freezer'])
        apply_event(activity, state, {'action': 'build_word', 'parts': ['item-1', 'item-8']})
        self.assertEqual(state['built_words'], ['freezer'])
        apply_event(activity, state, {'action': 'build_word', 'parts': ['item-2']})
        self.assertEqual(state['built_words'], ['freezer', 'fries'])

    def test_target_aware_matching_is_scoped(self):
        self.assertTrue(l22_g4_pronunciation_match('free', 'three'))
        self.assertFalse(l22_g4_pronunciation_match('free', 'banana'))

    def test_reading_client_exposes_listening_processing_result_and_voice_feedback(self):
        script = (Path(__file__).resolve().parent / 'static/pabasa_app/js/prescribed_l22_g4_f_builder.js').read_text(encoding='utf-8')
        self.assertIn("uiPhase='listening'", script)
        self.assertIn("uiPhase='processing'", script)
        self.assertIn('Pinoproseso ang iyong pagbasa', script)
        self.assertIn('spinner', script)
        self.assertIn('await announce(feedback)', script)
        self.assertIn("if(busy||speechBusy||uiPhase==='listening'||uiPhase==='processing')return", script)
        self.assertIn('stopStream()', script)

    def test_startup_modal_and_replay_share_the_canonical_instruction_path(self):
        script = (Path(__file__).resolve().parent / 'static/pabasa_app/js/prescribed_l22_g4_f_builder.js').read_text(encoding='utf-8')
        template = (Path(__file__).resolve().parent / 'templates/pabasa_app/prescribed_l22_g4_f_builder_page.html').read_text(encoding='utf-8')
        self.assertIn("function playInstruction(){return playAudio(instruction)}", script)
        self.assertIn("document.getElementById('instruction').onclick=playInstruction", script)
        self.assertIn("const startLesson=window.PabasaLessonStart||", script)
        self.assertIn("startLesson({modalId:'wb-l22-g4-start'", script)
        self.assertIn("playInstruction()", script)
        self.assertNotIn('setTimeout(()=>playInstruction', script)
        self.assertIn('id="wb-l22-g4-start"', template)
        self.assertIn('id="wb-l22-g4-start-button"', template)
        self.assertIn('id="wb-l22-g4-later-button"', template)
        self.assertIn("lesson_start_modal.css", template)
        self.assertIn("lesson_start_modal.js", template)
        self.assertIn('SESSION 8 · LESSON 22 · GAWAIN 4', template)

    def test_page_uses_specialized_template_and_canonical_next_route(self):
        token = uuid.uuid4().hex
        session = self.client.session
        session.update({'user_id': 0, 'user_role': 'student', 'email': f'{token}@example.com'})
        session.save()
        # Preview is intentionally not used here; the catalog and route wiring
        # are covered without fabricating a student record in this focused test.
        self.assertEqual(reverse('prescribed_activity_page', kwargs={'activity_key': self.key}), '/dashboard/assessment/activity/prescribed/aral-l22-g4-f-syllable-builder/')
