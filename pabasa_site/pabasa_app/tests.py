from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth.hashers import check_password, make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta
from io import BytesIO
from pathlib import Path
import hashlib
import json
import os
import uuid
from unittest.mock import patch

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from .forms import AdminPracticeMaterialForm
from .models import Material, User, Section, Assessment, Notification, Course, Note, LiveAssessmentSession
from .reading_stt import (
    ReadingMatcher,
    analyze_reading,
    language_code_for,
    target_phrase_hints,
    v1_model_for_language,
    word_numbers_in_transcript,
)
from .hunt_scoring import classify_speech, normalize_speech, stars_for_points
from .test_accounts import PRINCIPAL_DEFAULT_CUSTOM_ID, PRINCIPAL_DEFAULT_PASSWORD
from .views import _apply_progression_unlock_override, _create_notification, _notify_principals, _material_response_payload, _fallback_material_items_from_text, _build_material_items_from_ocr_layout, _build_image_upload_debug_info, _adapted_reading_level_from_attempts, _adapted_reading_level_label, _assessment_fluency_score, _assessment_score_payload, _build_reading_report_pdf, _derive_dashboard_greeting_name, _display_reading_level, _build_latest_reading_level_payload
from .weekly_digest import send_weekly_digest
from .scoring import build_assessment_score_payload


class ClassMaterialsApiTests(TestCase):
    def test_get_class_materials_groups_vowel_materials_under_vowel_bucket(self):
        teacher = User.objects.create(
            custom_id="TCHR-1001",
            role="teacher",
            first_name="Tina",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=2,
            birth_year=1990,
            email="teacher1001@example.com",
            password_hash=make_password("teacher-password"),
        )
        section = Section.objects.create(
            teacher=teacher,
            class_name="Class A",
            class_code="CLS-A1001",
            subject="Reading",
            is_active=True,
        )
        material = Material.objects.create(
            title="Vowel Drill",
            item_type="vowel",
            content_text="a\ne",
            content_json={"items": ["a", "e"]},
            type="assessment",
            status="published",
            section=section,
            teacher=teacher,
            is_active=True,
        )

        session = self.client.session
        session["user_id"] = teacher.id
        session["user_role"] = teacher.role
        session.save()

        response = self.client.get(reverse("get_class_materials"), {"class_code": section.class_code})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("vowel", data["materials"])
        self.assertEqual(len(data["materials"]["vowel"]), 1)
        self.assertEqual(data["materials"]["vowel"][0]["id"], f"material-{material.id}")
        self.assertEqual(data["materials"]["vowel"][0]["item_type"], "vowel")


class DashboardAchievementBadgeTests(TestCase):
    def test_dashboard_template_contains_practice_star_achievement(self):
        template_path = Path(__file__).resolve().parent / "templates" / "pabasa_app" / "dashboard.html"
        content = template_path.read_text(encoding="utf-8")

        self.assertIn("'practice-star'", content)
        self.assertIn("Complete every level in Free Mode, Color Mode, and Hunt Mode", content)
        self.assertIn("pabasa_practice_progress_v1", content)
        self.assertNotIn("pabasa_practice_sessions_completed", content)
        self.assertNotIn(">= 10", content)


class DashboardGreetingNameTests(TestCase):
    def test_uses_first_name_when_available(self):
        self.assertEqual(_derive_dashboard_greeting_name(first_name="Jamie", full_name="Jamie Reader"), "Jamie")

    def test_uses_first_word_of_full_name_for_legacy_accounts(self):
        self.assertEqual(_derive_dashboard_greeting_name(first_name="", full_name="Maria Clara Dela Cruz"), "Maria")

    def test_falls_back_to_student_when_no_name_data_exists(self):
        self.assertEqual(_derive_dashboard_greeting_name(first_name="", full_name=""), "Student")


class AssessmentPageTemplateTests(TestCase):
    def test_assessment_page_includes_vowel_material_support(self):
        template_path = Path(__file__).resolve().parent / "templates" / "pabasa_app" / "assessment.html"
        content = template_path.read_text(encoding="utf-8")

        self.assertIn('const materialTypes = ["word", "sentence", "paragraph", "vowel"];', content)
        self.assertIn('vowel: "{% url \'reading_vowel_page\' %}"', content)


class TeacherSignupTemplateTests(TestCase):
    def test_teacher_signup_template_includes_privacy_step_and_consent_controls(self):
        template_path = Path(__file__).resolve().parent / "templates" / "pabasa_app" / "teacher_signup.html"
        content = template_path.read_text(encoding="utf-8")

        self.assertIn('data-signup-step="3"', content)
        self.assertIn("I agree to the Privacy Policy and Terms of Service", content)
        self.assertIn("${stepLabels[currentStep]} ${currentStep + 1}/${steps.length}", content)


class StudentSignupTemplateTests(TestCase):
    def test_student_signup_template_includes_privacy_step_and_consent_controls(self):
        template_path = Path(__file__).resolve().parent / "templates" / "pabasa_app" / "student_signup.html"
        content = template_path.read_text(encoding="utf-8")

        self.assertIn('data-signup-step="3"', content)
        self.assertIn("I agree to the Privacy Policy and Terms of Service", content)
        self.assertIn("Step ${currentStep + 1} of ${steps.length}", content)


