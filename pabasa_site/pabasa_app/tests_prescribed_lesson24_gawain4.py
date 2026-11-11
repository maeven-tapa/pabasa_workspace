from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from .prescribed_workbook import (
    L24_G4_X_WORDS,
    L24_G4_X_CANONICAL_WORDS,
    apply_event,
    get_activity,
    initial_l24_g4_state,
    initial_l24_g4_builder_state,
    normalize_l24_g4_builder_state,
    l24_g4_pronunciation_match,
    L24_G4_BUILDER_READING_ALIASES,
    l24_g4_builder_pronunciation_match,
    initial_l24_g5_syllabication_state,
    normalize_l24_g5_syllabication_state,
)


class Lesson24Gawain4WorkbookTests(SimpleTestCase):
    def test_configured_reading_to_builder_and_completion_state_machine(self):
        """Exercise the target-only gate with temporary, test-only aliases."""
        activity = get_activity('aral-l24-g4-x-syllable-builder')
        aliases = {item['id']: {f"approved-{item['id']}"} for item in activity['items']}
        with patch.dict(L24_G4_BUILDER_READING_ALIASES, aliases, clear=True):
            state = initial_l24_g4_builder_state()
            normalize_l24_g4_builder_state(state)
            self.assertFalse(state['reading_configuration_required'])
            self.assertTrue(l24_g4_builder_pronunciation_match('item-1', 'approved-item-1'))
            self.assertFalse(l24_g4_builder_pronunciation_match('item-1', 'unapproved-item-1'))
            self.assertEqual([item['id'] for item in activity['items'] if item['text'] == 'phone'], ['item-5', 'item-12'])
            apply_event(activity, state, {'action': 'reading_started'})
            for _ in range(3):
                apply_event(activity, state, {'action': 'reading_syllable_attempt', 'item_index': 0}, verified_reading=False)
            self.assertEqual(state['reading_phase'], 'help')
            apply_event(activity, state, {'action': 'read_aloud'})
            apply_event(activity, state, {'action': 'retry_reading'})
            for index in range(len(activity['items'])):
                apply_event(activity, state, {'action': 'reading_syllable_attempt', 'item_index': index, 'transcript': f'approved-item-{index + 1}'}, verified_reading=True)
            self.assertTrue(state['read_aloud_completed'])
            self.assertEqual(state['reading_index'], 12)
            self.assertEqual(state['reading_phase'], 'complete')
            apply_event(activity, state, {'action': 'build_words', 'words': [['item-1', 'item-8']]})
            apply_event(activity, state, {'action': 'finish'})
            self.assertTrue(state['completed'])
            completed_state = dict(state)
            apply_event(activity, state, {'action': 'finish'})
            self.assertEqual(state, completed_state)

    def test_unconfigured_reading_gate_keeps_existing_builder_available(self):
        activity = get_activity('aral-l24-g4-x-syllable-builder')
        state = initial_l24_g4_builder_state()
        self.assertEqual(L24_G4_BUILDER_READING_ALIASES, {})
        apply_event(activity, state, {'action': 'reading_started'})
        self.assertTrue(state['reading_configuration_required'])
        self.assertEqual(state['reading_index'], 0)
        self.assertEqual(state['reading_attempts'], 0)
        apply_event(activity, state, {'action': 'draft', 'draft': {'builder': ['item-1'], 'words': []}})
        self.assertEqual(state['draft']['builder'], ['item-1'])

    def test_builder_preserves_multiple_submissions_and_finish_eligibility(self):
        activity = get_activity('aral-l24-g4-x-syllable-builder')
        state = initial_l24_g4_builder_state()
        with self.assertRaisesMessage(ValueError, 'Bumuo muna'):
            apply_event(activity, state, {'action': 'finish'})
        apply_event(activity, state, {'action': 'build_words', 'words': [['item-1', 'item-8']]})
        apply_event(activity, state, {'action': 'build_words', 'words': [['item-5', 'item-10']]})
        restored = normalize_l24_g4_builder_state(state)
        self.assertEqual(restored['built_words'], [['item-1', 'item-8'], ['item-5', 'item-10']])
        self.assertEqual(restored['index'], 2)
        apply_event(activity, restored, {'action': 'finish'})
        self.assertTrue(restored['completed'])

    def test_reading_scaffold_is_target_guarded_and_uses_local_mapped_audio(self):
        root = Path(__file__).parent
        js = (root / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        views = (root / 'views.py').read_text(encoding='utf-8')
        template = (root / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')
        self.assertIn('function startL24G4Reading()', js)
        self.assertIn("if(l24G4Builder&&!preview&&!l24G4BuilderFallback&&!state.read_aloud_completed)", js)
        self.assertIn('let l24G4BuilderFallback = false;', js)
        self.assertIn("add('Bumuo ng Salita',()=>{l24G4BuilderFallback=true;renderBuilder();},false)", js)
        self.assertIn("if(state.reading_configuration_required){\n      state.last_feedback='Hindi pa handa ang pagsuri ng pagbigkas para sa gawaing ito.'", js)
        self.assertIn('if(l24G4Builder)content.replaceChildren(box)', js)
        self.assertIn("workbook_payload.activity.activity_key == 'aral-l24-g4-x-syllable-builder' %}<script src=\"{% static 'pabasa_app/js/prescribed_workbook.js' %}?v=20261111-l24-g4-reading-first-1\"", template)
        self.assertIn("l22_g1_audio_root = 'pabasa_app/prescribed/audio/SESSION_8/LESSON_22/GAWAIN_1/'", views)
        self.assertIn("'Handa ka na?': static(l22_g1_audio_root + 'Handa ka na_TTS.mp3')", views)

    def test_big_box_activity_uses_exact_four_by_three_source_grid(self):
        activity = get_activity('aral-l24-g4-x-syllable-builder')
        self.assertEqual(activity['interaction_type'], 'builder')
        self.assertEqual(activity['instruction'], 'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita mula rito.')
        self.assertEqual([item['text'] for item in activity['items']], [
            'A', 'Fe', 'xe', 'xy', 'phone', 'sax',
            'rox', 'lex', 'o', 'lix', 'lo', 'phone',
        ])
        self.assertEqual(len(activity['items']), 12)
        self.assertEqual(sum(item['text'] == 'phone' for item in activity['items']), 2)
        self.assertEqual(L24_G4_X_CANONICAL_WORDS, ())

    def test_big_box_builds_by_stable_cell_ids_and_resets(self):
        activity = get_activity('aral-l24-g4-x-syllable-builder')
        state = initial_l24_g4_builder_state()
        apply_event(activity, state, {
            'action': 'draft',
            'draft': {'builder': ['item-1', 'item-8'], 'words': [['item-1', 'item-8']]},
        })
        self.assertEqual(state['draft']['builder'], ['item-1', 'item-8'])
        apply_event(activity, state, {'action': 'build_words', 'words': [['item-1', 'item-8']]})
        restored = normalize_l24_g4_builder_state(state)
        self.assertEqual(restored['built_words'], [['item-1', 'item-8']])
        apply_event(activity, restored, {'action': 'finish'})
        self.assertTrue(restored['completed'])
        apply_event(activity, restored, {'action': 'restart'})
        self.assertEqual(restored, initial_l24_g4_builder_state())

    def test_builder_renderer_is_not_the_generic_oral_reading_path(self):
        js = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        self.assertIn("if(l24G4Builder&&!preview){renderBuilder();lock();return;}", js)
        self.assertIn("button('Isumite ang mga salita',()=>perform({action:'build_words',words}),true)", js)
        self.assertIn("(!l24G4Builder&&!oral().passed)", js)

    def test_identity_content_order_and_assets(self):
        activity = get_activity('aral-l24-g4-x-pictures')
        self.assertEqual((activity['session'], activity['lesson'], activity['activity_number']), (8, 24, '4'))
        self.assertEqual(activity['instruction'], 'Kilalanin ang bawat larawan at subuking basahin ito kasabay ng guro.')
        self.assertEqual(tuple(item['text'] for item in activity['items']), L24_G4_X_WORDS)
        self.assertEqual(len(activity['items']), 3)
        self.assertEqual(activity['images'], {
            'item-1': '/static/pabasa_app/images/aral_workbook/x-ray.png',
            'item-2': '/static/pabasa_app/images/aral_workbook/fax-machine.png',
            'item-3': '/static/pabasa_app/images/aral_workbook/fox.png',
        })

    def test_speech_matching_is_exact_with_safe_x_ray_hyphen_normalization(self):
        self.assertTrue(l24_g4_pronunciation_match('x-ray', 'X ray'))
        self.assertTrue(l24_g4_pronunciation_match('fax machine', 'fax machine'))
        self.assertTrue(l24_g4_pronunciation_match('fox', 'FOX'))
        self.assertFalse(l24_g4_pronunciation_match('fax machine', 'fax'))
        self.assertFalse(l24_g4_pronunciation_match('fox', 'foxes'))

    def test_progress_advances_once_and_stale_item_is_ignored(self):
        activity = get_activity('aral-l24-g4-x-pictures')
        state = initial_l24_g4_state()
        for index, word in enumerate(L24_G4_X_WORDS):
            apply_event(activity, state, {'action': 'reading_attempt', 'item_index': index, 'transcript': word}, True)
            apply_event(activity, state, {'action': 'reading_attempt', 'item_index': index, 'transcript': word}, True)
            self.assertEqual(state['index'], index + 1)
        self.assertTrue(state['completed'])
        self.assertEqual(state['completed_words'], [0, 1, 2])

        state = initial_l24_g4_state()
        apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 1, 'transcript': 'fax machine'}, True)
        self.assertEqual(state['index'], 0)
        self.assertEqual(state['completed_words'], [])

    def test_standardized_picture_reading_hooks_are_scoped(self):
        js = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        css = (Path(__file__).parent / 'static/pabasa_app/css/prescribed_l24_g4_pictures.css').read_text(encoding='utf-8')
        template = (Path(__file__).parent / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')
        for expected in ('wb-picture-reading', 'wb-picture-image', 'wb-picture-word', 'wb-picture-feedback', 'Pakinggan', 'Basahin'):
            self.assertIn(expected, js)
        self.assertIn('wb-l24-g4-pictures-page', css)
        self.assertIn('section_display_label', template)
        self.assertIn('aral-l24-g4-x-pictures', template)
        self.assertNotIn('overflow:hidden', css)

    def test_picture_instruction_waits_for_lesson24_start_event(self):
        js = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        template = (Path(__file__).parent / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')
        self.assertIn(
            'if(!preview&&!instructionSpoken&&!pictureReading)',
            js,
        )
        self.assertIn(
            'if(pictureReading&&!activityStarted&&text===instructionText)return;',
            js,
        )
        self.assertIn("document.addEventListener('pabasa:l24-started'", js)
        self.assertIn('playPrescribedAudio(instructionText,true)', js)
        self.assertIn('20261019-save-recovery', template)


class Lesson24Gawain5SyllabicationTests(SimpleTestCase):
    def test_worked_example_and_exact_student_content(self):
        activity = get_activity('aral-l24-g5-z-syllabication')
        self.assertEqual(activity['interaction_type'], 'syllables')
        self.assertEqual(activity['instruction'], 'Pantigin ang sumusunod na salitang may letrang Zz. Ginawa ang unang bilang para sa iyo.')
        self.assertEqual(activity['worked_example'], '1. zigzag = zig•zag')
        self.assertEqual([item['text'] for item in activity['items']], [
            'Zandra', 'Gomez', 'Zamora', 'zipper', 'Zarate',
            'Legazpi', 'Zoren', 'zebra', 'Mendoza',
        ])
        self.assertEqual(activity['syllable_answers'], [
            'Zan-dra', 'Go-mez', 'Za-mo-ra', 'zip-per', 'Za-ra-te',
            'Le-gaz-pi', 'Zo-ren', 'ze-bra', 'Men-do-za',
        ])

    def test_example_is_not_interactive_and_progress_starts_at_zandra(self):
        activity = get_activity('aral-l24-g5-z-syllabication')
        state = initial_l24_g5_syllabication_state()
        self.assertEqual(state['index'], 0)
        self.assertEqual(state['answers'], {})
        self.assertEqual(activity['item_labels'][0], '2.')
        self.assertNotIn('zigzag', [item['text'] for item in activity['items']])

    def test_answer_progress_persistence_completion_and_reset(self):
        activity = get_activity('aral-l24-g5-z-syllabication')
        state = initial_l24_g5_syllabication_state()
        apply_event(activity, state, {'action': 'answer', 'item_index': 0, 'answer': {'text': 'wrong'} })
        self.assertEqual(state['index'], 0)
        self.assertEqual(state['last_feedback'], 'Subukan muli.')
        for index, answer in enumerate(activity['syllable_answers']):
            apply_event(activity, state, {'action': 'answer', 'item_index': index, 'answer': {'text': answer}})
            restored = normalize_l24_g5_syllabication_state(state)
            self.assertEqual(restored['index'], index + 1)
        self.assertTrue(state['completed'])
        self.assertEqual(len(state['answers']), 9)
        apply_event(activity, state, {'action': 'restart'})
        self.assertEqual(state, initial_l24_g5_syllabication_state())

    def test_dedicated_renderer_and_scoped_ui(self):
        root = Path(__file__).parent
        js = (root / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        css = (root / 'static/pabasa_app/css/prescribed_l24_g5_syllabication.css').read_text(encoding='utf-8')
        template = (root / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')
        self.assertIn("renderL24G5Syllables()", js)
        self.assertIn('wb-g5-workspace', js)
        self.assertIn('PRESCRIBED-BG.jpg', css)
        self.assertIn('wb-progress-track', template)
        self.assertNotIn('overflow:hidden', css)
