import io
import wave
import math
import struct

from django.test import SimpleTestCase

from .audio_fluency import AudioAnalysisError, extract_audio_features


def tone_wav(seconds=0.2, silence=False):
    rate = 16000
    samples = b'\x00\x00' * int(rate * seconds) if silence else b'\xff\x1f' * int(rate * seconds)
    out = io.BytesIO()
    with wave.open(out, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate); wav.writeframes(samples)
    return out.getvalue()

def segmented_wav(parts):
    rate = 16000; raw = bytearray()
    for seconds, active in parts:
        count = int(rate * seconds)
        raw.extend((b'\xff\x1f' if active else b'\x00\x00') * count)
    out = io.BytesIO()
    with wave.open(out, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate); wav.writeframes(raw)
    return out.getvalue()


class AudioFeatureTests(SimpleTestCase):
    def test_empty_and_corrupt_audio_are_non_fatal_errors(self):
        with self.assertRaisesRegex(AudioAnalysisError, 'empty_audio'):
            extract_audio_features(b'')
        with self.assertRaisesRegex(AudioAnalysisError, 'audio_decode_failed'):
            extract_audio_features(b'not-audio')

    def test_synthetic_audio_reports_bounded_measurements(self):
        result = extract_audio_features(tone_wav())
        self.assertEqual(result['sample_rate'], 16000)
        self.assertEqual(result['channels'], 1)
        self.assertGreater(result['duration_seconds'], 0)
        self.assertIn(result['quality'], {'usable', 'low_signal'})

    def test_silence_is_not_classified(self):
        result = extract_audio_features(tone_wav(silence=True))
        self.assertEqual(result['quality'], 'low_signal')
        self.assertNotIn('classification', result)

    def test_internal_pause_and_boundaries_are_measured(self):
        result = extract_audio_features(segmented_wav([(0.2, True), (0.2, False), (0.2, True)]), item_index=8)
        self.assertEqual(result['content_type'], 'phrase')
        self.assertEqual(len(result['speech_segments']), 2)
        self.assertAlmostEqual(result['internal_silence_segments'][0]['duration_seconds'], 0.2, delta=0.03)
        self.assertEqual(len(result['candidate_hesitation_pauses']), 1)
        self.assertIsNone(result['possible_restart_count'])

    def test_content_boundaries(self):
        self.assertEqual(extract_audio_features(tone_wav(), item_index=0)['content_type'], 'word')
        self.assertEqual(extract_audio_features(tone_wav(), item_index=17)['content_type'], 'sentence')
