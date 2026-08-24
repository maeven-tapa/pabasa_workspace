from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from pabasa_app.views import _sync_assessment_workflow_state


class AssessmentWorkflowBranchingTests(SimpleTestCase):
    def _run_sync(self, score_payload):
        student = SimpleNamespace(id=1, pk=1, reading_level="")
        state = {}

        def fake_get_user_state(_student):
            return state

        def fake_set_user_state(_student, next_state):
            next_state = dict(next_state or {})
            state.clear()
            state.update(next_state)

        with patch("pabasa_app.views._get_user_state", side_effect=fake_get_user_state), \
             patch("pabasa_app.views._set_user_state", side_effect=fake_set_user_state), \
             patch("pabasa_app.views._aral_eligible_classification", return_value=False), \
             patch("pabasa_app.views.timezone.now", return_value=SimpleNamespace(isoformat=lambda: "2026-08-24T00:00:00")):
            _sync_assessment_workflow_state(student, score_payload=score_payload)

        return state.get("student_end_assessment_state", {})

    def test_word_branch_uses_correct_words_six_goes_to_sentences_low(self):
        end_state = self._run_sync({
            "assessment_type": "word",
            "correct_words": 6,
            "final_score": 58,
            "total_score": 58,
        })
        self.assertEqual(end_state.get("next_stage"), "sentences_low")

    def test_word_branch_uses_correct_words_seven_goes_to_sentences_high(self):
        end_state = self._run_sync({
            "assessment_type": "word",
            "correct_words": 7,
            "final_score": 58,
            "total_score": 58,
        })
        self.assertEqual(end_state.get("next_stage"), "sentences_high")
        self.assertEqual(end_state.get("stage"), "sentences_high")

    def test_word_branch_uses_correct_words_ten_goes_to_sentences_high(self):
        end_state = self._run_sync({
            "assessment_type": "word",
            "correct_words": 10,
            "final_score": 58,
            "total_score": 58,
        })
        self.assertEqual(end_state.get("next_stage"), "sentences_high")
        self.assertEqual(end_state.get("stage"), "sentences_high")

    def test_weighted_score_does_not_override_word_branch(self):
        end_state = self._run_sync({
            "assessment_type": "word",
            "correct_words": 7,
            "word_count": 7,
            "final_score": 58,
            "total_score": 58,
            "overall_raw_score": 58,
        })
        self.assertEqual(end_state.get("next_stage"), "sentences_high")
        self.assertEqual(end_state.get("correct_words"), 7)
        self.assertEqual(end_state.get("stage"), "sentences_high")

    def test_sentence_branch_advances_to_story(self):
        end_state = self._run_sync({
            "assessment_type": "sentence",
            "final_score": 12,
            "total_score": 12,
        })
        self.assertEqual(end_state.get("next_stage"), "story")

    def test_story_branch_uses_comprehension_and_reading_percentage(self):
        end_state = self._run_sync({
            "assessment_type": "paragraph",
            "story_read_percent": 82,
            "correct_answers": 5,
            "final_score": 82,
            "total_score": 82,
        })
        self.assertEqual(end_state.get("next_stage"), "completed_grade_level")
