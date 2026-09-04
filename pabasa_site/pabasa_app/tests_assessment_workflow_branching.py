import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from pabasa_app.views import (
    _aral_eligible_classification,
    _crla_grade2_part1_level,
    _crla_grade2_part2_profile,
    _is_finalized_grade_level_crla_result,
    _reader_assessment_state,
    persist_student_end_assessment_state,
    _sync_assessment_workflow_state,
)
from pabasa_app.scoring import (
    build_assessment_score_payload,
    crla_part1_classification,
    crla_part1_total,
    crla_task1_next_task,
)


class AssessmentWorkflowBranchingTests(SimpleTestCase):
    def test_part1_classification_matches_official_boundaries(self):
        expected = {
            10: "Full Refresher",
            11: "Moderate Refresher",
            16: "Moderate Refresher",
            17: "Light Refresher",
            26: "Light Refresher",
            27: "Grade Ready",
            30: "Grade Ready",
        }
        for total, classification in expected.items():
            with self.subTest(total=total):
                self.assertEqual(crla_part1_classification(total), classification)
                self.assertEqual(_crla_grade2_part1_level(10, total), classification)

    def test_word_branching_and_part1_total_remain_unchanged(self):
        self.assertEqual(crla_task1_next_task(6), "Task 2L / Rhymes")
        self.assertEqual(crla_task1_next_task(7), "Task 2H / Sentences")
        self.assertEqual(crla_part1_total(6, task2l_score=4), 10)
        self.assertEqual(crla_part1_total(7, task2h_score=10), 17)

    @staticmethod
    def _result(classification="Reading At Grade Level", status="completed", completed=True, crla=True, official=None):
        return SimpleNamespace(
            attempt_status=status,
            completed_at=object() if completed else None,
            crla_classification=classification,
            classification="",
            system_assessment_key="",
            source_assessment=None,
            material=SimpleNamespace(
                assessment_kind="crla" if crla else "regular",
                is_official_reading=crla if official is None else official,
                system_assessment_key="",
            ),
        )

    def test_finalized_crla_grade_level_result_is_authoritative(self):
        self.assertTrue(_is_finalized_grade_level_crla_result(self._result()))
        student = SimpleNamespace(pk=1, reading_level="Reading At Grade Level")
        with patch("pabasa_app.views._get_user_state", return_value={"aral_status": "active"}), \
             patch("pabasa_app.views._finalized_grade_level_crla_result_exists", return_value=True):
            resolved = _reader_assessment_state(student)
        self.assertTrue(resolved["reading_at_grade_level_complete"])
        self.assertFalse(resolved["aral_eligible"])
        self.assertEqual(resolved["aral_status"], "ineligible")

    def test_other_finalized_crla_classifications_are_not_grade_level_complete(self):
        for classification in (
            "Transitioning Reader", "Developing Reader", "High Emerging Reader", "Low Emerging Reader",
        ):
            with self.subTest(classification=classification):
                self.assertFalse(_is_finalized_grade_level_crla_result(self._result(classification=classification)))

    def test_profile_grade_level_without_finalized_crla_is_not_complete(self):
        student = SimpleNamespace(pk=1, reading_level="Reading At Grade Level")
        with patch("pabasa_app.views._get_user_state", return_value={}), \
             patch("pabasa_app.views._finalized_grade_level_crla_result_exists", return_value=False):
            resolved = _reader_assessment_state(student)
        self.assertFalse(resolved["reading_at_grade_level_complete"])

    def test_in_progress_crla_grade_level_result_is_not_complete(self):
        self.assertFalse(_is_finalized_grade_level_crla_result(self._result(status="started")))
        self.assertFalse(_is_finalized_grade_level_crla_result(self._result(completed=False)))

    def test_stale_crla_completion_flags_and_grade_profile_are_not_complete(self):
        student = SimpleNamespace(pk=1, reading_level="Reading At Grade Level")
        for stale_flag in ("crla_pretest_completed", "crla_posttest_completed"):
            with self.subTest(stale_flag=stale_flag), \
                 patch("pabasa_app.views._get_user_state", return_value={stale_flag: True}), \
                 patch("pabasa_app.views._finalized_grade_level_crla_result_exists", return_value=False):
                resolved = _reader_assessment_state(student)
                self.assertFalse(resolved["reading_at_grade_level_complete"])

    def test_non_crla_terminal_grade_level_result_is_not_complete(self):
        self.assertFalse(_is_finalized_grade_level_crla_result(self._result(crla=False)))
        self.assertFalse(_is_finalized_grade_level_crla_result(self._result(crla=False, official=True)))

    def test_in_progress_crla_does_not_mark_window_completed(self):
        student = SimpleNamespace(id=1, pk=1, reading_level="Reading At Grade Level")
        state = {}
        assessment = SimpleNamespace(assessment_kind="crla", system_assessment_phase="pretest")
        with patch("pabasa_app.views._get_user_state", return_value=state), \
             patch("pabasa_app.views._set_user_state", side_effect=lambda _student, value: state.update(value)), \
             patch("pabasa_app.views.timezone.now", return_value=SimpleNamespace(isoformat=lambda: "2026-09-01T00:00:00")):
            _sync_assessment_workflow_state(
                student,
                {"assessment_type": "word", "correct_words": 7},
                assessment=assessment,
            )
        self.assertFalse(state.get("crla_pretest_completed", False))
        self.assertFalse(any(window.get("completed") for window in state.get("crla_windows", {}).values()))

    def test_grade_level_completion_card_has_only_dashboard_and_practice_actions(self):
        html = render_to_string("pabasa_app/reading_assessment_workflow.html", {
            "stage": "grade_level_complete",
            "crla_assessment_items_json": [],
        })
        self.assertIn("READING GOAL ACHIEVED", html)
        self.assertIn("You're Reading at Grade Level!", html)
        self.assertIn("You have completed your reading assessment.", html)
        self.assertIn(f'href="{reverse("dashboard")}"', html)
        self.assertIn(f'href="{reverse("practice")}"', html)
        self.assertEqual(html.count('class="btn btn-primary workflow-button primary"'), 2)
        for forbidden in (
            "Start Reading Assessment", "Continue Assessment", "Take Assessment Again",
            "Retake Assessment", "Continue Reading Assessment", "Start ARAL Intervention",
        ):
            self.assertNotIn(forbidden, html)

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
        self.assertEqual(payload["crla_classification"], "High Emerging Reader")

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
        self.assertEqual(payload["crla_score_data"]["task2_score"], 10)
        self.assertEqual(payload["crla_score_data"]["part1_total_score"], 17)
        self.assertEqual(payload["crla_classification"], "Transitioning Reader")
        self.assertEqual(payload["crla_score_data"]["crla_classification"], "Transitioning Reader")

    def test_selected_official_story_number_survives_completion_scoring(self):
        for story_number in (1, 2):
            with self.subTest(story_number=story_number):
                payload = build_assessment_score_payload({
                    "assessment_type": "paragraph",
                    "crla_score_data": {
                        "story_number": story_number,
                        "story_total_words": 96 if story_number == 1 else 95,
                        "words_read": 80,
                        "miscues": 2,
                        "duration_seconds": 120,
                        "comprehension_total": 6,
                        "comprehension_correct": 4,
                    },
                })
                self.assertEqual(payload["crla_score_data"]["story_number"], story_number)

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
        self.assertEqual(payload["crla_classification"], "Transitioning Reader")
        self.assertEqual(payload["total_score"], 56)

    def test_part2_server_helper_matches_authoritative_band_mapping(self):
        self.assertEqual(_crla_grade2_part2_profile(53.68, 6), "Reading At Grade Level")

    def test_other_part2_classification_bands_remain_available(self):
        self.assertEqual(_crla_grade2_part2_profile(50, 3), "Transitioning Reader")
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
        self.assertEqual(end_state["classification"], "Reading At Grade Level")
        self.assertEqual(_crla_grade2_part2_profile(53.68, 6), "Reading At Grade Level")
        # teacher rule: cross-band final classification follows comprehension band
        self.assertEqual(_crla_grade2_part2_profile(70, 4), "Transitioning Reader")

    def test_completed_part2_persistence_uses_server_classification_without_material(self):
        student = SimpleNamespace(id=1, pk=1, reading_level="")
        factory = RequestFactory()
        endpoint = persist_student_end_assessment_state.__wrapped__.__wrapped__
        cases = (
            ({"material_id": "material-1", "classification": "Reading At Grade Level"}, True),
            ({"material_id": "material-invalid", "classification": "Reading At Grade Level"}, False),
            ({"classification": "Reading At Grade Level"}, False),
        )
        for client_fields, material_found in cases:
            with self.subTest(client_fields=client_fields), \
                 patch("pabasa_app.views._check_auth", return_value=True), \
                 patch("pabasa_app.views.User.objects.filter") as user_filter, \
                 patch("pabasa_app.views.Material.objects.filter") as material_filter:
                state = {}
                user_filter.return_value.first.return_value = student
                material_filter.return_value.first.return_value = SimpleNamespace(
                    id=1, is_official_reading=True, assessment_kind="crla",
                ) if material_found else None
                student.preference = {"reading_assessment_state": state}
                request = factory.post(
                    "/api/assessment/end-state/",
                    data=json.dumps({
                        "stage": "completed",
                        "story_read_percent": 80,
                        "correct_answers": 0,
                        **client_fields,
                    }),
                    content_type="application/json",
                )
                request.session = {"user_id": 1}
                with patch("pabasa_app.views._get_user_state", return_value=state), \
                     patch("pabasa_app.views._set_user_state", side_effect=lambda _student, value: state.update(value)):
                    response = endpoint(request)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(state["reader_classification"], "High Emerging Reader")
                self.assertEqual(state["student_end_assessment_state"]["classification"], "High Emerging Reader")

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

    def test_official_crla_comprehension_count_survives_final_completion(self):
        source = (Path(__file__).parent / "static" / "pabasa_app" / "js" / "assessment_reader.js").read_text(encoding="utf-8")
        handler = source.split("async function completeCRLASpokenAttempt", 1)[1].split("function startCRLASpokenAttempt", 1)[0]
        self.assertIn("const correctAnswers = currentStoryResults.filter(Boolean).length;", handler)
        self.assertIn("story_read_percent: storyReadPercent", handler)
        self.assertIn("words_read: persisted.words_read", handler)
        self.assertIn("miscues: persisted.miscues", handler)
        self.assertIn("wpm: persisted.wpm", handler)
        self.assertIn("correct_answers: correctAnswers", handler)
        self.assertIn("comprehension_correct: correctAnswers", handler)
        self.assertIn("total_questions: currentStoryQuestions.length", handler)
        self.assertIn('stage: "story_comprehension"', handler)
        self.assertIn("await showLearnerExperience();", handler)
        self.assertLess(
            handler.index("latestScores = {"),
            handler.index("await showLearnerExperience();"),
        )
        rating = source.split("async function saveLearnerExperienceRating", 1)[1].split("function startCRLASpokenAttempt", 1)[0]
        self.assertIn("learner_experience_rating: selectedRating", rating)
        self.assertIn('stage: "completed"', rating)
        self.assertIn("deferLocalStorage: true", rating)
        self.assertIn("await showCompletion(true);", rating)

        restore = source.split("function loadItems", 1)[1].split("function updateUI", 1)[0]
        self.assertIn("renderPersistedEndState(persistedEndState)", restore)
        self.assertIn("renderCRLAComprehensionState(restoredStory.title, persistedEndState)", restore)
        comprehension_restore = source.split("function renderCRLAComprehensionState", 1)[1].split("function renderStorySelection", 1)[0]
        self.assertIn("persistedState.crla_question_index", comprehension_restore)
        self.assertIn("persistedState.crla_answers", comprehension_restore)
        self.assertIn("persistedState.crla_results", comprehension_restore)
        self.assertIn("currentStoryQuestions = questions.slice(0, 6)", comprehension_restore)
        self.assertIn("persistCRLAComprehensionState", comprehension_restore)

        writer = source.split("function writeStudentEndState", 1)[1].split("// CRLA Official Assessment", 1)[0]
        self.assertIn("deferLocalStorage", writer)
        self.assertIn("if (accepted && deferLocalStorage)", writer)
        self.assertIn("return accepted ? result : null;", writer)

        endpoint = (Path(__file__).parent / "views.py").read_text(encoding="utf-8")
        allowed_stages = endpoint.split("allowed_stages =", 1)[1].split("allowed_fields =", 1)[0]
        self.assertIn("'learner_experience'", allowed_stages)

    def test_part1_terminal_states_share_learner_experience_gate(self):
        source = (Path(__file__).parent / "static" / "pabasa_app" / "js" / "assessment_reader.js").read_text(encoding="utf-8")
        completion = source.split("function showCompletion(isFullCompletion)", 1)[1].split("function startAssessmentTimer", 1)[0]
        self.assertIn('"early_completed_words", "early_completed_sentences"', completion)
        self.assertIn('stage: "learner_experience"', completion)
        self.assertIn("renderLearnerExperienceState();", completion)
        self.assertLess(completion.index("renderLearnerExperienceState();"), completion.index("completionSubmitted = true;"))
        self.assertLess(completion.index("renderLearnerExperienceState();"), completion.index("recordAssessmentCompletion.request"))
        self.assertIn('stage: "completed"', completion)
        self.assertIn("learner_experience_rating", completion)

    def test_learner_experience_restores_before_branch_resume(self):
        source = (Path(__file__).parent / "static" / "pabasa_app" / "js" / "assessment_reader.js").read_text(encoding="utf-8")
        restore = source.split("function loadItems", 1)[1].split("function updateUI", 1)[0]
        self.assertIn('persistedStage === "learner_experience"', restore)
        self.assertIn("renderLearnerExperienceState();", restore)
        self.assertLess(restore.index('persistedStage === "learner_experience"'), restore.index("const requestedStage"))

    def test_rating_save_is_integer_bounded_and_failure_safe(self):
        source = (Path(__file__).parent / "static" / "pabasa_app" / "js" / "assessment_reader.js").read_text(encoding="utf-8")
        rating = source.split("async function saveLearnerExperienceRating", 1)[1].split("function startCRLASpokenAttempt", 1)[0]
        template = (Path(__file__).parent / "templates" / "pabasa_app" / "learner_experience_rating.html").read_text(encoding="utf-8")
        self.assertIn('{% for rating in "12345" %}', template)
        self.assertIn("Number.parseInt(rating, 10)", rating)
        self.assertIn("selectedRating < 1 || selectedRating > 5", rating)
        self.assertIn('stage: "completed"', rating)
        self.assertIn("deferLocalStorage: true", rating)
        self.assertIn("We could not save your rating. Please try again.", rating)
        self.assertIn("learnerExperienceContinue.disabled = false", rating)

    def test_official_story_choices_have_stable_one_based_keys(self):
        source = (Path(__file__).parent / "static" / "pabasa_app" / "js" / "assessment_reader.js").read_text(encoding="utf-8")
        choices = source.split("function getStoryChoicesFromAssessment", 1)[1].split("function shortStoryPreview", 1)[0]
        self.assertIn(".map((item, index) => ({", choices)
        self.assertIn("key: index + 1", choices)

        score_data = source.split("function buildCrlaScoreData", 1)[1].split("function setCompletionActionButtonsProcessing", 1)[0]
        self.assertIn("story_number: source.story_number ?? currentSelectedStory?.key ?? null", score_data)

    def test_terminal_story_sync_forwards_story_identity(self):
        source = (Path(__file__).parent / "views.py").read_text(encoding="utf-8")
        endpoint = source.split("def persist_student_end_assessment_state", 1)[1].split("_STORY_ANSWER_FILLER_WORDS", 1)[0]
        self.assertIn("'story_number': saved.get('story_number')", endpoint)
        self.assertIn("'selected_story': saved.get('selected_story')", endpoint)

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
            "correct_sentences": 2,
            "items_completed": 4,
            "correct_words": 8,
        }, {"correct_words": 8, "stage": "sentences_high"})
        self.assertEqual(end_state.get("branch"), "sentences")
        self.assertEqual(end_state.get("task1_score"), 8)
        self.assertIsNone(end_state.get("task2_rhymes_score"))
        self.assertEqual(end_state.get("task2_sentences_score"), 5)
        self.assertEqual(end_state.get("part1_total_score"), 13)
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

    def test_seven_words_plus_three_sentences_uses_weighted_score(self):
        end_state = self._run_sync({
            "assessment_type": "sentence",
            "correct_sentences": 3,
            "items_completed": 4,
            "final_score": 58,
        }, {"correct_words": 7, "stage": "sentences_high"})
        self.assertEqual(end_state.get("stage"), "transition_to_story")
        self.assertEqual(end_state.get("next_stage"), "story_selection")
        self.assertEqual(end_state.get("routing_score"), 14)
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
        self.assertEqual(end_state.get("routing_score"), 17)

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
        self.assertEqual(ready.get("part1_reading_level"), "Light Refresher")

        maximum = self._run_sync({
            "assessment_type": "sentence",
            "correct_sentences": 10,
            "items_completed": 4,
        }, {"correct_words": 10, "stage": "sentences_high"})
        self.assertEqual(maximum.get("part1_total_score"), 20)
        self.assertEqual(maximum.get("part1_reading_level"), "Light Refresher")

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

        self.assertEqual(state["reader_classification"], "Transitioning Reader")
        self.assertTrue(state["aral_eligible"])
        self.assertEqual(state["aral_status"], "active")
        self.assertEqual(state["crla_windows"]["pretest"]["classification"], "Transitioning Reader")

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
