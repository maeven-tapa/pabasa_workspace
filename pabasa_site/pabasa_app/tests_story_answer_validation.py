from pathlib import Path

from django.test import SimpleTestCase

from .reading_stt import align_story_transcript
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
    def test_part2_profile_reading_bands_include_25_percent(self):
        cases = (
            (0, 0),
            (24, 0),
            (24.99, 0),
            (25, 0),
            (25.01, 1),
            (26, 1),
            (50, 1),
            (50.01, 2),
            (51, 2),
            (75, 2),
            (75.01, 3),
            (76, 3),
            (100, 3),
        )
        for percentage, expected_band in cases:
            with self.subTest(percentage=percentage):
                denominator = 10000 if percentage % 1 else 100
                words_read = round(denominator * percentage / 100)
                profile = crla_part2_profile(denominator, words_read, 0, 60, 0)
                self.assertEqual(profile["reading_band"], expected_band)

    def test_part2_profile_comprehension_bands_use_official_5_to_6_highest_band(self):
        expected_bands = {
            0: 0,
            1: 1,
            2: 1,
            3: 2,
            4: 2,
            5: 3,
            6: 3,
        }
        for answers, expected_band in expected_bands.items():
            with self.subTest(answers=answers):
                profile = crla_part2_profile(100, 80, 20, 60, answers)
                self.assertEqual(profile["comprehension_band"], expected_band)

    def test_part2_profile_uses_5_and_6_answers_for_grade_level(self):
        for answers in (5, 6):
            with self.subTest(answers=answers):
                profile = crla_part2_profile(100, 80, 20, 60, answers)
                self.assertEqual(profile["classification"], "Reading At Grade Level")

    def test_part2_profile_uses_comprehension_for_cross_band_final_classification(self):
        cross_band_cases = (
            (80, 0, "High Emerging Reader"),
            (80, 2, "Developing Reader"),
            (80, 4, "Transitioning Reader"),
            (40, 5, "Reading At Grade Level"),
            (20, 3, "Transitioning Reader"),
        )
        for words_read, answers, expected in cross_band_cases:
            with self.subTest(words_read=words_read, answers=answers):
                profile = crla_part2_profile(100, words_read, 100 - words_read, 60, answers)
                self.assertEqual(profile["classification"], expected)

    def test_part2_profile_keeps_same_band_cases(self):
        same_band_cases = (
            (20, 0, "High Emerging Reader"),
            (40, 2, "Developing Reader"),
            (60, 4, "Transitioning Reader"),
            (80, 6, "Reading At Grade Level"),
        )
        for words_read, answers, expected in same_band_cases:
            with self.subTest(words_read=words_read, answers=answers):
                profile = crla_part2_profile(100, words_read, 100 - words_read, 60, answers)
                self.assertEqual(profile["classification"], expected)

    def test_alignment_counts_substitution_omission_and_insertion(self):
        cases = (
            ("THE CAT SAT", "THE DOG SAT", 2, 1),
            ("THE CAT SAT", "THE CAT", 2, 1),
            ("THE CAT SAT", "THE BIG CAT SAT", 3, 1),
            ("aa bb cc dd ee ff", "aa aa cc aa dd ee", 4, 3),
        )
        for expected, spoken, correct_words, miscues in cases:
            with self.subTest(expected=expected, spoken=spoken):
                result = align_story_transcript(expected, spoken)
                self.assertEqual(result["correct_words"], correct_words)
                self.assertEqual(result["miscues"], miscues)

    def test_story_browser_uses_deduplicated_alignment_miscues(self):
        source = (Path(__file__).parent / "static" / "pabasa_app" / "js" / "assessment_reader.js").read_text(encoding="utf-8")
        self.assertIn("let storyMiscueResponseKeys = new Set();", source)
        self.assertIn("if (storyMiscueResponseKeys.has(responseKey)) return;", source)
        self.assertIn("recordStoryAlignmentMiscues(data, context);", source)
        self.assertIn("storyMiscueCount += alignmentMiscues;", source)
        self.assertNotIn("miscues: Math.max(0, totalStoryWords - correctWordsRead())", source)
        completion = source.split("async function showStoryCompletionScreen", 1)[1].split("function hideStoryCompletionScreen", 1)[0]
        self.assertIn("miscues: storyMiscueCount", completion)

    def test_story_browser_passage_accuracy_fallback_does_not_subtract_miscues(self):
        source = (Path(__file__).parent / "static" / "pabasa_app" / "js" / "assessment_reader.js").read_text(encoding="utf-8")
        self.assertIn(
            "Math.round((Math.max(0, wordsRead) / storyTotalWords) * 10000) / 100",
            source,
        )
        self.assertNotIn("wordsRead - (miscues || 0)", source)

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
            (50, 50, 3, "Transitioning Reader"),
            (25, 75, 1, "Developing Reader"),
        )
        for words_read, miscues, answers, expected in cases:
            with self.subTest(words_read=words_read, miscues=miscues, answers=answers):
                profile = crla_part2_profile(100, words_read, miscues, 60, answers)
                self.assertEqual(profile["classification"], expected)

    def test_classifies_each_reading_and_comprehension_band(self):
        cases = (
            (24, 0, 'High Emerging Reader'),
            (50, 2, 'Developing Reader'),
            (75, 4, 'Transitioning Reader'),
            (76, 5, 'Reading At Grade Level'),
            (100, 6, 'Reading At Grade Level'),
        )
        for reading_percent, correct_answers, expected in cases:
            with self.subTest(reading_percent=reading_percent, correct_answers=correct_answers):
                self.assertEqual(
                    _crla_grade2_part2_profile(reading_percent, correct_answers),
                    expected,
                )

    def test_comprehension_priority_when_reading_and_comprehension_differ(self):
        self.assertEqual(_crla_grade2_part2_profile(90, 0), 'High Emerging Reader')
        self.assertEqual(_crla_grade2_part2_profile(20, 6), 'Reading At Grade Level')
        self.assertEqual(_crla_grade2_part2_profile(80, 3), 'Transitioning Reader')
