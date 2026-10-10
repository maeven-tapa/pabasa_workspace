import hashlib
from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_workbook import apply_event, get_activity, initial_state


class Lesson22Gawain1AudioTests(SimpleTestCase):
    key = 'aral-l22-g1-c-syllable-builder'
    audio_dir = Path(__file__).parent / 'static/pabasa_app/prescribed/audio/SESSION_8/LESSON_22/GAWAIN_1'
    original_files = {
        'Basahin_ang_mga_pantig_mula_sa_Bid_box_TTS.mp3',
        'Letrang C. Handa kana_TTS.mp3',
        *(f'{name}_TTS.mp3' for name in ('bi', 'bu', 'ca', 'cac', 'car', 'ce', 'com', 'do', 'ga', 'les', 'net', 'pu', 'te', 'ter', 'tus', 'yan')),
        'Handa ka na_TTS.mp3',
        'Magaling! Nabasa mo nang tama ang lahat ng pantig._TTS.mp3',
        'Subukan muli._TTS.mp3',
        'Tama!_TTS.mp3',
    }
    added_files = {
        'Bumuo muna ng kahit isang wastong salita._TTS.mp3',
        'Bumuo ng ibang salita._TTS.mp3',
        'Gumamit ng mga pantig sa Big Box._TTS.mp3',
        'Hindi available ang audio_TTS.mp3',
        'Hindi available ang mikropono sa browser na ito._TTS.mp3',
        'Hindi available ang panuto._TTS.mp3',
        'Hindi ko malinaw na narinig. Subukan muli._TTS.mp3',
        'Hindi magamit ang mikropono. Subukan muli._TTS.mp3',
        'Hindi nakuha ang iyong boses. Subukan muli._TTS.mp3',
        'Hindi wastong mga pantig._TTS.mp3',
        'Magaling! Natapos mo ang Gawain 1._TTS.mp3',
        'Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa._TTS.mp3',
        'Pakinggan muna ang tamang pagbigkas._TTS.mp3',
        'Subukan muli. Hindi pa matiyak ang salitang ito._TTS.mp3',
        'Walang nakuha sa recording. Subukan muli._TTS.mp3',
    }
    manifest_entries = {
        'Bumuo muna ng kahit isang wastong salita.': 'Bumuo muna ng kahit isang wastong salita._TTS.mp3',
        'Bumuo ng ibang salita.': 'Bumuo ng ibang salita._TTS.mp3',
        'Gumamit ng mga pantig sa Big Box.': 'Gumamit ng mga pantig sa Big Box._TTS.mp3',
        'Hindi available ang audio': 'Hindi available ang audio_TTS.mp3',
        'Hindi available ang audio.': 'Hindi available ang audio_TTS.mp3',
        'Hindi available ang mikropono sa browser na ito.': 'Hindi available ang mikropono sa browser na ito._TTS.mp3',
        'Hindi available ang panuto.': 'Hindi available ang panuto._TTS.mp3',
        'Hindi ko malinaw na narinig. Subukan muli.': 'Hindi ko malinaw na narinig. Subukan muli._TTS.mp3',
        'Hindi magamit ang mikropono. Subukan muli.': 'Hindi magamit ang mikropono. Subukan muli._TTS.mp3',
        'Hindi nakuha ang iyong boses. Subukan muli.': 'Hindi nakuha ang iyong boses. Subukan muli._TTS.mp3',
        'Hindi wastong mga pantig.': 'Hindi wastong mga pantig._TTS.mp3',
        'Magaling! Natapos mo ang Gawain 1.': 'Magaling! Natapos mo ang Gawain 1._TTS.mp3',
        'Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.': 'Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa._TTS.mp3',
        'Pakinggan muna ang tamang pagbigkas.': 'Pakinggan muna ang tamang pagbigkas._TTS.mp3',
        'Subukan muli. Hindi pa matiyak ang salitang ito.': 'Subukan muli. Hindi pa matiyak ang salitang ito._TTS.mp3',
        'Walang nakuha sa recording. Subukan muli.': 'Walang nakuha sa recording. Subukan muli._TTS.mp3',
    }

    def setUp(self):
        root = Path(__file__).parent
        self.js = (root / 'static/pabasa_app/js/prescribed_workbook.js').read_text(encoding='utf-8')
        self.views = (root / 'views.py').read_text(encoding='utf-8')
        self.template = (root / 'templates/pabasa_app/prescribed_workbook_page.html').read_text(encoding='utf-8')

    def test_gawain1_content_and_audio_manifest_cover_all_runtime_syllables(self):
        activity = get_activity(self.key)
        syllables = [item['text'] for item in activity['items']]
        self.assertEqual(syllables, ['cac', 'ce', 'ca', 'bu', 'com', 'pu', 'ga', 'tus', 'ter', 'yan', 'Car', 'do', 'bi', 'ca', 'net', 'te', 'Ce', 'les'])
        self.assertIn("'syllables': {", self.views)
        self.assertIn("'feedback': {", self.views)
        self.assertIn("'completion': {", self.views)
        for text in set(syllables):
            self.assertIn(f"'{text}'", self.views)
            self.assertTrue((self.audio_dir / f'{text.lower()}_TTS.mp3').is_file(), text)

    def test_all_gawain1_recordings_are_nonempty_mp3_files(self):
        expected = self.original_files | self.added_files
        self.assertEqual({path.name for path in self.audio_dir.glob('*.mp3')}, expected)
        self.assertEqual(len(self.original_files), 22)
        self.assertEqual(len(expected), 37)
        for name in expected:
            path = self.audio_dir / name
            self.assertGreater(path.stat().st_size, 0, name)
            self.assertEqual(path.read_bytes()[:3], b'ID3', name)

    def test_added_manifest_entries_point_to_target_audio_and_preserve_existing_entries(self):
        for text, filename in self.manifest_entries.items():
            self.assertIn(f"'{text}': '{filename}'", self.views)
            self.assertTrue((self.audio_dir / filename).is_file(), filename)
        self.assertIn("'Letrang C. Handa kana?': 'Letrang C. Handa kana_TTS.mp3'", self.views)
        self.assertIn("'Magaling! Nabasa mo nang tama ang lahat ng pantig.': 'Magaling! Nabasa mo nang tama ang lahat ng pantig._TTS.mp3'", self.views)

    def test_target_instruction_uses_rendered_local_audio_before_google_tts(self):
        instruction = 'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita mula rito.'
        self.assertIn(f"'{instruction}'", self.js)
        self.assertIn("'instruction': 'Basahin_ang_mga_pantig_mula_sa_Bid_box_TTS.mp3'", self.views)
        self.assertIn("const mapped = (l22G1 && L22_G1_MAPPED_TEXT.has(text))", self.js)

    def test_uncertain_word_feedback_is_constructed_word_validation_feedback(self):
        activity = get_activity(self.key)
        state = initial_state()
        state['read_aloud_completed'] = True
        state['reading_phase'] = 'complete'
        apply_event(activity, state, {'action': 'build_word', 'parts': ['item-1', 'item-2']})
        self.assertEqual(state['last_feedback'], 'Subukan muli. Hindi pa matiyak ang salitang ito.')
        self.assertEqual(state['building_attempts'], 1)
        self.assertFalse(state['found_words'])
        self.assertIn("'Subukan muli. Hindi pa matiyak ang salitang ito.'", self.js)

    def test_completion_selection_has_one_target_playback_and_non_target_selection_remains(self):
        completion_branch = self.js.split('if(l22G1){if(state.completed)', 1)[1].split('if(l23G1)', 1)[0]
        self.assertEqual(completion_branch.count("await playPrescribedAudio('Magaling! Nabasa mo nang tama ang lahat ng pantig.',true)"), 1)
        self.assertEqual(completion_branch.count('await playPrescribedAudio(state.last_feedback,true)'), 1)
        self.assertIn("state.completed && text === 'Magaling! Nabasa mo nang tama ang lahat ng pantig.'", self.js)
        self.assertIn("? 'Magaling! Natapos mo ang Gawain 1.' : text", self.js)
        self.assertIn("const l23G1 = a.activity_key === 'aral-l23-g1-n-syllable-builder';", self.js)
        self.assertIn('(l23G1 && G1_MAPPED_TEXT.has(text))', self.js)
        self.assertIn("if(l23G1){if(state.completed){await playPrescribedAudio('Magaling! Natapos mo ang Gawain 1.'", self.js)
        self.assertNotIn('playbackText = l23G1', self.js)

    def test_gawain1_audio_precedes_google_tts_and_cache_token_is_scoped(self):
        self.assertIn('const localUrl=', self.js)
        self.assertIn('(l22G1 && L22_G1_MAPPED_TEXT.has(text))', self.js)
        self.assertIn("(localAudio.syllables || {})[playbackText]", self.js)
        self.assertIn("(localAudio.feedback || {})[playbackText]", self.js)
        self.assertIn("(localAudio.completion || {})[playbackText]", self.js)
        self.assertIn("new Audio(localUrl)", self.js)
        self.assertIn("'Letrang C. Handa kana?': 'Letrang C. Handa kana_TTS.mp3'", self.views)
        self.assertIn("aral-l22-g1-c-syllable-builder' %}<script", self.template)
        self.assertIn('20261005-l22-g1-startup-audio-4', self.template)

    def test_result_feedback_is_audio_only_but_operational_and_missing_statuses_remain_visible(self):
        self.assertIn("const L22_G1_OPERATIONAL_FEEDBACK = new Set(['Handa ka na?', 'Nakikinig...', 'Sinusuri ang iyong pagbasa...', 'Hindi magamit ang mikropono ngayon. Subukan muli mamaya.']);", self.js)
        self.assertIn("const l22G1ShouldHideResult = text => l22G1 && Boolean(text) && L22_G1_MAPPED_TEXT.has(text) && !L22_G1_OPERATIONAL_FEEDBACK.has(text);", self.js)
        self.assertIn("primary.classList.toggle('wb-audio-only-result',l22G1ShouldHideResult(text))", self.js)
        self.assertIn("wb-builder-feedback${l22G1ShouldHideResult(state.last_feedback)?' wb-audio-only-result':''}", self.js)
        self.assertIn("phaseStatus.classList.toggle('wb-audio-only-result',l22G1ShouldHideResult(state.last_feedback));", self.js)
        self.assertIn('.wb-l22-g1-page .wb-audio-only-result', (Path(__file__).parent / 'static/pabasa_app/css/prescribed_l22_c_builder.css').read_text(encoding='utf-8'))
        self.assertIn('Hindi magamit ang mikropono ngayon. Subukan muli mamaya.', self.js)
        self.assertIn('20261007-l22-g1-result-audio-only-1', self.template)

    def test_gawain1_startup_owner_is_independent_and_instruction_replay_remains(self):
        self.assertIn("if(!startupNarrationStarted){startupNarrationStarted=true;playStartup();}", self.js)
        self.assertIn("playPrescribedAudio(l22StartupTtsText,true)", self.js)
        self.assertNotIn('wb-l22-g1-start-audio-retry', self.template)
        self.assertIn('id="wb-instruction-replay"', self.template)

    def test_gawain1_restart_control_is_target_scoped_and_reachable(self):
        self.assertIn("}else if(!preview&&l22G1){", self.js)
        self.assertIn("restart.id='wb-l22-reset';", self.js)
        self.assertIn("perform({action:'restart'})", self.js)
        workbook = (Path(__file__).parent / 'prescribed_workbook.py').read_text(encoding='utf-8')
        self.assertIn("def _apply_l22_c_builder", workbook)
        self.assertIn("if action == 'restart':", workbook)

    def test_instruction_recording_hash_is_stable(self):
        digest = hashlib.sha256((self.audio_dir / 'Basahin_ang_mga_pantig_mula_sa_Bid_box_TTS.mp3').read_bytes()).hexdigest()
        self.assertEqual(digest, 'dcd6d619b12abd1505e2fc508632f8dcb7269d9aa662d4e0c841b9bff3b26599')
