from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_activity_catalog import prescribed_activity
from .views import _normalized_oral_picture_match_state


class Gawain7StartStateTests(SimpleTestCase):
    def setUp(self):
        self.activity = prescribed_activity('lesson-17-18-gawain-7')

    def test_new_attempt_waits_on_the_separate_start_page(self):
        state = _normalized_oral_picture_match_state(self.activity, {})
        self.assertEqual(state['phase'], 'intro')
        self.assertEqual(state['current_oral_word_index'], 0)

    def test_started_attempt_resumes_the_current_reading_word(self):
        state = _normalized_oral_picture_match_state(self.activity, {
            'phase': 'oral_reading', 'unlocked_oral_words': ['riles', 'puso'],
            'stt_attempts': {'robot': 3}, 'state_version': 4,
        })
        self.assertEqual(state['phase'], 'oral_reading')
        self.assertEqual(state['current_oral_word_index'], 2)
        self.assertEqual(state['stt_attempts']['robot'], 3)

    def test_matching_remains_locked_until_all_five_words_are_read(self):
        state = _normalized_oral_picture_match_state(self.activity, {
            'phase': 'matching', 'unlocked_oral_words': ['riles', 'puso'],
        })
        self.assertEqual(state['phase'], 'oral_reading')
        self.assertEqual(state['current_oral_word_index'], 2)


class Gawain7AudioLifecycleTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        app_dir = Path(__file__).resolve().parent
        cls.page = (app_dir / 'templates' / 'pabasa_app' / 'prescribed_oral_picture_word_matching_page.html').read_text(encoding='utf-8')
        cls.controls = (app_dir / 'static' / 'pabasa_app' / 'js' / 'session6_prescribed_controls.js').read_text(encoding='utf-8')

    def test_all_five_number_clips_are_followed_by_the_matching_word_clip(self):
        number_clips = [
            'unang_salita_sa_lima.mp3', 'ikalawang_salita_sa_lima.mp3',
            'ikatlong_salita_sa_lima.mp3', 'ika_apat_na_salita_sa_lima.mp3',
            'ikalimang_salita_sa_lima.mp3',
        ]
        for filename in number_clips:
            self.assertIn(filename, self.page)
        self.assertIn('await playClip(numberClips[index],run);await playClip(`basahin_${word}.mp3`,run)', self.page)

    def test_cancel_and_unexpected_pause_have_distinct_outcomes(self):
        self.assertIn("error.name='AbortError'", self.page)
        self.assertIn("player.onpause=()=>finish(player.ended?null:", self.page)
        self.assertIn("player.__session6PauseReason?canceled():Error('Nahinto ang audio.", self.page)
        self.assertIn("pauseIntentionally(activeAudio, 'canceled')", self.controls)
        self.assertIn("pauseIntentionally(activeAudio, 'superseded')", self.controls)

    def test_pause_navigation_and_new_prompt_invalidate_stale_callbacks(self):
        self.assertIn("stopAudio(event.detail?.reason||'canceled')", self.page)
        self.assertIn("if(run===audioRun)controls.forEach", self.page)
        self.assertIn("const run=stopAudio('new-prompt')", self.page)

    def test_listen_retries_the_full_prompt_without_recording_an_attempt(self):
        self.assertIn("event.target.closest('#listen')", self.page)
        self.assertIn('playWordPrompt(s.current_oral_word_index)', self.page)
        prompt_source = self.page.split('async function playWordPrompt', 1)[1].split('async function announce', 1)[0]
        self.assertNotIn('stt_attempts[word]=', prompt_source)
        self.assertNotIn('read_aloud_plays[word]=', prompt_source)
