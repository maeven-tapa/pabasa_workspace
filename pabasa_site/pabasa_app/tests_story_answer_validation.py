from django.test import SimpleTestCase

from .scoring import crla_part2_profile
from .views import _crla_grade2_part2_profile, story_answer_matches


class StoryAnswerMeaningMatchTests(SimpleTestCase):
    def test_accepts_natural_kuneho_variations(self):
        expected = 'Si Kuneho.'
        for response in ('Kuneho', 'Si Kuneho', 'Kuneho po', 'Si Kuneho po', 'yung kuneho'):
            with self.subTest(response=response):
                self.assertTrue(story_answer_matches(expected, response))

    def test_rejects_a_different_character(self):
        self.assertFalse(story_answer_matches('Si Kuneho.', 'Si Pagong po'))

    def test_requires_all_essential_parts_of_a_short_answer(self):
        self.assertTrue(story_answer_matches('Limang bola.', 'May limang bola po.'))
        self.assertFalse(story_answer_matches('Limang bola.', 'May bola po.'))

    def test_ignores_case_punctuation_and_diacritics(self):
        self.assertTrue(story_answer_matches('PULÁ.', 'Ang sagot ko po ay pula!'))

    def test_empty_answer_is_never_correct(self):
        self.assertFalse(story_answer_matches('Si Kuneho.', ''))


class StoryReadingClassificationTests(SimpleTestCase):
    def test_part2_profile_does_not_double_subtract_miscues(self):
        cases = (
            (80, 20, 80.0),
            (50, 50, 50.0),
            (25, 75, 25.0),
            (100, 0, 100.0),
        )
        for words_read, miscues, expected_percent in cases:
            with self.subTest(words_read=words_read, miscues=miscues):
                profile = crla_part2_profile(100, words_read, miscues, 60, 0)
                self.assertEqual(profile["words_read"], words_read)
                self.assertEqual(profile["miscues"], miscues)
                self.assertEqual(profile["correct_word_percent"], expected_percent)
                self.assertEqual(profile["passage_accuracy_percent"], expected_percent)

    def test_part2_profile_wpm_uses_correct_word_count(self):
        profile = crla_part2_profile(100, 80, 20, 60, 0)
        self.assertEqual(profile["wpm"], 80.0)

    def test_part2_profile_classification_uses_corrected_percentage(self):
        cases = (
            (80, 20, 6, "Reading At Grade Level"),
            (50, 50, 3, "Developing Reader"),
            (25, 75, 1, "High Emerging Reader"),
        )
        for words_read, miscues, answers, expected in cases:
            with self.subTest(words_read=words_read, miscues=miscues, answers=answers):
                profile = crla_part2_profile(100, words_read, miscues, 60, answers)
                self.assertEqual(profile["classification"], expected)

    def test_classifies_each_reading_and_comprehension_band(self):
        cases = (
            (24, 0, 'Low Emerging Reader'),
            (50, 2, 'High Emerging Reader'),
            (75, 4, 'Developing Reader'),
            (76, 5, 'Transitioning Reader'),
            (100, 6, 'Reading At Grade Level'),
        )
        for reading_percent, correct_answers, expected in cases:
            with self.subTest(reading_percent=reading_percent, correct_answers=correct_answers):
                self.assertEqual(
                    _crla_grade2_part2_profile(reading_percent, correct_answers),
                    expected,
                )

    def test_uses_lower_band_when_reading_and_comprehension_differ(self):
        self.assertEqual(_crla_grade2_part2_profile(90, 0), 'NOT AVAILABLE')
        self.assertEqual(_crla_grade2_part2_profile(20, 6), 'NOT AVAILABLE')
        self.assertEqual(_crla_grade2_part2_profile(80, 3), 'NOT AVAILABLE')
