from django.test import SimpleTestCase
from django.urls import reverse
from django.template.loader import render_to_string
from pathlib import Path

from .prescribed_workbook import (
    ACTIVITIES, L23_G1_WORDS, apply_event, get_activity, initial_l23_g1_state,
    l23_g1_pronunciation_match,
)


class Lesson23Gawain1Tests(SimpleTestCase):
    def test_render_pipeline_is_wired_for_the_canonical_key(self):
        root = Path(__file__).resolve().parent
        template = (root / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')
        renderer = (root / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        startup = (root / 'static/pabasa_app/js/prescribed_l23_startup.js').read_text(encoding='utf-8')
        stylesheet = (root / 'static/pabasa_app/css/prescribed_l23_g1_standard.css').read_text(encoding='utf-8')

        key = 'aral-l23-g1-n-syllable-builder'
        self.assertEqual(
            reverse('prescribed_activity_page', kwargs={'activity_key': key}),
            '/dashboard/assessment/activity/prescribed/aral-l23-g1-n-syllable-builder/',
        )
        self.assertIn(key, template)
        self.assertIn("prescribed_l23_g1_standard.css", template)
        self.assertIn("prescribed_workbook.js", template)
        self.assertIn("prescribed_l23_startup.js", template)
        self.assertIn('id="wb-l23-g1-start"', template)
        self.assertIn('id="wb-l23-g1-start-button"', template)
        self.assertIn('class="wb-l23-g1-page-layout"', template)
        self.assertIn('id="wb-back"', template)
        self.assertIn('wb-l23-g1-header-replay', template)
        self.assertIn("const l23G1 = a.activity_key === 'aral-l23-g1-n-syllable-builder';", renderer)
        self.assertIn('function renderCBuilder()', renderer)
        self.assertIn('class="wb-bigbox"', renderer)
        self.assertIn('class="wb-reading-panel"', renderer)
        self.assertIn('class="wb-word-panel', renderer)
        self.assertIn('wb-l23-g1-completion-modal', renderer)
        self.assertIn('Magaling!', renderer)
        self.assertIn('Natapos mo ang Gawain 1.', renderer)
        self.assertIn('SUNOD NA GAWAIN', renderer)
        self.assertIn('BUMALIK SA AKING ARALIN', renderer)
        self.assertIn('requestL23G1Restart', renderer)
        self.assertIn("if(l23G1)content.querySelector('.wb-l22-banner')?.remove();", renderer)
        self.assertIn('const backLink=document.getElementById(\'wb-back\');if(backLink)backLink.hidden=preview;', renderer)
        self.assertIn(key, startup)
        self.assertIn("const modal = document.getElementById(`wb-l23-${number}-start`);", startup)
        self.assertIn('grid-template-rows:repeat(4,', stylesheet)
        self.assertIn('grid-template-columns:minmax(0,1.25fr) minmax(300px,.75fr)', stylesheet)
        self.assertIn('.wb-l23-page .wb-start-cue{top:4px;', stylesheet)

    def test_workbook_template_renders_the_target_payload_and_startup_controls(self):
        activity = get_activity('aral-l23-g1-n-syllable-builder')
        html = render_to_string('pabasa_app/prescribed_workbook_page.html', {
            'workbook_payload': {
                'activity': activity,
                'state': initial_l23_g1_state(),
                'preview': False,
                'progress_url': reverse('prescribed_activity_progress', kwargs={'activity_key': activity['activity_key']}),
                'read_aloud_url': reverse('reading_read_aloud_api'),
                'back_url': reverse('assessment'),
                'next_url': reverse('prescribed_activity_page', kwargs={'activity_key': 'aral-l23-g2-n-word-reading'}),
                'local_audio': {},
            },
        })
        self.assertIn('Big Box: Ñ', html)
        self.assertIn('id="wb-content"', html)
        self.assertIn('id="wb-l23-g1-start"', html)
        self.assertIn('id="wb-back"', html)
        self.assertIn('wb-l23-g1-header-replay', html)
        self.assertIn('prescribed_l23_g1_standard.css', html)
        self.assertIn('prescribed_l23_startup.js', html)

    def test_workbook_instruction_and_big_box_are_exact(self):
        activity = get_activity('aral-l23-g1-n-syllable-builder')
        self.assertEqual(activity['instruction'], 'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita mula rito.')
        self.assertEqual(activity['rows'], [
            ['Ni', 'La', 'ña'], ['Cas', 'Bi', 'da'],
            ['El', 'ño', 'ñan'], ['Cen', 'ta', 'ñe'],
        ])
        self.assertEqual([item['text'] for item in activity['items']], [
            'Ni', 'La', 'ña', 'Cas', 'Bi', 'da', 'El', 'ño', 'ñan', 'Cen', 'ta', 'ñe',
        ])

    def test_reading_is_sequential_and_only_real_errors_consume_attempts(self):
        activity = get_activity('aral-l23-g1-n-syllable-builder')
        state = initial_l23_g1_state()
        apply_event(activity, state, {'action': 'reading_started'})
        apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': ''}, None)
        self.assertEqual(state['reading_attempts'], 0)
        apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': 'wrong'}, False)
        self.assertEqual((state['index'], state['reading_attempts']), (0, 1))
        apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': 'ni'}, True)
        self.assertEqual((state['index'], state['reading_attempts']), (1, 0))
        for item in activity['items'][1:]:
            apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': item['text']}, True)
        self.assertTrue(state['read_aloud_completed'])
        self.assertEqual(state['index'], 12)

    def test_help_retry_and_word_build_completion_require_both_phases(self):
        activity = get_activity('aral-l23-g1-n-syllable-builder')
        state = initial_l23_g1_state()
        with self.assertRaisesMessage(ValueError, 'Basahin muna'):
            apply_event(activity, state, {'action': 'build_word', 'parts': ['item-1', 'item-8']})
        apply_event(activity, state, {'action': 'reading_started'})
        for _ in range(3):
            apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': 'wrong'}, False)
        self.assertEqual(state['reading_phase'], 'help')
        apply_event(activity, state, {'action': 'read_aloud'})
        apply_event(activity, state, {'action': 'retry_reading'})
        for item in activity['items']:
            apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': item['text']}, True)
        apply_event(activity, state, {'action': 'build_word', 'parts': ['item-1', 'item-8']})
        self.assertEqual(state['found_words'], list(L23_G1_WORDS))
        apply_event(activity, state, {'action': 'finish'})
        self.assertTrue(state['completed'])

    def test_ntilde_pronunciation_is_scoped_to_current_target(self):
        self.assertTrue(l23_g1_pronunciation_match('ño', 'nyo'))
        self.assertTrue(l23_g1_pronunciation_match('ña', 'na'))
        self.assertFalse(l23_g1_pronunciation_match('ño', 'ni'))
        self.assertFalse(l23_g1_pronunciation_match('La', 'ño'))
