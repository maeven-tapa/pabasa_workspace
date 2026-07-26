from django.test import SimpleTestCase

from .reader_classification import (
    AT_GRADE_LEVEL,
    DEVELOPING,
    HIGH_EMERGING,
    LOW_EMERGING,
    TRANSITIONING,
    classify_reader,
)


class ReaderClassificationTests(SimpleTestCase):
    def test_words_only_is_low_emerging(self):
        self.assertEqual(
            classify_reader([{"assessment_type": "word", "status": "completed"}]),
            LOW_EMERGING,
        )

    def test_words_and_sentences_is_high_emerging(self):
        attempts = [
            {"assessment_type": "word", "status": "completed"},
            {"assessment_type": "sentence", "status": "completed"},
        ]
        self.assertEqual(classify_reader(attempts), HIGH_EMERGING)

    def test_paragraph_totals_are_cumulative_across_assessments(self):
        attempts = [
            {"assessment_type": "paragraph", "correct_items": 2, "items_completed": 5},
            {"assessment_type": "paragraph", "correct_items": 3, "items_completed": 5},
        ]
        self.assertEqual(classify_reader(attempts), TRANSITIONING)

    def test_paragraph_thresholds(self):
        self.assertEqual(
            classify_reader([{"assessment_type": "paragraph", "correct_items": 49, "items_completed": 100}]),
            DEVELOPING,
        )
        self.assertEqual(
            classify_reader([{"assessment_type": "paragraph", "correct_items": 75, "items_completed": 100}]),
            TRANSITIONING,
        )
        self.assertEqual(
            classify_reader([{"assessment_type": "paragraph", "correct_items": 76, "items_completed": 100}]),
            AT_GRADE_LEVEL,
        )

    def test_incomplete_attempts_do_not_change_level(self):
        attempts = [
            {"assessment_type": "word", "status": "completed"},
            {"assessment_type": "sentence", "status": "started"},
        ]
        self.assertEqual(classify_reader(attempts), LOW_EMERGING)

    def test_legacy_paragraph_without_correct_item_count_is_ignored(self):
        attempts = [
            {"assessment_type": "word", "status": "completed"},
            {"assessment_type": "paragraph", "items_completed": 4, "correct_items": None},
        ]
        self.assertEqual(classify_reader(attempts), LOW_EMERGING)
