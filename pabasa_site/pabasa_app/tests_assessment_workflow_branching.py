from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from pabasa_app.views import _sync_assessment_workflow_state


class AssessmentWorkflowBranchingTests(SimpleTestCase):
    def _run_sync(self, score_payload, initial_end_state=None):
        student = SimpleNamespace(id=1, pk=1, reading_level="")
        state = {"student_end_assessment_state": dict(initial_end_state or {})} if initial_end_state else {}

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

    def test_six_words_stops_with_early_results(self):
        end_state = self._run_sync({
            "assessment_type": "word",
            "correct_words": 6,
            "final_score": 58,
            "total_score": 58,
        })
        self.assertEqual(end_state.get("stage"), "early_completed_words")
        self.assertEqual(end_state.get("next_stage"), "completed")
        self.assertEqual(end_state.get("routing_score"), 6)
        self.assertEqual(end_state.get("classification"), "Low Emerging Reader")

    def test_low_branch_persists_workbook_fields(self):
        end_state = self._run_sync({
            "assessment_type": "word",
            "correct_words": 5,
            "task2_rhymes_score": 4,
        })
        self.assertEqual(end_state.get("branch"), "rhymes")
        self.assertEqual(end_state.get("task1_score"), 5)
        self.assertEqual(end_state.get("task2_rhymes_score"), 4)
        self.assertIsNone(end_state.get("task2_sentences_score"))
        self.assertEqual(end_state.get("part1_total_score"), 9)

    def test_low_branch_boundary_full_refresher(self):
        end_state = self._run_sync({
            "assessment_type": "word",
            "correct_words": 6,
            "task2_rhymes_score": 4,
        })
        self.assertEqual(end_state.get("part1_total_score"), 10)
        self.assertEqual(end_state.get("part1_reading_level"), "Full Refresher")

    def test_low_branch_boundary_moderate_refresher(self):
        end_state = self._run_sync({
            "assessment_type": "word",
            "correct_words": 6,
            "task2_rhymes_score": 5,
        })
        self.assertEqual(end_state.get("part1_total_score"), 11)
        self.assertEqual(end_state.get("part1_reading_level"), "Moderate Refresher")

    def test_word_branch_uses_correct_words_seven_goes_to_sentences_high(self):
        end_state = self._run_sync({
            "assessment_type": "word",
            "correct_words": 7,
            "final_score": 58,
            "total_score": 58,
        })
        self.assertEqual(end_state.get("next_stage"), "sentences_high")
        self.assertEqual(end_state.get("stage"), "transition_to_sentence")

    def test_word_branch_uses_correct_words_ten_goes_to_sentences_high(self):
        end_state = self._run_sync({
            "assessment_type": "word",
            "correct_words": 10,
            "final_score": 58,
            "total_score": 58,
        })
        self.assertEqual(end_state.get("next_stage"), "sentences_high")
        self.assertEqual(end_state.get("stage"), "transition_to_sentence")

    def test_high_branch_persists_workbook_fields(self):
        end_state = self._run_sync({
            "assessment_type": "sentence",
            "correct_sentences": 6,
            "items_completed": 4,
            "correct_words": 8,
        }, {"correct_words": 8, "stage": "sentences_high"})
        self.assertEqual(end_state.get("branch"), "sentences")
        self.assertEqual(end_state.get("task1_score"), 8)
        self.assertIsNone(end_state.get("task2_rhymes_score"))
        self.assertEqual(end_state.get("task2_sentences_score"), 6)
        self.assertEqual(end_state.get("part1_total_score"), 24)
        self.assertEqual(end_state.get("part1_reading_level"), "Light Refresher")

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
        self.assertEqual(end_state.get("stage"), "transition_to_sentence")

    def test_seven_words_plus_three_sentences_is_ten_and_stops(self):
        end_state = self._run_sync({
            "assessment_type": "sentence",
            "correct_sentences": 3,
            "items_completed": 4,
            "final_score": 58,
        }, {"correct_words": 7, "stage": "sentences_high"})
        self.assertEqual(end_state.get("stage"), "early_completed_sentences")
        self.assertEqual(end_state.get("next_stage"), "completed")
        self.assertEqual(end_state.get("routing_score"), 10)
        self.assertEqual(end_state.get("correct_sentences"), 3)
        self.assertEqual(end_state.get("sentence_items_administered"), 4)
        self.assertEqual(end_state.get("classification"), "High Emerging Reader")

    def test_seven_words_plus_four_sentences_is_eleven_and_transitions(self):
        end_state = self._run_sync({
            "assessment_type": "sentence",
            "correct_sentences": 4,
            "items_completed": 4,
            "final_score": 40,
        }, {"correct_words": 7, "stage": "sentences_high"})
        self.assertEqual(end_state.get("stage"), "transition_to_story")
        self.assertEqual(end_state.get("next_stage"), "story_selection")
        self.assertEqual(end_state.get("routing_score"), 11)

    def test_ten_words_plus_zero_sentences_stops_at_ten(self):
        end_state = self._run_sync({
            "assessment_type": "sentence", "correct_sentences": 0, "items_completed": 4,
        }, {"correct_words": 10, "stage": "sentences_high"})
        self.assertEqual(end_state.get("stage"), "early_completed_sentences")
        self.assertEqual(end_state.get("cumulative_correct"), 10)

    def test_ten_words_plus_one_sentence_transitions_at_eleven(self):
        end_state = self._run_sync({
            "assessment_type": "sentence", "correct_sentences": 1, "items_completed": 4,
        }, {"correct_words": 10, "stage": "sentences_high"})
        self.assertEqual(end_state.get("stage"), "transition_to_story")
        self.assertEqual(end_state.get("cumulative_correct"), 11)

    def test_grade_ready_boundary_and_maximum_high_branch(self):
        ready = self._run_sync({
            "assessment_type": "sentence",
            "correct_sentences": 10,
            "items_completed": 4,
        }, {"correct_words": 7, "stage": "sentences_high"})
        self.assertEqual(ready.get("part1_total_score"), 27)
        self.assertEqual(ready.get("part1_reading_level"), "Grade Ready")

        maximum = self._run_sync({
            "assessment_type": "sentence",
            "correct_sentences": 10,
            "items_completed": 4,
        }, {"correct_words": 10, "stage": "sentences_high"})
        self.assertEqual(maximum.get("part1_total_score"), 30)
        self.assertEqual(maximum.get("part1_reading_level"), "Grade Ready")

    def test_story_branch_uses_comprehension_and_reading_percentage(self):
        end_state = self._run_sync({
            "assessment_type": "paragraph",
            "story_read_percent": 82,
            "correct_answers": 5,
            "final_score": 82,
            "total_score": 82,
        })
        self.assertEqual(end_state.get("next_stage"), "completed")
        self.assertEqual(end_state.get("stage"), "completed")

    def test_pre_midline_and_post_use_the_same_word_threshold(self):
        for phase in ("pretest", "midtest", "posttest"):
            with self.subTest(phase=phase):
                assessment = SimpleNamespace(assessment_kind="crla", system_assessment_phase=phase)
                student = SimpleNamespace(id=1, pk=1, reading_level="")
                state = {}
                with patch("pabasa_app.views._get_user_state", return_value=state), \
                     patch("pabasa_app.views._set_user_state", side_effect=lambda _student, value: state.update(value)), \
                     patch("pabasa_app.views._aral_eligible_classification", return_value=False), \
                     patch("pabasa_app.views._active_school_calendar", return_value=None), \
                     patch("pabasa_app.views.timezone.now", return_value=SimpleNamespace(isoformat=lambda: "2026-08-24T00:00:00")):
                    _sync_assessment_workflow_state(student, {"assessment_type": "word", "correct_words": 7}, assessment=assessment)
                self.assertEqual(state["student_end_assessment_state"]["stage"], "transition_to_sentence")
                with patch("pabasa_app.views._get_user_state", return_value=state), \
                     patch("pabasa_app.views._set_user_state", side_effect=lambda _student, value: state.update(value)), \
                     patch("pabasa_app.views._aral_eligible_classification", return_value=False), \
                     patch("pabasa_app.views._active_school_calendar", return_value=None), \
                     patch("pabasa_app.views.timezone.now", return_value=SimpleNamespace(isoformat=lambda: "2026-08-24T00:00:00")):
                    _sync_assessment_workflow_state(student, {
                        "assessment_type": "sentence", "correct_items": 4, "items_completed": 4,
                    }, assessment=assessment)
                self.assertEqual(state["student_end_assessment_state"]["cumulative_correct"], 11)
                self.assertEqual(state["student_end_assessment_state"]["stage"], "transition_to_story")
