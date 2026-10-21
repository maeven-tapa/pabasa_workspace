"""Regression coverage for the real Lesson 3 Gawain 1 transcription endpoint."""
import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings

from .views import reading_transcribe_api


PAIRS = (
    ('MAIS', 'LAPIS', True), ('BATA', 'MATA', True),
    ('TASA', 'PAGONG', False), ('WALO', 'TATLO', True),
    ('BAKA', 'BABOY', False), ('KAHON', 'DAHON', True),
)
TRANSLATIONS = dict(zip(
    (word for pair in PAIRS for word in pair[:2]),
    ('corn', 'pencil', 'child', 'eye', 'cup', 'turtle', 'eight', 'three',
     'cow', 'pig', 'box', 'leaf'),
))


@override_settings(GOOGLE_STT_API_KEY='test-key', GOOGLE_STT_MODEL='chirp_3')
class Lesson3ReadingTests(SimpleTestCase):
    def transcribe(self, target, heard, *, knowlez=False, stream=False, **fields):
        request = RequestFactory().post('/api/reading/transcribe/', {
            'audio': SimpleUploadedFile('synthetic.webm', b'test-audio', content_type='audio/webm'),
            'target_text': target, 'language': 'Filipino', 'mode': 'reading',
            'prescribed_activity_key': 'lesson-3-gawain-1', **fields,
        })
        request._dont_enforce_csrf_checks = True
        with (
            patch('pabasa_app.views._check_auth', return_value=True),
            patch('pabasa_app.views._enforce_student_access_for_request', return_value=None),
            patch('pabasa_app.views.uses_knowlez_stt', return_value=knowlez),
            patch('pabasa_app.crla_stream.prescribed_stream_transcript', return_value=heard if stream else None),
            patch('pabasa_app.views.transcribe_audio_bytes_with_model', return_value=(heard, 'chirp_3', '')) as google,
            patch('pabasa_app.views.transcribe_knowlez_audio', return_value=(heard, 'knowlez_stt', '')) as alternate,
        ):
            response = reading_transcribe_api(request)
        self.assertEqual(response.status_code, 200)
        if stream:
            google.assert_not_called()
            alternate.assert_not_called()
        elif knowlez:
            alternate.assert_called_once()
            google.assert_not_called()
        else:
            self.assertEqual(google.call_args.kwargs['language_code'], 'fil-PH')
            self.assertFalse(google.call_args.kwargs['allow_fallback'])
        return json.loads(response.content)

    def assert_verdict(self, target, heard, correct, **fields):
        result = self.transcribe(target, heard, **fields)
        self.assertTrue(result['success'])
        self.assertEqual(result['complete'], correct, (target, heard, result))
        self.assertEqual(result['raw_transcript'], heard)
        self.assertEqual(result['transcript'], heard)
        self.assertEqual(result['processed_transcript'], heard)
        self.assertEqual(result['correct_word_count'], int(correct))
        self.assertEqual(result['current_word_index'], int(correct))
        self.assertEqual(result['progress'], 100 if correct else 0)
        self.assertEqual(result['matched'], len(result['syllables']) if correct else 0)
        self.assertFalse(result['syllable_stitching_applied'])
        self.assertEqual(result['syllable_context'], '')
        return result

    def test_english_translations_of_all_twelve_words_are_rejected(self):
        for target, heard in TRANSLATIONS.items():
            with self.subTest(target=target, heard=heard):
                self.assert_verdict(target, heard, False)

    def test_all_words_accept_case_punctuation_accents_and_syllable_spacing(self):
        for target in TRANSLATIONS:
            for heard in (target.lower(), f'  {target.title()}!  ', ' '.join(target.lower()),
                          '-'.join(target.lower())):
                with self.subTest(target=target, heard=heard):
                    self.assert_verdict(target, heard, True)
        self.assert_verdict('WALO', 'wálo.', True)
        self.assert_verdict('TATLO', 'ta\u0301tlo', True)

    def test_wrong_words_partial_words_digits_and_extra_tokens_are_rejected(self):
        for target, heard in (
            ('WALO', '8'), ('TATLO', '3'), ('WALO', 'wala'), ('TATLO', 'tatay'),
            ('WALO', 'lo'), ('WALO', 'ang walo'), ('WALO', 'walong'),
            ('TATLO', 'tatlo three'), ('WALO', 'walo 한국어'), ('WALO', 'wa🤖lo'),
            ('WALO', ''), ('TATLO', '...'), ('WALO', 'walo 8'),
        ):
            with self.subTest(target=target, heard=heard):
                self.assert_verdict(target, heard, False)

    def test_previous_word_never_satisfies_the_next_word(self):
        words = list(TRANSLATIONS)
        for index, target in enumerate(words):
            with self.subTest(target=target):
                self.assert_verdict(target, words[index - 1].lower(), False)

    def test_progress_and_prior_syllables_cannot_complete_a_bad_attempt(self):
        for heard in ('eight', '', 'lo'):
            self.assert_verdict('WALO', heard, False,
                                current_syllable_index='999', syllable_context='wa')
        self.assert_verdict('TATLO', 'lo', False, syllable_context='tat')
        self.assert_verdict('WALO', 'walo', True, current_syllable_index='999')

    def test_clip_alternate_provider_and_stream_use_the_same_reading_rule(self):
        for fields in ({}, {'knowlez': True}, {'stream': True}):
            for target, correct, wrong in (('WALO', 'walo', 'eight'), ('TATLO', 'tatlo', 'three')):
                self.assert_verdict(target, correct, True, **fields)
                self.assert_verdict(target, wrong, False, **fields)

    def test_legacy_stream_identity_also_selects_the_literal_validator(self):
        self.assert_verdict('WALO', 'eight', False, stream=True,
            prescribed_activity_key='', prescribed_stream_activity='lesson-3-gawain-1')

    def test_generic_number_reading_remains_unchanged(self):
        result = self.transcribe('8', 'eight', prescribed_activity_key='another-activity')
        self.assertTrue(result['complete'])

    def test_other_evaluator_flags_cannot_override_the_literal_verdict(self):
        self.assert_verdict('WALO', 'eight', False,
            l22_c_pronunciation='1', l22_c_syllable='eight', l22_c_sound='hard',
            salitang_magkatugma_exact='1', crla_rhymes='1')

    def test_selected_provider_failure_is_not_success_or_google_fallback(self):
        from .knowlez_stt import KnowlezSpeechError
        request = RequestFactory().post('/api/reading/transcribe/', {
            'audio': SimpleUploadedFile('synthetic.webm', b'test-audio'),
            'target_text': 'WALO', 'language': 'Filipino', 'mode': 'reading',
            'prescribed_activity_key': 'lesson-3-gawain-1',
        })
        request._dont_enforce_csrf_checks = True
        with (
            patch('pabasa_app.views._check_auth', return_value=True),
            patch('pabasa_app.views._enforce_student_access_for_request', return_value=None),
            patch('pabasa_app.views.uses_knowlez_stt', return_value=True),
            patch('pabasa_app.views.transcribe_knowlez_audio', side_effect=KnowlezSpeechError('Unavailable')),
            patch('pabasa_app.views.transcribe_audio_bytes_with_model') as google,
        ):
            response = reading_transcribe_api(request)
        self.assertEqual(response.status_code, 502)
        self.assertFalse(json.loads(response.content)['success'])
        google.assert_not_called()

    def test_production_browser_recording_and_rhyme_functions(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is needed to exercise the production activity functions.')
        root = Path(__file__).resolve().parent
        result = subprocess.run([node, str(root / 'tests_lesson3_reading.js')],
            input=json.dumps({
                'template': str(root / 'templates/pabasa_app/lesson_3_gawain_1_page.html'),
                'pairs': PAIRS,
                'correct': self.transcribe('WALO', 'walo'),
                'incorrect': self.transcribe('WALO', 'eight'),
            }), text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

