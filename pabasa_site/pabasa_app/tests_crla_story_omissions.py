"""Confirmed story skips must resync without giving skipped words credit."""
from django.test import SimpleTestCase

from .reading_stt import ReadingMatcher, align_story_transcript


class CrlaStoryOmissionTests(SimpleTestCase):
    def align(self, text, spoken, start=0, language='fil-PH', strict=True):
        return align_story_transcript(text, spoken, language, start_word_index=start,
                                      crla_story_reading=strict)

    def test_single_and_consecutive_omissions_keep_spoken_tail_aligned(self):
        text = 'Si Ana ay masaya sa bahay.'
        for spoken, skipped in [('Si Ana masaya sa bahay', [2]),
                                ('Si masaya sa bahay', [1, 2]),
                                ('masaya sa bahay', [0, 1, 2]),
                                ('sa bahay', [0, 1, 2, 3])]:
            with self.subTest(spoken=spoken):
                result = self.align(text, spoken)
                self.assertEqual(result['miscues'], len(skipped))
                self.assertEqual(result['correct_words'], 6 - len(skipped))
                self.assertEqual([r['expected_index'] for r in result['word_results']], list(range(6)))
                self.assertEqual([r['expected_index'] for r in result['word_results']
                                  if r['type'] == 'omission'], skipped)
                self.assertEqual(result['word_results'][-1]['type'], 'correct')

    def test_skip_from_nonzero_cursor_leaves_later_words_pending(self):
        result = self.align('Si Ana ay masaya sa bahay ngayon.', 'sa bahay', start=2)
        self.assertEqual([(r['expected_index'], r['type']) for r in result['word_results']],
                         [(2, 'omission'), (3, 'omission'), (4, 'correct'), (5, 'correct')])
        self.assertEqual(result['recognized_text'], 'sa bahay')

    def test_large_english_skip_uses_same_word_evidence(self):
        result = self.align('The little brown dog ran into the garden today.',
                            'the garden', language='en-US')
        self.assertEqual(result['miscues'], 6)
        self.assertEqual(result['correct_words'], 2)
        self.assertEqual(result['word_results'][-1]['expected_index'], 7)

    def test_silence_and_partial_reading_do_not_omit_unread_tail(self):
        for spoken, count in [('', 0), ('Si Ana', 2)]:
            with self.subTest(spoken=spoken):
                result = self.align('Si Ana ay masaya sa bahay.', spoken)
                self.assertEqual(result['miscues'], 0)
                self.assertEqual(len(result['word_results']), count)

    def test_single_word_or_ambiguous_pair_does_not_jump_to_distant_text(self):
        cases = [('Si Ana ay masaya sa bahay', 'bahay'),
                 ('Si Ana ay masaya sa bahay sa bahay', 'sa bahay')]
        for text, spoken in cases:
            with self.subTest(spoken=spoken):
                result = self.align(text, spoken)
                self.assertLessEqual(result['word_results'][-1]['expected_index'], 1)

    def test_wrong_spoken_prefix_does_not_trigger_large_omission_resync(self):
        result = self.align('Si Ana ay masaya sa bahay ngayon', 'mali sa bahay')
        self.assertLess(result['word_results'][-1]['expected_index'], 5)

    def test_regular_story_alignment_keeps_existing_behavior(self):
        result = self.align('Si Ana ay masaya sa bahay', 'sa bahay', strict=False)
        self.assertEqual([r['type'] for r in result['word_results']],
                         ['substitution', 'substitution'])

    def test_resync_preserves_explicit_crla_aliases(self):
        result = self.align('Si Ana ay kasama ni Aling Kuneho', 'aleng conejo')
        self.assertEqual(result['miscues'], 5)
        self.assertEqual(result['correct_words'], 2)

    def test_partial_syllable_cursor_still_resolves_whole_skipped_word(self):
        matcher = ReadingMatcher('Si Ana ay masaya sa bahay', 2, 'fil-PH', crla_story_reading=True)
        result = self.align(matcher.target_text, 'masaya sa bahay', start=matcher.current_word_index)
        self.assertEqual([r['expected_index'] for r in result['word_results'] if r['type'] == 'omission'], [1, 2])
