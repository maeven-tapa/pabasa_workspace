import json
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.test import TestCase
from django.urls import reverse

from .models import Material, School, Section, StudentActivityProgress, User
from .prescribed_activity_catalog import PRESCRIBED_ACTIVITIES, active_prescribed_activities
from .prescribed_workbook import (
    ACTIVITIES, L22_C_ACCEPTED_BUILDS, L22_G2_C_WORDS, L22_G3_C_WORD_PATHS, L22_G5_F_WORD_PATHS, apply_event, get_activity,
    initial_l22_g2_state, initial_l22_g3_state, initial_l22_g5_state,
    initial_state, l22_g2_pronunciation_match, initial_l23_g1_state,
    l23_g1_pronunciation_match, normalize_l22_g2_speech,
    normalize_l22_c_state, search_paths, initial_s9_a2_state,
    L23_G3_J_WORDS, L23_G4_SYLLABLE_ANSWERS, L23_G7_Q_WORDS, initial_l23_g3_state,
    initial_l23_g4_state, initial_l23_g7_state, l23_g3_pronunciation_match,
    l23_g7_pronunciation_match, normalize_l23_g4_syllables,
)
from .reading_stt import l22_c_pronunciation_match


class WorkbookStateTests(SimpleTestCase):
    def test_session8_completion_popup_contract_covers_all_renderers(self):
        root = Path(__file__).parent
        js_root = root / 'static/pabasa_app/js'
        css_root = root / 'static/pabasa_app/css'
        popup = (js_root / 'session8_completion_popup.js').read_text(encoding='utf-8')
        popup_css = (css_root / 'session8_completion_popup.css').read_text(encoding='utf-8')
        shared = (js_root / 'prescribed_workbook.js').read_text(encoding='utf-8')
        controls = (root / 'templates/pabasa_app/session8_11_prescribed_controls.html').read_text(encoding='utf-8')

        self.assertIn("aria-modal','true'", popup)
        self.assertIn("node.inert=true", popup)
        self.assertIn('Bumalik sa Aking Aralin', popup)
        self.assertNotIn('Magpatuloy', popup)
        self.assertNotIn('Susunod', popup)
        self.assertIn('backdrop-filter:blur(6px)', popup_css)
        self.assertIn('place-items:center', popup_css)
        self.assertIn('session8_completion_popup.css', controls)
        self.assertIn('session8_completion_popup.js', controls)

        shared_keys = {
            'aral-l22-g1-c-syllable-builder', 'aral-l23-g1-n-syllable-builder',
            'aral-l23-g3-j-word-reading', 'aral-l23-g4-j-syllabication',
            'aral-l23-g6-q-syllable-builder', 'aral-l23-g7-q-word-reading',
            'aral-l24-g1-v-syllable-builder', 'aral-l24-g3-x-word-reading',
            'aral-l24-g4-x-pictures', 'aral-l24-g4-x-syllable-builder',
            'aral-l24-g5-z-syllabication', 'aral-l24-g6-z-word-search',
            'aral-l24-g7-z-word-reading',
        }
        self.assertEqual(len(shared_keys), 13)
        for key in shared_keys:
            self.assertIn(repr(key), shared)
        self.assertIn('Session8CompletionPopup?.show', shared)

        dedicated = {
            'aral-l22-g2-c-word-reading': 'prescribed_l22_g2_reading.js',
            'aral-l22-g6-f-word-reading': 'prescribed_l22_g2_reading.js',
            'aral-l22-g3-c-word-search': 'prescribed_l22_g3_word_search.js',
            'aral-l22-g4-f-syllable-builder': 'prescribed_l22_g4_f_builder.js',
            'aral-l22-g5-f-word-search': 'prescribed_l22_g5_f_word_search.js',
            'aral-l23-g2-n-word-reading': 'prescribed_l23_g2_reading.js',
            'aral-l23-g5-j-word-search': 'prescribed_l23_g5_j_word_search.js',
            'aral-l24-g2-v-word-reading': 'prescribed_l24_g2_reading.js',
            'aral-l24-g3-x-repeat': 'prescribed_l24_g3_repeat.js',
        }
        self.assertEqual(len(dedicated), 9)
        for key, source_name in dedicated.items():
            with self.subTest(activity_key=key):
                self.assertIn(key, ACTIVITIES)
                self.assertTrue((js_root / source_name).exists())
        self.assertIn('dedicatedCompletions', popup)
        for selector in ('.l23g2-page .panel.complete', '.l23g5-page .complete',
                         '.l24g2-complete', '.l24g3-repeat-dialog-backdrop'):
            self.assertIn(selector, popup)

        repeat = (js_root / 'prescribed_l24_g3_repeat.js').read_text(encoding='utf-8')
        self.assertIn("if (finished) window.Session8CompletionPopup?.show", repeat)
        self.assertNotIn('l24g3-repeat-dialog-backdrop', repeat)
        self.assertNotIn('Magpatuloy sa Susunod na Gawain', repeat)

    def test_session8_reading_target_labels_are_removed_from_active_renderers(self):
        js_root = Path(__file__).parent / 'static/pabasa_app/js'
        workbook = (js_root / 'prescribed_workbook.js').read_text(encoding='utf-8')
        l24_reading = (js_root / 'prescribed_l24_g2_reading.js').read_text(encoding='utf-8')

        for source in (workbook, l24_reading):
            self.assertNotIn('Tunog / Salitang Babasahin', source)
            self.assertNotIn('Salitang Babasahin', source)

        self.assertNotIn('wb-reading-target-label', workbook)
        self.assertNotIn('wb-g7-subtitle', workbook)
        self.assertNotIn('wb-l23-g3-subtitle', workbook)
        self.assertIn('<h2>BASAHIN</h2>', workbook)
        self.assertIn('<h2>BASAHIN</h2>', l24_reading)

        self.assertIn('wb-reading-target', workbook)
        self.assertIn('wb-g7-current-word', workbook)
        self.assertIn('wb-l23-g3-target', workbook)
        self.assertIn('l24g2-target', l24_reading)

        rendered_sources = {
            'aral-l22-g1-c-syllable-builder': 'prescribed_workbook.js',
            'aral-l22-g6-f-word-reading': 'prescribed_workbook.js',
            'aral-l23-g1-n-syllable-builder': 'prescribed_workbook.js',
            'aral-l23-g2-n-word-reading': 'prescribed_workbook.js',
            'aral-l23-g3-j-word-reading': 'prescribed_workbook.js',
            'aral-l23-g6-q-syllable-builder': 'prescribed_workbook.js',
            'aral-l24-g1-v-syllable-builder': 'prescribed_workbook.js',
            'aral-l24-g2-v-word-reading': 'prescribed_l24_g2_reading.js',
            'aral-l24-g3-x-word-reading': 'prescribed_workbook.js',
            'aral-l24-g7-z-word-reading': 'prescribed_workbook.js',
        }
        for activity_key, source_name in rendered_sources.items():
            with self.subTest(activity_key=activity_key):
                activity = get_activity(activity_key)
                html = render_to_string('pabasa_app/prescribed_workbook_page.html', {
                    'workbook_payload': {'activity': activity},
                })
                self.assertIn(source_name, html)
                self.assertIn(activity['title'], html)
                self.assertTrue(activity['items'])

        x_word_html = render_to_string('pabasa_app/prescribed_workbook_page.html', {
            'workbook_payload': {'activity': get_activity('aral-l24-g3-x-word-reading')},
        })
        self.assertNotIn('prescribed_l24_g3_word_reading.js', x_word_html)

    def test_lesson23_gawain7_uses_horizontal_progress_and_single_main_title(self):
        root = Path(__file__).parent
        template = (root / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')
        script = (root / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        css = (root / 'static/pabasa_app/css/prescribed_l23_g7_reading.css').read_text(encoding='utf-8')

        self.assertIn("activity_key == 'aral-l23-g7-q-word-reading'", template)
        self.assertIn('<div id="wb-progress-row">', template)
        self.assertIn('if(qReading||l23G3||l24G3WordReading)readingHeading.remove()', script)
        self.assertIn('#wb-progress-track', css)
        self.assertIn('grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr))', css)
        self.assertIn('width:clamp(260px,24vw,320px)', css)
        self.assertIn('width:clamp(220px,24vw,280px)', css)

    def test_targeted_ui_consistency_repairs_are_guarded(self):
        root = Path(__file__).parent
        script = (root / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        g4_css = (root / 'static/pabasa_app/css/prescribed_l23_g4_syllabication.css').read_text(encoding='utf-8')
        g7_css = (root / 'static/pabasa_app/css/prescribed_l23_g7_reading.css').read_text(encoding='utf-8')

        self.assertIn('qReading||l23G3||l24G3WordReading', script)
        self.assertIn("activity_key === 'aral-l23-g3-j-word-reading'", script)
        self.assertIn("activity_key === 'aral-l24-g3-x-word-reading'", script)
        self.assertIn('max-width:100%;min-width:0', g4_css)
        self.assertIn('width:min(230px,100%)', g4_css)
        self.assertIn('background:#b9dfe3', g7_css)

    def test_session8_duplicate_header_instructions_are_activity_scoped_and_audio_backed(self):
        hidden = {
            'aral-l23-g1-n-syllable-builder': 'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita mula rito.',
            'aral-l23-g6-q-syllable-builder': 'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salitang.',
            'aral-l23-g7-q-word-reading': 'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Qq.',
            'aral-l24-g1-v-syllable-builder': 'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita.',
            'aral-l24-g4-x-pictures': 'Kilalanin ang bawat larawan at subuking basahin ito kasabay ng guro.',
            'aral-l24-g3-x-word-reading': 'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Xx.',
            'aral-l24-g6-z-word-search': 'Panuto: Hanapin at bilugan sa loob ng Big Box ang sumusunod na mga salita.',
        }
        flagged = {key for key, activity in ACTIVITIES.items() if activity.get('hide_header_instruction')}
        self.assertEqual(flagged, set(hidden))

        for key, instruction in hidden.items():
            with self.subTest(activity_key=key):
                activity = get_activity(key)
                self.assertEqual(activity['instruction'], instruction)
                html = render_to_string('pabasa_app/prescribed_workbook_page.html', {
                    'workbook_payload': {'activity': activity},
                })
                self.assertIn(f'<h1>{activity["title"]}</h1>', html)
                self.assertNotIn(f'<p class="wb-instruction">{instruction}</p>', html)

        for key in ('aral-l22-g3-c-word-search', 'aral-l22-g5-f-word-search'):
            activity = get_activity(key)
            html = render_to_string('pabasa_app/prescribed_workbook_page.html', {
                'workbook_payload': {'activity': activity},
            })
            self.assertIn(f'<p class="wb-instruction">{activity["instruction"]}</p>', html)

        script = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        self.assertIn('const instructionText = a.instruction;', script)
        self.assertIn('playPrescribedAudio(instructionText,true)', script)
        self.assertIn('playPrescribedAudio(a.instruction)', script)
        self.assertIn('id="wb-instruction-replay"', script)

    def test_lesson22_extended_cleanup_preserves_audio_feedback_contracts(self):
        g1 = get_activity('aral-l22-g1-c-syllable-builder')
        g2_template = (Path(__file__).parent / 'templates/pabasa_app/prescribed_l22_g2_reading_page.html').read_text(encoding='utf-8')

        root = Path(__file__).parent
        workbook = (root / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        builder_css = (root / 'static/pabasa_app/css/prescribed_l22_c_builder.css').read_text(encoding='utf-8')
        g2_reading = (root / 'static/pabasa_app/js/prescribed_l22_g2_reading.js').read_text(encoding='utf-8')
        self.assertEqual(g1['instruction'], 'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita mula rito.')
        self.assertIn("const L22_G1_MAPPED_TEXT = new Set([l22StartupTtsText", workbook)
        self.assertIn("if(l22G1){if(state.completed)await playPrescribedAudio", workbook)
        self.assertIn("else if(L22_G1_MAPPED_TEXT.has(state.last_feedback))await playPrescribedAudio(state.last_feedback,true)", workbook)
        self.assertIn('.wb-l22-g1-page .wb-phase-status,.wb-l22-g1-page .wb-builder-feedback', builder_css)
        self.assertIn('prescribed_l22_g2_reading.js', g2_template)
        self.assertIn("${isL22G2?'':`<p class=\"instruction\">${esc(canonicalInstruction)}</p>`}", g2_reading)
        self.assertIn("${isL22G2?'':`<button class=\"instruction-audio", g2_reading)
        self.assertIn("${isL22G2?'':`<p class=\"sound-label\">Tunog / Salitang Babasahin</p>`}", g2_reading)
        self.assertIn("${isL22G2?'':`<div class=\"heard\">", g2_reading)
        self.assertIn("${isL22G2?'':`<p class=\"feedback", g2_reading)
        self.assertIn('const instruction=document.getElementById(\'instruction\');if(instruction)instruction.onclick=playInstruction', g2_reading)
        self.assertIn('if(j.state?.completed){await playCompletion();if(isL22G6)await playFeedback(feedback)}else await playFeedback(feedback)', g2_reading)
        self.assertIn("await playFeedback('Handa ka na?')", g2_reading)
        self.assertIn("window.addEventListener('pagehide',()=>{stream?.getTracks().forEach(t=>t.stop());cancelSpeech()})", g2_reading)
        self.assertIn('wb-reading-target', workbook)
        self.assertIn('id="wb-l22-reading-action"', workbook)

    def test_session8_only_hides_rendered_duplicate_restart_controls(self):
        targets = {
            'aral-l22-g1-c-syllable-builder': 'prescribed_workbook.js',
            'aral-l22-g2-c-word-reading': 'prescribed_l22_g2_reading.js',
            'aral-l22-g3-c-word-search': 'prescribed_l22_g3_word_search.js',
            'aral-l22-g4-f-syllable-builder': 'prescribed_l22_g4_f_builder.js',
            'aral-l22-g5-f-word-search': 'prescribed_l22_g5_f_word_search.js',
            'aral-l22-g6-f-word-reading': 'prescribed_l22_g2_reading.js',
            'aral-l23-g1-n-syllable-builder': 'prescribed_workbook.js',
            'aral-l23-g2-n-word-reading': 'prescribed_l23_g2_reading.js',
            'aral-l23-g6-q-syllable-builder': 'prescribed_workbook.js',
            'aral-l24-g2-v-word-reading': 'prescribed_l24_g2_reading.js',
            'aral-l24-g3-x-repeat': 'prescribed_l24_g3_repeat.js',
            'aral-l24-g4-x-syllable-builder': 'prescribed_workbook.js',
            'aral-l24-g5-z-syllabication': 'prescribed_workbook.js',
            'aral-l24-g6-z-word-search': 'prescribed_workbook.js',
            'aral-l24-g7-z-word-reading': 'prescribed_workbook.js',
        }
        self.assertEqual(set(targets), {
            'aral-l22-g1-c-syllable-builder', 'aral-l22-g2-c-word-reading',
            'aral-l22-g3-c-word-search', 'aral-l22-g4-f-syllable-builder',
            'aral-l22-g5-f-word-search', 'aral-l22-g6-f-word-reading',
            'aral-l23-g1-n-syllable-builder', 'aral-l23-g2-n-word-reading',
            'aral-l23-g6-q-syllable-builder', 'aral-l24-g2-v-word-reading',
            'aral-l24-g3-x-repeat', 'aral-l24-g4-x-syllable-builder',
            'aral-l24-g5-z-syllabication', 'aral-l24-g6-z-word-search',
            'aral-l24-g7-z-word-reading',
        })
        js_root = Path(__file__).parent / 'static/pabasa_app/js'
        for source_name in set(targets.values()):
            source = (js_root / source_name).read_text(encoding='utf-8')
            self.assertNotIn('Ulitin Mula sa Simula', source)

        workbook_source = (js_root / 'prescribed_workbook.js').read_text(encoding='utf-8')
        self.assertIn('Subukan Muli', workbook_source)
        self.assertIn('Pakinggan Muli', workbook_source)
        self.assertIn('wb-s9-a1-complete-reset', workbook_source)
        self.assertIn('wb-s9-a2-complete-reset', workbook_source)

        controls_source = (js_root / 'prescribed_session8_11_controls.js').read_text(encoding='utf-8')
        self.assertIn("action:'restart',revision:Number(state.revision || 0)", controls_source)

        legacy_source = (js_root / 'prescribed_l24_g3_word_reading.js').read_text(encoding='utf-8')
        self.assertIn('Ulitin Mula sa Simula', legacy_source)
        template_source = (Path(__file__).parent / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')
        self.assertNotIn('prescribed_l24_g3_word_reading.js', template_source)

    def test_session8_wp5_remaining_cleanup_is_scoped_to_the_approved_activities(self):
        targets = {
            'aral-l22-g3-c-word-search', 'aral-l22-g4-f-syllable-builder',
            'aral-l22-g5-f-word-search', 'aral-l22-g6-f-word-reading',
            'aral-l23-g1-n-syllable-builder', 'aral-l23-g2-n-word-reading',
            'aral-l23-g3-j-word-reading', 'aral-l23-g4-j-syllabication',
            'aral-l23-g5-j-word-search', 'aral-l23-g6-q-syllable-builder',
            'aral-l23-g7-q-word-reading', 'aral-l24-g1-v-syllable-builder',
            'aral-l24-g2-v-word-reading', 'aral-l24-g3-x-repeat',
            'aral-l24-g4-x-pictures', 'aral-l24-g3-x-word-reading',
            'aral-l24-g4-x-syllable-builder', 'aral-l24-g5-z-syllabication',
            'aral-l24-g6-z-word-search', 'aral-l24-g7-z-word-reading',
        }
        self.assertEqual(len(targets), 20)
        self.assertTrue(targets.issubset(ACTIVITIES))

        css_root = Path(__file__).parent / 'static/pabasa_app/css'
        sources = {
            'prescribed_l22_g2_reading.css': ('l22g6-page',),
            'prescribed_l22_g3_word_search.css': ('l22g3-page', 'l22g5-page'),
            'prescribed_l22_g4_f_builder.css': ('l22g4-page',),
            'prescribed_l23_g2_reading.css': ('l23g2-page',),
            'prescribed_l23_g5_j_word_search.css': ('l23g5-page',),
            'prescribed_l24_g3_repeat.css': ('wb-l24-g3-repeat-page',),
            'prescribed_workbook.css': (
                'wb-l23-page', 'wb-l23-g3-page', 'wb-l23-g4-syllabication',
                'wb-l23-g6-page', 'wb-l23-g7-reading', 'wb-l24-g1-page',
                'wb-l24-g2-page', 'wb-l24-g4-pictures-page', 'wb-l24-g3-word-page',
                'wb-l24-g4-builder-page', 'wb-l24-g5-page', 'wb-l24-g6-page',
                'wb-l24-g7-page',
            ),
        }
        for filename, selectors in sources.items():
            source = (css_root / filename).read_text(encoding='utf-8')
            with self.subTest(filename=filename):
                for selector in selectors:
                    self.assertIn(selector, source)
                self.assertIn('clip:rect(0,0,0,0)', source)

        shared = (css_root / 'prescribed_workbook.css').read_text(encoding='utf-8')
        self.assertNotIn('wb-l22-g1-page #wb-instruction-replay', shared)
        self.assertNotIn('wb-l23-g3-page .wb-l23-g3-list-panel h2', shared)
        self.assertNotIn('wb-l24-g5-page .wb-g5-panel-heading', shared)
        self.assertNotIn('wb-l24-g6-page .wb-g6-help', shared)

        g4 = (css_root / 'prescribed_l22_g4_f_builder.css').read_text(encoding='utf-8')
        self.assertNotIn('.l22g4-page .tile small', g4)

    def test_session9_activity2_keeps_workbook_instruction_and_requires_drawing_and_courteous_word(self):
        activity = get_activity('aral-s9-a2-helping-drawing')
        self.assertEqual(activity['interaction_type'], 'drawing')
        self.assertIn('Draw and color a situation at home where you helped someone.', activity['instruction'])
        self.assertEqual(activity['expected_writing'], ['Please', 'Sorry', 'Thank you', 'You’re welcome.'])
        state = initial_s9_a2_state()
        with self.assertRaisesMessage(ValueError, 'Gumuhit muna'):
            apply_event(activity, state, {'action': 'answer', 'answer': {'strokes': [], 'text': 'Thank you'}})
        stroke = {'color': '#df4b4b', 'points': [[0, 0], [1200, 525]]}
        with self.assertRaisesMessage(ValueError, 'Isulat muna'):
            apply_event(activity, state, {'action': 'answer', 'answer': {'strokes': [stroke], 'text': ''}})
        apply_event(activity, state, {'action': 'draft', 'draft': {'strokes': [stroke], 'text': 'Thank you', 'tool': 'draw', 'color': '#df4b4b', 'size': 'large'}})
        self.assertFalse(state['completed'])
        apply_event(activity, state, {'action': 'answer', 'answer': {'strokes': [stroke], 'text': 'Thank you'}})
        self.assertTrue(state['completed'])
        self.assertEqual(state['answers']['item-1']['text'], 'Thank you')

    def test_session9_activity2_restart_clears_saved_work(self):
        activity = get_activity('aral-s9-a2-helping-drawing')
        state = initial_s9_a2_state()
        stroke = {'color': '#183e63', 'points': [[10, 10], [20, 20]]}
        apply_event(activity, state, {'action': 'answer', 'answer': {'strokes': [stroke], 'text': 'Please'}})
        apply_event(activity, state, {'action': 'restart'})
        self.assertEqual(state, initial_s9_a2_state())

    def test_session9_activity1_keeps_instruction_and_required_family_sentence(self):
        activity = get_activity('aral-s9-a1-family-drawing')
        self.assertEqual(activity['instruction'], 'Draw a picture of your family. Under your drawing, write the sentence “This is my family.”')
        self.assertEqual(activity['interaction_type'], 'drawing')
        self.assertEqual(activity['expected_writing'], ['This is my family.'])
        self.assertTrue(activity['review_required'])

    def test_lesson23_gawain7_keeps_exact_q_words_and_instruction(self):
        reading = get_activity('aral-l23-g7-q-word-reading')
        self.assertEqual(reading['instruction'], 'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Qq.')
        self.assertEqual(tuple(item['text'] for item in reading['items']), L23_G7_Q_WORDS)
        self.assertEqual(len(reading['items']), 5)
        self.assertNotEqual(reading['activity_key'], 'aral-l23-g3-j-word-reading')

    def test_lesson23_gawain7_reading_progress_retry_duplicate_and_completion(self):
        activity = get_activity('aral-l23-g7-q-word-reading')
        state = initial_l23_g7_state()
        apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 0, 'transcript': 'wrong'}, False)
        self.assertEqual(state['index'], 0)
        self.assertEqual(state['completed_words'], [])
        apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 0, 'transcript': 'QUISUMBING!'}, True)
        with self.assertRaisesMessage(ValueError, 'kasalukuyang salita'):
            apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 0, 'transcript': 'Quisumbing'}, True)
        self.assertEqual(state['index'], 1)
        self.assertEqual(state['completed_words'], [0])
        for word in L23_G7_Q_WORDS[1:]:
            apply_event(activity, state, {'action': 'reading_attempt', 'transcript': word}, True)
        self.assertTrue(state['completed'])
        self.assertEqual(state['completed_words'], list(range(5)))
        before = dict(state)
        apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 4, 'transcript': 'Quintos'}, True)
        self.assertEqual(state, before)

    def test_lesson23_gawain7_uses_three_attempt_help_unlock_and_retry_reset(self):
        activity = get_activity('aral-l23-g7-q-word-reading')
        state = initial_l23_g7_state()
        self.assertEqual(state['reading_attempts'], 0)
        self.assertEqual(state['reading_phase'], 'read')
        for attempt in (1, 2, 3):
            apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 0, 'transcript': 'wrong'}, False)
            self.assertEqual(state['reading_attempts'], attempt)
        self.assertEqual(state['reading_phase'], 'help')
        with self.assertRaisesMessage(ValueError, 'Pakinggan ang tamang pagbigkas'):
            apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 0, 'transcript': 'wrong'}, False)
        apply_event(activity, state, {'action': 'read_aloud'}, None)
        self.assertTrue(state['pronunciation_help_played'])
        apply_event(activity, state, {'action': 'retry_reading'}, None)
        self.assertEqual(state['reading_attempts'], 0)
        self.assertEqual(state['reading_phase'], 'read')
        self.assertFalse(state['pronunciation_help_played'])

    def test_lesson23_gawain7_proper_name_matching_is_scoped_and_case_safe(self):
        for word in L23_G7_Q_WORDS:
            with self.subTest(word=word):
                self.assertTrue(l23_g7_pronunciation_match(word, word.lower() + '!'))
                self.assertFalse(l23_g7_pronunciation_match(word, 'unrelated word'))
    def test_lesson23_j_activities_keep_exact_workbook_content(self):
        reading = get_activity('aral-l23-g3-j-word-reading')
        syllables = get_activity('aral-l23-g4-j-syllabication')
        self.assertEqual(reading['instruction'], 'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Jj.')
        self.assertEqual(tuple(item['text'] for item in reading['items']), L23_G3_J_WORDS)
        self.assertEqual(syllables['instruction'], 'Pantigin ang sumusunod na salita.')
        self.assertEqual(tuple(item['text'] for item in syllables['items']), ('jacket', 'pajama', 'Jonathan', 'jam', 'Joselito'))
        self.assertEqual(tuple(syllables['syllable_answers']), L23_G4_SYLLABLE_ANSWERS)

    def test_lesson23_gawain3_advances_once_and_restores_completion(self):
        activity = get_activity('aral-l23-g3-j-word-reading')
        state = initial_l23_g3_state()
        apply_event(activity, state, {'action': 'reading_attempt', 'transcript': 'wrong'}, False)
        self.assertEqual(state['index'], 0)
        apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 0, 'transcript': 'Jacket'}, True)
        with self.assertRaisesMessage(ValueError, 'kasalukuyang salita'):
            apply_event(activity, state, {'action': 'reading_attempt', 'item_index': 0, 'transcript': 'Jacket'}, True)
        self.assertEqual(state['index'], 1)
        self.assertEqual(state['completed_words'], [0])
        for word in L23_G3_J_WORDS[1:]:
            apply_event(activity, state, {'action': 'reading_attempt', 'transcript': word}, True)
        self.assertTrue(state['completed'])
        self.assertEqual(state['index'], 8)
        self.assertEqual(state['completed_words'], list(range(8)))

    def test_lesson23_gawain3_proper_name_matching_is_scoped(self):
        self.assertTrue(l23_g3_pronunciation_match('Jennifer', '  JENNIFER! '))
        self.assertFalse(l23_g3_pronunciation_match('Jennifer', 'Jeffrey'))

    def test_lesson23_gawain4_requires_exact_verified_syllable_boundaries(self):
        activity = get_activity('aral-l23-g4-j-syllabication')
        state = initial_l23_g4_state()
        apply_event(activity, state, {'action': 'answer', 'answer': {'text': 'jack - et'} })
        self.assertEqual(state['index'], 1)
        self.assertEqual(normalize_l23_g4_syllables('PA - JA - MA'), 'pa-ja-ma')
        apply_event(activity, state, {'action': 'answer', 'answer': {'text': 'pa-ja-ma'}})
        apply_event(activity, state, {'action': 'answer', 'answer': {'text': 'Jo-na-than'}})
        apply_event(activity, state, {'action': 'answer', 'answer': {'text': 'jam'}})
        apply_event(activity, state, {'action': 'answer', 'answer': {'text': 'Jo-se-li-to'}})
        self.assertTrue(state['completed'])
        self.assertEqual(len(state['answers']), 5)

    def test_lesson23_gawain4_wrong_boundary_does_not_advance(self):
        activity = get_activity('aral-l23-g4-j-syllabication')
        state = initial_l23_g4_state()
        apply_event(activity, state, {'action': 'answer', 'answer': {'text': 'ja-cket'}})
        self.assertEqual(state['index'], 0)
        self.assertFalse(state['completed'])

    def test_lesson22_gawain2_preserves_exact_words_columns_and_alternating_order(self):
        activity = get_activity('aral-l22-g2-c-word-reading')
        self.assertEqual(tuple(item['text'] for item in activity['items']), L22_G2_C_WORDS)
        self.assertEqual(activity['column_headers'], ['C = /k/', 'C = /s/'])
        self.assertEqual([row[0] for row in activity['rows']], ['computer', 'cactus', 'camera', 'cabinet', 'Caloocan', 'Coron', 'Vic'])
        self.assertEqual([row[1] for row in activity['rows']], ['Cebu', 'Cita', 'Celso', 'Vicente', 'Celeste', 'Celsa', 'Carlos'])

    def test_lesson22_gawain2_advances_only_after_correct_reading_and_supports_restart(self):
        activity = get_activity('aral-l22-g2-c-word-reading')
        state = initial_l22_g2_state()
        apply_event(activity, state, {'action': 'reading_started'})
        for _ in range(3):
            apply_event(activity, state, {'action': 'reading_attempt', 'transcript': 'wrong'}, False)
        self.assertEqual(state['sequence_index'], 0)
        self.assertEqual(state['reading_phase'], 'help')
        apply_event(activity, state, {'action': 'read_aloud'})
        apply_event(activity, state, {'action': 'retry_reading'})
        apply_event(activity, state, {'action': 'reading_attempt', 'transcript': 'computer'}, True)
        self.assertEqual(state['completed_words'], [0])
        self.assertEqual(state['sequence_index'], 1)
        apply_event(activity, state, {'action': 'restart'})
        self.assertEqual(state, initial_l22_g2_state())

    def test_lesson22_gawain2_completion_persists_at_fourteen(self):
        activity = get_activity('aral-l22-g2-c-word-reading')
        state = initial_l22_g2_state()
        for word in L22_G2_C_WORDS:
            apply_event(activity, state, {'action': 'reading_started'})
            apply_event(activity, state, {'action': 'reading_attempt', 'transcript': word}, True)
        self.assertTrue(state['completed'])
        self.assertEqual(state['sequence_index'], 14)
        self.assertEqual(state['completed_words'], list(range(14)))

    def test_lesson22_gawain2_cita_alias_is_normalized_and_scoped(self):
        activity = get_activity('aral-l22-g2-c-word-reading')
        self.assertEqual(activity['items'][3]['text'], 'Cita')
        self.assertEqual(normalize_l22_g2_speech('  SITA!  '), 'sita')
        self.assertTrue(l22_g2_pronunciation_match('Cita', 'SITA'))
        self.assertTrue(l22_g2_pronunciation_match('Cita', 'cita'))
        self.assertTrue(l22_g2_pronunciation_match('Celsa', 'selsa'))
        self.assertTrue(l22_g2_pronunciation_match('Celsa', 'celsa'))
        self.assertFalse(l22_g2_pronunciation_match('Cita', 'camera'))
        self.assertFalse(l22_g2_pronunciation_match('Celso', 'sita'))

    def test_lesson22_gawain2_success_keeps_canonical_word_after_advancement(self):
        activity = get_activity('aral-l22-g2-c-word-reading')
        state = initial_l22_g2_state()
        for index, transcript in ((0, 'computer'), (1, 'cebu'), (2, 'cactus'), (3, 'cita'),
                                   (4, 'camera'), (5, 'celso'), (6, 'cabinet'), (7, 'vicente'),
                                   (8, 'caloocan'), (9, 'celeste'), (10, 'coron'), (11, 'selsa')):
            apply_event(activity, state, {'action': 'reading_started'}, None)
            apply_event(activity, state, {'action': 'reading_attempt', 'transcript': transcript}, True)
            self.assertEqual(state['last_successful_word'], L22_G2_C_WORDS[index])
        self.assertEqual(state['sequence_index'], 12)
        self.assertEqual(state['last_transcript'], 'selsa')
        self.assertEqual(state['last_successful_word'], 'Celsa')

    def test_lesson22_gawain2_failure_and_unclear_clear_canonical_display(self):
        activity = get_activity('aral-l22-g2-c-word-reading')
        state = initial_l22_g2_state()
        apply_event(activity, state, {'action': 'reading_attempt', 'transcript': 'computer'}, True)
        self.assertEqual(state['last_successful_word'], 'computer')
        apply_event(activity, state, {'action': 'reading_attempt', 'transcript': 'wrong'}, False)
        self.assertEqual(state['last_transcript'], 'wrong')
        self.assertEqual(state['last_successful_word'], '')
        apply_event(activity, state, {'action': 'reading_attempt', 'transcript': ''}, None)
        self.assertEqual(state['last_transcript'], '')
        self.assertEqual(state['last_successful_word'], '')

    def test_lesson22_gawain2_local_audio_precedence_and_scoped_fallback(self):
        activity = get_activity('aral-l22-g2-c-word-reading')
        instruction = 'Basahin ang mga salitang nagtataglay ng hiram na letrang C na may tunog na /k/ at /s/.'
        self.assertEqual(activity['instruction'], instruction)
        source = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l22_g2_reading.js').read_text(encoding='utf-8')
        self.assertEqual(source.count("const INSTRUCTION_TEXT='" + instruction + "';"), 1)
        self.assertIn("isL22G2=a.activity_key==='aral-l22-g2-c-word-reading'", source)
        self.assertIn('localAudio=(isL22G2||isL22G6)?(data.local_audio||{}):{}', source)
        self.assertIn('if(url)return playAudioUrl(url,!isL22G6,text)', source)
        self.assertIn('async function playFeedback(text){if(!isL22G2&&!isL22G6)return false;', source)
        self.assertIn('async function playCompletion(){if(!isL22G2)return;', source)
        self.assertIn("for(const text of ['Magaling!','Natapos mo ang Gawain 2.'])", source)
        self.assertEqual(source.count('function playInstruction()'), 1)
        self.assertEqual(source.count('function playSpeech(text)'), 1)
        self.assertNotIn('speechSynthesis', source)
        self.assertNotIn('speakWithGoogle(text)', source.split('async function playFeedback', 1)[1].split('async function playCompletion', 1)[0])
    def test_lesson22_c_pronunciation_accepts_scoped_hard_and_soft_c_spellings(self):
        self.assertTrue(l22_c_pronunciation_match('cac', 'cactus', 'kak', 'hard'))
        self.assertTrue(l22_c_pronunciation_match('cac', 'cactus', 'cock', 'hard'))
        self.assertTrue(l22_c_pronunciation_match('cac', 'cactus', 'Cock', 'hard'))
        self.assertTrue(l22_c_pronunciation_match('com', 'computer', 'kom', 'hard'))
        self.assertTrue(l22_c_pronunciation_match('Ce', 'Celeste', 'se', 'soft'))
        self.assertFalse(l22_c_pronunciation_match('Ce', 'Celeste', 'ke', 'soft'))
        self.assertFalse(l22_c_pronunciation_match('cac', 'cactus', 'tat', 'hard'))

    def test_lesson22_gawain1_accepts_strict_pantig_aliases_for_all_big_box_targets(self):
        targets = (
            ('cac', 'cactus', 'kak'), ('ce', 'Cebu', 'se'), ('ca', 'Cagayan', 'ka'),
            ('bu', 'Cebu', ''), ('com', 'computer', 'kom'), ('pu', 'computer', ''),
            ('ga', 'Cagayan', ''), ('tus', 'cactus', ''), ('ter', 'computer', ''),
            ('yan', 'Cagayan', ''), ('Car', 'Cardo', 'kar'), ('do', 'Cardo', ''),
            ('bi', 'cabinet', ''), ('ca', 'cabinet', 'ka'), ('net', 'cabinet', ''),
            ('te', 'Celeste', ''), ('Ce', 'Celeste', 'se'), ('les', 'Celeste', ''),
        )
        for expected, context, alias in targets:
            transcript = alias or expected
            self.assertTrue(
                l22_c_pronunciation_match(expected, context, transcript, 'hard' if expected.lower().startswith(('ca', 'car', 'com')) else 'soft'),
                (expected, context, transcript),
            )

    def test_lesson22_gawain1_context_aliases_are_target_scoped_and_strict(self):
        self.assertTrue(l22_c_pronunciation_match('cac', 'cactus', 'cactus', 'hard'))
        self.assertFalse(l22_c_pronunciation_match('tus', 'cactus', 'cactus', 'hard'))
        self.assertFalse(l22_c_pronunciation_match('cac', 'cactus', 'ca', 'hard'))
        self.assertFalse(l22_c_pronunciation_match('cac', 'cactus', 'unrelated word', 'hard'))
        self.assertFalse(l22_c_pronunciation_match('ca', 'Cagayan', 'cactus', 'hard'))
        self.assertTrue(l22_c_pronunciation_match('Ce', 'Celeste', '  se!  ', 'soft'))

    def test_lesson22_gawain1_bu_accepts_observed_boo_only_for_the_exact_target(self):
        activity = get_activity('aral-l22-g1-c-syllable-builder')
        match = lambda expected, transcript, key=activity['activity_key']: l22_c_pronunciation_match(
            expected, 'Cebu', transcript, 'soft', key,
        )

        self.assertTrue(match('bu', 'bu'))
        self.assertTrue(match('bu', 'Boo.'))
        self.assertTrue(match('bu', '  BOO  '))
        for rejected in ('bow', 'bo', 'ba', 'bi', 'be', 'bus', 'book'):
            self.assertFalse(match('bu', rejected), rejected)
        self.assertTrue(match('bu', 'boo now'))
        self.assertFalse(match('ca', 'boo'))
        self.assertFalse(match('bu', 'boo', 'aral-l22-g2-c-word-reading'))

        state = initial_state()
        apply_event(activity, state, {'action': 'reading_started'})
        apply_event(activity, state, {
            'action': 'reading_syllable_attempt', 'transcript': 'bu',
        }, match('bu', 'Boo.'))
        self.assertEqual(state['index'], 1)
        self.assertEqual(state['reading_attempts'], 0)
        self.assertEqual(state['last_feedback'], 'Tama!')

    def test_lesson22_gawain1_com_accepts_observed_comb_only_for_the_exact_target(self):
        key = 'aral-l22-g1-c-syllable-builder'
        match = lambda expected, transcript, activity_key=key: l22_c_pronunciation_match(
            expected, 'computer', transcript, 'hard', activity_key,
        )

        for transcript in ('com', 'kom', 'computer', 'comb', 'Comb.', 'COMB.'):
            with self.subTest(transcript=transcript):
                self.assertTrue(match('com', transcript))
        for transcript in ('come', 'calm', 'um', 'unrelated'):
            with self.subTest(transcript=transcript):
                self.assertFalse(match('com', transcript))
        self.assertTrue(match('com', 'comb comb'))
        self.assertFalse(match('ca', 'comb'))
        self.assertFalse(match('com', 'comb', 'aral-l22-g2-c-word-reading'))

    def test_lesson22_gawain1_complete_18_cell_strict_acceptance_matrix(self):
        key = 'aral-l22-g1-c-syllable-builder'
        cells = (
            ('cac', 'cactus', 'hard', ('cac', 'kak', 'cock', 'cactus'), 'cake'),
            ('ce', 'Cebu', 'soft', ('ce', 'se', 'cebu'), 'see'),
            ('ca', 'Cagayan', 'hard', ('ca', 'ka', 'cagayan'), 'kay'),
            ('bu', 'Cebu', 'soft', ('bu', 'boo'), 'bow'),
            ('com', 'computer', 'hard', ('com', 'kom', 'computer', 'comb'), 'come'),
            ('pu', 'computer', 'hard', ('pu', 'pooh', 'poo'), 'pew'),
            ('ga', 'Cagayan', 'hard', ('ga',), 'go'),
            ('tus', 'cactus', 'hard', ('tus', 'tuss'), 'toast'),
            ('ter', 'computer', 'hard', ('ter',), 'tear'),
            ('yan', 'Cagayan', 'hard', ('yan',), 'yarn'),
            ('Car', 'Cardo', 'hard', ('car', 'kar', 'cardo'), 'care'),
            ('do', 'Cardo', 'hard', ('do',), 'dough'),
            ('bi', 'cabinet', 'hard', ('bi', 'bee', 'be', 'b'), 'bead'),
            ('ca', 'cabinet', 'hard', ('ca', 'ka', 'cabinet'), 'kay'),
            ('net', 'cabinet', 'hard', ('net', 'nett'), 'knit'),
            ('te', 'Celeste', 'soft', ('te', 't'), 'tea'),
            ('Ce', 'Celeste', 'soft', ('ce', 'se', 'celeste'), 'see'),
            ('les', 'Celeste', 'soft', ('les', 'less'), 'lease'),
        )
        self.assertEqual(
            tuple(item['text'] for item in get_activity(key)['items']),
            ('cac', 'ce', 'ca', 'bu', 'com', 'pu', 'ga', 'tus', 'ter', 'yan', 'Car', 'do', 'bi', 'ca', 'net', 'te', 'Ce', 'les'),
        )
        self.assertEqual(len({expected.casefold() for expected, *_ in cells}), 16)
        for expected, word, sound, accepted, rejected in cells:
            for transcript in accepted:
                self.assertTrue(l22_c_pronunciation_match(expected, word, transcript, sound, key), (expected, transcript))
            self.assertFalse(l22_c_pronunciation_match(expected, word, rejected, sound, key), (expected, rejected))
            for other, other_word, other_sound, *_ in cells:
                if other.casefold() != expected.casefold():
                    self.assertFalse(l22_c_pronunciation_match(other, other_word, expected, other_sound, key), (expected, other))

    def test_lesson22_gawain1_new_aliases_are_activity_scoped_and_accept_repetition(self):
        key = 'aral-l22-g1-c-syllable-builder'
        aliases = {
            'pu': ('computer', 'hard', ('pooh', 'poo'), 'pew'),
            'tus': ('cactus', 'hard', ('tuss', 'Tuss.', 'TUSS'), 'toast'),
            'bi': ('cabinet', 'hard', ('bee', 'be', 'B', 'b', 'B.'), 'bead'),
            'net': ('cabinet', 'hard', ('nett',), 'knit'),
            'te': ('Celeste', 'soft', ('t', 'T', 'T.', 'té'), 'de'),
            'les': ('Celeste', 'soft', ('less',), 'lease'),
        }
        for expected, (word, sound, accepted, rejected) in aliases.items():
            for alias in accepted:
                self.assertTrue(l22_c_pronunciation_match(expected, word, alias, sound, key))
                self.assertFalse(l22_c_pronunciation_match(expected, word, alias, sound, 'aral-l22-g2-c-word-reading'))
                self.assertTrue(l22_c_pronunciation_match(expected, word, f'{alias} {alias}', sound, key))
                for other, (other_word, other_sound, _, _) in aliases.items():
                    if other != expected:
                        self.assertFalse(l22_c_pronunciation_match(other, other_word, alias, other_sound, key))
            self.assertFalse(l22_c_pronunciation_match(expected, word, rejected, sound, key))
        for expected, word, sound in (
            ('cac', 'cactus', 'hard'), ('ce', 'Cebu', 'soft'), ('ca', 'Cagayan', 'hard'),
            ('bu', 'Cebu', 'soft'), ('com', 'computer', 'hard'), ('pu', 'computer', 'hard'),
            ('ga', 'Cagayan', 'hard'), ('tus', 'cactus', 'hard'), ('ter', 'computer', 'hard'),
            ('yan', 'Cagayan', 'hard'), ('car', 'Cardo', 'hard'), ('do', 'Cardo', 'hard'),
            ('net', 'cabinet', 'hard'), ('te', 'Celeste', 'soft'), ('les', 'Celeste', 'soft'),
        ):
            self.assertFalse(l22_c_pronunciation_match(expected, word, 'B.', sound, key))
        for expected, word, sound in (
            ('cac', 'cactus', 'hard'), ('ce', 'Cebu', 'soft'), ('ca', 'Cagayan', 'hard'),
            ('bu', 'Cebu', 'soft'), ('com', 'computer', 'hard'), ('pu', 'computer', 'hard'),
            ('ga', 'Cagayan', 'hard'), ('tus', 'cactus', 'hard'), ('ter', 'computer', 'hard'),
            ('yan', 'Cagayan', 'hard'), ('car', 'Cardo', 'hard'), ('do', 'Cardo', 'hard'),
            ('bi', 'cabinet', 'hard'), ('net', 'cabinet', 'hard'), ('les', 'Celeste', 'soft'),
        ):
            self.assertFalse(l22_c_pronunciation_match(expected, word, 'T.', sound, key))
        self.assertFalse(l22_c_pronunciation_match('te', 'Celeste', 'tea', 'soft', key))
        self.assertFalse(l22_c_pronunciation_match('te', 'Celeste', 'tee', 'soft', key))

    def test_lesson22_gawain1_accepts_target_token_in_natural_speech_only(self):
        key = 'aral-l22-g1-c-syllable-builder'
        self.assertTrue(l22_c_pronunciation_match('ga', 'Cagayan', 'ga ga ga ga ga', 'hard', key))
        self.assertTrue(l22_c_pronunciation_match('ga', 'Cagayan', 'ga ga ay ga', 'hard', key))
        self.assertTrue(l22_c_pronunciation_match('te', 'Celeste', 'te te ay alam ko yan eh te', 'soft', key))
        self.assertTrue(l22_c_pronunciation_match('te', 'Celeste', 'ay alam ko yan te', 'soft', key))
        self.assertFalse(l22_c_pronunciation_match('ga', 'Cagayan', 'ka ka ka', 'hard', key))
        self.assertFalse(l22_c_pronunciation_match('te', 'Celeste', 'alam', 'soft', key))
        self.assertFalse(l22_c_pronunciation_match('te', 'Celeste', 'malayo', 'soft', key))

    def test_lesson22_cock_alias_does_not_leak_to_other_pantig(self):
        self.assertFalse(l22_c_pronunciation_match('ce', 'Cebu', 'cock', 'soft'))
        self.assertFalse(l22_c_pronunciation_match('tus', 'cactus', 'cock', 'hard'))

    def test_lesson22_gawain1_duplicate_ca_entries_advance_by_index(self):
        activity = get_activity('aral-l22-g1-c-syllable-builder')
        state = initial_state()
        apply_event(activity, state, {'action': 'reading_started'})
        for index, item in enumerate(activity['items']):
            apply_event(activity, state, {
                'action': 'reading_syllable_attempt',
                'transcript': item['text'],
            }, True)
            self.assertEqual(state['index'], index + 1)
        self.assertEqual(activity['items'][2]['text'], activity['items'][13]['text'])
        self.assertTrue(state['read_aloud_completed'])

    def test_exact_scope_and_searches(self):
        self.assertEqual(len(ACTIVITIES), len(set(ACTIVITIES)))
        for a in ACTIVITIES.values():
            self.assertIn(a['session'], (8, 9))
            self.assertIn(a['printed_page'], range(38, 50))
            if a['interaction_type'] == 'search':
                for item in a['items']:
                    self.assertTrue(search_paths(a, item['text']), (a['activity_key'], item['text']))

    def test_three_readings_three_listens_repeat_and_gate(self):
        a = get_activity('aral-l23-g5-j-word-search')
        state = initial_state()
        with self.assertRaises(ValueError):
            apply_event(a, state, {'action': 'answer', 'answer': search_paths(a, 'jacket')[0]})
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
        apply_event(a, state, {'action': 'answer', 'answer': search_paths(a, 'jacket')[0]})
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
        with self.assertRaisesMessage(ValueError, 'Bumuo muna ng lahat'):
            apply_event(a, s, {'action': 'finish'})
        apply_event(a, s, {'action': 'build_word', 'parts': ['item-1', 'item-8']})
        with self.assertRaisesMessage(ValueError, 'ibang salita'):
            apply_event(a, s, {'action': 'build_word', 'parts': ['item-1', 'item-8']})
        self.assertEqual(s['found_words'], ['cactus'])

    def test_lesson22_gawain1_requires_all_unique_words_before_completion(self):
        a = get_activity('aral-l22-g1-c-syllable-builder')
        self.assertEqual(tuple(L22_C_ACCEPTED_BUILDS), (
            'cactus', 'Cebu', 'Cagayan', 'Cardo', 'cabinet', 'Celeste', 'computer',
        ))
        self.assertEqual(a['building_word_total'], 7)
        self.assertNotIn('com', L22_C_ACCEPTED_BUILDS)
        renderer = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        self.assertIn("(state.found_words||[]).length===Number(a.building_word_total||0)", renderer)
        self.assertIn('aria-label="Mga Tamang Salita"', renderer)
        s = initial_state()
        s.update(index=len(a['items']), read_aloud_started=True, read_aloud_completed=True,
                 reading_phase='complete', found_words=['cactus'])
        normalize_l22_c_state(s)
        with self.assertRaisesMessage(ValueError, 'Bumuo muna ng lahat'):
            apply_event(a, s, {'action': 'finish'})
        self.assertFalse(s['completed'])
        self.assertEqual(s['found_words'], ['cactus'])
        for word, pieces in L22_C_ACCEPTED_BUILDS.items():
            if word == 'cactus':
                continue
            ids = [next(item['id'] for item in a['items'] if item['text'] == piece) for piece in pieces]
            apply_event(a, s, {'action': 'build_word', 'parts': ids})
            self.assertFalse(s['completed'])
        apply_event(a, s, {'action': 'finish'})
        self.assertTrue(s['completed'])
        self.assertEqual(set(s['found_words']), set(L22_C_ACCEPTED_BUILDS))
        self.assertEqual(s['index'], len(a['items']))

    def test_lesson22_gawain1_restores_premature_completion_to_word_building(self):
        a = get_activity('aral-l22-g1-c-syllable-builder')
        s = initial_state()
        s.update(index=len(a['items']), read_aloud_started=True, read_aloud_completed=True,
                 reading_phase='complete', found_words=['Celeste'], completed=True)
        normalize_l22_c_state(s)
        self.assertFalse(s['completed'])
        self.assertEqual(s['index'], len(a['items']))
        self.assertTrue(s['read_aloud_completed'])
        self.assertEqual(s['found_words'], ['Celeste'])

    def test_lesson22_gawain1_normalization_deduplicates_and_rejects_unknown_words(self):
        s = {'found_words': ['cactus', 'Cactus', 'unknown'], 'read_aloud_completed': True,
             'completed': True, 'index': 18}
        normalize_l22_c_state(s)
        self.assertEqual(s['found_words'], ['cactus'])
        self.assertFalse(s['completed'])

    def test_lesson22_gawain1_com_is_one_big_box_piece(self):
        a = get_activity('aral-l22-g1-c-syllable-builder')
        self.assertEqual(a['items'][4], {'id': 'item-5', 'text': 'com'})
        self.assertNotIn('m', [item['text'] for item in a['items']])
        self.assertEqual(
            [a['items'][item_id - 1]['text'] for item_id in (4, 5, 6)],
            ['bu', 'com', 'pu'],
        )
        renderer = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        styles = (Path(__file__).parent / 'static/pabasa_app/css/prescribed_l22_c_builder.css').read_text(encoding='utf-8')
        self.assertIn('tile.textContent=item.text', renderer)
        self.assertIn('white-space:nowrap', styles)
        s = initial_state()
        apply_event(a, s, {'action': 'reading_started'})
        apply_event(a, s, {'action': 'reading_attempt'}, True)
        apply_event(a, s, {'action': 'build_word', 'parts': ['item-5']})
        self.assertEqual(s['found_words'], [])
        self.assertEqual(s['pending_words'], [{'word': 'com', 'parts': ['item-5']}])
        self.assertEqual(s['building_attempts'], 1)

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
    def test_lesson22_gawain1_restart_restores_empty_reading_state(self):
        activity = get_activity('aral-l22-g1-c-syllable-builder')
        state = {
            'index': len(activity['items']), 'read_aloud_started': True,
            'read_aloud_completed': True, 'reading_phase': 'complete',
            'reading_attempts': 2, 'found_words': ['cactus'],
            'draft': {'builder': ['item-1']}, 'completed': False,
        }
        apply_event(activity, state, {'action': 'restart'})
        self.assertEqual(state['index'], 0)
        self.assertFalse(state['read_aloud_started'])
        self.assertFalse(state['read_aloud_completed'])
        self.assertEqual(state['reading_phase'], 'read')
        self.assertEqual(state['reading_attempts'], 0)
        self.assertEqual(state['found_words'], [])
        self.assertEqual(state['draft'], {'builder': []})

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

    def test_lesson22_gawain1_uses_three_real_mistakes_before_pronunciation_help(self):
        a = get_activity('aral-l22-g1-c-syllable-builder')
        s = initial_state()
        apply_event(a, s, {'action': 'reading_started'})
        apply_event(a, s, {'action': 'reading_syllable_attempt', 'transcript': ''}, None)
        self.assertEqual(s['reading_attempts'], 0)
        self.assertEqual(s['index'], 0)
        for attempt in range(1, 4):
            apply_event(a, s, {'action': 'reading_syllable_attempt', 'transcript': 'wrong'}, False)
            self.assertEqual(s['reading_attempts'], attempt)
            self.assertEqual(s['index'], 0)
        self.assertEqual(s['reading_phase'], 'help')
        self.assertFalse(s['read_aloud_completed'])
        apply_event(a, s, {'action': 'read_aloud'})
        self.assertTrue(s['pronunciation_help_played'])
        self.assertEqual(s['index'], 0)
        apply_event(a, s, {'action': 'retry_reading'})
        self.assertEqual(s['reading_attempts'], 0)
        self.assertEqual(s['reading_phase'], 'read')
        apply_event(a, s, {'action': 'reading_syllable_attempt', 'transcript': 'cac'}, True)
        self.assertEqual(s['index'], 1)
        self.assertEqual(s['reading_attempts'], 0)

    def test_lesson22_gawain1_migrates_legacy_co_m_selection_to_com(self):
        a = get_activity('aral-l22-g1-c-syllable-builder')
        legacy = {
            'index': 19, 'completed': False, 'read_aloud_completed': True,
            'draft': {'builder': ['item-5', 'item-19']},
        }
        apply_event(a, legacy, {'action': 'draft', 'draft': {'builder': ['item-5', 'item-19']}})
        self.assertEqual(legacy['draft']['builder'], ['item-5'])

    def test_lesson23_gawain1_complete_12_cell_scoped_acceptance_matrix(self):
        key = 'aral-l23-g1-n-syllable-builder'
        cells = (
            ('Ni', ('ni', 'knee', 'Knee.'), 'knot'),
            ('La', ('la',), 'law'),
            ('ña', ('ña', 'na'), 'nya'),
            ('Cas', ('cas', 'kas', 'kass'), 'cash'),
            ('Bi', ('bi', 'bee', 'be', 'b', 'B', 'B.'), 'bead'),
            ('da', ('da',), 'the'),
            ('El', ('el', 'ell', 'l', 'L', 'L.'), 'ale'),
            ('ño', ('ño', 'no', 'nyo'), 'noon'),
            ('ñan', ('ñan', 'nan', 'nyan'), 'none'),
            ('Cen', ('cen', 'sen'), 'scene'),
            ('ta', ('ta',), 'tea'),
            ('ñe', ('ñe', 'ne', 'nye'), 'nay'),
        )
        self.assertEqual(
            tuple(item['text'] for item in get_activity(key)['items']),
            ('Ni', 'La', 'ña', 'Cas', 'Bi', 'da', 'El', 'ño', 'ñan', 'Cen', 'ta', 'ñe'),
        )
        self.assertEqual(len(cells), 12)
        self.assertEqual(len({expected.casefold() for expected, *_ in cells}), 12)
        for expected, accepted, rejected in cells:
            for transcript in accepted:
                self.assertTrue(l23_g1_pronunciation_match(expected, transcript, key), (expected, transcript))
                self.assertFalse(
                    l23_g1_pronunciation_match(expected, transcript, 'aral-l23-g2-j-word-reading'),
                    (expected, transcript),
                )
                self.assertFalse(
                    l23_g1_pronunciation_match(expected, f'{transcript} {transcript}', key),
                    (expected, transcript),
                )
                for other, *_ in cells:
                    if other.casefold() != expected.casefold():
                        self.assertFalse(l23_g1_pronunciation_match(other, transcript, key), (expected, other))
            self.assertFalse(l23_g1_pronunciation_match(expected, rejected, key), (expected, rejected))
        self.assertFalse(l23_g1_pronunciation_match('Ni', 'ñi', key))

    def test_lesson23_gawain1_new_aliases_advance_once_without_attempts(self):
        key = 'aral-l23-g1-n-syllable-builder'
        activity = get_activity(key)
        aliases = {'Ni': ('Knee.',), 'Bi': ('B', 'b', 'B.'), 'El': ('L', 'l', 'L.')}
        for expected, transcripts in aliases.items():
            target_index = next(index for index, item in enumerate(activity['items']) if item['text'] == expected)
            for transcript in transcripts:
                state = initial_l23_g1_state()
                apply_event(activity, state, {'action': 'reading_started'})
                for item in activity['items'][:target_index]:
                    apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': item['text']}, True)
                verified = l23_g1_pronunciation_match(expected, transcript, key)
                apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': transcript}, verified)
                self.assertEqual(state['index'], target_index + 1, (expected, transcript))
                self.assertEqual(state['last_feedback'], 'Tama!', (expected, transcript))
                self.assertEqual(state['reading_attempts'], 0, (expected, transcript))

    def test_lesson23_gawain1_retry_help_and_building_transition_are_preserved(self):
        activity = get_activity('aral-l23-g1-n-syllable-builder')
        state = initial_l23_g1_state()
        apply_event(activity, state, {'action': 'reading_started'})
        for _ in range(3):
            apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': 'wrong'}, False)
        self.assertEqual(state['index'], 0)
        self.assertEqual(state['reading_phase'], 'help')
        apply_event(activity, state, {'action': 'read_aloud'})
        apply_event(activity, state, {'action': 'retry_reading'})
        for index, item in enumerate(activity['items'], start=1):
            apply_event(activity, state, {'action': 'reading_syllable_attempt', 'transcript': item['text']}, True)
            self.assertEqual(state['index'], index)
            self.assertEqual(state['reading_attempts'], 0)
            self.assertEqual(state['last_feedback'], 'Tama!')
        self.assertTrue(state['read_aloud_completed'])
        apply_event(activity, state, {'action': 'build_word', 'parts': ['item-1', 'item-8']})
        self.assertEqual(state['found_words'], ['Niño'])
        apply_event(activity, state, {'action': 'finish'})
        self.assertTrue(state['completed'])


