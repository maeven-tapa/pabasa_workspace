"""L15 G2 upload/recognition regressions; no live speech requests or database."""
import json
from unittest.mock import patch

from django.contrib.sessions.backends.db import SessionStore
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings
from google.cloud.speech_v2.types import cloud_speech

from . import reading_stt, views
from .prescribed_activity_catalog import prescribed_activity

KEY = 'lesson-15-gawain-2-angkop-na-pantig'


@override_settings(DEBUG=False, GOOGLE_CLOUD_PROJECT_ID='test-project', GOOGLE_STT_MODEL='chirp_3',
                   GOOGLE_STT_LOCATION='us', GOOGLE_STT_API_KEY='test-key')
class Lesson15Gawain2SpeechTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.session = SessionStore(session_key='a' * 32)
        self.session._session_cache = {'user_id': 1, 'user_role': 'admin'}
        for target, value in [('pabasa_app.views._check_auth', True),
                             ('pabasa_app.views._enforce_student_access_for_request', None),
                             ('pabasa_app.views.uses_knowlez_stt', False),
                             ('pabasa_app.reading_stt.google_stt_credentials', object())]:
            mock = patch(target, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        client = patch('google.cloud.speech_v2.SpeechClient')
        self.client = client.start()
        self.addCleanup(client.stop)

    def request(self, **fields):
        request = self.factory.post('/api/reading/transcribe/', {
            'target_text': 'oyayi', 'language': 'fil-PH', 'mode': 'word',
            'prescribed_activity_key': KEY,
            'audio': SimpleUploadedFile('clip.webm', b'disposable-audio', 'audio/webm'), **fields},
            HTTP_X_PABASA_STT_MODEL='chirp_3')
        request.session = self.session
        request._dont_enforce_csrf_checks = True
        return request

    def recognize(self, transcript, response_language='fil-PH', **fields):
        self.client.return_value.recognize.return_value = cloud_speech.RecognizeResponse(results=[{
            'language_code': response_language, 'alternatives': [{'transcript': transcript}]}])
        response = views.reading_transcribe_api(self.request(**fields))
        self.assertEqual(response.status_code, 200, response.content)
        return json.loads(response.content)

    def test_actual_inventory_and_one_word_filipino_context(self):
        words = [item['word'] for item in prescribed_activity(KEY)['part1_items']]
        self.assertEqual(words, ['yo-yo', 'masaya', 'yungib', 'oyayi', 'yelo'])
        for word in words:
            result = self.recognize(word, target_text=word, language='English')
            self.assertTrue(result['complete'])
            config = self.client.return_value.recognize.call_args.kwargs['request'].config
            self.assertEqual(config.model, 'chirp_3')
            self.assertEqual(list(config.language_codes), ['fil-PH'])
            hints = config.adaptation.phrase_sets[0].inline_phrase_set.phrases
            self.assertEqual([hint.value for hint in hints], [word])
            self.assertEqual(hints[0].boost, 0)
            self.assertEqual(result['stt_requested_language_codes'], ['fil-PH'])
            self.assertEqual(result['stt_response_language_codes'], ['fil-PH'])
            self.assertEqual(result['stt_recognition_context'], [word])
            self.assertFalse(result['stt_language_autodetection'])

    def test_hangul_mixed_script_and_stale_tass_never_match(self):
        self.assertTrue(reading_stt.analyze_reading('oyayi', 0, 'oyayi 한국', 'fil-PH')['complete'])
        for transcript in ['오 야 이', 'oyayi 한국', '한국 oyayi', 'oya\u1100yi', '\u3131', '\uffa1']:
            result = self.recognize(transcript, syllable_context='o ya')
            self.assertFalse(result['complete'])
            self.assertFalse(result['matched'])
            self.assertEqual(result['current_syllable_index'], 0)
            self.assertEqual(result['syllable_context'], '')
            self.assertEqual(result['raw_transcript'], transcript)
            self.assertEqual(result['recognition_rejected_reason'], 'non_filipino_language')

    def test_korean_metadata_blocks_latin_output_missing_metadata_is_not_invented(self):
        rejected = self.recognize('oyayi', response_language='ko-KR')
        self.assertFalse(rejected['complete'])
        self.assertEqual(rejected['stt_response_language_codes'], ['ko-KR'])
        accepted = self.recognize('oyayi', response_language='')
        self.assertTrue(accepted['complete'])
        self.assertEqual(accepted['stt_response_language_codes'], [])

    def test_latin_matching_segmentation_and_yelo_alias_contract_preserved(self):
        for word, heard in [('yo-yo', 'yo yo'), ('masaya', 'ma sa ya'),
                            ('yungib', 'yun gib'), ('oyayi', 'o ya yi'), ('yelo', 'ye lo'),
                            ('yelo', 'hielo')]:
            baseline = reading_stt.analyze_reading(word, 0, heard, 'fil-PH')
            result = self.recognize(heard, target_text=word)
            self.assertEqual(result['complete'], baseline['complete'])
            self.assertEqual(result['raw_transcript'], heard)
            self.assertNotIn('recognition_rejected_reason', result)
        # The existing browser's hielo allowance is independent of the server
        # match verdict; do not replace that activity-specific scoring rule.

    def test_incomplete_syllables_reject_and_a_valid_retry_passes(self):
        for fragment in ['o', 'ya', 'y', 'o ya y']:
            self.assertFalse(self.recognize(fragment)['complete'])
        self.assertTrue(self.recognize('oyayi')['complete'])

    def test_only_reading_inventory_is_valid_context_not_choices_or_l14_words(self):
        for word in ['ya', 'ye', 'yi', 'yo', 'yu', 'mata', 'oyayi unrelated']:
            response = views.reading_transcribe_api(self.request(target_text=word))
            self.assertEqual(response.status_code, 400)
        self.client.return_value.recognize.assert_not_called()

    @override_settings(DEBUG=True)
    @patch('pabasa_app.views.google_stt_credentials_available', return_value=False)
    def test_no_silent_local_provider_switch(self, credentials):
        request = self.request()
        request.META.pop('HTTP_X_PABASA_STT_MODEL')
        request.META['HTTP_HOST'] = 'localhost'
        self.client.return_value.recognize.return_value = cloud_speech.RecognizeResponse()
        result = json.loads(views.reading_transcribe_api(request).content)
        self.assertEqual(result['stt_model'], 'chirp_3')
        credentials.assert_not_called()

    def test_explicit_provider_selection_is_preserved(self):
        request = self.request()
        request.META['HTTP_X_PABASA_STT_MODEL'] = 'chirp_2'
        self.client.return_value.recognize.return_value = cloud_speech.RecognizeResponse()
        self.assertEqual(views.reading_transcribe_api(request).status_code, 200)
        config = self.client.return_value.recognize.call_args.kwargs['request'].config
        self.assertEqual(config.model, 'chirp_2')
        self.assertFalse(cloud_speech.RecognitionConfig.pb(config).HasField('adaptation'))
        with patch.object(views, 'uses_knowlez_stt', return_value=True), \
                patch.object(views, 'transcribe_knowlez_audio', return_value=('oyayi', 'knowlez_stt', '')) as provider:
            result = json.loads(views.reading_transcribe_api(self.request()).content)
            self.assertTrue(result['complete'])
            self.assertEqual(result['stt_provider'], 'knowlez')
            self.assertEqual(provider.call_args.args[1], 'fil-PH')

    def test_unrelated_activity_does_not_receive_target_specific_adaptation(self):
        result = self.recognize('oyayi', prescribed_activity_key='lesson-13-gawain-2')
        self.assertTrue(result['complete'])
        config = self.client.return_value.recognize.call_args.kwargs['request'].config
        self.assertFalse(cloud_speech.RecognitionConfig.pb(config).HasField('adaptation'))
        self.assertNotIn('stt_response_language_codes', result)
