from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_workbook import (
    L24_G6_Z_WORD_PATHS,
    apply_event,
    get_activity,
    initial_l24_g6_state,
    normalize_l24_g6_state,
)


class Lesson24Gawain6WordSearchTests(SimpleTestCase):
    key = 'aral-l24-g6-z-word-search'

    def test_workbook_content_and_grid_are_exact(self):
        activity = get_activity(self.key)
        self.assertEqual(activity['instruction'], 'Panuto: Hanapin at bilugan sa loob ng Big Box ang sumusunod na mga salita.')
        self.assertEqual([item['text'] for item in activity['items']], [
            'zipper', 'zoo', 'zebra', 'zigzag', 'Perez',
            'Rizal', 'Zamora', 'Zam', 'Zoren', 'Zeny',
        ])
        self.assertEqual(len(activity['grid']), 8)
        self.assertTrue(all(len(row) == 9 for row in activity['grid']))
        self.assertEqual(sum(len(row) for row in activity['grid']), 72)
        self.assertEqual(activity['grid'][0], 'ZAMORATYZ')
        self.assertEqual(activity['grid'][-1], 'SMRIZALUK')
        self.assertEqual(activity['interaction_type'], 'search')

    def test_canonical_paths_cover_all_targets(self):
        activity = get_activity(self.key)
        expected = [item['text'] for item in activity['items']]
        self.assertEqual(list(L24_G6_Z_WORD_PATHS), expected)
        for word, path in L24_G6_Z_WORD_PATHS.items():
            self.assertEqual(''.join(activity['grid'][row][column] for row, column in path).casefold(), word.casefold())

    def test_valid_invalid_duplicate_completion_and_reset(self):
        activity = get_activity(self.key)
        state = initial_l24_g6_state()
        apply_event(activity, state, {'action': 'select_word', 'word': 'zipper', 'path': L24_G6_Z_WORD_PATHS['zipper']})
        self.assertEqual(set(state['found_words']), {'zipper'})
        self.assertFalse(state['completed'])
        apply_event(activity, state, {'action': 'select_word', 'word': 'zoo', 'path': [[0, 0], [0, 1], [0, 2]]})
        self.assertEqual(set(state['found_words']), {'zipper'})
        self.assertEqual(state['last_feedback'], 'Subukan muli.')
        apply_event(activity, state, {'action': 'select_word', 'word': 'zipper', 'path': L24_G6_Z_WORD_PATHS['zipper']})
        self.assertEqual(len(state['found_words']), 1)
        self.assertEqual(state['last_feedback'], 'Nahanap mo na ang salitang ito.')
        for word, path in L24_G6_Z_WORD_PATHS.items():
            apply_event(activity, state, {'action': 'select_word', 'word': word, 'path': path})
        self.assertTrue(state['completed'])
        self.assertEqual(len(state['found_words']), 10)
        self.assertEqual(len(normalize_l24_g6_state(state)['found_words']), 10)
        apply_event(activity, state, {'action': 'restart'})
        self.assertEqual(state, initial_l24_g6_state())

    def test_renderer_template_and_css_are_word_search_specific(self):
        root = Path(__file__).parent
        js = (root / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        css = (root / 'static/pabasa_app/css/prescribed_l24_g6_search.css').read_text(encoding='utf-8')
        template = (root / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')
        self.assertIn('renderL24G6WordSearch()', js)
        self.assertIn('select_word', js)
        self.assertIn('wb-g6-grid', js)
        self.assertIn('PRESCRIBED-BG.jpg', css)
        self.assertIn('aral-l24-g6-z-word-search', template)
        self.assertNotIn('overflow:hidden', css)

    def test_renderer_cell_markup_does_not_shadow_selection_state(self):
        js = (Path(__file__).parent / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        renderer = js.split('function renderL24G6WordSearch', 1)[1].split('function renderFill', 1)[0]
        self.assertIn('const isSelected=selected.some', renderer)
        self.assertNotIn('const selected=selected.some', renderer)
        self.assertIn("addEventListener('pointerdown'", renderer)

    def test_completion_flow_is_target_scoped_and_idempotent(self):
        root = Path(__file__).parent
        js = (root / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        views = (root / 'views.py').read_text(encoding='utf-8')
        self.assertIn('let audioRun = 0, instructionSpoken = false, pendingSpeech = \'\', g6CompletionPromise = null;', js)
        self.assertIn('if(g6Search&&state.completed&&!wasCompleted)await completeG6();', js)
        completion_branch = js.split('if(g6Search){', 1)[1].split('if(g7Reading){', 1)[0]
        self.assertIn('BUMALIK SA AKING ARALIN', completion_branch)
        self.assertIn('SUNOD NA GAWAIN', completion_branch)
        self.assertNotIn('>Bumalik sa Aking Aralin</a>', completion_branch)
        self.assertIn('renderL24G6WordSearch();', completion_branch)
        self.assertIn('document.body.insertAdjacentHTML', completion_branch)
        self.assertIn('id="wb-g6-completion-modal"', completion_branch)
        self.assertNotIn('content.innerHTML=`<div class="wb-g6-completion-modal"', completion_branch)
        self.assertIn("if(g6Search&&L24_G6_WORD_SEARCH_MAPPED_TEXT.has(state.last_feedback))await playPrescribedAudio(state.last_feedback,true);", js)
        self.assertIn('g6CompletionPromise=null;modal.remove();perform({action:\'restart\'})', js)
        g6_view = views.split("audio_root = 'pabasa_app/prescribed/audio/SESSION_8/LESSON_24/BAHAGI_2/GAWAIN_6/'", 1)[1].split("if activity_key == 'aral-l24-g7-z-word-reading':", 1)[0]
        self.assertIn("'completion_url': reverse('prescribed_activity_complete'", g6_view)

    def test_dashboard_uses_current_scoped_g6_progress(self):
        views = (Path(__file__).parent / 'views.py').read_text(encoding='utf-8')
        dashboard_branch = views.split("if stage == 'original':", 1)[1].split("        try:\n            logger.warning(", 1)[0]
        self.assertIn("g6_progress = _current_progress_queryset(user).filter(activity_key=g6_key).first()", dashboard_branch)
        self.assertIn("context['prescribed_activity_progress'].pop(g6_key, None)", dashboard_branch)