class PrescribedWorkbookFlowTests(TestCase):
    def setUp(self):
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
        from .prescribed_test_fixtures import prescribed_term_fixture
        prescribed_term_fixture(self.student, teacher=self.teacher, section=self.section)
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

    def test_session8_pause_restart_contract_resets_each_activity_pattern(self):
        """The shared Pause menu must use each activity's revision-aware restart path."""
        controls = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_session8_11_controls.js').read_text(encoding='utf-8')
        self.assertIn("const restartBody = usesResetPayload ? {reset:true,total_items:Number(payload.total_items || payload.progress?.total_items || 0)} : {action:'restart',revision:Number(state.revision || 0)}", controls)
        self.assertIn('body:JSON.stringify(restartBody)', controls)
        self.assertIn('if (!response.ok || !result.success)', controls)
        keys = tuple(key for key, activity in ACTIVITIES.items() if activity['session'] == 8)
        self.assertEqual(len(keys), 22)
        untouched_key = 'aral-s9-a1-family-drawing'
        StudentActivityProgress.objects.create(
            student=self.student, activity_key=untouched_key,
            school_calendar=None, term=None, current_index=3, completed_items=3,
            correct_items=3, total_items=5, activity_completed=False,
            state={'revision': 7, 'found_words': {'Fina': {'color': '#fff'}}},
        )

        with patch('pabasa_app.views._student_can_open_prescribed_activity', return_value=True):
            for key in keys:
                with self.subTest(activity_key=key):
                    url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
                    first = self.client.post(
                        url, json.dumps({'action': 'restart', 'revision': 0}),
                        content_type='application/json',
                    )
                    self.assertEqual(first.status_code, 200, first.content)
                    first_state = first.json()['state']
                    self.assertFalse(first.json()['progress']['activity_completed'])
                    self.assertEqual(first.json()['progress']['completed_items'], 0)

                    stale = self.client.post(
                        url, json.dumps({'action': 'restart', 'revision': 0}),
                        content_type='application/json',
                    )
                    self.assertEqual(stale.status_code, 409, stale.content)

                    second = self.client.post(
                        url, json.dumps({'action': 'restart', 'revision': first_state['revision']}),
                        content_type='application/json',
                    )
                    self.assertEqual(second.status_code, 200, second.content)
                    self.assertEqual(second.json()['progress']['completed_items'], 0)

        untouched = StudentActivityProgress.objects.get(student=self.student, activity_key=untouched_key)
        self.assertEqual(untouched.current_index, 3)
        self.assertEqual(untouched.state['revision'], 7)

    def test_dashboard_derives_gawain1_status_from_authoritative_word_state(self):
        key = 'aral-l22-g1-c-syllable-builder'
        StudentActivityProgress.objects.create(
            student=self.student, activity_key=key,
            school_calendar=None, term=None, current_index=18,
            completed_items=1, correct_items=1, total_items=1,
            activity_completed=True,
            state={
                'index': 18, 'read_aloud_completed': True,
                'found_words': ['cactus'], 'completed': True,
            },
        )
        response = self.client.get(reverse('assessment'))
        self.assertEqual(response.status_code, 200)
        entry = response.context['prescribed_activity_progress'][key]
        self.assertEqual(entry['completed_items'], 1)
        self.assertEqual(entry['total_items'], 7)
        self.assertFalse(entry['activity_completed'])
        self.assertFalse(entry['state']['completed'])
        self.assertEqual(entry['state']['index'], 18)

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
        self.assertContains(page, 'wb-l22-g1-start')
        self.assertContains(page, 'MAMAYA NA LANG')
        self.assertNotIn('material_id', page.context['workbook_payload'])
        state = page.context['workbook_payload']['state']
        response = self.client.post(progress_url, json.dumps({'action': 'reading_started', 'revision': state['revision']}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        state = response.json()['state']
        with patch('pabasa_app.views.reading_transcribe_api', return_value=JsonResponse({
            'success': True, 'transcript': 'cac', 'complete': True,
            'stt_model': 'chirp_2', 'stt_words': [{'word': 'cac', 'confidence': 0.84}],
            'stt_word_confidence_type': 'provider_value_not_confidence',
        })) as speech:
            response = self.client.post(progress_url, {
                'action': 'reading_syllable_attempt', 'revision': state['revision'],
                'audio': SimpleUploadedFile('reading.webm', b'audio', content_type='audio/webm'),
            })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(speech.called)
        self.assertEqual(response.json()['stt_model'], 'chirp_2')
        self.assertEqual(response.json()['stt_words'], [{'word': 'cac', 'confidence': 0.84}])
        self.assertEqual(response.json()['stt_word_confidence_type'], 'provider_value_not_confidence')
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
            'success': True, 'transcript': '', 'complete': False,
        })):
            response = self.client.post(progress_url, {
                'action': 'reading_syllable_attempt', 'revision': state['revision'],
                'audio': SimpleUploadedFile('reading.webm', b'audio', content_type='audio/webm'),
            })
        self.assertEqual(response.status_code, 200, response.content)
        state = response.json()['state']
        self.assertEqual(state['index'], 1)
        self.assertEqual(state['reading_attempts'], 1)
        self.assertEqual(state['last_transcript'], '')
        self.assertEqual(state['last_feedback'], 'Hindi ko malinaw na narinig. Subukan muli.')
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
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('Bumuo muna ng lahat', response.json()['error'])
        progress = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
        self.assertFalse(progress.activity_completed)
        self.assertFalse(progress.state['completed'])
        for parts in (
            ['item-2', 'item-4'],       # Cebu
            ['item-3', 'item-7', 'item-10'],  # Cagayan
            ['item-11', 'item-12'],     # Cardo
            ['item-3', 'item-13', 'item-15'],  # cabinet
            ['item-17', 'item-18', 'item-16'],  # Celeste
            ['item-5'],                 # com
            ['item-5', 'item-6', 'item-9'],  # computer
        ):
            response = self.client.post(progress_url, json.dumps({
                'action': 'build_word', 'parts': parts, 'revision': state['revision'],
            }), content_type='application/json')
            self.assertEqual(response.status_code, 200, response.content)
            state = response.json()['state']
        self.assertEqual(state['found_words'], list(L22_C_ACCEPTED_BUILDS))
        response = self.client.post(progress_url, json.dumps({'action': 'finish', 'revision': state['revision']}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        progress = StudentActivityProgress.objects.get(student=self.student, activity_key=key)
        self.assertTrue(progress.activity_completed)
        self.assertTrue(progress.state['completed'])
        self.assertEqual(progress.current_index, 1)

    def test_lesson22_gawain2_completion_payload_points_to_gawain3_and_assessment(self):
        g2_key = 'aral-l22-g2-c-word-reading'
        g3_key = 'aral-l22-g3-c-word-search'
        self.session_student(self.teacher)
        response = self.client.get(
            reverse('prescribed_activity_page', kwargs={'activity_key': g2_key}),
            {'preview': '1'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('pabasa_app/prescribed_l22_g2_reading_page.html', [template.name for template in response.templates])
        self.assertContains(response, 'prescribed_l22_g2_reading.js')
        payload = response.context['workbook_payload']
        self.assertEqual(
            payload['next_url'],
            reverse('prescribed_activity_page', kwargs={'activity_key': g3_key}),
        )
        self.assertEqual(payload['back_url'], reverse('assessment'))
        next_response = self.client.get(payload['next_url'], {'preview': '1'})
        self.assertEqual(next_response.status_code, 200)
        self.assertEqual(next_response.context['workbook_payload']['activity']['activity_key'], g3_key)

        source = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l22_g2_reading.js').read_text(encoding='utf-8')
        self.assertNotIn('Magpatuloy sa Gawain 3', source)
        self.assertIn('Bumalik sa Aking Aralin', source)
        self.assertNotIn('id="restart">Ulitin Mula sa Simula</button></section></div>`;document.getElementById(\'restart\')', source)

    def test_lesson22_gawain3_route_and_persisted_state(self):
        key = 'aral-l22-g3-c-word-search'
        page_url = reverse('prescribed_activity_page', kwargs={'activity_key': key})
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        page = self.client.get(page_url)
        self.assertEqual(page.status_code, 200, page.content)
        self.assertEqual(page.context['workbook_payload']['activity']['activity_key'], key)
        self.assertIn('pabasa_app/prescribed_l22_g3_word_search_page.html', [template.name for template in page.templates])
        state = page.context['workbook_payload']['state']
        response = self.client.post(progress_url, json.dumps({
            'action': 'select_word', 'word': 'Cebu', 'path': L22_G3_C_WORD_PATHS['Cebu'],
            'color': '#f2c94c', 'revision': state['revision'],
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['progress']['completed_items'], 1)
        reopened = self.client.get(page_url)
        self.assertEqual(reopened.context['workbook_payload']['state']['found_words']['Cebu']['color'], '#f2c94c')

    def test_lesson22_gawain3_uses_single_replayable_filipino_audio_feedback_path(self):
        source = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_l22_g3_word_search.js').read_text(encoding='utf-8')
        template = (Path(__file__).parent / 'templates/pabasa_app/prescribed_l22_g3_word_search_page.html').read_text(encoding='utf-8')
        self.assertIn("const instruction = 'Hanapin at kulayan ng paboritong kulay ang sumusunod na salita sa ibaba.'", source)
        self.assertIn("window.PabasaLessonStart?.({", source)
        self.assertIn("startId: 'wb-l22-g3-start-button'", source)
        self.assertIn("playInstruction({automatic:true})", source)
        self.assertNotIn('setTimeout(() => playInstruction({automatic:true}), 0)', source)
        self.assertIn("result.tts_language !== 'fil-PH' || (!result.local_audio && result.voice_name !== 'fil-PH-Wavenet-A')", source)
        self.assertIn('function speakFeedback(message)', source)
        self.assertIn("Pakinggan Muli ang Panuto", source)
        self.assertIn('finish?.()', source)
        self.assertNotIn('speechSynthesis', source)
        self.assertIn('font-size:clamp(1rem,2.2vw,1.35rem)', template)
        self.assertIn('id="wb-l22-g3-start"', template)
        self.assertIn("lesson_start_modal.css", template)

    def test_lesson22_gawain3_instruction_audio_mapping_returns_local_mp3(self):
        self.session_student(self.student)
        response = self.client.post(reverse('reading_read_aloud_api'), {
            'target_text': 'Hanapin at kulayan ng paboritong kulay ang sumusunod na salita sa ibaba.',
            'language': 'Filipino',
            'mode': 'reading',
            'prescribed_activity_key': 'aral-l22-g3-c-word-search',
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['local_audio'])
        self.assertEqual(response.json()['mime_type'], 'audio/mpeg')
        self.assertGreater(len(response.json()['audio_content']), 0)

    def test_lesson22_syllable_attempt_sends_whole_word_context_to_english_stt(self):
        key = 'aral-l22-g1-c-syllable-builder'
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        state = initial_state()
        self.client.post(progress_url, json.dumps({'action': 'reading_started', 'revision': state['revision']}), content_type='application/json')

        def inspect_reading_request(request):
            self.assertEqual(request.POST['target_text'], 'cactus')
            self.assertEqual(request.POST['language'], 'English')
            self.assertEqual(request.POST['l22_c_pronunciation'], '1')
            self.assertEqual(request.POST['l22_c_syllable'], 'cac')
            self.assertEqual(request.POST['l22_c_sound'], 'hard')
            return JsonResponse({'success': True, 'transcript': 'cactus', 'raw_transcript': 'kak', 'complete': False})

        with patch('pabasa_app.views.reading_transcribe_api', side_effect=inspect_reading_request):
            response = self.client.post(progress_url, {
                'action': 'reading_syllable_attempt', 'revision': 1,
                'audio': SimpleUploadedFile('reading.webm', b'audio', content_type='audio/webm'),
            })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['state']['index'], 1)

    def test_lesson22_cock_alias_uses_normal_progression_path(self):
        key = 'aral-l22-g1-c-syllable-builder'
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        state = initial_state()
        self.client.post(progress_url, json.dumps({'action': 'reading_started', 'revision': state['revision']}), content_type='application/json')

        def cock_reading_response(request):
            self.assertEqual(request.POST['l22_c_syllable'], 'cac')
            self.assertEqual(request.POST['l22_c_sound'], 'hard')
            return JsonResponse({'success': True, 'transcript': 'cock', 'raw_transcript': 'cock', 'complete': False})

        with patch('pabasa_app.views.reading_transcribe_api', side_effect=cock_reading_response):
            response = self.client.post(progress_url, {
                'action': 'reading_syllable_attempt', 'revision': 1,
                'audio': SimpleUploadedFile('reading.webm', b'audio', content_type='audio/webm'),
            })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['state']['index'], 1)
        self.assertEqual(response.json()['state']['last_transcript'], 'cock')

    def test_lesson22_boo_alias_advances_through_the_normal_correct_result_path(self):
        key = 'aral-l22-g1-c-syllable-builder'
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        state = initial_state()
        response = self.client.post(
            progress_url,
            json.dumps({'action': 'reading_started', 'revision': state['revision']}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        state = response.json()['state']

        def observed_stt_response(request):
            expected = request.POST['l22_c_syllable']
            transcript = 'Boo.' if expected == 'bu' else expected
            return JsonResponse({
                'success': True, 'transcript': transcript,
                'raw_transcript': transcript, 'complete': False,
            })

        with patch('pabasa_app.views.reading_transcribe_api', side_effect=observed_stt_response):
            for expected in ('cac', 'ce', 'ca', 'bu'):
                response = self.client.post(progress_url, {
                    'action': 'reading_syllable_attempt', 'revision': state['revision'],
                    'audio': SimpleUploadedFile('reading.webm', b'audio', content_type='audio/webm'),
                })
                self.assertEqual(response.status_code, 200, response.content)
                state = response.json()['state']
                self.assertEqual(state['last_feedback'], 'Tama!')
                self.assertEqual(state['reading_attempts'], 0)

        self.assertEqual(state['index'], 4)
        self.assertEqual(state['last_transcript'], 'bu')

    def test_lesson22_gawain1_new_aliases_advance_through_the_normal_correct_result_path(self):
        key = 'aral-l22-g1-c-syllable-builder'
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        state = initial_state()
        response = self.client.post(
            progress_url,
            json.dumps({'action': 'reading_started', 'revision': state['revision']}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        state = response.json()['state']
        approved_transcripts = {'com': 'Comb.', 'pu': 'Poo.', 'tus': 'Tuss.', 'bi': 'B.', 'net': 'Nett.', 'te': 'T.', 'les': 'less'}

        def approved_alias_response(request):
            expected = request.POST['l22_c_syllable']
            transcript = approved_transcripts.get(expected.casefold(), expected)
            return JsonResponse({
                'success': True, 'transcript': transcript,
                'raw_transcript': transcript, 'complete': False,
            })

        with patch('pabasa_app.views.reading_transcribe_api', side_effect=approved_alias_response):
            for index, _item in enumerate(get_activity(key)['items'], start=1):
                response = self.client.post(progress_url, {
                    'action': 'reading_syllable_attempt', 'revision': state['revision'],
                    'audio': SimpleUploadedFile('reading.webm', b'audio', content_type='audio/webm'),
                })
                self.assertEqual(response.status_code, 200, response.content)
                state = response.json()['state']
                self.assertEqual(state['index'], index)
                self.assertEqual(state['last_feedback'], 'Tama!')
                self.assertEqual(state['reading_attempts'], 0)

        self.assertTrue(state['read_aloud_completed'])

    def test_lesson23_gawain1_aliases_advance_through_the_normal_correct_result_path(self):
        key = 'aral-l23-g1-n-syllable-builder'
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        state = initial_l23_g1_state()
        response = self.client.post(
            progress_url,
            json.dumps({'action': 'reading_started', 'revision': state['revision']}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        state = response.json()['state']

        observed_targets = []

        def approved_alias_response(request):
            expected = request.POST['target_text']
            observed_targets.append(expected)
            transcript = {'Ni': 'Knee.', 'Bi': 'B.', 'El': 'L.'}.get(expected, f'{expected}.')
            return JsonResponse({
                'success': True, 'transcript': transcript,
                'raw_transcript': transcript, 'complete': False,
            })

        with patch('pabasa_app.views.reading_transcribe_api', side_effect=approved_alias_response):
            for index, _item in enumerate(get_activity(key)['items'], start=1):
                response = self.client.post(progress_url, {
                    'action': 'reading_syllable_attempt', 'revision': state['revision'],
                    'audio': SimpleUploadedFile('reading.webm', b'audio', content_type='audio/webm'),
                })
                self.assertEqual(response.status_code, 200, response.content)
                state = response.json()['state']
                self.assertEqual(state['index'], index)
                self.assertEqual(state['last_feedback'], 'Tama!')
                self.assertEqual(state['reading_attempts'], 0)

        self.assertTrue(state['read_aloud_completed'])
        self.assertEqual(
            observed_targets,
            ['Ni', 'La', 'ña', 'Cas', 'Bi', 'da', 'El', 'ño', 'ñan', 'Cen', 'ta', 'ñe'],
        )

    @patch('pabasa_app.views.synthesize_read_aloud_audio', return_value='encoded-audio')
    def test_lesson_22_read_aloud_uses_prescribed_filipino_voice(self, synthesize):
        self.session_student(self.student)
        response = self.client.post(reverse('reading_read_aloud_api'), {
            'target_text': 'Basahin ang naka-highlight na pantig.',
            'language': 'Filipino',
            'mode': 'reading',
            'prescribed_activity_key': 'aral-l22-g1-c-syllable-builder',
        })

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['tts_language'], 'fil-PH')
        self.assertEqual(response.json()['voice_name'], 'fil-PH-Wavenet-A')
        self.assertEqual(synthesize.call_args.args[2], 'fil-PH')
        self.assertEqual(synthesize.call_args.kwargs['voice_gender'], 'FEMALE')

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
            ('aral-s9-a2-helping-drawing', 9),
        ):
            with self.subTest(activity_key=key):
                response = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': key}))
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.context['workbook_payload']['activity']['session'], expected_session)

    def test_session9_activity1_renders_draw_then_write_interface(self):
        response = self.client.get(reverse('prescribed_activity_page', kwargs={
            'activity_key': 'aral-s9-a1-family-drawing',
        }))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(response, 'Draw a picture of your family. Under your drawing, write the sentence')
        self.assertContains(response, 'prescribed_s9_a1_family_drawing.css')
        self.assertContains(response, 'wb-s9-family-page')

    def test_session9_activity2_renders_large_coloring_interface(self):
        response = self.client.get(reverse('prescribed_activity_page', kwargs={
            'activity_key': 'aral-s9-a2-helping-drawing',
        }))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(response, 'Draw and color a situation at home where you helped someone.')
        self.assertContains(response, 'prescribed_s9_a2_helping_drawing.css')
        self.assertContains(response, 'wb-s9-helping-page')
        self.assertContains(response, 'wb-progress-track')

    def test_session9_drawing_activities_use_exact_instruction_start_modal_and_shared_read_aloud(self):
        expected = {
            'aral-s9-a1-family-drawing': 'Draw a picture of your family. Under your drawing, write the sentence “This is my family.”',
            'aral-s9-a2-helping-drawing': 'Draw and color a situation at home where you helped someone. Under your drawing, write the courteous word you used: “Please” / “Sorry” / “Thank you” / “You’re welcome.”',
        }
        source = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        self.assertNotIn('speechSynthesis', source)
        for key, instruction in expected.items():
            with self.subTest(activity_key=key):
                response = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': key}))
                self.assertEqual(response.context['workbook_payload']['activity']['session_key'], 'session-9')
                self.assertEqual(response.context['workbook_payload']['activity']['instruction'], instruction)
                self.assertContains(response, 'id="wb-s9-start"')
                self.assertContains(response, 'id="wb-s9-start-button"')
                self.assertContains(response, 'MAYBE LATER')
                self.assertContains(response, instruction)
                self.assertContains(response, 'id="wb-instruction-replay"')

    @patch('pabasa_app.views.synthesize_read_aloud_audio', return_value='encoded-audio')
    def test_session9_instruction_read_aloud_uses_english_google_voice_path(self, synthesize):
        self.session_student(self.student)
        for key in ('aral-s9-a1-family-drawing', 'aral-s9-a2-helping-drawing'):
            with self.subTest(activity_key=key):
                instruction = get_activity(key)['instruction']
                response = self.client.post(reverse('reading_read_aloud_api'), {
                    'target_text': instruction,
                    'language': 'English',
                    'mode': 'reading',
                    'prescribed_activity_key': key,
                    'prescribed_session_key': 'session-9',
                })
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()['tts_language'], 'en-PH')
                self.assertEqual(response.json()['voice_name'], '')
                self.assertEqual(synthesize.call_args.args[2], 'en-PH')


class TeacherSession89IntegrationTests(TestCase):
    def setUp(self):
        school = School.objects.create(name='Teacher Review School', code='TRS')
        self.student = User.objects.create(custom_id='TR-STUDENT', role='student', first_name='Review', last_name='Student', email='review-student@example.com', password_hash='test', sex='N/A', birth_month=1, birth_day=1, birth_year=2016, school_record=school)
        self.teacher = User.objects.create(custom_id='TR-TEACHER', role='teacher', first_name='Review', last_name='Teacher', email='review-teacher@example.com', password_hash='test', sex='N/A', birth_month=1, birth_day=1, birth_year=1990, school_record=school)
        self.section = Section.objects.create(school=school, class_code='TR-1', class_name='Teacher Review', subject='Reading', teacher=self.teacher, is_active=True)
        self.section.add_student(self.student)
        from .prescribed_test_fixtures import prescribed_term_fixture
        prescribed_term_fixture(self.student, teacher=self.teacher, section=self.section)

    def set_session(self, user):
        session = self.client.session
        session.update({'user_id': user.pk, 'user_role': user.role, 'email': user.email})
        session.save()

    def _create_legacy_progress(self, activity_key):
        progress = StudentActivityProgress.objects.create(
            student=self.student,
            activity_key=activity_key,
            current_index=4,
            completed_items=4,
            correct_items=4,
            total_items=5,
            state={'revision': 77, 'completed_words': [4]},
        )
        # Emulate a legacy row that is not scoped to the student's active term.
        StudentActivityProgress.objects.filter(pk=progress.pk).update(school_calendar=None, term=None)
        return progress

    def test_teacher_preview_can_use_legacy_progress_fallback(self):
        key = 'aral-l23-g7-q-word-reading'
        self._create_legacy_progress(key)
        self.student.school_calendar = None
        self.student.save(update_fields=['school_calendar', 'updated_at'])
        self.set_session(self.teacher)

        with patch('pabasa_app.views._current_learning_context', return_value={}):
            response = self.client.get(
                reverse('prescribed_activity_page', kwargs={'activity_key': key}),
                {'preview': '1', 'student_id': self.student.pk},
            )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.context['workbook_payload']
        self.assertTrue(payload['preview'])
        self.assertEqual(payload['state']['revision'], 77)
        self.assertEqual(payload['state']['completed_words'], [4])

    @patch('pabasa_app.views._student_can_open_prescribed_activity', return_value=True)
    def test_student_access_does_not_restore_legacy_progress_from_another_term(self, _open):
        key = 'aral-l23-g7-q-word-reading'
        self._create_legacy_progress(key)
        self.set_session(self.student)

        response = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': key}))

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.context['workbook_payload']
        self.assertFalse(payload['preview'])
        self.assertNotEqual(payload['state'].get('revision'), 77)
        self.assertNotIn(4, payload['state'].get('completed_words', []))

    def test_teacher_preview_requires_authorization_and_is_view_only(self):
        outsider = User.objects.create(
            custom_id='TR-OUTSIDER-PREVIEW', role='teacher', first_name='Other', last_name='Teacher',
            email='other-preview@example.com', password_hash='test', sex='N/A', birth_month=1,
            birth_day=1, birth_year=1990, school_record=self.student.school_record,
        )
        self.set_session(outsider)
        denied = self.client.get(
            reverse('prescribed_activity_page', kwargs={'activity_key': 'aral-l23-g7-q-word-reading'}),
            {'preview': '1', 'student_id': self.student.pk},
        )
        self.assertEqual(denied.status_code, 403)

        self.set_session(self.teacher)
        preview = self.client.get(
            reverse('prescribed_activity_page', kwargs={'activity_key': 'aral-l23-g7-q-word-reading'}),
            {'preview': '1', 'student_id': self.student.pk},
        )
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertTrue(preview.context['workbook_payload']['preview'])
        invalid_review = self.client.post(
            reverse('teacher_prescribed_review_action'),
            json.dumps({'student_id': self.student.pk, 'activity_key': 'aral-l23-g7-q-word-reading', 'action': 'complete'}),
            content_type='application/json',
        )
        self.assertEqual(invalid_review.status_code, 400)

    def test_teacher_session8_progress_is_read_only_and_activity_scoped(self):
        self.set_session(self.teacher)
        page = self.client.get(reverse('teacher_prescribed_review_page'))
        self.assertEqual(page.status_code, 200, page.content)
        response = self.client.get(reverse('teacher_prescribed_progress'), {'student_id': self.student.pk, 'session': 8})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()['activities']), 22)
        self.assertTrue(all('preview_url' in row and 'artifact' not in row for row in response.json()['activities']))

    @patch('pabasa_app.views._student_can_open_prescribed_activity', return_value=True)
    def test_session9_submission_waits_for_teacher_and_complete_persists(self, _open):
        self.set_session(self.student)
        stroke = {'color': '#183e63', 'width': 5, 'points': [[1, 1], [4, 4]]}
        response = self.client.post(reverse('prescribed_activity_progress', kwargs={'activity_key': 'aral-s9-a1-family-drawing'}), json.dumps({'action': 'answer', 'revision': 0, 'answer': {'text': 'This is my family.', 'strokes': [stroke]}}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()['progress']['activity_completed'])
        self.assertTrue(response.json()['state']['awaiting_teacher_verdict'])
        self.set_session(self.teacher)
        response = self.client.get(reverse('teacher_prescribed_progress'), {'student_id': self.student.pk, 'session': 9})
        self.assertEqual(response.status_code, 200, response.content)
        row = next(item for item in response.json()['activities'] if item['activity_key'] == 'aral-s9-a1-family-drawing')
        self.assertEqual(row['status'], 'Pending Teacher Review')
        self.assertEqual(row['artifact']['text'], 'This is my family.')
        response = self.client.post(reverse('teacher_prescribed_review_action'), json.dumps({'student_id': self.student.pk, 'activity_key': 'aral-s9-a1-family-drawing', 'action': 'complete'}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['activity_completed'])

    def test_teacher_review_rejects_unenrolled_students(self):
        outsider = User.objects.create(custom_id='TR-OUTSIDER', role='teacher', first_name='Other', last_name='Teacher', email='other-teacher@example.com', password_hash='test', sex='N/A', birth_month=1, birth_day=1, birth_year=1990, school_record=self.student.school_record)
        self.set_session(outsider)
        response = self.client.get(reverse('teacher_prescribed_progress'), {'student_id': self.student.pk, 'session': 8})
        self.assertEqual(response.status_code, 403)
        response = self.client.post(reverse('teacher_prescribed_review_action'), json.dumps({'student_id': self.student.pk, 'activity_key': 'aral-s9-a1-family-drawing', 'action': 'complete'}), content_type='application/json')
        self.assertEqual(response.status_code, 403)

    @patch('pabasa_app.views._student_can_open_prescribed_activity', return_value=True)
    def test_session9_retry_keeps_activity_incomplete_and_allows_resubmission(self, _open):
        stroke = {'color': '#183e63', 'width': 5, 'points': [[1, 1], [4, 4]]}
        self.set_session(self.student)
        url = reverse('prescribed_activity_progress', kwargs={'activity_key': 'aral-s9-a2-helping-drawing'})
        first = self.client.post(url, json.dumps({'action': 'answer', 'revision': 0, 'answer': {'text': 'Please', 'strokes': [stroke]}}), content_type='application/json')
        self.assertEqual(first.status_code, 200, first.content)
        self.set_session(self.teacher)
        review = self.client.post(reverse('teacher_prescribed_review_action'), json.dumps({'student_id': self.student.pk, 'activity_key': 'aral-s9-a2-helping-drawing', 'action': 'retry'}), content_type='application/json')
        self.assertEqual(review.status_code, 200, review.content)
        self.assertFalse(review.json()['activity_completed'])
        self.set_session(self.student)
        second = self.client.post(url, json.dumps({'action': 'answer', 'revision': 0, 'answer': {'text': 'Thank you', 'strokes': [stroke]}}), content_type='application/json')
        self.assertEqual(second.status_code, 200, second.content)
        self.assertFalse(second.json()['progress']['activity_completed'])
