from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from pabasa_app.views import _aral_eligible_classification, _crla_grade2_part2_profile, _sync_assessment_workflow_state
from pabasa_app.scoring import build_assessment_score_payload


class AssessmentWorkflowBranchingTests(SimpleTestCase):
    def test_story_correct_words_cannot_become_task1(self):
        payload = build_assessment_score_payload({
            "assessment_type": "paragraph",
            "crla_score_data": {
                "story_total_words": 221,
                "words_read": 49,
                "miscues": 0,
                "duration_seconds": 120,
                "comprehension_total": 6,
                "comprehension_correct": 0,
            },
            "correct_words": 49,
        })
        self.assertIsNone(payload["crla_score_data"]["task1_score"])
        self.assertEqual(payload["crla_classification"], "Low Emerging Reader")

    def test_crla_task1_always_reports_official_ten_items(self):
        payload = build_assessment_score_payload({
            "assessment_type": "word",
            "target_word_count": 221,
            "correct_words": 7,
            "crla_score_data": {"target_word_count": 221},
        })
        self.assertEqual(payload["crla_score_data"]["task1_total_words"], 10)

    def test_crla_task1_count_stays_ten_when_paragraph_payload_carries_story_length(self):
        payload = build_assessment_score_payload({
            "assessment_type": "paragraph",
            "correct_words": 13,
            "target_word_count": 95,
            "crla_score_data": {
                "task1_score": 13,
                "task1_total_words": 95,
                "story_total_words": 95,
            },
        })
        self.assertEqual(payload["crla_score_data"]["task1_total_words"], 10)
        self.assertIsNone(payload["crla_score_data"]["task1_correct_words"])
        self.assertIsNone(payload["crla_score_data"]["task1_score"])

    def test_story_words_read_cannot_populate_task1_correct_words(self):
        payload = build_assessment_score_payload({
            "assessment_type": "paragraph",
            "correct_words": 56,
            "target_word_count": 95,
            "crla_score_data": {
                "story_total_words": 95,
                "words_read": 56,
                "miscues": 39,
                "duration_seconds": 869.25,
                "comprehension_total": 6,
                "comprehension_correct": 3,
            },
        })
        self.assertEqual(payload["crla_score_data"]["words_read"], 56)
        self.assertIsNone(payload["crla_score_data"]["task1_correct_words"])
        self.assertIsNone(payload["crla_score_data"]["task1_score"])

    def test_task1_score_above_official_limit_is_rejected(self):
        payload = build_assessment_score_payload({
            "assessment_type": "paragraph",
            "crla_score_data": {"task1_score": 56, "words_read": 56},
        })
        self.assertIsNone(payload["crla_score_data"]["task1_score"])

    def test_valid_task1_and_task2_remain_independent_from_story_words(self):
        payload = build_assessment_score_payload({
            "assessment_type": "paragraph",
            "correct_words": 56,
            "crla_score_data": {
                "task1_total_words": 10,
                "task1_correct_words": 7,
                "task1_score": 7,
                "task2_type": "Task 2H / Sentences",
                "task2_score": 4,
                "part1_total_score": 11,
                "story_total_words": 80,
                "words_read": 60,
                "miscues": 3,
                "duration_seconds": 90,
                "comprehension_total": 6,
                "comprehension_correct": 3,
            },
        })
        self.assertEqual(payload["crla_score_data"]["task1_correct_words"], 7)
        self.assertEqual(payload["crla_score_data"]["task1_score"], 7)
        self.assertEqual(payload["crla_score_data"]["task2_type"], "Task 2H / Sentences")
        self.assertEqual(payload["crla_score_data"]["task2_score"], 4)
        self.assertEqual(payload["crla_score_data"]["part1_total_score"], 11)
        self.assertEqual(payload["crla_classification"], "Transitioning Reader")
        self.assertEqual(payload["crla_score_data"]["crla_classification"], "Transitioning Reader")

    def test_valid_part2_classification_ignores_legacy_generic_aggregates(self):
        payload = build_assessment_score_payload({
            "assessment_type": "paragraph",
            "correct_words": 56,
            "accuracy": 58.95,
            "pronunciation_score": 22.67,
            "fluency_score": 35,
            "total_score": 56,
            "crla_score_data": {
                "story_total_words": 80,
                "words_read": 50,
                "miscues": 3,
                "duration_seconds": 90,
                "comprehension_total": 6,
                "comprehension_correct": 3,
            },
        })
        self.assertEqual(payload["crla_classification"], "Developing Reader")
        self.assertEqual(payload["total_score"], 56)

    def test_part2_server_helper_matches_authoritative_band_mapping(self):
        self.assertEqual(_crla_grade2_part2_profile(53.68, 6), "Transitioning Reader")

    def test_other_part2_classification_bands_remain_available(self):
        self.assertEqual(_crla_grade2_part2_profile(50, 3), "Developing Reader")
        self.assertEqual(_crla_grade2_part2_profile(100, 6), "Reading At Grade Level")

    def test_part2_classification_persists_through_completed_state_sync(self):
        end_state = self._run_sync({
            "assessment_type": "paragraph",
            "story_total_words": 95,
            "words_read": 73,
            "miscues": 22,
            "duration_seconds": 491.88,
            "story_read_percent": 53.68,
            "comprehension_total": 6,
            "comprehension_correct": 6,
            "correct_answers": 6,
            "crla_classification": "Transitioning Reader",
        })
        self.assertEqual(end_state["classification"], "Transitioning Reader")

    def test_overlay_prefers_authoritative_crla_classification(self):
        source = (Path(__file__).parent / "static" / "pabasa_app" / "js" / "assessment_reader.js").read_text(encoding="utf-8")
        resolver = source.split("function resolveClassificationLabel", 1)[1].split("function isAralEligibleClassification", 1)[0]
        self.assertIn("scorePayload?.crla_classification", resolver)
        self.assertLess(resolver.index("scorePayload?.crla_classification"), resolver.index("scorePayload?.classification"))

    def test_story_segment_completion_advances_before_final_completion(self):
        source = (Path(__file__).parent / "static" / "pabasa_app" / "js" / "assessment_reader.js").read_text(encoding="utf-8")
        handler = source.split("function handleSpeechResult", 1)[1].split("function renderSyllableDisplay", 1)[0]
        self.assertIn('if (currentStoryState === "story_reading")', handler)
        self.assertIn("currentPageIndex < getCurrentPageCount() - 1", handler)
        self.assertIn('renderStoryComprehensionState(currentSelectedStory.title)', source)
        completion = source.split("async function showStoryCompletionScreen", 1)[1].split("function hideStoryCompletionScreen", 1)[0]
        self.assertIn("await showCompletion(true);", completion)

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
        self.assertEqual(end_state.get("stage"), "transition_to_rhymes")
        self.assertEqual(end_state.get("next_stage"), "rhymes")
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
        self.assertEqual(end_state.get("next_stage"), "sentences")
        self.assertEqual(end_state.get("stage"), "transition_to_sentence")

    def test_word_branch_uses_correct_words_ten_goes_to_sentences_high(self):
        end_state = self._run_sync({
            "assessment_type": "word",
            "correct_words": 10,
            "final_score": 58,
            "total_score": 58,
        })
        self.assertEqual(end_state.get("next_stage"), "sentences")
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
        self.assertEqual(end_state.get("part1_total_score"), 14)
        self.assertEqual(end_state.get("part1_reading_level"), "Moderate Refresher")

    def test_weighted_score_does_not_override_word_branch(self):
        end_state = self._run_sync({
            "assessment_type": "word",
            "correct_words": 7,
            "word_count": 7,
            "final_score": 58,
            "overall_raw_score": 58,
        })
        self.assertEqual(end_state.get("next_stage"), "sentences")
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
        self.assertEqual(ready.get("part1_total_score"), 17)
        self.assertEqual(ready.get("part1_reading_level"), "Grade Ready")

        maximum = self._run_sync({
            "assessment_type": "sentence",
            "correct_sentences": 10,
            "items_completed": 4,
        }, {"correct_words": 10, "stage": "sentences_high"})
        self.assertEqual(maximum.get("part1_total_score"), 20)
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

    def test_story_branch_persists_all_part_two_values(self):
        end_state = self._run_sync({
            "assessment_type": "paragraph",
            "story_number": 2,
            "selected_story": "Ang Pagong at ang Kuneho",
            "story_total_words": 126,
            "total_story_words": 126,
            "words_read": 93,
            "total_words_read": 93,
            "miscues": 4,
            "duration_seconds": 126,
            "wpm": 44.29,
            "comprehension_total": 6,
            "total_questions": 6,
            "comprehension_correct": 4,
            "correct_answers": 4,
            "story_read_percent": 73.81,
        })
        for field, expected in {
            "story_total_words": 126,
            "total_story_words": 126,
            "words_read": 93,
            "total_words_read": 93,
            "miscues": 4,
            "duration_seconds": 126,
            "wpm": 44.29,
            "comprehension_total": 6,
            "total_questions": 6,
            "comprehension_correct": 4,
            "correct_answers": 4,
        }.items():
            self.assertEqual(end_state.get(field), expected, field)

    def test_all_terminal_reader_classifications_route_by_final_label(self):
        expected = {
            "Low Emerging Reader": True,
            "High Emerging Reader": True,
            "Developing Reader": True,
            "Transitioning Reader": True,
            "Reader at Grade Level": False,
        }
        for classification, should_route in expected.items():
            with self.subTest(classification=classification):
                self.assertEqual(_aral_eligible_classification(classification), should_route)

    def test_story_terminal_classification_becomes_persisted_workflow_classification(self):
        student = SimpleNamespace(id=1, pk=1, reading_level="")
        state = {}
        assessment = SimpleNamespace(assessment_kind="crla", system_assessment_phase="pretest")
        with patch("pabasa_app.views._get_user_state", return_value=state), \
             patch("pabasa_app.views._set_user_state", side_effect=lambda _student, value: state.update(value)), \
             patch("pabasa_app.views._active_school_calendar", return_value=None), \
             patch("pabasa_app.views.timezone.now", return_value=SimpleNamespace(isoformat=lambda: "2026-08-24T00:00:00")):
            _sync_assessment_workflow_state(student, {
                "assessment_type": "paragraph",
                "story_read_percent": 70,
                "correct_answers": 4,
                "crla_classification": "Readers at Grade Level",
            }, assessment=assessment)

        self.assertEqual(state["reader_classification"], "Developing Reader")
        self.assertTrue(state["aral_eligible"])
        self.assertEqual(state["aral_status"], "active")
        self.assertEqual(state["crla_windows"]["pretest"]["classification"], "Developing Reader")

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
