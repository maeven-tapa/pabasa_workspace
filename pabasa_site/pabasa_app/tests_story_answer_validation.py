from django.test import SimpleTestCase

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
    def test_classifies_each_reading_and_comprehension_band(self):
        cases = (
            (24, 0, 'High Emerging Reader'),
            (50, 2, 'Developing Reader'),
            (75, 4, 'Transitioning Reader'),
            (100, 6, 'Reading at Grade Level'),
        )
        for reading_percent, correct_answers, expected in cases:
            with self.subTest(reading_percent=reading_percent, correct_answers=correct_answers):
                self.assertEqual(
                    _crla_grade2_part2_profile(reading_percent, correct_answers),
                    expected,
                )

    def test_uses_lower_band_when_reading_and_comprehension_differ(self):
        self.assertEqual(_crla_grade2_part2_profile(90, 0), 'High Emerging Reader')
        self.assertEqual(_crla_grade2_part2_profile(20, 6), 'High Emerging Reader')
        self.assertEqual(_crla_grade2_part2_profile(80, 3), 'Transitioning Reader')