class AssessmentResultsPageTests(TestCase):
    def test_completion_page_uses_child_friendly_summary_copy(self):
        template_path = Path(__file__).resolve().parent / "templates" / "pabasa_app" / "reading_assessment_base.html"
        content = template_path.read_text(encoding="utf-8")

        self.assertIn("Great job completing your reading assessment! Your results show your current reading performance. Keep practicing to improve your reading skills.", content)
        self.assertNotIn("This assessment result is based on the student's reading accuracy, fluency, pronunciation, and pacing during the assessment.", content)
        self.assertNotIn("completionPerformanceInterpretation", content)

    def test_completion_page_has_loading_placeholder_for_results(self):
        template_path = Path(__file__).resolve().parent / "templates" / "pabasa_app" / "reading_assessment_base.html"
        content = template_path.read_text(encoding="utf-8")

        self.assertIn("completion-loading", content)
        self.assertIn("Calculating your score breakdown...", content)

    def test_build_reading_report_pdf_omits_performance_interpretation(self):
        report = {
            "student_name": "Jane Doe",
            "student_id": "1001",
            "grade_level": "Grade 2",
            "email": "jane@example.com",
            "joined_classes": ["Class A"],
            "course_name": "Reading",
            "course_code": "R1",
            "reading_level": "Transitioning Readers",
            "accuracy": 88,
            "wpm": 68,
            "fluency_score": 84,
            "duration_seconds": 120,
            "time_score": 90,
            "pronunciation_score": 82,
            "final_score": 85,
            "summary": "Strong performance",
            "recommendation": "Keep practicing",
            "completed_at": timezone.now().isoformat(),
        }

        pdf_bytes = _build_reading_report_pdf(report)
        reader = PdfReader(BytesIO(pdf_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

        self.assertIn("Reading Level", text)
        self.assertNotIn("Performance Interpretation", text)


class ReadingMatcherTests(TestCase):
    def test_material_languages_use_philippine_stt_locales(self):
        self.assertEqual(language_code_for("English"), "en-PH")
        self.assertEqual(language_code_for("Filipino"), "fil-PH")

    def test_philippine_locales_use_supported_v1_models(self):
        self.assertEqual(v1_model_for_language("latest_short", "en-PH"), "command_and_search")
        self.assertEqual(v1_model_for_language("latest_short", "fil-PH"), "")

    def test_english_homophone_is_accepted(self):
        result = analyze_reading("two", 0, "too", language_code="en-US")

        self.assertEqual(result["correct_word_count"], 1)
        self.assertTrue(result["complete"])

    def test_non_homophone_is_rejected(self):
        result = analyze_reading("cat", 0, "cut", language_code="en-US")

        self.assertEqual(result["correct_word_count"], 0)
        self.assertFalse(result["complete"])

    def test_cmu_homophones_are_not_applied_to_filipino(self):
        result = analyze_reading("two", 0, "too", language_code="fil-PH")

        self.assertEqual(result["correct_word_count"], 0)
        self.assertFalse(result["complete"])

    def test_filipino_syllable_tokens_match_one_target_word(self):
        result = analyze_reading("kabayo", 0, "ka ba yo", language_code="fil-PH")

        self.assertEqual(result["correct_word_count"], 1)
        self.assertTrue(result["complete"])
        self.assertEqual(result["matched"], 3)

    def test_filipino_joined_syllables_allow_one_stt_vowel_error(self):
        result = analyze_reading("puno", 0, "po no", language_code="fil-PH")

        self.assertEqual(result["correct_word_count"], 1)
        self.assertTrue(result["complete"])

    def test_filipino_target_adds_whole_word_and_syllable_hints(self):
        self.assertEqual(target_phrase_hints("Araw Puno", "fil-PH"), ["araw", "a", "raw", "puno", "pu", "no"])
        self.assertEqual(target_phrase_hints("Araw", "en-PH"), [])

    def test_english_tokens_are_not_joined_into_one_target_word(self):
        result = analyze_reading("somebody", 0, "some body", language_code="en-PH")

        self.assertEqual(result["correct_word_count"], 0)
        self.assertFalse(result["complete"])

    def test_word_numbers_in_english_transcript(self):
        self.assertEqual(
            word_numbers_in_transcript("I read 19 of 1,000 words."),
            "I read nineteen of one thousand words.",
        )

    def test_word_numbers_preserves_raw_numbers_for_non_english_transcript(self):
        self.assertEqual(word_numbers_in_transcript("Bumasa ng 19", "fil-PH"), "Bumasa ng 19")

    def test_word_numbers_does_not_rewrite_decimal_values(self):
        self.assertEqual(word_numbers_in_transcript("Score: 19.5"), "Score: 19.5")

    def test_wrong_word_does_not_complete_target(self):
        result = analyze_reading("water", 0, "apple")

        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["correct_word_count"], 0)
        self.assertFalse(result["complete"])

    def test_numeric_text_is_not_treated_as_list_marker(self):
        result = analyze_reading("19", 0, "19")

        self.assertEqual(result["correct_word_count"], 1)
        self.assertTrue(result["complete"])
        self.assertEqual(result["matched"], 1)

    def test_numeric_target_and_spoken_number_words_match(self):
        result = analyze_reading("19", 0, "nineteen")

        self.assertEqual(result["correct_word_count"], 1)
        self.assertTrue(result["complete"])
        self.assertEqual(result["matched"], 1)

    def test_numeric_target_and_spoken_digit_match(self):
        result = analyze_reading("Nineteen", 0, "19")

        self.assertEqual(result["correct_word_count"], 1)
        self.assertTrue(result["complete"])
        self.assertTrue(result["matched"] > 0)

    def test_normalize_words_preserves_numeric_tokens_with_punctuation(self):
        self.assertEqual(ReadingMatcher.normalize_words("19."), ["19"])
        self.assertEqual(ReadingMatcher.normalize_words("19,"), ["19"])


class AdaptedReadingLevelTests(TestCase):
    def test_adapted_reading_level_label_uses_expected_thresholds(self):
        self.assertEqual(_adapted_reading_level_label(0.90), "Readers at Grade Level")
        self.assertEqual(_adapted_reading_level_label(0.76), "Transitioning Readers")
        self.assertEqual(_adapted_reading_level_label(0.60), "Developing Readers")
        self.assertEqual(_adapted_reading_level_label(0.45), "High Emerging Readers")
        self.assertEqual(_adapted_reading_level_label(0.25), "Low Emerging Readers")

    def test_adapted_reading_level_averages_across_assessment_types(self):
        result = _adapted_reading_level_from_attempts([
            {"total_score": 80, "assessment_type": "word"},
            {"total_score": 80, "assessment_type": "sentence"},
            {"total_score": 80, "assessment_type": "paragraph"},
        ])

        self.assertEqual(result["adapted_level_score"], 0.76)
        self.assertEqual(result["adapted_reading_level"], "Transitioning Readers")
        self.assertEqual(result["adapted_reading_level_disclaimer"], "Great job completing your reading assessment! Your results show your current reading performance. Keep practicing to improve your reading skills.")

    def test_assessment_fluency_score_is_more_forgiving_for_accurate_slow_readers(self):
        self.assertEqual(_assessment_fluency_score(0.10, 95), 52)
        self.assertEqual(_assessment_fluency_score(0.20, 95), 60)

    def test_display_reading_level_uses_consistent_classification_labels(self):
        self.assertEqual(_display_reading_level("Transitioning", None), "Transitioning Readers")
        self.assertEqual(_display_reading_level(None, {"final_score": 60}), "High Emerging Readers")

    def test_display_reading_level_prefers_score_classification_over_stale_adapted_labels(self):
        self.assertEqual(
            _display_reading_level(None, {"final_score": 81, "adapted_reading_level": "Low Emerging Readers"}),
            "Transitioning Readers",
        )

    def test_build_latest_reading_level_payload_uses_latest_score_classification(self):
        payload = _build_latest_reading_level_payload({"total_score": 81, "assessment_type": "word"}, fallback="Low Emerging Readers")

        self.assertEqual(payload["reading_level"], "Transitioning Readers")
        self.assertEqual(payload["adapted_reading_level"], "Transitioning Readers")

    def test_assessment_score_payload_uses_word_multiplier_for_high_emerging_levels(self):
        result = _assessment_score_payload({
            "scores": {
                "fluency_score": 0,
                "accuracy": 0,
                "pronunciation_score": 0,
                "time_score": 0,
                "total_score": 56,
            },
            "assessment_type": "word",
        })

        self.assertEqual(result["adapted_level_score"], 0.5)
        self.assertEqual(result["adapted_reading_level"], "High Emerging Readers")

    def test_assessment_score_payload_uses_word_multiplier_for_lower_high_emerging_levels(self):
        result = _assessment_score_payload({
            "scores": {
                "fluency_score": 0,
                "accuracy": 0,
                "pronunciation_score": 0,
                "time_score": 0,
                "total_score": 47,
            },
            "assessment_type": "word",
        })

        self.assertEqual(result["adapted_level_score"], 0.42)
        self.assertEqual(result["adapted_reading_level"], "High Emerging Readers")

    def test_assessment_score_payload_uses_weighted_total_and_interpretation(self):
        result = _assessment_score_payload({
            "scores": {
                "fluency_score": 6,
                "accuracy": 60,
                "pronunciation_score": 60,
                "time_score": 0,
                "total_score": 31,
            },
            "assessment_type": "word",
        })

        self.assertEqual(result["overall_raw_score"], 49)
        self.assertEqual(result["final_score"], 44)
        self.assertEqual(result["total_score"], 44)
        self.assertFalse(result["passed"])
        self.assertEqual(result["performance_interpretation"], "Needs Support")
        self.assertEqual(result["adapted_reading_level"], "High Emerging Readers")

    def test_assessment_score_payload_uses_vowel_osps_multiplier_for_classification(self):
        result = _assessment_score_payload({
            "scores": {
                "fluency_score": 84,
                "accuracy": 84,
                "pronunciation_score": 84,
                "time_score": 0,
                "total_score": 84,
            },
            "assessment_type": "vowel",
        })

        self.assertEqual(result["overall_raw_score"], 80)
        self.assertEqual(result["final_score"], 68)
        self.assertEqual(result["crla_classification"], "High Emerging Readers")
        self.assertEqual(result["adapted_level_score"], 0.68)

    def test_assessment_score_payload_uses_vowel_multiplier_for_vc_materials(self):
        result = _assessment_score_payload({
            "scores": {
                "fluency_score": 84,
                "accuracy": 84,
                "pronunciation_score": 84,
                "time_score": 0,
                "total_score": 84,
            },
            "assessment_type": "vc",
        })

        self.assertEqual(result["osps_multiplier"], 0.85)
        self.assertEqual(result["final_score"], 68)


class CentralizedAssessmentScoringTests(TestCase):
    def test_build_assessment_score_payload_computes_time_score_from_pace(self):
        payload = build_assessment_score_payload({
            "assessment_type": "word",
            "correct_words": 45,
            "incorrect_words": 5,
            "skipped_words": 0,
            "duration_seconds": 60,
            "target_word_count": 50,
            "pronunciation_metrics": {"score": 80},
            "fluency_metrics": {"score": 70},
        })

        self.assertEqual(payload["time_score"], 100.0)
        self.assertEqual(payload["overall_raw_score"], 87)
        self.assertEqual(payload["final_score"], 78)

    def test_build_assessment_score_payload_uses_weighted_formula_for_all_metrics(self):
        payload = build_assessment_score_payload({
            "assessment_type": "word",
            "correct_words": 80,
            "incorrect_words": 20,
            "skipped_words": 0,
            "duration_seconds": 60,
            "target_word_count": 100,
            "pronunciation_metrics": {"score": 40},
            "fluency_metrics": {"score": 60},
            "time_score": 20,
        })

        self.assertEqual(payload["accuracy"], 80.0)
        self.assertEqual(payload["fluency_score"], 60.0)
        self.assertEqual(payload["pronunciation_score"], 40.0)
        self.assertEqual(payload["time_score"], 20.0)
        self.assertEqual(payload["overall_raw_score"], 74)
        self.assertEqual(payload["final_score"], 67)

    def test_build_assessment_score_payload_uses_raw_metrics_for_authoritative_score(self):
        payload = build_assessment_score_payload({
            "assessment_type": "word",
            "correct_words": 100,
            "incorrect_words": 0,
            "skipped_words": 0,
            "duration_seconds": 60,
            "target_word_count": 100,
            "pronunciation_metrics": {"score": 62.5},
            "fluency_metrics": {"score": 60},
        })

        self.assertEqual(payload["accuracy"], 100.0)
        self.assertEqual(payload["fluency_score"], 60.0)
        self.assertEqual(payload["pronunciation_score"], 62.5)
        self.assertEqual(payload["final_score"], 81)
        self.assertEqual(payload["crla_classification"], "Transitioning Readers")

    def test_build_assessment_score_payload_handles_missing_pronunciation_data(self):
        payload = build_assessment_score_payload({
            "assessment_type": "paragraph",
            "correct_words": 12,
            "incorrect_words": 8,
            "skipped_words": 0,
            "duration_seconds": 90,
            "target_word_count": 20,
            "fluency_metrics": {"score": 80},
        })

        self.assertEqual(payload["accuracy"], 60.0)
        self.assertEqual(payload["pronunciation_score"], 0.0)
        self.assertEqual(payload["final_score"], 55)
        self.assertEqual(payload["crla_classification"], "Low Emerging Readers")

    def test_build_assessment_score_payload_uses_zero_fluency_for_skipped_assessment(self):
        payload = build_assessment_score_payload({
            "assessment_type": "word",
            "correct_words": 0,
            "incorrect_words": 0,
            "skipped_words": 0,
            "duration_seconds": 0,
            "target_word_count": 20,
            "transcript": "",
            "speech_recognition_used": False,
            "needs_manual_review": False,
        })

        self.assertEqual(payload["fluency_score"], 0.0)
        self.assertEqual(payload["overall_raw_score"], 0)
        self.assertEqual(payload["final_score"], 0)
        self.assertEqual(payload["crla_classification"], "Low Emerging Readers")


class HuntScoringRuleTests(TestCase):
    def test_normalization_and_missing_confidence_fallback(self):
        self.assertEqual(normalize_speech(" C\u00c1t! "), "cat")
        self.assertEqual(classify_speech("Cat!", "cat"), ("Excellent", 2))
        self.assertEqual(classify_speech("dog", "cat"), ("Weak", 0))

    def test_confidence_thresholds(self):
        self.assertEqual(classify_speech("cat", "cat", .80), ("Excellent", 2))
        self.assertEqual(classify_speech("cat", "cat", .79), ("Mixed", 1))
        self.assertEqual(classify_speech("cat", "cat", .50), ("Mixed", 1))
        self.assertEqual(classify_speech("cat", "cat", .49), ("Weak", 0))
        self.assertEqual(classify_speech("dog", "cat", .99), ("Weak", 0))

    def test_star_thresholds_never_award_zero(self):
        self.assertEqual([stars_for_points(p) for p in (0, 4, 5, 7, 8, 10)], [1, 1, 2, 2, 3, 3])

    def test_frontend_has_duplicate_guard_and_non_scoring_checkpoint(self):
        source = (Path(__file__).resolve().parent / "static" / "pabasa_app" / "js" / "practice_reader.js").read_text(encoding="utf-8")
        template = (Path(__file__).resolve().parent / "templates" / "pabasa_app" / "practice_reader_base.html").read_text(encoding="utf-8")
        self.assertIn("if (!isHuntMode || huntResults[index]) return null", source)
        self.assertIn("if (currentIndex === 3 && huntCheckpointToast)", source)
        self.assertIn("if (result.points > 0)", source)
        self.assertIn("speechItemIndex !== currentIndex || huntAdvanceInProgress", source)
        self.assertIn("Try again — keep reading the same word.", source)
        self.assertIn("if (!huntResults[currentIndex]) finalizeHuntSpeechResult", source)
        self.assertIn("updateReadingToggleButton()", source)
        self.assertIn("practiceRecordingWindowMs(targetText)", source)
        self.assertIn("huntListeningDesired", source)
        self.assertIn("scheduleContinuousRecognition(currentIndex, 120)", source)
        self.assertIn("stopContinuousRecognitionByUser()", source)
        self.assertIn("Google Speech results will appear here while you read.", template)
        self.assertIn("Raw mic input", template)
        self.assertIn("Waiting for speech...", template)
        self.assertIn('id="huntReadAloudBtn"', template)
        self.assertIn('/api/reading/read-aloud/', source)
        self.assertIn('formData.append("tts_profile", "hunt")', source)
        self.assertIn("activeDot.appendChild(huntFlightBird)", source)
        self.assertIn("grid-template-columns: .72fr 1.12fr 1fr .72fr", template)
        self.assertIn("transform: translate(-50%,-50%)", template)
        self.assertIn("/api/practice/hunt/award-stars/", source)
        self.assertIn("if (huntAwardSubmitted)", source)
        self.assertIn('id="huntPointsDisplay">Points: 0/10', template)
        self.assertIn('Available Stars: {{ student_available_stars|default:0 }}', template)
        self.assertIn('starCount.textContent = `Available Stars: ${data.available_stars}`', source)


class StudentSignupCustomIdTests(TestCase):
    def setUp(self):
        self.client = Client()

    def _set_pending_student_signup(self, grade_level, email):
        session = self.client.session
        session["pending_student_signup"] = {
            "first_name": "Jamie",
            "last_name": "Reader",
            "email": email,
            "middle_initial": "",
            "suffix": "",
            "sex": "female",
            "birth_month": 1,
            "birth_day": 15,
            "birth_year": 2014,
            "password_hash": make_password("student-password"),
            "contact_no": "",
            "grade_level": grade_level,
            "section": "",
            "reading_level": "",
        }
        session["pending_student_signup_otp"] = "123456"
        session["pending_student_signup_otp_created"] = timezone.now().timestamp()
        session.save()

    @patch("pabasa_site.pabasa_app.views._notify_admins")
    @patch("pabasa_site.pabasa_app.views.send_student_confirmation_email")
    def test_verify_student_otp_uses_selected_grade_for_custom_id_prefix(self, mock_email, mock_notify):
        self._set_pending_student_signup("Grade 6", "grade6@example.com")

        response = self.client.post(reverse("verify_student_otp"), {"otp": "123456"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["custom_id"], "G6-0001")
        self.assertEqual(User.objects.get(email="grade6@example.com").custom_id, "G6-0001")

    @patch("pabasa_site.pabasa_app.views._notify_admins")
    @patch("pabasa_site.pabasa_app.views.send_student_confirmation_email")
    def test_verify_student_otp_increments_custom_id_per_grade_prefix(self, mock_email, mock_notify):
        User.objects.create(
            custom_id="G3-0001",
            role="student",
            first_name="Gia",
            last_name="Three",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=2,
            birth_day=2,
            birth_year=2013,
            email="existing-g3@example.com",
            password_hash=make_password("student-password"),
            grade_level="Grade 3",
        )
        User.objects.create(
            custom_id="G6-0001",
            role="student",
            first_name="Gino",
            last_name="Six",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=3,
            birth_day=3,
            birth_year=2012,
            email="existing-g6@example.com",
            password_hash=make_password("student-password"),
            grade_level="Grade 6",
        )

        self._set_pending_student_signup("Grade 3", "next-g3@example.com")
        response = self.client.post(reverse("verify_student_otp"), {"otp": "123456"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["custom_id"], "G3-0002")
        self.assertEqual(User.objects.get(email="next-g3@example.com").custom_id, "G3-0002")

    def test_similar_wrong_word_does_not_match_when_first_sound_differs(self):
        result = analyze_reading("house", 0, "mouse")

        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["correct_word_count"], 0)
        self.assertFalse(result["complete"])

    def test_correct_words_advance_in_order_until_first_missing_target(self):
        result = analyze_reading("the water is cold", 0, "the apple is cold")

        self.assertEqual(result["correct_word_count"], 1)
        self.assertFalse(result["complete"])


class PracticeProgressionTests(TestCase):
    def test_apply_progression_unlock_override_only_marks_ui_hint_without_changing_state(self):
        progression = {
            "sections": [
                {
                    "difficulty": "easy",
                    "levels": [
                        {"difficulty": "easy", "level": "level_1", "state": "locked", "unlocked": False, "button_label": "Locked"},
                        {"difficulty": "easy", "level": "level_2", "state": "locked", "unlocked": False, "button_label": "Locked"},
                    ],
                }
            ]
        }

        updated = _apply_progression_unlock_override(progression, "easy_level_2")
        levels = updated["sections"][0]["levels"]

        self.assertEqual(levels[0]["state"], "locked")
        self.assertFalse(levels[0]["unlocked"])
        self.assertEqual(levels[1]["state"], "locked")
        self.assertFalse(levels[1]["unlocked"])
        self.assertEqual(updated["ui_unlock_target"], "easy_level_2")


class SharedMaterialImportTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            custom_id=f"TCH-{uuid.uuid4().hex[:8].upper()}",
            role="teacher",
            first_name="Tina",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=5,
            birth_day=10,
            birth_year=1988,
            email="shared-import-teacher@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )
        self.other_teacher = User.objects.create(
            custom_id=f"TCH-{uuid.uuid4().hex[:8].upper()}",
            role="teacher",
            first_name="Mina",
            last_name="Shared",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=7,
            birth_day=4,
            birth_year=1991,
            email="shared-source-teacher@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )
        self.shared_material = Material.objects.create(
            teacher=self.other_teacher,
            title="Shared Reading",
            item_type="word",
            prompt_text="One",
            content_text="One\nTwo",
            content_json={"items": ["One", "Two"], "language": "English"},
            type="assessment",
            source_type="shared",
            status="published",
            is_active=True,
        )
        session = self.client.session
        session["user_id"] = self.teacher.id
        session["user_role"] = self.teacher.role
        session["first_name"] = self.teacher.first_name
        session["last_name"] = self.teacher.last_name
        session["email"] = self.teacher.email
        session["custom_id"] = self.teacher.custom_id
        session.save()

    def test_importing_shared_material_without_changes_reuses_original(self):
        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Shared Reading",
                "reading_type": "word",
                "content": "One\nTwo",
                "status": "published",
                "usage_type": "assessment",
                "source_type": "shared",
                "source_material_id": self.shared_material.id,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data.get("reused", False))
        self.assertEqual(Material.objects.filter(teacher=self.teacher).count(), 0)
        self.assertEqual(Material.objects.filter(source_type="shared", teacher=self.other_teacher).count(), 1)

    def test_importing_shared_material_with_changes_creates_updated_duplicate(self):
        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Shared Reading",
                "reading_type": "word",
                "content": "One\nTwo\nThree",
                "status": "draft",
                "usage_type": "assessment",
                "source_type": "shared",
                "source_material_id": self.shared_material.id,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertFalse(data.get("reused", False))
        duplicate_materials = Material.objects.filter(teacher=self.teacher, source_type="shared")
        self.assertEqual(duplicate_materials.count(), 1)
        duplicate_material = duplicate_materials.get()
        self.assertTrue(duplicate_material.title.startswith("[UPDATED]"))
        self.assertEqual(duplicate_material.status, "draft")


class OcrLayoutGroupingTests(TestCase):
    def test_build_material_items_from_ocr_layout_returns_words_in_reading_order(self):
        layout = [
            {"text": "Hello", "left": 10, "top": 20, "width": 40, "height": 12, "conf": 95, "block_num": 0, "par_num": 0, "line_num": 0, "word_num": 0},
            {"text": "world", "left": 60, "top": 20, "width": 40, "height": 12, "conf": 95, "block_num": 0, "par_num": 0, "line_num": 0, "word_num": 1},
        ]

        items = _build_material_items_from_ocr_layout(layout, "word")

        self.assertEqual(items, ["Hello", "world"])

    def test_build_material_items_from_ocr_layout_groups_lines_into_sentences(self):
        layout = [
            {"text": "The", "left": 10, "top": 20, "width": 20, "height": 12, "conf": 95, "block_num": 0, "par_num": 0, "line_num": 0, "word_num": 0},
            {"text": "quick", "left": 40, "top": 20, "width": 30, "height": 12, "conf": 95, "block_num": 0, "par_num": 0, "line_num": 0, "word_num": 1},
            {"text": "brown", "left": 80, "top": 20, "width": 30, "height": 12, "conf": 95, "block_num": 0, "par_num": 0, "line_num": 0, "word_num": 2},
            {"text": "fox", "left": 120, "top": 20, "width": 20, "height": 12, "conf": 95, "block_num": 0, "par_num": 0, "line_num": 0, "word_num": 3},
            {"text": "jumps", "left": 10, "top": 45, "width": 35, "height": 12, "conf": 95, "block_num": 0, "par_num": 0, "line_num": 1, "word_num": 0},
            {"text": "over", "left": 50, "top": 45, "width": 25, "height": 12, "conf": 95, "block_num": 0, "par_num": 0, "line_num": 1, "word_num": 1},
            {"text": "the", "left": 80, "top": 45, "width": 20, "height": 12, "conf": 95, "block_num": 0, "par_num": 0, "line_num": 1, "word_num": 2},
            {"text": "lazy", "left": 105, "top": 45, "width": 25, "height": 12, "conf": 95, "block_num": 0, "par_num": 0, "line_num": 1, "word_num": 3},
            {"text": "dog", "left": 135, "top": 45, "width": 20, "height": 12, "conf": 95, "block_num": 0, "par_num": 0, "line_num": 1, "word_num": 4},
        ]

        items = _build_material_items_from_ocr_layout(layout, "sentence")

        self.assertEqual(items, ["The quick brown fox", "jumps over the lazy dog"])

    def test_build_material_items_from_ocr_layout_groups_paragraphs_by_vertical_gap(self):
        layout = [
            {"text": "First", "left": 10, "top": 20, "width": 30, "height": 12, "conf": 95, "block_num": 0, "par_num": 0, "line_num": 0, "word_num": 0},
            {"text": "paragraph", "left": 45, "top": 20, "width": 50, "height": 12, "conf": 95, "block_num": 0, "par_num": 0, "line_num": 0, "word_num": 1},
            {"text": "Second", "left": 10, "top": 70, "width": 34, "height": 12, "conf": 95, "block_num": 0, "par_num": 1, "line_num": 0, "word_num": 0},
            {"text": "paragraph", "left": 50, "top": 70, "width": 50, "height": 12, "conf": 95, "block_num": 0, "par_num": 1, "line_num": 0, "word_num": 1},
        ]

        items = _build_material_items_from_ocr_layout(layout, "paragraph")

        self.assertEqual(items, ["First paragraph", "Second paragraph"])


class MaterialUploadExtractionTests(TestCase):
    def test_build_image_upload_debug_info_reports_upload_size_and_hash(self):
        upload = SimpleUploadedFile("scan.png", b"abc123", content_type="image/png")

        info = _build_image_upload_debug_info(upload, source="received")

        self.assertEqual(info["source"], "received")
        self.assertEqual(info["size"], 6)
        self.assertEqual(info["sha256"], hashlib.sha256(b"abc123").hexdigest())
        self.assertEqual(info["content_type"], "image/png")

    def setUp(self):
        self.teacher = User.objects.create(
            custom_id=f"TCH-{uuid.uuid4().hex[:8].upper()}",
            role="teacher",
            first_name="Tina",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=5,
            birth_day=10,
            birth_year=1988,
            email="upload-teacher@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = self.teacher.id
        session["user_role"] = self.teacher.role
        session["first_name"] = self.teacher.first_name
        session["last_name"] = self.teacher.last_name
        session["email"] = self.teacher.email
        session["custom_id"] = self.teacher.custom_id
        session.save()

    def test_extract_endpoint_honors_selected_pdf_pages(self):
        buffer = BytesIO()
        pdf_canvas = canvas.Canvas(buffer)
        pdf_canvas.drawString(72, 720, "Intro page")
        pdf_canvas.showPage()
        pdf_canvas.drawString(72, 720, "Page 2")
        pdf_canvas.showPage()
        pdf_canvas.drawString(72, 720, "Last page")
        pdf_canvas.save()
        buffer.seek(0)

        pdf_file = SimpleUploadedFile(
            "sample.pdf",
            buffer.read(),
            content_type="application/pdf",
        )

        response = self.client.post(
            reverse("extract_reading_material_file"),
            {"file": pdf_file, "selection_mode": "selected", "selected_pages": "2"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["page_count"], 3)
        self.assertEqual(data["selected_pages"], [2])
        self.assertEqual(data["items"], ["Page 2"])

    @patch("pabasa_app.views._extract_text_from_image", return_value="")
    def test_extract_endpoint_returns_empty_items_without_warning_when_image_ocr_detects_no_text(self, mock_extract_text_from_image):
        image_file = SimpleUploadedFile(
            "scan.png",
            b"not-a-real-image",
            content_type="image/png",
        )

        response = self.client.post(
            reverse("extract_reading_material_file"),
            {"file": image_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["items"], [])
        self.assertEqual(data.get("warnings", []), [])
        self.assertEqual(data.get("warning_message", ""), "")
        mock_extract_text_from_image.assert_called_once()

    @patch("pabasa_app.views._extract_text_from_image", return_value="Alpha beta gamma")
    def test_extract_endpoint_exposes_alias_payload_fields_for_upload_ui(self, mock_extract_text_from_image):
        image_file = SimpleUploadedFile(
            "scan.png",
            b"not-a-real-image",
            content_type="image/png",
        )

        response = self.client.post(
            reverse("extract_reading_material_file"),
            {"file": image_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["items"], ["Alpha", "beta", "gamma"])
        self.assertEqual(data["extracted_items"], ["Alpha", "beta", "gamma"])
        self.assertEqual(data["extractedItems"], ["Alpha", "beta", "gamma"])
        mock_extract_text_from_image.assert_called_once()

    @patch("pabasa_app.views._extract_text_from_image", return_value="Alpha beta gamma")
    @patch("pabasa_app.views._build_extracted_material_items", return_value=("word", []))
    def test_extract_endpoint_returns_warning_response_when_extracted_text_cannot_be_split(self, mock_build_extracted_material_items, mock_extract_text_from_image):
        image_file = SimpleUploadedFile(
            "scan.png",
            b"not-a-real-image",
            content_type="image/png",
        )

        response = self.client.post(
            reverse("extract_reading_material_file"),
            {"file": image_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["items"], ["Alpha", "beta", "gamma"])
        self.assertTrue(any("could not be converted" in warning.lower() for warning in data.get("warnings", [])))
        mock_extract_text_from_image.assert_called_once()
        mock_build_extracted_material_items.assert_called_once()

    @patch("pabasa_app.views._build_extracted_material_items", side_effect=RuntimeError("boom"))
    def test_extract_endpoint_returns_warning_response_when_item_building_fails(self, mock_build_extracted_material_items):
        image_file = SimpleUploadedFile(
            "scan.png",
            b"not-a-real-image",
            content_type="image/png",
        )

        response = self.client.post(
            reverse("extract_reading_material_file"),
            {"file": image_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["items"], [])
        self.assertTrue(any("could not be processed" in warning.lower() for warning in data.get("warnings", [])))
        mock_build_extracted_material_items.assert_called_once()

    @patch("pabasa_app.views._extract_text_from_image", return_value="Alpha beta gamma")
    @patch("pabasa_app.views._build_extracted_material_items", return_value=("word", []))
    def test_extract_endpoint_falls_back_to_text_items_when_server_returns_no_items(self, mock_build_extracted_material_items, mock_extract_text_from_image):
        image_file = SimpleUploadedFile(
            "scan.png",
            b"not-a-real-image",
            content_type="image/png",
        )

        response = self.client.post(
            reverse("extract_reading_material_file"),
            {"file": image_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["items"], ["Alpha", "beta", "gamma"])
        mock_extract_text_from_image.assert_called_once()
        mock_build_extracted_material_items.assert_called_once()

    @patch("pabasa_app.views._extract_text_from_image", return_value={"text": "Line one\nLine two\n\nLine three", "layout": []})
    def test_extract_endpoint_preserves_newlines_for_ocr_text(self, mock_extract_text_from_image):
        image_file = SimpleUploadedFile(
            "scan.png",
            b"not-a-real-image",
            content_type="image/png",
        )

        response = self.client.post(
            reverse("extract_reading_material_file"),
            {"file": image_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("Line one\nLine two", data["text"])
        self.assertIn("\n\nLine three", data["text"])
        mock_extract_text_from_image.assert_called_once()

    @patch("pabasa_app.views._extract_text_from_image", return_value={"text": "", "layout": []})
    def test_extract_endpoint_returns_warning_when_image_ocr_yields_no_text(self, mock_extract_text_from_image):
        image_file = SimpleUploadedFile(
            "scan.png",
            b"not-a-real-image",
            content_type="image/png",
        )

        response = self.client.post(
            reverse("extract_reading_material_file"),
            {"file": image_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["items"], [])
        self.assertTrue(data.get("warnings") or data.get("warning_message"))
        mock_extract_text_from_image.assert_called_once()

    def test_fallback_material_items_preserve_paragraph_blocks(self):
        text = "First line\nSecond line\n\nThird line"
        self.assertEqual(_fallback_material_items_from_text(text), ["First line Second line", "Third line"])


class PrincipalReportsExportTests(TestCase):
    def test_default_timezone_is_asia_manila(self):
        self.assertEqual(settings.TIME_ZONE, "Asia/Manila")

    def setUp(self):
        self.user = User.objects.create(
            custom_id=f"ADM-{uuid.uuid4().hex[:8].upper()}",
            role="admin",
            first_name="Principal",
            last_name="User",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="principal@example.com",
            password_hash="hashed-password",
        )
        session = self.client.session
        session["user_id"] = self.user.id
        session["user_role"] = self.user.role
        session["first_name"] = self.user.first_name
        session["last_name"] = self.user.last_name
        session["email"] = self.user.email
        session["custom_id"] = self.user.custom_id
        session.save()

    def test_principal_reports_pdf_export_returns_pdf_response(self):
        response = self.client.get(reverse("principal_reports"), {"report_type": "school", "export": "pdf"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_principal_reports_pdf_export_includes_summary_overview(self):
        response = self.client.get(reverse("principal_reports"), {"report_type": "school", "export": "pdf"})

        self.assertEqual(response.status_code, 200)
        reader = PdfReader(BytesIO(response.content))
        extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

        self.assertTrue(extracted_text or response.content.startswith(b"%PDF"))


class PrincipalReportsPreviewTests(TestCase):
    def setUp(self):
        unique_suffix = uuid.uuid4().hex[:8].upper()
        self.principal = User.objects.create(
            custom_id=f"PRN-{unique_suffix}",
            role="principal",
            first_name="Jobelyn",
            last_name="Valdez",
            middle_initial="A",
            suffix="",
            sex="female",
            birth_month=6,
            birth_day=3,
            birth_year=1980,
            email="principal-preview@example.com",
            password_hash=make_password("Principal@123"),
        )
        self.teacher = User.objects.create(
            custom_id=f"TCH-{unique_suffix}",
            role="teacher",
            first_name="Rowan",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="teacher-preview@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )
        self.student = User.objects.create(
            custom_id=f"STD-{unique_suffix}",
            role="student",
            first_name="Ava",
            last_name="Learner",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=2,
            birth_day=2,
            birth_year=2012,
            email="student-preview@example.com",
            password_hash=make_password("student-password"),
            grade_level="Grade 2",
        )
        self.section = Section.objects.create(
            class_code=f"G2-{unique_suffix}",
            class_name="Grade 2 Preview",
            header="Reading Class",
            description="Preview section",
            teacher=self.teacher,
            is_active=True,
            subject="Reading",
            students=[{
                "student_id": self.student.id,
                "custom_id": self.student.custom_id,
                "first_name": self.student.first_name,
                "last_name": self.student.last_name,
                "email": self.student.email,
                "joined_at": timezone.now().isoformat(),
                "is_active": True,
            }],
        )
        self.assessment = Assessment.objects.create(
            title="Preview Assessment",
            code="ASM-PRV1",
            assessment_type="word",
            status="published",
            teacher=self.teacher,
            section=self.section,
            is_active=True,
            attempt_no=1,
        )
        self.assessment.record_attempt(
            self.student,
            status="completed",
            total_score=87,
            accuracy=90,
            pronunciation_score=84,
            completed_at=timezone.now(),
        )
        session = self.client.session
        session["user_id"] = self.principal.id
        session["user_role"] = self.principal.role
        session["first_name"] = self.principal.first_name
        session["last_name"] = self.principal.last_name
        session["email"] = self.principal.email
        session["custom_id"] = self.principal.custom_id
        session.save()

    def test_principal_reports_preview_shows_live_assessment_data(self):
        response = self.client.get(reverse("principal_reports"), {"report_type": "assessment"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assessment Report")
        self.assertContains(response, "Preview Assessment")
        self.assertContains(response, "87.0%")
        self.assertContains(response, "100%")

    def test_principal_reports_excel_export_still_returns_csv_response(self):
        response = self.client.get(reverse("principal_reports"), {"report_type": "assessment", "export": "excel"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment; filename=", response["Content-Disposition"])

    def test_principal_reports_page_uses_a_single_report_workflow(self):
        response = self.client.get(reverse("principal_reports"), {"report_type": "assessment"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a report")
        self.assertNotContains(response, "Recently Generated Reports")

    def test_principal_reports_disables_grade_filter_for_non_grade_reports(self):
        response = self.client.get(reverse("principal_reports"), {"report_type": "school"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="gradeLevel"')
        self.assertContains(response, 'disabled')

    def test_principal_reports_preview_uses_distinct_headers_for_each_report_type(self):
        school_response = self.client.get(reverse("principal_reports"), {"report_type": "school"})
        grade_response = self.client.get(reverse("principal_reports"), {"report_type": "grade"})
        assessment_response = self.client.get(reverse("principal_reports"), {"report_type": "assessment"})

        self.assertEqual(school_response.status_code, 200)
        self.assertEqual(grade_response.status_code, 200)
        self.assertEqual(assessment_response.status_code, 200)
        self.assertContains(school_response, "School Name")
        self.assertContains(grade_response, "Grade")
        self.assertContains(assessment_response, "Assessment")

    def test_principal_reports_export_buttons_submit_current_report_selection(self):
        response = self.client.get(reverse("principal_reports"), {"report_type": "assessment"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="export"')
        self.assertContains(response, 'value="pdf"')
        self.assertContains(response, 'value="excel"')


class LiveAssessmentStartTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            custom_id=f"TCH-{uuid.uuid4().hex[:8].upper()}",
            role="teacher",
            first_name="Tina",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=5,
            birth_day=10,
            birth_year=1988,
            email="live-teacher@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )
        self.student = User.objects.create(
            custom_id=f"STD-{uuid.uuid4().hex[:8].upper()}",
            role="student",
            first_name="Lia",
            last_name="Student",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=6,
            birth_day=2,
            birth_year=2012,
            email="live-student@example.com",
            password_hash=make_password("student-password"),
            grade_level="Grade 2",
        )
        self.section = Section.objects.create(
            class_code=f"LIV-{uuid.uuid4().hex[:6].upper()}",
            class_name="Live Assessment Class",
            header="Reading",
            description="Live assessment test class",
            teacher=self.teacher,
            is_active=True,
            subject="Reading",
            students=[{
                "student_id": self.student.id,
                "custom_id": self.student.custom_id,
                "first_name": self.student.first_name,
                "last_name": self.student.last_name,
                "email": self.student.email,
                "joined_at": timezone.now().isoformat(),
                "is_active": True,
            }],
        )
        self.material = Material.objects.create(
            title="Live Assessment Material",
            code="MAT-LIVE-1",
            item_type="word",
            type="assessment",
            status="published",
            teacher=self.teacher,
            section=self.section,
            is_active=True,
        )
        self.course = Course.objects.create(
            code=f"CRS-{uuid.uuid4().hex[:6].upper()}",
            title="Live Course",
            description="Course for live assessment tests",
            teacher=self.teacher,
            is_active=True,
        )
        self.course.sections.add(self.section)
        self.course.materials.add(self.material)

        session = self.client.session
        session["user_id"] = self.teacher.id
        session["user_role"] = self.teacher.role
        session["first_name"] = self.teacher.first_name
        session["last_name"] = self.teacher.last_name
        session["email"] = self.teacher.email
        session["custom_id"] = self.teacher.custom_id
        session.save()

    def test_teacher_can_start_live_assessment_and_notify_students(self):
        response = self.client.post(
            reverse("start_live_assessment"),
            json.dumps({
                "course_id": self.course.id,
                "material_id": self.material.id,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertIn("session", body)
        self.assertTrue(body["session"]["url"])

        session = LiveAssessmentSession.objects.filter(id=body["session"]["id"]).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, 'waiting')
        self.assertEqual(session.student_count, 1)

        notif = Notification.objects.filter(recipient=self.student).order_by("-created_at").first()
        self.assertIsNotNone(notif)
        self.assertIn("live", notif.title.lower())
        self.assertIn("/dashboard/live-assessment/", notif.action_url)
        self.assertIn("live_session_id=", notif.action_url)

    def test_teacher_start_live_assessment_closes_existing_active_session(self):
        existing = LiveAssessmentSession.objects.create(
            id=uuid.uuid4().hex,
            teacher=self.teacher,
            course=self.course,
            material=self.material,
            student_ids=[self.student.id],
            student_count=1,
            status='waiting',
            countdown_seconds=10,
        )

        response = self.client.post(
            reverse("start_live_assessment"),
            json.dumps({
                "course_id": self.course.id,
                "material_id": self.material.id,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])

        existing.refresh_from_db()
        self.assertEqual(existing.status, 'ended')
        self.assertIsNotNone(existing.ends_at)
        self.assertEqual(existing.student_ids, [self.student.id])
        self.assertTrue(any(
            'Existing live assessment session closed automatically before starting a new session.' in entry.get('message', '')
            for entry in existing.activity_log or []
        ))

        new_session = LiveAssessmentSession.objects.filter(id=body["session"]["id"]).first()
        self.assertIsNotNone(new_session)
        self.assertNotEqual(existing.id, new_session.id)
        self.assertEqual(new_session.status, 'waiting')

    def test_live_assessment_end_action_sets_ends_at_and_student_states(self):
        session = LiveAssessmentSession.objects.create(
            id=uuid.uuid4().hex,
            teacher=self.teacher,
            course=self.course,
            material=self.material,
            student_ids=[self.student.id],
            student_count=1,
            status='started',
            countdown_seconds=0,
            start_at=timezone.now() - timedelta(seconds=10),
            student_states={
                str(self.student.id): {
                    'status': 'reading',
                    'progress': 0.5,
                    'connection_status': 'connected',
                }
            },
        )

        response = self.client.post(
            reverse("live_assessment_session_action", kwargs={"session_id": session.id}),
            json.dumps({"action": "end"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["session"]["status"], 'ended')

        session.refresh_from_db()
        self.assertEqual(session.status, 'ended')
        self.assertIsNotNone(session.ends_at)
        self.assertEqual(session.student_states[str(self.student.id)]["status"], 'completed')
        self.assertEqual(session.student_states[str(self.student.id)]["connection_status"], 'disconnected')

    def test_teacher_end_waiting_live_assessment_session(self):
        session = LiveAssessmentSession.objects.create(
            id=uuid.uuid4().hex,
            teacher=self.teacher,
            course=self.course,
            material=self.material,
            student_ids=[self.student.id],
            student_count=1,
            status='waiting',
            countdown_seconds=10,
        )

        response = self.client.post(
            reverse("live_assessment_session_action", kwargs={"session_id": session.id}),
            json.dumps({"action": "end"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["session"]["status"], 'ended')

        session.refresh_from_db()
        self.assertEqual(session.status, 'ended')
        self.assertIsNotNone(session.ends_at)

    def test_stale_live_assessment_session_auto_ends_on_poll(self):
        session = LiveAssessmentSession.objects.create(
            id=uuid.uuid4().hex,
            teacher=self.teacher,
            course=self.course,
            material=self.material,
            student_ids=[self.student.id],
            student_count=1,
            status='waiting',
            countdown_seconds=10,
        )
        LiveAssessmentSession.objects.filter(id=session.id).update(created_at=timezone.now() - timedelta(hours=25))

        student_client = Client()
        student_session = student_client.session
        student_session['user_id'] = self.student.id
        student_session['user_role'] = 'student'
        student_session['first_name'] = self.student.first_name
        student_session['last_name'] = self.student.last_name
        student_session['email'] = self.student.email
        student_session['custom_id'] = self.student.custom_id
        student_session.save()

        response = student_client.get(reverse("live_assessment_session_state", kwargs={"session_id": session.id}))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["session"]["status"], 'ended')

        session.refresh_from_db()
        self.assertEqual(session.status, 'ended')
        self.assertIsNotNone(session.ends_at)

    def test_live_assessment_session_state_api_returns_200_after_session_started(self):
        session = LiveAssessmentSession.objects.create(
            id=uuid.uuid4().hex,
            teacher=self.teacher,
            course=self.course,
            material=self.material,
            student_ids=[self.student.id],
            student_count=1,
            status='started',
            countdown_seconds=3,
            start_at=timezone.now() - timedelta(seconds=1),
        )

        response = self.client.get(reverse("live_assessment_session_state", kwargs={"session_id": session.id}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["session"]["status"], 'started')
        self.assertIn('reader_url', data["session"])

    def test_student_can_publish_live_assessment_state_updates(self):
        session = LiveAssessmentSession.objects.create(
            id=uuid.uuid4().hex,
            teacher=self.teacher,
            course=self.course,
            material=self.material,
            student_ids=[self.student.id],
            student_count=1,
            status='started',
            countdown_seconds=0,
            start_at=timezone.now() - timedelta(seconds=10),
            student_states={str(self.student.id): {'status': 'waiting', 'progress': 0, 'connection_status': 'waiting'}},
        )

        student_client = Client()
        student_session = student_client.session
        student_session['user_id'] = self.student.id
        student_session['user_role'] = 'student'
        student_session['first_name'] = self.student.first_name
        student_session['last_name'] = self.student.last_name
        student_session['email'] = self.student.email
        student_session['custom_id'] = self.student.custom_id
        student_session.save()

        response = student_client.post(
            reverse('live_assessment_student_state_update', kwargs={'session_id': session.id}),
            json.dumps({
                'status': 'reading',
                'items_completed': 2,
                'items_total': 6,
                'progress': 0.33,
                'elapsed_seconds': 12,
                'current_item': 'cat',
                'final_score': 88,
                'connection_status': 'connected',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['success'])
        session.refresh_from_db()
        student_state = session.student_states[str(self.student.id)]
        self.assertEqual(student_state['status'], 'reading')
        self.assertEqual(student_state['items_completed'], 2)
        self.assertEqual(student_state['items_total'], 6)
        self.assertEqual(student_state['progress'], 0.33)
        self.assertEqual(student_state['elapsed_seconds'], 12)
        self.assertEqual(student_state['final_score'], 88)
        self.assertEqual(student_state['connection_status'], 'connected')

    def test_record_assessment_completion_updates_live_session_score(self):
        session = LiveAssessmentSession.objects.create(
            id=uuid.uuid4().hex,
            teacher=self.teacher,
            course=self.course,
            material=self.material,
            student_ids=[self.student.id],
            student_count=1,
            status='started',
            countdown_seconds=0,
            start_at=timezone.now() - timedelta(seconds=10),
            student_states={str(self.student.id): {'status': 'reading', 'progress': 0.5, 'connection_status': 'connected'}},
        )

        student_client = Client()
        student_session = student_client.session
        student_session['user_id'] = self.student.id
        student_session['user_role'] = 'student'
        student_session['first_name'] = self.student.first_name
        student_session['last_name'] = self.student.last_name
        student_session['email'] = self.student.email
        student_session['custom_id'] = self.student.custom_id
        student_session.save()

        response = student_client.post(
            reverse('record_assessment_completion'),
            json.dumps({
                'material_id': f'material-{self.material.id}',
                'activity_type': 'assessment',
                'class_code': self.section.class_code,
                'live_session_id': session.id,
                'scores': {
                    'fluency_score': 90,
                    'accuracy': 88,
                    'pronunciation_score': 86,
                    'time_score': 94,
                    'duration_seconds': 15,
                    'word_count': 18,
                    'transcript': 'cat dog',
                    'speech_recognition_used': True,
                },
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        session.refresh_from_db()
        self.assertEqual(session.student_states[str(self.student.id)]['final_score'], 89)

    def test_teacher_can_pause_and_resume_live_assessment_session(self):
        session = LiveAssessmentSession.objects.create(
            id=uuid.uuid4().hex,
            teacher=self.teacher,
            course=self.course,
            material=self.material,
            student_ids=[self.student.id],
            student_count=1,
            status='started',
            countdown_seconds=0,
            start_at=timezone.now() - timedelta(seconds=10),
            student_states={str(self.student.id): {'status': 'reading', 'progress': 0}},
        )

        response = self.client.post(
            reverse("live_assessment_session_action", kwargs={"session_id": session.id}),
            json.dumps({"action": "pause"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        pause_body = response.json()
        self.assertTrue(pause_body["success"])
        self.assertEqual(pause_body["session"]["status"], 'paused')
        session.refresh_from_db()
        self.assertEqual(session.status, 'paused')
        self.assertEqual(session.student_states[str(self.student.id)]["status"], 'paused')
        self.assertEqual(session.student_states[str(self.student.id)]["previous_status"], 'reading')

        response = self.client.post(
            reverse("live_assessment_session_action", kwargs={"session_id": session.id}),
            json.dumps({"action": "resume"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        resume_body = response.json()
        self.assertTrue(resume_body["success"])
        self.assertEqual(resume_body["session"]["status"], 'started')
        session.refresh_from_db()
        self.assertEqual(session.status, 'started')
        self.assertEqual(session.student_states[str(self.student.id)]["status"], 'reading')
        self.assertNotIn('previous_status', session.student_states[str(self.student.id)])

    def test_save_settings_persists_selection_and_notifies_students_for_waiting_room(self):
        session = LiveAssessmentSession.objects.create(
            id=uuid.uuid4().hex,
            teacher=self.teacher,
            course=self.course,
            material=self.material,
            student_ids=[],
            student_count=0,
            status='waiting',
            countdown_seconds=10,
        )

        response = self.client.post(
            reverse("live_assessment_session_action", kwargs={"session_id": session.id}),
            json.dumps({
                "action": "save_settings",
                "selected_student_ids": [self.student.id],
                "countdown_seconds": 5,
                "timing_mode": "none",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])

        session.refresh_from_db()
        self.assertEqual(session.student_ids, [self.student.id])
        self.assertEqual(session.student_count, 1)
        self.assertEqual(session.countdown_seconds, 5)
        self.assertEqual(session.status, 'waiting')
        self.assertIn(str(self.student.id), session.student_states)
        self.assertEqual(session.student_states[str(self.student.id)]['status'], 'waiting')

        notif = Notification.objects.filter(recipient=self.student).order_by('-created_at').first()
        self.assertIsNotNone(notif)
        self.assertIn('/waiting/', notif.action_url)
        self.assertIn('live-assessment', notif.action_url)


class PrincipalAccountBootstrapTests(TestCase):
    def test_login_recreates_missing_principal_account_once(self):
        self.assertFalse(User.objects.filter(custom_id=PRINCIPAL_DEFAULT_CUSTOM_ID).exists())

        response = self.client.post(
            reverse("login_user"),
            {
                "custom_id": PRINCIPAL_DEFAULT_CUSTOM_ID,
                "password": PRINCIPAL_DEFAULT_PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        principal = User.objects.get(custom_id=PRINCIPAL_DEFAULT_CUSTOM_ID)
        self.assertEqual(principal.role, "principal")
        self.assertTrue(check_password(PRINCIPAL_DEFAULT_PASSWORD, principal.password_hash))
        self.assertEqual(User.objects.filter(custom_id=PRINCIPAL_DEFAULT_CUSTOM_ID).count(), 1)

        second_response = self.client.post(
            reverse("login_user"),
            {
                "custom_id": PRINCIPAL_DEFAULT_CUSTOM_ID,
                "password": PRINCIPAL_DEFAULT_PASSWORD,
            },
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertTrue(second_response.json()["success"])
        self.assertEqual(User.objects.filter(custom_id=PRINCIPAL_DEFAULT_CUSTOM_ID).count(), 1)


class ProfileUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            custom_id="TCH-0001",
            role="teacher",
            first_name="Old",
            last_name="Name",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="old@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = self.user.id
        session["user_role"] = self.user.role
        session["first_name"] = self.user.first_name
        session["last_name"] = self.user.last_name
        session["email"] = self.user.email
        session["custom_id"] = self.user.custom_id
        session.save()

    def test_profile_page_includes_hidden_save_flag(self):
        response = self.client.get(reverse("profile"))

        self.assertContains(response, 'name="save_account_details" value="true"', html=False)

    def test_profile_post_updates_user_record(self):
        response = self.client.post(
            reverse("profile"),
            {
                "save_account_details": "true",
                "first_name": "New",
                "last_name": "Name",
                "middle_initial": "Q",
                "suffix": "Jr.",
                "email": "new@example.com",
                "bio": "Updated bio",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success"], True)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "New")
        self.assertEqual(self.user.last_name, "Name")
        self.assertEqual(self.user.middle_initial, "Q")
        self.assertEqual(self.user.suffix, "Jr.")
        self.assertEqual(self.user.email, "new@example.com")
        self.assertIn({"profile_info": {"bio": "Updated bio"}}, self.user.tags)


class MaterialCreationTests(TestCase):
    def test_add_reading_material_saves_selected_filipino_language(self):
        user = User.objects.create(
            custom_id="TCH-0002",
            role="teacher",
            first_name="Language",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="language@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Filipino reading",
                "content": "Araw\nBuwan",
                "reading_type": "word",
                "status": "published",
                "usage_type": "practice",
                "class_code": "",
                "language": "Filipino",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        material = Material.objects.latest("id")
        self.assertEqual(material.content_json.get("language"), "Filipino")
        self.assertEqual(material.type, "assessment")
        self.assertEqual(material.source_type, "shared")

    def test_material_response_payload_preserves_saved_language(self):
        material = Material.objects.create(
            teacher=self.teacher,
            title="Language reading",
            item_type="word",
            prompt_text="Araw",
            content_text="Araw",
            content_json={"items": ["Araw"], "language": "Filipino"},
            type="assessment",
            source_type="shared",
            status="published",
            is_active=True,
        )

        payload = _material_response_payload(material)

        self.assertEqual(payload["language"], "Filipino")

    def test_material_saved_language_display_uses_saved_value_or_not_set(self):
        material = Material.objects.create(
            teacher=self.teacher,
            title="Language reading",
            item_type="word",
            prompt_text="Araw",
            content_text="Araw",
            content_json={"items": ["Araw"], "language": "Filipino"},
            type="assessment",
            source_type="shared",
            status="published",
            is_active=True,
        )

        self.assertEqual(material.get_saved_language_display(), "Filipino")

        material.content_json = {"items": ["Araw"], "language": "English"}
        material.save(update_fields=["content_json", "updated_at"])
        self.assertEqual(material.get_saved_language_display(), "English")

        legacy_material = Material.objects.create(
            teacher=self.teacher,
            title="Legacy reading",
            item_type="word",
            prompt_text="Araw",
            content_text="Araw",
            content_json={},
            type="assessment",
            source_type="shared",
            status="published",
            is_active=True,
        )

        self.assertEqual(legacy_material.get_saved_language_display(), "Not Set")

    def test_add_reading_material_response_includes_shared_source_type(self):
        user = User.objects.create(
            custom_id="TCH-0003",
            role="teacher",
            first_name="Source",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="source@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Shared reading",
                "content": "Araw\nBuwan",
                "reading_type": "word",
                "status": "published",
                "usage_type": "assessment",
                "source_type": "shared",
                "class_code": "",
                "language": "Tagalog",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        material = Material.objects.latest("id")
        self.assertEqual(material.type, "assessment")
        self.assertEqual(material.source_type, "shared")

    def test_add_reading_material_reuses_existing_shared_material(self):
        user = User.objects.create(
            custom_id="TCH-0006",
            role="teacher",
            first_name="Reuse",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="reuse@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        existing = Material.objects.create(
            teacher=user,
            title="Shared reading",
            item_type="word",
            prompt_text="Araw",
            content_text="Araw\nBuwan",
            content_json={"items": ["Araw", "Buwan"], "language": "Tagalog"},
            type="assessment",
            source_type="shared",
            status="published",
            is_active=True,
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Shared reading",
                "content": "Araw\nBuwan",
                "reading_type": "word",
                "status": "published",
                "usage_type": "assessment",
                "source_type": "shared",
                "source_material_id": existing.id,
                "class_code": "",
                "language": "Tagalog",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertTrue(payload["reused"])
        self.assertEqual(payload["created_count"], 0)
        self.assertEqual(payload["material_ids"], [existing.id])
        self.assertEqual(Material.objects.filter(source_type="shared", title="Shared reading").count(), 1)

    @patch("pabasa_app.views._compute_teacher_overview")
    def test_add_reading_material_reuse_skips_overview(self, mock_overview):
        user = User.objects.create(
            custom_id="TCH-0008",
            role="teacher",
            first_name="ReuseOverview",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="reuse-overview@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        existing = Material.objects.create(
            teacher=user,
            title="Shared reading",
            item_type="word",
            prompt_text="Araw",
            content_text="Araw\nBuwan",
            content_json={"items": ["Araw", "Buwan"], "language": "Tagalog"},
            type="assessment",
            source_type="shared",
            status="published",
            is_active=True,
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Shared reading",
                "content": "Araw\nBuwan",
                "reading_type": "word",
                "status": "published",
                "usage_type": "assessment",
                "source_type": "shared",
                "source_material_id": existing.id,
                "class_code": "",
                "language": "Tagalog",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        mock_overview.assert_not_called()

    def test_add_reading_material_saves_vowel_and_vc_items_as_vowel(self):
        user = User.objects.create(
            custom_id="TCH-0007",
            role="teacher",
            first_name="Vowel",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="vowel@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Vowel reading",
                "content": "a\nbe\nmi",
                "reading_type": "word",
                "status": "published",
                "usage_type": "assessment",
                "class_code": "",
                "language": "English",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])

        material = Material.objects.latest("id")
        self.assertEqual(material.item_type, "vowel")
        self.assertEqual(material.content_json.get("items"), ["a", "be", "mi"])

    def test_add_reading_material_saves_multiple_paragraph_items(self):
        user = User.objects.create(
            custom_id="TCH-0003",
            role="teacher",
            first_name="Paragraph",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="paragraph@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Paragraph reading",
                "content": "First paragraph text.\n\nSecond paragraph text.",
                "reading_type": "paragraph",
                "status": "published",
                "usage_type": "practice",
                "class_code": "",
                "language": "English",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])

        material = Material.objects.latest("id")
        self.assertEqual(material.item_type, "paragraph")
        self.assertEqual(material.content_json.get("items"), ["First paragraph text.", "Second paragraph text."])

    def test_add_reading_material_saves_separate_sentence_items_from_multiline_content(self):
        user = User.objects.create(
            custom_id="TCH-0004",
            role="teacher",
            first_name="Sentence",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="sentence@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Sentence reading",
                "content": "First sentence.\nSecond sentence.\nThird sentence.",
                "reading_type": "sentence",
                "status": "published",
                "usage_type": "assessment",
                "class_code": "",
                "language": "English",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])

        material = Material.objects.latest("id")
        self.assertEqual(material.item_type, "sentence")
        self.assertEqual(material.content_json.get("items"), ["First sentence.", "Second sentence.", "Third sentence."])

    @patch("pabasa_app.views._compute_teacher_overview")
    def test_add_reading_material_skips_overview_by_default(self, mock_overview):
        user = User.objects.create(
            custom_id="TCH-0004",
            role="teacher",
            first_name="Fast",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="fast@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Fast create",
                "content": "alpha",
                "reading_type": "word",
                "status": "published",
                "usage_type": "practice",
                "class_code": "",
                "language": "English",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        mock_overview.assert_not_called()

    def test_add_reading_material_saves_shared_source_type(self):
        user = User.objects.create(
            custom_id="TCH-0005",
            role="teacher",
            first_name="Shared",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="shared@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["first_name"] = user.first_name
        session["last_name"] = user.last_name
        session["email"] = user.email
        session["custom_id"] = user.custom_id
        session.save()

        response = self.client.post(
            reverse("add_reading_material"),
            json.dumps({
                "title": "Shared reading",
                "content": "Araw\nBuwan",
                "reading_type": "word",
                "status": "published",
                "usage_type": "practice",
                "class_code": "",
                "language": "Tagalog",
                "source_type": "shared",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["material"]["source_type"], "shared")

        material = Material.objects.latest("id")
        self.assertEqual(material.source_type, "shared")

    def test_teacher_courses_api_includes_material_source_type(self):
        teacher = User.objects.create(
            custom_id="TCH-0004",
            role="teacher",
            first_name="Course",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="course@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        section = Section.objects.create(
            class_code="CRS-1001",
            class_name="Course 1",
            header="Reading Class",
            description="",
            teacher=teacher,
            subject="Reading",
        )
        student = User.objects.create(
            custom_id="STD-1001",
            role="student",
            first_name="Metric",
            last_name="Student",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=2015,
            email="metric.student@example.com",
            password_hash="hashed-password",
        )
        section.students = [{
            "student_id": student.id,
            "custom_id": student.custom_id,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "email": student.email,
            "is_active": True,
        }]
        section.save(update_fields=["students"])
        course = Course.objects.create(
            code="C-1001",
            title="Shared Course",
            description="",
            teacher=teacher,
        )
        course.sections.add(section)

        material = Material.objects.create(
            title="Imported reading",
            item_type="word",
            content_text="Araw",
            content_json={"items": ["Araw"], "language": "English"},
            type="practice",
            source_type="shared",
            status="published",
            difficulty_level="",
            is_active=True,
            section=section,
        )
        course.materials.add(material)
        assessment = Assessment.objects.create(
            title="Course assessment",
            code="ASM-1001",
            assessment_type="word",
            status="published",
            teacher=teacher,
            section=section,
            is_active=True,
            attempt_no=1,
        )
        course.assessments.add(assessment)
        Assessment.objects.create(
            title="Material progress",
            code="ASM-1002",
            assessment_type="word",
            status="published",
            teacher=teacher,
            section=section,
            material=material,
            student=student,
            attempt_status="completed",
            is_active=True,
            attempt_no=1,
            items_completed=2,
            total_score=100,
        )

        session = self.client.session
        session["user_id"] = teacher.id
        session["user_role"] = teacher.role
        session["first_name"] = teacher.first_name
        session["last_name"] = teacher.last_name
        session["email"] = teacher.email
        session["custom_id"] = teacher.custom_id
        session.save()

        response = self.client.get(reverse("get_teacher_courses_api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        course_payload = next(item for item in payload["courses"] if item["id"] == course.id)
        material_payload = next(item for item in course_payload["materials"] if item["id"] == material.id)
        self.assertEqual(material_payload["source_type"], "shared")
        self.assertTrue(material_payload["is_shared_material"])
        self.assertEqual(course_payload["metrics"], {
            "sections": 1,
            "assessments": 1,
            "materials": 1,
            "students": 1,
            "average_progress": 100.0,
        })

    def test_teacher_courses_api_preserves_saved_material_language(self):
        teacher = User.objects.create(
            custom_id="TCH-0012",
            role="teacher",
            first_name="Language",
            last_name="Owner",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="language-owner@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        section = Section.objects.create(
            class_code="LANG-1001",
            class_name="Language Class",
            header="Reading Class",
            description="",
            teacher=teacher,
            subject="Reading",
        )
        course = Course.objects.create(
            code="C-LANG-1",
            title="Language Course",
            description="",
            teacher=teacher,
        )
        course.sections.add(section)
        material = Material.objects.create(
            teacher=teacher,
            title="Language reading",
            item_type="word",
            content_text="Araw",
            content_json={"items": ["Araw"], "language": "Tagalog"},
            type="assessment",
            source_type="personal",
            status="published",
            is_active=True,
            section=section,
        )
        course.materials.add(material)

        session = self.client.session
        session["user_id"] = teacher.id
        session["user_role"] = teacher.role
        session["first_name"] = teacher.first_name
        session["last_name"] = teacher.last_name
        session["email"] = teacher.email
        session["custom_id"] = teacher.custom_id
        session.save()

        response = self.client.get(reverse("get_teacher_courses_api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        course_payload = next(item for item in payload["courses"] if item["id"] == course.id)
        material_payload = next(item for item in course_payload["materials"] if item["id"] == material.id)
        self.assertEqual(material_payload["language"], "Tagalog")
        self.assertEqual(material_payload["content_json"]["language"], "Tagalog")

    def test_teacher_courses_api_keeps_personal_materials_unmarked_as_shared(self):
        current_teacher = User.objects.create(
            custom_id="TCH-0012",
            role="teacher",
            first_name="Current",
            last_name="Owner",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="current-owner@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        other_teacher = User.objects.create(
            custom_id="TCH-0013",
            role="teacher",
            first_name="Other",
            last_name="Owner",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="other-owner@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        course = Course.objects.create(
            code="C-PERSONAL-1",
            title="Personal Course",
            description="",
            teacher=current_teacher,
        )
        material = Material.objects.create(
            teacher=other_teacher,
            title="Private reading",
            item_type="word",
            content_text="Araw",
            content_json={"items": ["Araw"], "language": "Tagalog"},
            type="assessment",
            source_type="personal",
            status="published",
            is_active=True,
        )
        course.materials.add(material)

        session = self.client.session
        session["user_id"] = current_teacher.id
        session["user_role"] = current_teacher.role
        session["first_name"] = current_teacher.first_name
        session["last_name"] = current_teacher.last_name
        session["email"] = current_teacher.email
        session["custom_id"] = current_teacher.custom_id
        session.save()

        response = self.client.get(reverse("get_teacher_courses_api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        course_payload = next(item for item in payload["courses"] if item["id"] == course.id)
        material_payload = next(item for item in course_payload["materials"] if item["id"] == material.id)
        self.assertEqual(material_payload["source_type"], "personal")
        self.assertEqual(material_payload["material_source"], "personal")
        self.assertFalse(material_payload["is_shared_material"])

    def test_delete_course_removes_course_and_related_records(self):
        teacher = User.objects.create(
            custom_id="TCH-0014",
            role="teacher",
            first_name="Delete",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="delete-course@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        section = Section.objects.create(
            class_code="DEL-1001",
            class_name="Delete Course Section",
            header="Reading Class",
            description="",
            teacher=teacher,
            subject="Reading",
        )
        course = Course.objects.create(
            code="C-DELETE-1",
            title="Delete Course",
            description="",
            teacher=teacher,
        )
        course.sections.add(section)
        material = Material.objects.create(
            teacher=teacher,
            title="Course material",
            item_type="word",
            content_text="Araw",
            content_json={"items": ["Araw"], "language": "Tagalog"},
            type="assessment",
            source_type="personal",
            status="published",
            is_active=True,
        )
        assessment = Assessment.objects.create(
            title="Course assessment",
            code="ASM-DELETE-1",
            assessment_type="word",
            status="published",
            teacher=teacher,
            section=section,
            is_active=True,
            attempt_no=1,
        )
        course.materials.add(material)
        course.assessments.add(assessment)

        session = self.client.session
        session["user_id"] = teacher.id
        session["user_role"] = teacher.role
        session["first_name"] = teacher.first_name
        session["last_name"] = teacher.last_name
        session["email"] = teacher.email
        session["custom_id"] = teacher.custom_id
        session.save()

        response = self.client.post(
            reverse("delete_course"),
            json.dumps({"course_id": course.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertFalse(Course.objects.filter(id=course.id).exists())
        self.assertFalse(material.refresh_from_db().is_active)
        self.assertFalse(assessment.refresh_from_db().is_active)

    def test_delete_course_accepts_prefixed_course_id(self):
        teacher = User.objects.create(
            custom_id="TCH-0015",
            role="teacher",
            first_name="Delete",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="delete-course-prefixed@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        course = Course.objects.create(
            code="C-DELETE-2",
            title="Delete Course Prefixed",
            description="",
            teacher=teacher,
        )

        session = self.client.session
        session["user_id"] = teacher.id
        session["user_role"] = teacher.role
        session["first_name"] = teacher.first_name
        session["last_name"] = teacher.last_name
        session["email"] = teacher.email
        session["custom_id"] = teacher.custom_id
        session.save()

        response = self.client.post(
            reverse("delete_course"),
            json.dumps({"course_id": f"course-{course.id}"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertFalse(Course.objects.filter(id=course.id).exists())

    def test_shared_courses_api_includes_own_shared_materials_without_personal_rows(self):
        current_teacher = User.objects.create(
            custom_id="TCH-0010",
            role="teacher",
            first_name="Current",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="current-shared@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        other_teacher = User.objects.create(
            custom_id="TCH-0011",
            role="teacher",
            first_name="Other",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="other-shared@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        current_course = Course.objects.create(
            code="C-CURRENT-1",
            title="Current Course",
            description="",
            teacher=current_teacher,
        )
        other_course = Course.objects.create(
            code="C-OTHER-1",
            title="Other Course",
            description="",
            teacher=other_teacher,
        )
        personal_material = Material.objects.create(
            teacher=current_teacher,
            title="Legacy private reading",
            item_type="word",
            content_text="Araw",
            content_json={"items": ["Araw"], "language": "Tagalog"},
            type="assessment",
            source_type="personal",
            status="published",
            is_active=True,
        )
        current_shared_material = Material.objects.create(
            teacher=current_teacher,
            title="Current shared reading",
            item_type="word",
            content_text="Buwan",
            content_json={"items": ["Buwan"], "language": "Tagalog"},
            type="assessment",
            source_type="shared",
            status="published",
            is_active=True,
        )
        shared_material = Material.objects.create(
            teacher=other_teacher,
            title="Original shared reading",
            item_type="word",
            content_text="Araw",
            content_json={"items": ["Araw"], "language": "Tagalog"},
            type="assessment",
            source_type="shared",
            status="published",
            is_active=True,
        )
        current_course.materials.add(personal_material, current_shared_material)
        other_course.materials.add(shared_material)

        session = self.client.session
        session["user_id"] = current_teacher.id
        session["user_role"] = current_teacher.role
        session["first_name"] = current_teacher.first_name
        session["last_name"] = current_teacher.last_name
        session["email"] = current_teacher.email
        session["custom_id"] = current_teacher.custom_id
        session.save()

        response = self.client.get(reverse("get_teacher_courses_api"), {"shared": "true"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        course_ids = {course["id"] for course in payload["courses"]}
        self.assertIn(current_course.id, course_ids)
        self.assertIn(other_course.id, course_ids)
        material_ids = {
            material["id"]
            for course in payload["courses"]
            for material in course["materials"]
        }
        self.assertNotIn(personal_material.id, material_ids)
        self.assertIn(current_shared_material.id, material_ids)
        self.assertIn(shared_material.id, material_ids)

    def test_courses_template_uses_selected_source_type_for_new_materials(self):
        template_path = Path(settings.BASE_DIR) / "pabasa_app" / "templates" / "pabasa_app" / "courses.html"
        template_content = template_path.read_text(encoding="utf-8")

        self.assertIn("const sourceType = ", template_content)
        self.assertIn("source_type: sourceType", template_content)
        self.assertNotIn("const sourceType = 'shared';", template_content)

    def test_add_material_to_course_response_includes_material_source_type(self):
        teacher = User.objects.create(
            custom_id="TCH-0006",
            role="teacher",
            first_name="Attach",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="attach@example.com",
            password_hash="hashed-password",
            teacher_role="Teacher",
        )
        section = Section.objects.create(
            class_code="ATT-1001",
            class_name="Attach 1",
            header="Reading Class",
            description="",
            teacher=teacher,
            subject="Reading",
        )
        course = Course.objects.create(
            code="ATT-C1",
            title="Attach Course",
            description="",
            teacher=teacher,
        )
        course.sections.add(section)
        material = Material.objects.create(
            title="Persistent shared reading",
            item_type="word",
            content_text="Araw",
            content_json={"items": ["Araw"], "language": "Tagalog"},
            type="assessment",
            source_type="shared",
            status="published",
            difficulty_level="",
            is_active=True,
            section=section,
            teacher=teacher,
        )

        session = self.client.session
        session["user_id"] = teacher.id
        session["user_role"] = teacher.role
        session["first_name"] = teacher.first_name
        session["last_name"] = teacher.last_name
        session["email"] = teacher.email
        session["custom_id"] = teacher.custom_id
        session.save()

        response = self.client.post(
            reverse("add_material_to_course"),
            json.dumps({"course_id": course.id, "material_id": material.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["material"]["source_type"], "shared")
        self.assertEqual(payload["material"]["material_source"], "shared")
        self.assertTrue(payload["material"]["is_shared_material"])


class PracticeReaderMaterialTests(TestCase):
    def setUp(self):
        self.student = User.objects.create(
            custom_id="STD-PRACT",
            role="student",
            first_name="Practice",
            last_name="Student",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=2012,
            email="practice-student@example.com",
            password_hash=make_password("student-password"),
            grade_level="Grade 1",
        )
        session = self.client.session
        session["user_id"] = self.student.id
        session["user_role"] = self.student.role
        session["first_name"] = self.student.first_name
        session["last_name"] = self.student.last_name
        session["email"] = self.student.email
        session["custom_id"] = self.student.custom_id
        session.save()

    def test_word_reader_receives_active_published_practice_items(self):
        Material.objects.create(
            title="Easy syllables",
            item_type="word",
            content_text="HA\nhe\nhi\nho\nhu",
            content_json={"source": "admin_practice", "difficulty": "easy", "items": ["HA", "he", "hi", "ho", "hu"]},
            status="published",
            difficulty_level="easy",
            is_active=True,
        )
        Material.objects.create(
            title="Draft syllables",
            item_type="word",
            content_text="draft",
            content_json={"items": ["draft"]},
            status="draft",
            difficulty_level="easy",
            is_active=True,
        )

        response = self.client.get(reverse("practice_word_page"), {"difficulty": "easy"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="practiceMaterialsData"', html=False)
        self.assertContains(response, '"items": ["HA", "he", "hi", "ho", "hu"]', html=False)
        self.assertNotContains(response, "Draft syllables")

    def test_word_reader_parses_comma_separated_content_text_when_json_items_missing(self):
        Material.objects.create(
            title="Comma syllables",
            item_type="word",
            content_text="HA, he, hi, ho, hu",
            content_json={},
            status="published",
            difficulty_level="easy",
            is_active=True,
        )

        response = self.client.get(reverse("practice_word_page"), {"difficulty": "easy"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"items": ["HA", "he", "hi", "ho", "hu"]', html=False)

    def test_practice_completion_records_student_done_status(self):
        material = Material.objects.create(
            title="Completion syllables",
            item_type="word",
            content_text="HA\nhe",
            content_json={"items": ["HA", "he"]},
            type="practice",
            status="published",
            difficulty_level="easy",
            is_active=True,
        )

        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "material_id": f"practice-{material.id}",
                "activity_type": "practice",
                "stars_earned": 20,
                "items_completed": 2,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["material_id"], f"practice-{material.id}")
        self.assertEqual(payload["status"], "Done")

        material.refresh_from_db()
        completion = material.content_json["student_completions"][str(self.student.id)]
        self.assertEqual(completion["status"], "completed")
        self.assertEqual(completion["stars_earned"], 20)
        self.assertEqual(completion["items_completed"], 2)
        self.assertEqual(material.status, "published")

    def test_practice_completion_saves_detailed_results_metrics(self):
        material = Material.objects.create(
            title="Scored practice",
            item_type="word",
            content_text="HA\nhe",
            content_json={"items": ["HA", "he"]},
            type="practice",
            status="published",
            difficulty_level="easy",
            is_active=True,
        )

        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "material_id": f"practice-{material.id}",
                "activity_type": "practice",
                "stars_earned": 20,
                "items_completed": 2,
                "correct_responses": 2,
                "incorrect_responses": 0,
                "reading_time_seconds": 45,
                "attempt_number": 1,
                "total_practice_items": 2,
                "total_read_words": 2,
                "total_skipped_words": 0,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])

        material.refresh_from_db()
        completion = material.content_json["student_completions"][str(self.student.id)]
        self.assertEqual(completion["score"], 100)
        self.assertEqual(completion["accuracy"], 100)
        self.assertEqual(completion["correct_responses"], 2)
        self.assertEqual(completion["incorrect_responses"], 0)
        self.assertEqual(completion["reading_time_seconds"], 45)
        self.assertEqual(completion["attempt_number"], 1)
        self.assertEqual(completion["total_practice_items"], 2)
        self.assertEqual(completion["total_read_words"], 2)
        self.assertEqual(completion["total_skipped_words"], 0)

    def test_color_mode_replay_never_reduces_saved_stars(self):
        material = Material.objects.create(
            title="Color score protection",
            item_type="word",
            content_text="HA\nhe\nhi\nho\nhu",
            content_json={"mode": "color", "difficulty": "easy", "level": "level_1"},
            type="practice",
            status="published",
            difficulty_level="easy",
            is_active=True,
        )
        endpoint = reverse("record_assessment_completion")
        base_payload = {
            "material_id": f"practice-{material.id}",
            "activity_type": "practice",
            "game_mode": "color",
            "items_completed": 5,
        }

        first = self.client.post(endpoint, data=json.dumps({**base_payload, "stars_earned": 50}), content_type="application/json")
        replay = self.client.post(endpoint, data=json.dumps({**base_payload, "stars_earned": 20}), content_type="application/json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        material.refresh_from_db()
        completion = material.content_json["student_completions"][str(self.student.id)]
        self.assertEqual(completion["stars_earned"], 50)

    def _hunt_material(self, level="level_1"):
        return Material.objects.create(
            title=f"Hunt {level}", item_type="word", content_text="one\ntwo\nthree\nfour\nfive",
            content_json={"mode": "hunt", "difficulty": "easy", "level": level},
            type="practice", status="published", difficulty_level="easy", is_active=True,
        )

    def _award_hunt(self, material, points):
        stars = 3 if points >= 8 else 2 if points >= 5 else 1
        return self.client.post(reverse("award_hunt_mode_stars"), data=json.dumps({
            "student_id": self.student.id, "level_id": f"practice-{material.id}",
            "total_points": points, "percentage": points * 10, "earned_stars": stars,
        }), content_type="application/json")

    def test_hunt_star_first_completion(self):
        payload = self._award_hunt(self._hunt_material(), 5).json()
        self.assertEqual((payload["earned_stars"], payload["star_delta"], payload["best_stars"]), (2, 2, 2))
        self.assertEqual((payload["total_stars_earned"], payload["available_stars"]), (2, 2))

    def test_hunt_star_improved_replay(self):
        material = self._hunt_material()
        self._award_hunt(material, 5)
        payload = self._award_hunt(material, 8).json()
        self.assertEqual((payload["star_delta"], payload["best_stars"], payload["available_stars"]), (1, 3, 3))

    def test_hunt_star_equal_replay(self):
        material = self._hunt_material()
        self._award_hunt(material, 5)
        payload = self._award_hunt(material, 7).json()
        self.assertEqual((payload["star_delta"], payload["best_stars"], payload["available_stars"]), (0, 2, 2))

    def test_hunt_star_lower_replay(self):
        material = self._hunt_material()
        self._award_hunt(material, 8)
        payload = self._award_hunt(material, 2).json()
        self.assertEqual((payload["star_delta"], payload["best_stars"], payload["available_stars"]), (0, 3, 3))

    def test_hunt_stars_are_independent_per_level(self):
        first = self._hunt_material("level_1")
        second = self._hunt_material("level_2")
        self._award_hunt(first, 5)
        payload = self._award_hunt(second, 8).json()
        self.assertEqual((payload["star_delta"], payload["total_stars_earned"], payload["available_stars"]), (3, 5, 5))

    def test_hunt_star_endpoint_requires_authenticated_student(self):
        material = self._hunt_material()
        self.client.logout()
        response = self._award_hunt(material, 5)
        self.assertIn(response.status_code, {302, 401, 403})

    def test_practice_results_route_redirects_to_shared_practice_flow(self):
        material = Material.objects.create(
            title="Results practice",
            item_type="word",
            content_text="HA\nhe",
            content_json={
                "items": ["HA", "he"],
                "student_completions": {
                    str(self.student.id): {
                        "student_id": self.student.id,
                        "status": "completed",
                        "completed_at": timezone.now().isoformat(),
                        "score": 80,
                        "accuracy": 80,
                        "correct_responses": 2,
                        "incorrect_responses": 1,
                        "reading_time_seconds": 60,
                        "attempt_number": 1,
                    }
                },
            },
            type="practice",
            status="published",
            difficulty_level="easy",
            is_active=True,
        )

        response = self.client.get(reverse("practice_results"), {"id": f"practice-{material.id}"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("practice"))

    def test_progression_page_renders_unlock_states_for_game_levels(self):
        Material.objects.create(
            title="Free Easy Level 1",
            item_type="word",
            content_text="sun",
            content_json={
                "mode": "free",
                "difficulty": "easy",
                "level": "level_1",
                "items": ["sun"],
                "student_completions": {
                    str(self.student.id): {
                        "student_id": self.student.id,
                        "status": "completed",
                        "completed_at": timezone.now().isoformat(),
                        "stars_earned": 3,
                    }
                },
            },
            type="practice",
            status="published",
            difficulty_level="easy",
            is_active=True,
        )
        Material.objects.create(
            title="Free Easy Level 2",
            item_type="word",
            content_text="moon",
            content_json={
                "mode": "free",
                "difficulty": "easy",
                "level": "level_2",
                "items": ["moon"],
            },
            type="practice",
            status="published",
            difficulty_level="easy",
            is_active=True,
        )

        response = self.client.get(reverse("practice_game_progression", args=["free"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Free Mode Adventure")
        self.assertContains(response, "Level 1")
        self.assertContains(response, "Level 2")
        self.assertContains(response, "Complete Level 1 to unlock this level.")

    def test_progression_page_marks_levels_without_content_as_unavailable(self):
        response = self.client.get(reverse("practice_game_progression", args=["free"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Content unavailable")

    def test_progression_page_shows_mode_tutorial_and_how_to_play_button(self):
        response = self.client.get(reverse("practice_game_progression", args=["free"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "How to Play")
        self.assertContains(response, "Welcome to Free Mode! Read the word aloud.")
        self.assertContains(response, 'data-tutorial-mode="free"')

    def test_student_theme_shop_renders_ui_only_catalog(self):
        response = self.client.get(reverse("theme_shop"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Theme Shop")
        self.assertContains(response, "Sky Island")
        self.assertContains(response, "Magic Library")
        self.assertContains(response, "Light and Dark Mode stay separate.")

    def test_theme_unlock_is_charged_once_and_can_be_equipped(self):
        self.student.available_stars = 200
        self.student.unlocked_themes = ["sky"]
        self.student.equipped_theme = "sky"
        self.student.save(update_fields=["available_stars", "unlocked_themes", "equipped_theme", "updated_at"])
        endpoint = reverse("student_theme_action")

        first = self.client.post(endpoint, data=json.dumps({"theme": "forest", "action": "unlock"}), content_type="application/json")
        duplicate = self.client.post(endpoint, data=json.dumps({"theme": "forest", "action": "unlock"}), content_type="application/json")
        equipped = self.client.post(endpoint, data=json.dumps({"theme": "forest", "action": "equip"}), content_type="application/json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(equipped.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.available_stars, 125)
        self.assertIn("forest", self.student.unlocked_themes)
        self.assertEqual(self.student.equipped_theme, "forest")

    def test_tutorial_header_shows_refined_storybook_prompt(self):
        response = self.client.get(reverse("practice_game_progression", args=["free"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quick Guide")
        self.assertContains(response, "Learn at your own pace.")

    def test_first_time_tutorial_overlay_shows_start_button(self):
        response = self.client.get(reverse("practice_game_progression", args=["free"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="tutorial-overlay is-open')
        self.assertContains(response, 'tutorial-start-btn')
        self.student.refresh_from_db()
        self.assertTrue(self.student.preference.get("free_mode_tutorial_seen"))

    def test_tutorial_auto_opens_only_on_first_mode_visit(self):
        first_response = self.client.get(reverse("practice_game_progression", args=["hunt"]))
        second_response = self.client.get(reverse("practice_game_progression", args=["hunt"]))

        self.assertContains(first_response, 'class="tutorial-overlay is-open')
        self.assertNotContains(second_response, 'class="tutorial-overlay is-open')

    def test_seen_tutorial_overlay_does_not_auto_open_after_new_session(self):
        self.student.preference = {"free_mode_tutorial_seen": True}
        self.student.save(update_fields=["preference", "updated_at"])
        new_client = Client()
        session = new_client.session
        session["user_id"] = self.student.id
        session["user_role"] = self.student.role
        session["first_name"] = self.student.first_name
        session["last_name"] = self.student.last_name
        session["email"] = self.student.email
        session["custom_id"] = self.student.custom_id
        session.save()

        response = new_client.get(reverse("practice_game_progression", args=["free"]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="tutorial-overlay is-open')
        self.assertContains(response, 'tutorial-start-btn')

    def test_mark_tutorial_seen_sets_user_preference_flag(self):
        response = self.client.post(reverse("practice_mark_tutorial_seen", args=["color"]))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.session.get("color_mode_tutorial_seen"))
        self.student.refresh_from_db()
        self.assertTrue(self.student.preference.get("color_mode_tutorial_seen"))

    def test_practice_reader_template_shows_results_breakdown(self):
        response = self.client.get(reverse("practice_word_page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Score Breakdown")
        self.assertContains(response, "Total Practice Items")
        self.assertContains(response, "Total Read Words")
        self.assertContains(response, "Total Skipped Words")

    def test_practice_hub_marks_only_completed_student_material_done(self):
        material = Material.objects.create(
            title="Done for one student",
            item_type="word",
            content_text="HA\nhe",
            content_json={
                "items": ["HA", "he"],
                "student_completions": {
                    str(self.student.id): {
                        "student_id": self.student.id,
                        "status": "completed",
                        "completed_at": timezone.now().isoformat(),
                    }
                },
            },
            type="practice",
            status="published",
            difficulty_level="easy",
            is_active=True,
        )

        response = self.client.get(reverse("practice"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'"id": "practice-{material.id}"', html=False)
        self.assertContains(response, '"status": "Done"', html=False)
        self.assertContains(response, '"is_done": true', html=False)

        other_student = User.objects.create(
            custom_id="STD-OTHER-PRACT",
            role="student",
            first_name="Other",
            last_name="Student",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=1,
            birth_day=1,
            birth_year=2012,
            email="other-practice-student@example.com",
            password_hash=make_password("student-password"),
            grade_level="Grade 1",
        )
        session = self.client.session
        session["user_id"] = other_student.id
        session["user_role"] = other_student.role
        session["first_name"] = other_student.first_name
        session["last_name"] = other_student.last_name
        session["email"] = other_student.email
        session["custom_id"] = other_student.custom_id
        session.save()

        response = self.client.get(reverse("practice"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'"id": "practice-{material.id}"', html=False)
        self.assertContains(response, '"status": "published"', html=False)
        self.assertContains(response, '"is_done": false', html=False)


class AdminPracticeMaterialFormTests(TestCase):
    def test_easy_items_require_at_least_one_item(self):
        form = AdminPracticeMaterialForm(data={
            'mode': 'free',
            'difficulty_level': 'easy',
            'level': 'level_1',
            'status': 'draft',
            'content_text': '',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('content_text', form.errors)

    def test_color_mode_items_are_limited_to_five_per_difficulty_and_level(self):
        form = AdminPracticeMaterialForm(data={
            'mode': 'color',
            'difficulty_level': 'easy',
            'level': 'level_1',
            'status': 'draft',
            'content_text': 'one\ntwo\nthree\nfour\nfive\nsix',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('content_text', form.errors)

    def test_duplicate_mode_difficulty_and_level_is_rejected(self):
        Material.objects.create(
            title='Existing Practice',
            item_type='word',
            prompt_text='',
            content_text='sun',
            content_json={'mode': 'free', 'difficulty': 'easy', 'level': 'level_1'},
            type='practice',
            status='published',
            difficulty_level='easy',
            is_active=True,
        )

        form = AdminPracticeMaterialForm(data={
            'mode': 'free',
            'difficulty_level': 'easy',
            'level': 'level_1',
            'status': 'draft',
            'content_text': 'sun',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)

    def test_medium_sentence_keeps_commas_inside_the_sentence(self):
        form = AdminPracticeMaterialForm(data={
            'mode': 'free',
            'difficulty_level': 'medium',
            'level': 'level_1',
            'status': 'draft',
            'content_text': 'The cat ran home, and it slept on the couch.',
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.practice_items(), ['The cat ran home, and it slept on the couch.'])

    def test_occupied_levels_are_detected_for_a_configuration(self):
        Material.objects.create(
            title='Existing Practice',
            item_type='word',
            prompt_text='',
            content_text='sun',
            content_json={'mode': 'free', 'difficulty': 'easy', 'level': 'level_1'},
            type='practice',
            status='published',
            difficulty_level='easy',
            is_active=True,
        )

        form = AdminPracticeMaterialForm()
        occupied_levels = form.get_occupied_levels('free', 'easy')

        self.assertEqual(occupied_levels, ['level_1'])


class PracticeAccessControlTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            custom_id="TCH-PRACT",
            role="teacher",
            first_name="Practice",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="practice-teacher@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )
        self.admin = User.objects.create(
            custom_id="ADM-PRACT",
            role="admin",
            first_name="Practice",
            last_name="Admin",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="practice-admin@example.com",
            password_hash=make_password("admin-password"),
        )

    def test_teacher_is_redirected_from_practice_reader(self):
        session = self.client.session
        session["user_id"] = self.teacher.id
        session["user_role"] = self.teacher.role
        session["first_name"] = self.teacher.first_name
        session["last_name"] = self.teacher.last_name
        session["email"] = self.teacher.email
        session["custom_id"] = self.teacher.custom_id
        session.save()

        response = self.client.get(reverse("practice_word_page"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("auth"), response.url)

    def test_admin_can_open_practice_assessment_management(self):
        session = self.client.session
        session["user_id"] = self.admin.id
        session["user_role"] = self.admin.role
        session["first_name"] = self.admin.first_name
        session["last_name"] = self.admin.last_name
        session["email"] = self.admin.email
        session["custom_id"] = self.admin.custom_id
        session.save()

        response = self.client.get(reverse("admin_practice_assessment"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Practice Content")


class SettingsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            custom_id="STD-0001",
            role="student",
            first_name="Settings",
            last_name="User",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=2012,
            email="settings@example.com",
            password_hash=make_password("old-password"),
            grade_level="Grade 1",
        )
        session = self.client.session
        session["user_id"] = self.user.id
        session["user_role"] = self.user.role
        session["first_name"] = self.user.first_name
        session["last_name"] = self.user.last_name
        session["email"] = self.user.email
        session["custom_id"] = self.user.custom_id
        session.save()

    def test_settings_password_change_updates_user_hash(self):
        response = self.client.post(
            reverse("settings"),
            {
                "settings_action": "change_password",
                "current_password": "old-password",
                "new_password": "new-password",
                "confirm_password": "new-password",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password changed successfully.")

        self.user.refresh_from_db()
        self.assertTrue(check_password("new-password", self.user.password_hash))

    def test_settings_saves_push_notification_preferences(self):
        response = self.client.post(
            reverse("settings"),
            {
                "settings_action": "save_notifications",
                "push_enabled": "on",
                "new_materials": "on",
                "progress_updates": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Push notification preferences saved.")

        self.user.refresh_from_db()
        self.assertIn({
            "notification_settings": {
                "push_enabled": True,
                "email_notifications": False,
                "weekly_digest_enabled": False,
                "new_materials": True,
                "reading_reminders": False,
                "progress_updates": True,
            }
        }, self.user.tags)

    def test_settings_saves_weekly_digest_preference(self):
        response = self.client.post(
            reverse("settings"),
            {
                "settings_action": "save_notifications",
                "push_enabled": "on",
                "email_notifications": "on",
                "weekly_digest_enabled": "on",
                "new_materials": "on",
                "reading_reminders": "on",
                "progress_updates": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.preference["notification_settings"]["weekly_digest_enabled"])

        fresh_response = self.client.get(reverse("settings"))
        self.assertEqual(fresh_response.status_code, 200)
        self.assertContains(fresh_response, 'id="weeklyDigestEnabled"')
        self.assertContains(fresh_response, 'name="weekly_digest_enabled" checked')


class AdminSettingsRenderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            custom_id="ADM-9999",
            role="admin",
            first_name="Admin",
            last_name="User",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="admin-settings@example.com",
            password_hash=make_password("admin-password"),
        )
        session = self.client.session
        session["user_id"] = self.user.id
        session["user_role"] = self.user.role
        session["first_name"] = self.user.first_name
        session["last_name"] = self.user.last_name
        session["email"] = self.user.email
        session["custom_id"] = self.user.custom_id
        session.save()

    def test_admin_settings_renders_new_settings_ui(self):
        response = self.client.get(reverse("admin_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pabasa_app/admin_settings.html")
        self.assertContains(response, "Push Notifications")
        self.assertContains(response, "Enable Notifications")
        self.assertContains(response, "Email Notifications")
        self.assertContains(response, "Save Preferences")
        self.assertContains(response, "Change Password")
        self.assertContains(response, "Current Password")
        self.assertContains(response, "New Password")
        self.assertContains(response, "Confirm Password")
        self.assertContains(response, "Update Password")
        self.assertNotContains(response, "Settings placeholder. CRUD is not implemented yet.")


class PrincipalNotificationTests(TestCase):
    def test_notify_principals_creates_in_app_notifications(self):
        principal = User.objects.create(
            custom_id=f"PRN-{uuid.uuid4().hex[:8].upper()}",
            role="principal",
            first_name="Principal",
            last_name="User",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="principal-notify@example.com",
            password_hash=make_password("principal-password"),
        )

        result = _notify_principals("School update", "A principal alert should be stored.", "success")

        self.assertEqual(result, 1)
        self.assertTrue(Notification.objects.filter(recipient=principal, title="School update").exists())

    def test_create_reading_class_notifies_principal(self):
        principal = User.objects.create(
            custom_id=f"PRN-{uuid.uuid4().hex[:8].upper()}",
            role="principal",
            first_name="Principal",
            last_name="User",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="principal-class@example.com",
            password_hash=make_password("principal-password"),
        )
        teacher = User.objects.create(
            custom_id=f"TCH-{uuid.uuid4().hex[:8].upper()}",
            role="teacher",
            first_name="Teacher",
            last_name="User",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="teacher-class@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )
        session = self.client.session
        session["user_id"] = teacher.id
        session["user_role"] = teacher.role
        session["first_name"] = teacher.first_name
        session["last_name"] = teacher.last_name
        session["email"] = teacher.email
        session["custom_id"] = teacher.custom_id
        session.save()

        response = self.client.post(
            reverse("create_reading_class"),
            json.dumps({
                "class_name": "Grade 1A",
                "header": "Reading Class",
                "description": "New class",
                "subject": "Reading",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Notification.objects.filter(recipient=principal, title__icontains="new class").exists())


class PreferenceDeliveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            custom_id="TCH-PREF",
            role="teacher",
            first_name="Pref",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="pref-teacher@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )

    def test_disabled_in_app_alerts_do_not_create_notification_rows(self):
        self.user.preference = {
            "notification_settings": {
                "push_enabled": False,
                "email_notifications": False,
                "weekly_digest_enabled": False,
            }
        }
        self.user.save(update_fields=["preference", "updated_at"])

        result = _create_notification(
            self.user,
            "Hidden alert",
            "This should not be stored.",
            send_email=False,
        )

        self.assertIsNone(result)
        self.assertFalse(Notification.objects.filter(recipient=self.user).exists())

    @patch("pabasa_app.views.send_mail")
    def test_email_alerts_respect_email_preference(self, mock_send_mail):
        self.user.preference = {
            "notification_settings": {
                "push_enabled": True,
                "email_notifications": False,
                "weekly_digest_enabled": False,
            }
        }
        self.user.save(update_fields=["preference", "updated_at"])

        _create_notification(self.user, "Stored only", "No email should be sent.")

        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 1)
        mock_send_mail.assert_not_called()

        self.user.preference["notification_settings"]["email_notifications"] = True
        self.user.save(update_fields=["preference", "updated_at"])
        _create_notification(self.user, "Stored and emailed", "Email should be sent.")

        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 2)
        mock_send_mail.assert_called_once()


class PrincipalSettingsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            custom_id="PRN-SES",
            role="principal",
            first_name="Jobelyn",
            last_name="Valdez",
            middle_initial="A",
            suffix="",
            sex="female",
            birth_month=6,
            birth_day=3,
            birth_year=1980,
            email="principal@example.com",
            password_hash=make_password("old-password"),
        )
        session = self.client.session
        session["user_id"] = self.user.id
        session["user_role"] = self.user.role
        session["first_name"] = self.user.first_name
        session["last_name"] = self.user.last_name
        session["email"] = self.user.email
        session["custom_id"] = self.user.custom_id
        session.save()

    def test_principal_settings_saves_school_information(self):
        response = self.client.post(
            reverse("principal_settings"),
            {
                "settings_action": "save_school_info",
                "school_name": "Example Elementary School",
                "school_code": "EX-001",
                "municipality": "Imus",
                "province": "Cavite",
                "district": "District 5",
                "region": "CALABARZON",
                "address": "Example Street",
                "contact": "0917-123-4567",
                "email": "principal@example.org",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "School information updated.")

        self.user.refresh_from_db()
        self.assertEqual(self.user.preference["principal_school_info"]["name"], "Example Elementary School")
        self.assertEqual(self.user.preference["principal_school_info"]["code"], "EX-001")

    def test_principal_settings_changes_password(self):
        response = self.client.post(
            reverse("principal_settings"),
            {
                "settings_action": "change_password",
                "current_password": "old-password",
                "new_password": "new-password",
                "confirm_password": "new-password",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password changed successfully.")

        self.user.refresh_from_db()
        self.assertTrue(check_password("new-password", self.user.password_hash))

    def test_principal_settings_updates_personal_information(self):
        response = self.client.post(
            reverse("principal_settings"),
            {
                "settings_action": "save_personal_info",
                "first_name": "Maria",
                "last_name": "Cruz",
                "middle_initial": "L",
                "email": "maria.cruz@example.org",
                "contact_number": "09171234567",
                "position": "Principal II",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Personal information updated.")

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Maria")
        self.assertEqual(self.user.last_name, "Cruz")
        self.assertEqual(self.user.middle_initial, "L")
        self.assertEqual(self.user.email, "maria.cruz@example.org")
        self.assertEqual(self.user.contact_no, "09171234567")
        self.assertEqual(self.user.preference["principal_profile_info"]["position"], "Principal II")


class AssessmentCompletionNotificationTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            custom_id="TCH-9001",
            role="teacher",
            first_name="Taylor",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="teacher9001@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )
        self.student = User.objects.create(
            custom_id="STU-9001",
            role="student",
            first_name="Jane",
            last_name="Doe",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=2,
            birth_day=2,
            birth_year=2012,
            email="student9001@example.com",
            password_hash=make_password("student-password"),
        )
        self.admin = User.objects.create(
            custom_id="ADM-9001",
            role="admin",
            first_name="Alex",
            last_name="Admin",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=3,
            birth_day=3,
            birth_year=1985,
            email="admin9001@example.com",
            password_hash=make_password("admin-password"),
        )
        self.principal = User.objects.create(
            custom_id="PRN-9001",
            role="principal",
            first_name="Paula",
            last_name="Principal",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=4,
            birth_day=4,
            birth_year=1980,
            email="principal9001@example.com",
            password_hash=make_password("principal-password"),
        )
        self.section = Section.objects.create(
            teacher=self.teacher,
            class_name="Class A",
            class_code="CLS-A9001",
            subject="Reading",
            is_active=True,
        )
        self.section.add_student(self.student)
        self.assessment = Assessment.objects.create(
            title="Reading Fluency Test",
            code="ASM-9001",
            assessment_type="word",
            content="cat\ndog",
            teacher=self.teacher,
            section=self.section,
            is_active=True,
        )

    def _login_student(self):
        session = self.client.session
        session["user_id"] = self.student.id
        session["user_role"] = self.student.role
        session.save()

    def _login_teacher(self):
        session = self.client.session
        session["user_id"] = self.teacher.id
        session["user_role"] = self.teacher.role
        session.save()

    def _login_admin(self):
        session = self.client.session
        session["user_id"] = self.admin.id
        session["user_role"] = self.admin.role
        session.save()

    def _login_principal(self):
        session = self.client.session
        session["user_id"] = self.principal.id
        session["user_role"] = self.principal.role
        session.save()

    def test_assessment_material_creation_leaves_assessments_table_empty_until_completion(self):
        material = Material.objects.create(
            title="New Assessment Material",
            item_type="word",
            content_text="cat\ndog",
            content_json={"items": ["cat", "dog"]},
            type="assessment",
            status="published",
            is_active=True,
        )

        self.assertIsNone(material.assessment)
        self.assertEqual(Assessment.objects.count(), 0)

        self._login_student()
        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "material_id": f"material-{material.id}",
                "activity_type": "assessment",
                "class_code": self.section.class_code,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        material.refresh_from_db()
        self.assertIsNotNone(material.assessment)
        self.assertEqual(Assessment.objects.count(), 1)
        self.assertEqual(material.assessment.get_student_attempt_count(self.student), 1)

    def test_repeated_assessment_completions_create_separate_assessment_rows(self):
        material = Material.objects.create(
            title="Retake Assessment",
            item_type="word",
            content_text="cat\ndog",
            content_json={"items": ["cat", "dog"]},
            type="assessment",
            status="published",
            is_active=True,
        )
        self._login_student()

        payload = json.dumps({
            "material_id": f"material-{material.id}",
            "activity_type": "assessment",
            "class_code": self.section.class_code,
        })

        first = self.client.post(reverse("record_assessment_completion"), data=payload, content_type="application/json")
        second = self.client.post(reverse("record_assessment_completion"), data=payload, content_type="application/json")

        self.assertTrue(first.json()["success"])
        self.assertTrue(second.json()["success"])

        material.refresh_from_db()
        self.assertIsNotNone(material.assessment)
        self.assertGreaterEqual(Assessment.objects.filter(code__startswith=material.assessment.code).count(), 2)
        attempts = material.assessment.get_attempts(self.student)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[0]["attempt_number"], 1)
        self.assertEqual(attempts[1]["attempt_number"], 2)
        self.assertNotEqual(attempts[0]["attempt_id"], attempts[1]["attempt_id"])

    def test_assessment_completion_creates_teacher_notification(self):
        self._login_student()
        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "assessment_id": f"assessment-{self.assessment.id}",
                "material_id": f"assessment-{self.assessment.id}",
                "activity_type": "assessment",
                "class_code": self.section.class_code,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        notification = Notification.objects.filter(
            recipient=self.teacher,
            created_by=self.student,
            notification_type="assessment",
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn("Jane Doe completed the assessment 'Reading Fluency Test' in Class A.", notification.message)
        self.assertFalse(notification.is_read)

    def test_assessment_completion_saves_scores_and_crla_classification(self):
        self._login_student()
        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "assessment_id": f"assessment-{self.assessment.id}",
                "material_id": f"assessment-{self.assessment.id}",
                "activity_type": "assessment",
                "class_code": self.section.class_code,
                "scores": {
                    "fluency_score": 90,
                    "accuracy": 88,
                    "pronunciation_score": 86,
                    "time_score": 94,
                    "total_score": 89.5,
                    "wpm": 72,
                    "duration_seconds": 15,
                    "word_count": 18,
                    "transcript": "cat dog",
                    "speech_recognition_used": True,
                },
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        self.assessment.refresh_from_db()
        attempt = self.assessment.get_attempts()[-1]
        self.assertEqual(attempt["fluency_score"], 90)
        self.assertEqual(attempt["accuracy"], 88)
        self.assertEqual(attempt["pronunciation_score"], 86)
        self.assertEqual(attempt["time_score"], 94)
        self.assertEqual(attempt["total_score"], 89.5)
        self.assertEqual(attempt["crla_classification"], "Transitioning Readers")
        self.assertEqual(attempt["wpm"], 72)

        self.student.refresh_from_db()
        self.assertEqual(self.student.reading_level, "Transitioning Readers")
        profile = self.student.preference.get("student_profile", {})
        self.assertEqual(profile["accuracy"], "88")
        self.assertEqual(profile["wpm"], "72")
        self.assertEqual(profile["crla_classification"], "Transitioning Readers")

    def test_numeric_material_id_records_assessment_attempt_by_assessment_id(self):
        self._login_student()
        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "material_id": str(self.assessment.id),
                "activity_type": "assessment",
                "class_code": self.section.class_code,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        self.assessment.refresh_from_db()
        self.assertEqual(len(self.assessment.get_attempts(self.student)), 1)
        self.assertEqual(self.assessment.get_student_attempt_count(self.student), 1)

    def test_duplicate_assessment_completion_records_multiple_attempts_with_unique_ids(self):
        self._login_student()
        payload = json.dumps({
            "assessment_id": f"assessment-{self.assessment.id}",
            "material_id": f"assessment-{self.assessment.id}",
            "activity_type": "assessment",
            "class_code": self.section.class_code,
        })

        first = self.client.post(
            reverse("record_assessment_completion"),
            data=payload,
            content_type="application/json",
        )
        second = self.client.post(
            reverse("record_assessment_completion"),
            data=payload,
            content_type="application/json",
        )

        self.assertTrue(first.json()["success"])
        self.assertTrue(second.json()["success"])

        self.assessment.refresh_from_db()
        attempts = self.assessment.get_attempts(self.student)
        self.assertEqual(len(attempts), 2)
        self.assertNotEqual(attempts[0]["attempt_id"], attempts[1]["attempt_id"])
        self.assertEqual(attempts[0]["attempt_number"], 1)
        self.assertEqual(attempts[1]["attempt_number"], 2)

    def test_teacher_update_material_does_not_create_assessment_record_when_none_exists(self):
        teacher = self.teacher
        material = Material.objects.create(
            title="Draft Assessment",
            item_type="word",
            content_text="cat\ndog",
            content_json={"items": ["cat", "dog"]},
            type="assessment",
            status="draft",
            is_active=False,
        )
        self.assertIsNone(material.assessment)

        session = self.client.session
        session["user_id"] = teacher.id
        session["user_role"] = teacher.role
        session.save()

        response = self.client.post(
            reverse("teacher_update_material"),
            data=json.dumps({
                "material_id": f"material-{material.id}",
                "title": "Draft Assessment Updated",
                "content": "cat dog",
                "status": "published",
                "usage_type": "assessment",
                "language": "English",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        material.refresh_from_db()
        self.assertIsNone(material.assessment)
        self.assertEqual(Assessment.objects.filter(title="Draft Assessment Updated").count(), 0)

    def test_numeric_material_id_records_assessment_attempt_by_assessment_id(self):
        self._login_student()
        payload = json.dumps({
            "assessment_id": f"assessment-{self.assessment.id}",
            "material_id": f"assessment-{self.assessment.id}",
            "activity_type": "assessment",
            "class_code": self.section.class_code,
        })
        first = self.client.post(
            reverse("record_assessment_completion"),
            data=payload,
            content_type="application/json",
        )
        second = self.client.post(
            reverse("record_assessment_completion"),
            data=payload,
            content_type="application/json",
        )
        self.assertTrue(first.json()["success"])
        self.assertTrue(second.json()["success"])
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.teacher,
                created_by=self.student,
                notification_type="assessment",
            ).count(),
            1,
        )

    def test_class_materials_only_marks_completed_after_completed_attempt(self):
        self._login_student()

        self.assessment.record_attempt(self.student, status="started")
        response = self.client.get(
            reverse("get_class_materials"),
            {"class_code": self.section.class_code},
        )
        self.assertEqual(response.status_code, 200)
        item = response.json()["materials"]["word"][0]
        self.assertEqual(item["attempt_count"], 1)
        self.assertEqual(item["completed_attempt_count"], 0)
        self.assertFalse(item["student_has_completed"])

        self.assessment.record_attempt(self.student, status="completed")
        response = self.client.get(
            reverse("get_class_materials"),
            {"class_code": self.section.class_code},
        )
        self.assertEqual(response.status_code, 200)
        item = response.json()["materials"]["word"][0]
        self.assertEqual(item["attempt_count"], 2)
        self.assertEqual(item["completed_attempt_count"], 1)
        self.assertTrue(item["student_has_completed"])

    def test_class_materials_include_latest_time_score_for_completed_attempt(self):
        self._login_student()

        self.assessment.record_attempt(
            self.student,
            status="completed",
            time_score=82,
            total_score=88,
        )
        response = self.client.get(
            reverse("get_class_materials"),
            {"class_code": self.section.class_code},
        )

        self.assertEqual(response.status_code, 200)
        item = response.json()["materials"]["word"][0]
        self.assertEqual(item["latest_time_score"], 82)
        self.assertEqual(item["latest_attempt_summary"]["time_score"], 82)

    def test_class_materials_do_not_duplicate_materials_with_assessment_rows(self):
        self._login_student()
        material = Material.objects.create(
            title="Duplicate Prevention Assessment",
            item_type="word",
            content_text="cat\ndog",
            content_json={"items": ["cat", "dog"]},
            type="assessment",
            status="published",
            section=self.section,
            is_active=True,
        )
        self.assertIsNone(material.assessment)

        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "material_id": f"material-{material.id}",
                "activity_type": "assessment",
                "class_code": self.section.class_code,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        response = self.client.get(
            reverse("get_class_materials"),
            {"class_code": self.section.class_code},
        )
        self.assertEqual(response.status_code, 200)
        items = response.json()["materials"]["word"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], f"material-{material.id}")

    def test_teacher_can_fetch_unread_notification(self):
        Notification.objects.create(
            recipient=self.teacher,
            created_by=self.student,
            title="📝 Student Completed an Assessment",
            message="Jane Doe completed the assessment 'Reading Fluency Test' in Class A.",
            notification_type="assessment",
            action_url=f"/dashboard/teacher/students/detail/?student_id={self.student.custom_id}",
        )
        self._login_teacher()
        response = self.client.get(reverse("get_notifications"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["notifications"]), 1)
        self.assertFalse(data["notifications"][0]["is_read"])

    def test_mark_notification_read_endpoint_updates_state(self):
        notification = Notification.objects.create(
            recipient=self.teacher,
            created_by=self.student,
            title="Unread teacher update",
            message="A fresh notification for the shared panel.",
            notification_type="assessment",
        )
        self._login_teacher()

        response = self.client.post(
            reverse("mark_notification_read"),
            data=json.dumps({"notification_id": notification.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_notifications_page_uses_shared_mount_for_all_roles(self):
        for login in (
            self._login_admin,
            self._login_teacher,
            self._login_student,
            self._login_principal,
        ):
            login()
            response = self.client.get(reverse("notifications"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'data-notifications-mount="page"', html=False)

    def test_practice_completion_notifies_admin_in_app_only(self):
        material = Material.objects.create(
            title="Practice Words",
            item_type="word",
            content_text="cat\ndog",
            content_json={"items": ["cat", "dog"]},
            status="published",
            is_active=True,
        )
        self._login_student()
        response = self.client.post(
            reverse("record_assessment_completion"),
            data=json.dumps({
                "material_id": f"material-{material.id}",
                "activity_type": "practice",
                "class_code": self.section.class_code,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        teacher_notification = Notification.objects.filter(
            recipient=self.teacher,
            created_by=self.student,
            notification_type="assessment",
        ).first()
        self.assertIsNone(teacher_notification)

        admin_notification = Notification.objects.filter(
            recipient=self.admin,
            created_by=self.student,
            notification_type="assessment",
        ).first()
        self.assertIsNotNone(admin_notification)
        self.assertIn("Jane Doe read \"Practice Words\"", admin_notification.message)
        self.assertFalse(admin_notification.is_read)


class WeeklyDigestTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            custom_id="TCH-DIGEST",
            role="teacher",
            first_name="Digest",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="digest-teacher@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
            preference={
                "notification_settings": {
                    "push_enabled": True,
                    "email_notifications": True,
                    "weekly_digest_enabled": True,
                }
            },
        )
        self.student = User.objects.create(
            custom_id="STD-DIGEST",
            role="student",
            first_name="Digest",
            last_name="Student",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=2,
            birth_day=2,
            birth_year=2013,
            email="digest-student@example.com",
            password_hash=make_password("student-password"),
        )
        self.section = Section.objects.create(
            teacher=self.teacher,
            class_name="Digest Class",
            class_code="DIG-001",
            subject="Reading",
            is_active=True,
        )
        self.section.add_student(self.student)
        self.assessment = Assessment.objects.create(
            teacher=self.teacher,
            section=self.section,
            title="Digest Assessment",
            code="DIG-ASM-001",
            assessment_type="word",
            content="cat\ndog",
            is_active=True,
        )
        self.start = timezone.now() - timedelta(days=7)
        self.end = timezone.now() + timedelta(seconds=1)
        self.assessment.record_attempt(
            self.student,
            status="completed",
            completed_at=(timezone.now() - timedelta(days=1)).isoformat(),
            total_score=88,
            accuracy=87,
            fluency_score=86,
            pronunciation_score=85,
        )

    @patch("pabasa_app.weekly_digest.send_mail")
    def test_weekly_digest_skips_disabled_user(self, mock_send_mail):
        self.teacher.preference["notification_settings"]["weekly_digest_enabled"] = False
        self.teacher.save(update_fields=["preference", "updated_at"])

        result = send_weekly_digest(self.teacher, self.start, self.end)

        self.assertEqual(result["skipped"], "weekly_digest_disabled")
        mock_send_mail.assert_not_called()

    @patch("pabasa_app.weekly_digest.send_mail")
    def test_teacher_weekly_digest_sends_html_email_and_records_window(self, mock_send_mail):
        result = send_weekly_digest(self.teacher, self.start, self.end)

        self.assertTrue(result["sent"])
        mock_send_mail.assert_called_once()
        email_body = mock_send_mail.call_args[0][1]
        html_body = mock_send_mail.call_args.kwargs["html_message"]
        self.assertIn("Assessments completed by students: 1", email_body)
        self.assertIn("Average class reading performance: 88.0%", email_body)
        self.assertIn("<html", html_body)
        self.assertIn("Your Weekly PABASA Digest", html_body)
        self.assertIn("pabasalogo.png", html_body)
        self.assertIn("Assessments made", html_body)
        self.assertIn("Class average", html_body)

        self.teacher.refresh_from_db()
        digest_meta = self.teacher.preference["weekly_digest"]
        self.assertEqual(digest_meta["last_window_start"], self.start.isoformat())
        self.assertEqual(digest_meta["last_window_end"], self.end.isoformat())

        duplicate = send_weekly_digest(self.teacher, self.start, self.end)
        self.assertEqual(duplicate["skipped"], "duplicate_window")
        mock_send_mail.assert_called_once()

    @patch("pabasa_app.weekly_digest.send_mail")
    def test_student_weekly_digest_sends_html_email(self, mock_send_mail):
        self.student.preference = {
            "notification_settings": {
                "push_enabled": True,
                "email_notifications": True,
                "weekly_digest_enabled": True,
            }
        }
        self.student.save(update_fields=["preference", "updated_at"])

        result = send_weekly_digest(self.student, self.start, self.end)

        self.assertTrue(result["sent"])
        html_body = mock_send_mail.call_args.kwargs["html_message"]
        self.assertIn("Assessments done", html_body)
        self.assertIn("Practice sessions", html_body)
        self.assertIn("Best Assessment", html_body)
        self.assertIn("Pending Assessments", html_body)


class TeacherStudentsDirectoryTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create(
            custom_id="TCH-DIR1",
            role="teacher",
            first_name="Directory",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="directory-teacher@example.com",
            password_hash=make_password("teacher-password"),
            teacher_role="Teacher",
        )
        self.student = User.objects.create(
            custom_id="STD-DIR1",
            role="student",
            first_name="Single",
            last_name="Student",
            middle_initial="",
            suffix="",
            sex="female",
            birth_month=2,
            birth_day=2,
            birth_year=2013,
            email="single-student@example.com",
            password_hash=make_password("student-password"),
        )
        self.section_a = Section.objects.create(
            teacher=self.teacher,
            class_name="Reading One",
            class_code="READ-ONE",
            subject="Reading",
            is_active=True,
        )
        self.section_b = Section.objects.create(
            teacher=self.teacher,
            class_name="Reading Two",
            class_code="READ-TWO",
            subject="Reading",
            is_active=True,
        )
        self.section_a.add_student(self.student)
        self.section_b.add_student(self.student)

        entries = self.section_b.get_enrolled_students()
        entries[0]["student_id"] = str(entries[0]["student_id"])
        self.section_b.students = entries
        self.section_b.save(update_fields=["students", "updated_at"])

        session = self.client.session
        session["user_id"] = self.teacher.id
        session["user_role"] = self.teacher.role
        session["first_name"] = self.teacher.first_name
        session["last_name"] = self.teacher.last_name
        session["email"] = self.teacher.email
        session["custom_id"] = self.teacher.custom_id
        session.save()

    def test_teacher_students_api_returns_one_row_with_joined_classes(self):
        response = self.client.get(reverse("get_teacher_students_api"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["students"]), 1)
        self.assertEqual(data["students"][0]["custom_id"], self.student.custom_id)
        self.assertCountEqual(data["students"][0]["classes"], ["Reading One", "Reading Two"])
        self.assertCountEqual(data["students"][0]["class_codes"], ["READ-ONE", "READ-TWO"])

    def test_teacher_overview_counts_unique_students_across_classes(self):
        response = self.client.get(reverse("get_teacher_overview"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["classes_count"], 2)
        self.assertEqual(data["total_students"], 1)

    def test_teacher_students_api_uses_latest_assessment_classification(self):
        assessment = Assessment.objects.create(
            teacher=self.teacher,
            section=self.section_a,
            title="Oral Reading Check",
            code="ASM-DIR-001",
            assessment_type="paragraph",
            status="published",
            is_active=True,
        )
        assessment.record_attempt(
            self.student,
            status="completed",
            completed_at="2026-06-01T09:00:00+00:00",
            total_score=87,
        )

        response = self.client.get(reverse("get_teacher_students_api"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["students"][0]["level"], "Transitioning Readers")
        self.assertTrue(data["students"][0]["has_completed_assessment"])

    def test_teacher_students_api_uses_adapted_level_from_attempt_history(self):
        word_assessment = Assessment.objects.create(
            teacher=self.teacher,
            section=self.section_a,
            title="Word Reading Check",
            code="ASM-DIR-002",
            assessment_type="word",
            status="published",
            is_active=True,
        )
        word_assessment.record_attempt(
            self.student,
            status="completed",
            completed_at="2026-06-01T09:00:00+00:00",
            total_score=56,
        )

        paragraph_assessment = Assessment.objects.create(
            teacher=self.teacher,
            section=self.section_a,
            title="Paragraph Reading Check",
            code="ASM-DIR-003",
            assessment_type="paragraph",
            status="published",
            is_active=True,
        )
        paragraph_assessment.record_attempt(
            self.student,
            status="completed",
            completed_at="2026-06-02T09:00:00+00:00",
            total_score=80,
        )

        response = self.client.get(reverse("get_teacher_students_api"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["students"][0]["adapted_reading_level"], "Developing")
        self.assertEqual(data["students"][0]["level"], "Transitioning Readers")

    def test_teacher_students_api_exposes_latest_completion_duration(self):
        assessment = Assessment.objects.create(
            teacher=self.teacher,
            section=self.section_a,
            title="Oral Reading Check",
            code="ASM-DIR-002",
            assessment_type="paragraph",
            status="published",
            is_active=True,
        )
        assessment.record_attempt(
            self.student,
            status="completed",
            completed_at="2026-06-01T09:00:00+00:00",
            total_score=87,
            duration_seconds=75,
        )

        response = self.client.get(reverse("get_teacher_students_api"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["students"][0]["duration_seconds"], 75)

    def test_teacher_students_api_returns_pending_without_assessment_data(self):
        response = self.client.get(reverse("get_teacher_students_api"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["students"][0]["level"], "Pending")
        self.assertFalse(data["students"][0]["has_completed_assessment"])

    def test_teacher_course_assessments_api_includes_section_assigned_material_assessments(self):
        course = Course.objects.create(
            teacher=self.teacher,
            title="Course Assigned Material",
            code="CRS-MAT-001",
            description="Course with section-assigned assessment material",
        )
        course.sections.add(self.section_a)

        other_teacher = User.objects.create(
            custom_id="TCH-SHARED",
            role="teacher",
            first_name="Shared",
            last_name="Teacher",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email="shared-teacher@example.com",
            password_hash=make_password("shared-password"),
            teacher_role="Teacher",
        )
        material = Material.objects.create(
            title="Shared Assessment",
            teacher=other_teacher,
            item_type="paragraph",
            type="assessment",
            status="published",
            is_active=True,
        )
        material.assigned_sections.add(self.section_a)

        material.record_assessment_result(
            self.student,
            status="completed",
            completed_at="2026-06-01T09:00:00+00:00",
            accuracy=82,
            wpm=65,
            fluency_score=78,
            pronunciation_score=80,
            time_score=85,
            total_score=83,
        )

        response = self.client.get(
            reverse("get_teacher_assessments_api"),
            {"course_id": course.id},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["assessments"]), 1)
        self.assertEqual(data["assessments"][0]["title"], "Shared Assessment")
        self.assertEqual(data["assessments"][0]["attempt_count"], 1)
        self.assertIn("created_at", data["assessments"][0])
        self.assertIn("updated_at", data["assessments"][0])
        self.assertIsNotNone(data["assessments"][0]["updated_at"])

    def test_students_template_uses_static_renderer_only(self):
        response = self.client.get(reverse("students"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pabasa_app/js/students.js", html=False)
        self.assertNotContains(response, "Students directory: prefer server")

    def test_course_detail_refresh_script_reloads_students_after_assessment_change(self):
        response = self.client.get(reverse("courses"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("async function refreshOpenCourseAfterAssessmentChange", content)
        self.assertIn("loadCourseStudents(openCourseId)", content)
        self.assertIn("Could not refresh course students after assessment change", content)

    def test_course_report_recipients_do_not_use_local_storage_students(self):
        response = self.client.get(reverse("courses"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        helper_start = content.index("async function fetchStudentsForCourse(course)")
        helper_end = content.index("// Course-scoped Reports loader", helper_start)
        helper_body = content[helper_start:helper_end]

        self.assertIn("/dashboard/teacher/students-api/", helper_body)
        self.assertNotIn("pabasa_added_students", helper_body)

    def test_course_update_composer_includes_report_preview_container(self):
        response = self.client.get(reverse("courses"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="courseSelectedStudentReportPreview"', html=False)

    @patch("pabasa_app.views.EmailMultiAlternatives")
    def test_send_course_update_emails_student_and_stores_note(self, mock_email_cls):
        course = Course.objects.create(
            teacher=self.teacher,
            title="Chapter 2",
            code="CRS-TEST-001",
            description="Course update test",
        )
        course.sections.add(self.section_a)
        assessment = Assessment.objects.create(
            teacher=self.teacher,
            section=self.section_a,
            title="Oral Reading Check",
            code="ASM-COURSE-001",
            assessment_type="paragraph",
            status="published",
            is_active=True,
        )
        assessment.record_attempt(
            self.student,
            status="completed",
            completed_at="2026-06-01T09:00:00+00:00",
            accuracy=88,
            wpm=72,
            fluency_score=84,
            pronunciation_score=86,
            time_score=90,
            total_score=87,
            crla_classification="Transitioning Readers",
        )

        response = self.client.post(
            reverse("send_course_update"),
            data=json.dumps({
                "course_id": course.id,
                "student_ids": [self.student.id],
                "update_type": "general",
                "message": "Hello {name}, keep practicing.",
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["sent_count"], 1)
        self.assertTrue(data["report_included"])
        self.assertIn("report_summary", data["sent"][0])
        mock_email_cls.assert_called_once()
        self.assertEqual(mock_email_cls.call_args[0][0], "Student Reading Progress Report – PABASA")
        email_instance = mock_email_cls.return_value
        email_body = mock_email_cls.call_args[0][1]
        self.assertIn("Dear Parent/Guardian", email_body)
        self.assertIn("Attached is the latest Reading Progress Report", email_body)
        self.assertIn("PABASA Team", email_body)
        self.assertNotIn("Reading Performance Report", email_body)
        self.assertNotIn("Accuracy: 88%", email_body)
        self.assertNotIn("Words Per Minute: 72 WPM", email_body)
        email_instance.attach.assert_called_once()
        self.assertEqual(email_instance.attach.call_args[0][0], "Single_Student_reading_report.pdf")
        self.assertEqual(email_instance.attach.call_args[0][2], "application/pdf")
        email_instance.send.assert_called_once_with(fail_silently=False)

        note = Note.objects.get(teacher=self.teacher, student=self.student)
        self.assertEqual(note.note_type, "course_update:general")
        self.assertIn("Chapter 2", note.note_text)
        self.assertIn("Hello Single Student, keep practicing.", note.note_text)
        self.assertIn("Reading Performance Report", note.note_text)
        self.assertIn("Suggested Home Support", note.note_text)

    @patch("pabasa_app.views.EmailMultiAlternatives")
    def test_send_course_update_includes_baseline_message_when_metrics_missing(self, mock_email_cls):
        course = Course.objects.create(
            teacher=self.teacher,
            title="Chapter 3",
            code="CRS-TEST-002",
            description="Missing metrics test",
        )
        course.sections.add(self.section_a)

        response = self.client.post(
            reverse("send_course_update"),
            data=json.dumps({
                "course_id": course.id,
                "student_ids": [self.student.id],
                "update_type": "followup",
                "message": "Hello {name}, we will check your baseline soon.",
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(mock_email_cls.call_args[0][0], "Student Reading Progress Report – PABASA")
        email_body = mock_email_cls.call_args[0][1]
        self.assertIn("Dear Parent/Guardian", email_body)
        self.assertIn("Attached is the latest Reading Progress Report", email_body)
        self.assertIn("PABASA Team", email_body)
        self.assertNotIn("No completed assessment yet", email_body)
        mock_email_cls.return_value.attach.assert_called_once()

        note = Note.objects.get(teacher=self.teacher, student=self.student)
        self.assertIn("No completed assessment yet", note.note_text)

    @patch("pabasa_app.views.EmailMultiAlternatives")
    def test_send_course_update_commendation_sends_certificate_attachment(self, mock_email_cls):
        course = Course.objects.create(
            teacher=self.teacher,
            title="Chapter 5",
            code="CRS-TEST-004",
            description="Commendation test",
        )
        course.sections.add(self.section_a)

        response = self.client.post(
            reverse("send_course_update"),
            data=json.dumps({
                "course_id": course.id,
                "student_ids": [self.student.id],
                "update_type": "commendation",
                "message": "Congratulations {name}!",
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertFalse(response.json()["report_included"])
        self.assertEqual(mock_email_cls.call_args[0][0], "Performance Commendation – PABASA")
        email_body = mock_email_cls.call_args[0][1]
        self.assertIn("Congratulations", email_body)
        self.assertIn("certificate is attached", email_body.lower())
        self.assertIn("outstanding reading performance", email_body.lower())
        self.assertEqual(mock_email_cls.return_value.attach.call_count, 1)
        attachment_name, attachment_bytes, mime_type = mock_email_cls.return_value.attach.call_args.args
        self.assertIn("certificate", attachment_name.lower())
        self.assertEqual(mime_type, "application/pdf")
        self.assertTrue(attachment_bytes)

    @patch("pabasa_app.views.EmailMultiAlternatives")
    def test_send_course_update_assessment_notice_sends_details_without_attachment(self, mock_email_cls):
        course = Course.objects.create(
            teacher=self.teacher,
            title="Chapter 6",
            code="CRS-TEST-005",
            description="Assessment notice test",
        )
        course.sections.add(self.section_a)

        response = self.client.post(
            reverse("send_course_update"),
            data=json.dumps({
                "course_id": course.id,
                "student_ids": [self.student.id],
                "update_type": "assessment",
                "message": "Please prepare for your upcoming reading assessment.",
                "assessment_title": "Oral Reading Check",
                "scheduled_at": "2026-07-10 09:00",
                "reading_material": "The Little Red Hen",
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertFalse(response.json()["report_included"])
        self.assertEqual(mock_email_cls.call_args[0][0], "Scheduled Assessment Notice – PABASA")
        email_body = mock_email_cls.call_args[0][1]
        self.assertIn("Oral Reading Check", email_body)
        self.assertIn("July 10, 2026 at 09:00 AM", email_body)
        self.assertIn("The Little Red Hen", email_body)
        self.assertIn("Please prepare", email_body)
        mock_email_cls.return_value.attach.assert_not_called()

    @patch("pabasa_app.views.EmailMultiAlternatives")
    def test_send_course_update_skips_unenrolled_and_missing_email_students(self, mock_email_cls):
        no_email_student = User.objects.create(
            custom_id="STD-NOEMAIL",
            role="student",
            first_name="No",
            last_name="Email",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=3,
            birth_day=3,
            birth_year=2013,
            email="",
            password_hash=make_password("student-password"),
        )
        outsider = User.objects.create(
            custom_id="STD-OUTSIDE",
            role="student",
            first_name="Outside",
            last_name="Student",
            middle_initial="",
            suffix="",
            sex="male",
            birth_month=4,
            birth_day=4,
            birth_year=2013,
            email="outside@example.com",
            password_hash=make_password("student-password"),
        )
        self.section_a.add_student(no_email_student)
        course = Course.objects.create(
            teacher=self.teacher,
            title="Chapter 4",
            code="CRS-TEST-003",
            description="Skipped recipient test",
        )
        course.sections.add(self.section_a)

        response = self.client.post(
            reverse("send_course_update"),
            data=json.dumps({
                "course_id": course.id,
                "student_ids": [self.student.id, no_email_student.id, outsider.id],
                "update_type": "general",
                "message": "Hello {name}, keep reading.",
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["sent_count"], 1)
        self.assertEqual(len(data["skipped"]), 2)
        self.assertCountEqual([item["reason"] for item in data["skipped"]], ["missing_email", "not_enrolled"])
        mock_email_cls.assert_called_once()
