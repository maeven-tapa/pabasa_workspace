import json
from unittest.mock import ANY, patch

from django.test import RequestFactory, SimpleTestCase

from .reading_stt import synthesize_read_aloud_audio
from .views import reading_read_aloud_api


class CrlaTeacherVoiceTests(SimpleTestCase):
    @patch('pabasa_app.reading_stt._post_google_tts', return_value='audio')
    def test_crla_uses_female_neural_voice_and_one_pacing_control(self, post_tts):
        for language, voice in (
            ('fil-PH', 'fil-ph-Neural2-A'), ('tl-PH', 'fil-ph-Neural2-A'),
            ('en-PH', 'en-US-Neural2-F'),
        ):
            with self.subTest(language=language):
                synthesize_read_aloud_audio(
                    "Si Bibo ay bata. Ano ang ginagawa niya?", 'test-key',
                    language_code=language, tts_profile='crla', voice_gender='MALE',
                )
                payload = post_tts.call_args.args[1]
                self.assertEqual(payload['voice']['name'], voice)
                self.assertEqual(payload['voice']['ssmlGender'], 'FEMALE')
                self.assertEqual(payload['input'], {'text': 'Si Bibo ay bata. Ano ang ginagawa niya?'})
                self.assertEqual(payload['audioConfig'], {
                    'audioEncoding': 'MP3', 'speakingRate': 0.92,
                    'pitch': 0, 'volumeGainDb': 0,
                })

    @patch('pabasa_app.reading_stt._post_google_tts', return_value='audio')
    def test_other_profiles_keep_existing_voice_and_rates(self, post_tts):
        synthesize_read_aloud_audio('Magandang araw.', 'test-key', language_code='fil-PH')
        payload = post_tts.call_args.args[1]
        self.assertEqual(payload['voice']['name'], 'fil-PH-Wavenet-A')
        self.assertIn('rate="92%"', payload['input']['ssml'])
        self.assertEqual(payload['audioConfig']['speakingRate'], 0.95)

    def test_crla_empty_text_is_rejected_before_provider_call(self):
        with patch('pabasa_app.reading_stt._post_google_tts') as provider:
            with self.assertRaises(RuntimeError):
                synthesize_read_aloud_audio('   ', 'test-key', tts_profile='crla')
            provider.assert_not_called()

    @patch('pabasa_app.views._check_auth', return_value=True)
    @patch('pabasa_app.views._enforce_student_access_for_request', return_value=None)
    @patch('pabasa_app.views.synthesize_read_aloud_audio', return_value='audio')
    def test_reading_and_question_requests_report_actual_crla_voice(self, synthesize, _access, _auth):
        for text in ('Si Bibo ay bata.', 'Ano ang ginagawa ni Bibo?'):
            for language, locale, voice in (
                ('Filipino', 'fil-PH', 'fil-ph-Neural2-A'),
                ('English', 'en-US', 'en-US-Neural2-F'),
            ):
                with self.subTest(text=text, language=language):
                    request = RequestFactory().post('/api/reading/read-aloud/', {
                        'target_text': text, 'language': language,
                        'mode': 'paragraph', 'tts_profile': 'crla',
                    })
                    request._dont_enforce_csrf_checks = True
                    response = reading_read_aloud_api(request)
                    self.assertEqual(response.status_code, 200)
                    data = json.loads(response.content)
                    self.assertEqual(data['tts_language'], locale)
                    self.assertEqual(data['voice_name'], voice)
                    synthesize.assert_called_with(text, ANY, ANY, credentials_file=ANY,
                                                 tts_profile='crla', voice_gender='FEMALE')

    @patch('pabasa_app.views._check_auth', return_value=True)
    @patch('pabasa_app.views._enforce_student_access_for_request', return_value=None)
    @patch('pabasa_app.views.synthesize_read_aloud_audio', return_value='audio')
    def test_non_crla_assessment_preserves_previous_pace(self, synthesize, _access, _auth):
        request = RequestFactory().post('/api/reading/read-aloud/', {
            'target_text': 'Magandang araw.', 'language': 'Filipino', 'tts_profile': 'assessment',
        })
        request._dont_enforce_csrf_checks = True
        response = reading_read_aloud_api(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['voice_name'], 'fil-PH-Wavenet-A')
        synthesize.assert_called_once_with('Magandang araw.', ANY, 'fil-PH', credentials_file=ANY,
                                          speaking_rate=1.0, prosody_rate='100%')
