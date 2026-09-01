import json
import re
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import Material, School, Section, User
from .sound_detective import catalog, validate_configuration
from .views import _sound_detective_launch_url


class SoundDetectiveCatalogTests(SimpleTestCase):
    def test_languages_sets_and_example_metadata(self):
        bank = catalog()
        self.assertEqual(len(bank["English"]["sets"]), 10)
        self.assertEqual(len(bank["Filipino"]["sets"]), 5)
        english_m = bank["English"]["sets"][0]
        monkey = next(item for item in english_m["items"] if item["word"] == "monkey")
        self.assertEqual((english_m["sound"], monkey["position"]), ("/m/", "Beginning"))
        self.assertEqual(monkey["audio_url"], "/static/pabasa_app/images/sound_detective/audio/m.mp3")

    def test_every_target_sound_maps_to_an_existing_phonics_file(self):
        audio_dir = Path(__file__).resolve().parent / "static" / "pabasa_app" / "images" / "sound_detective" / "audio"
        for language in catalog().values():
            for sound_set in language["sets"]:
                expected_name = f"{sound_set['sound'].strip('/')}.mp3"
                self.assertTrue((audio_dir / expected_name).is_file())
                self.assertTrue(all(item["audio_url"].endswith(f"/{expected_name}") for item in sound_set["items"]))

    def test_validation_rejects_cross_set_items(self):
        bank = catalog()
        wrong_id = bank["English"]["sets"][1]["items"][0]["id"]
        with self.assertRaisesMessage(ValueError, "belong to the selected sound set"):
            validate_configuration({"language": "English", "sound_set": "set_1", "selected_word_ids": [wrong_id]})

    def test_validation_returns_authoritative_items(self):
        selected = [item["id"] for item in catalog()["Filipino"]["sets"][4]["items"]]
        result = validate_configuration({"language": "Filipino", "sound_set": "set_5", "selected_word_ids": selected, "number_of_questions": 4})
        self.assertEqual(result["target_sound"], "/k/")
        self.assertEqual(len(result["items"]), 6)
        self.assertTrue(all("/filipino/Set_5/" in item["image_url"] for item in result["items"]))

    def test_every_catalog_set_resolves_its_existing_images(self):
        bank = catalog()
        for language_name, language in bank.items():
            for sound_set in language["sets"]:
                selected_ids = [item["id"] for item in sound_set["items"]]
                result = validate_configuration({
                    "language": language_name,
                    "sound_set": sound_set["id"],
                    "selected_word_ids": selected_ids,
                })
                self.assertEqual(len(result["items"]), len(selected_ids))

        filipino_t = bank["Filipino"]["sets"][2]["items"][-1]
        self.assertEqual(
            filipino_t["image_url"],
            "/static/pabasa_app/images/sound_detective/filipino/Set_5/itik.png",
        )

    def test_launch_url_uses_activity_route_prefixed_material_and_section(self):
        self.assertEqual(
            _sound_detective_launch_url("material-69", 12),
            "/dashboard/assessment/activity/sound-detective/?id=material-69&section_id=12",
        )
        self.assertNotIn("/dashboard/assessment/sound-detective/", _sound_detective_launch_url(69, 12))


class SoundDetectivePageTests(TestCase):
    def setUp(self):
        self.student = User.objects.create(
            custom_id="STD-SOUND-DETECTIVE", role="student", first_name="Sound", last_name="Learner",
            middle_initial="", suffix="", sex="female", birth_month=1, birth_day=1, birth_year=2015,
            email="sound-detective@example.com", password_hash="hashed-password",
        )
        session = self.client.session
        session.update({"user_id": self.student.id, "user_role": "student", "email": self.student.email})
        session.save()

    def test_saved_configuration_reopens_in_student_component(self):
        bank_set = catalog()["English"]["sets"][0]
        content = validate_configuration({"language": "English", "sound_set": "set_1", "selected_word_ids": [item["id"] for item in bank_set["items"]], "number_of_questions": 6})
        content.update({"template_title": "Sound Detective", "template_lesson": "Phonological Awareness"})
        material = Material.objects.create(title="My Sound Detective", item_type="word", type="assessment", source_type="template", status="published", student_access=True, content_json=content)
        route = reverse("sound_detective_page")
        query = {"id": f"material-{material.id}", "section_id": "12"}
        response = self.client.get(route, query)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(route, "/dashboard/assessment/activity/sound-detective/")
        self.assertEqual(self.client.get(f"/dashboard/assessment/sound-detective/?id=material-{material.id}&section_id=12").status_code, 404)
        self.assertTemplateUsed(response, "pabasa_app/sound_detective_page.html")
        self.assertTemplateUsed(response, "pabasa_app/base_dashboard.html")
        self.assertNotContains(response, "/reading_ui/")
        self.assertContains(response, "pabasa_app/js/sound_detective.js")
        rendered = response.content.decode()
        payload_match = re.search(
            r'<script id="sound-detective-data" type="application/json">(.*?)</script>',
            rendered,
            re.S,
        )
        self.assertIsNotNone(payload_match)
        browser_payload = json.loads(payload_match.group(1))
        self.assertIsInstance(browser_payload, dict)
        self.assertEqual(len(browser_payload["items"]), 6)
        self.assertEqual(browser_payload["items"][0]["id"], bank_set["items"][0]["id"])
        self.assertTrue(all(item.get("image_url") and item.get("position") for item in browser_payload["items"]))
        payload = response.context["sound_detective_material_json"]
        self.assertEqual(payload["title"], "My Sound Detective")
        self.assertEqual(payload["material_id"], f"material-{material.id}")
        self.assertEqual(payload["section_id"], "12")
        self.assertEqual(payload["items"][1]["position"], "Beginning")
        self.assertEqual(payload["progress"], {
            "current_index": 0, "completed_items": 0, "activity_completed": False,
            "correct_items": 0,
        })

        progress_url = f'{reverse("sound_detective_progress")}?id=material-{material.id}&section_id=12'
        partial = self.client.post(progress_url, data=json.dumps({
            "current_index": 1, "completed_items": 1, "activity_completed": False,
        }), content_type="application/json")
        self.assertEqual(partial.status_code, 200)
        reopened = self.client.get(route, query)
        self.assertEqual(reopened.context["sound_detective_material_json"]["progress"]["current_index"], 1)
        self.assertEqual(reopened.context["sound_detective_material_json"]["progress"]["correct_items"], 1)
        self.assertFalse(reopened.context["sound_detective_material_json"]["progress"]["activity_completed"])

        for item_number in range(2, 7):
            completed = self.client.post(progress_url, data=json.dumps({
                "current_index": item_number, "completed_items": item_number,
                "activity_completed": item_number == 6,
            }), content_type="application/json")
            self.assertEqual(completed.status_code, 200)
        completed_reopen = self.client.get(route, query)
        self.assertTrue(completed_reopen.context["sound_detective_material_json"]["progress"]["activity_completed"])
        self.assertTrue(completed_reopen.context["sound_detective_material_json"]["completion"]["completed"])
        self.assertEqual(completed_reopen.context["sound_detective_material_json"]["completion"]["correct_items"], 6)
        self.assertEqual(material.assessment_results.filter(student=self.student, attempt_status="completed").count(), 1)
        replay_attempt = self.client.post(progress_url, data=json.dumps({
            "current_index": 0, "completed_items": 0, "correct_items": 0,
            "activity_completed": False,
        }), content_type="application/json")
        self.assertEqual(replay_attempt.status_code, 200)
        self.assertTrue(replay_attempt.json()["already_completed"])
        self.assertEqual(material.assessment_results.filter(student=self.student, attempt_status="completed").count(), 1)

    def test_sound_detective_intro_copies_and_recruitment_buttons_exist(self):
        script_path = Path(__file__).resolve().parent / 'static' / 'pabasa_app' / 'js' / 'sound_detective.js'
        source = script_path.read_text(encoding='utf-8')
        self.assertIn('CASE FILE #001', source)
        self.assertIn('For many years, mysterious sounds have been hiding inside words. Some hide at the beginning. Some hide in the middle. And some hide at the end.', source)
        self.assertIn('We need someone clever enough to find them...', source)
        self.assertIn('could you be the detective we\'re looking for?', source)
        self.assertIn('data.student_name', source)
        self.assertIn('YES! I\'M READY!', source)
        self.assertIn('NO, MAYBE LATER', source)
        self.assertIn('Will you be our Sound Detective?', source)
        self.assertIn("if(introPhase==='newspaper'){renderIntro();return}", source)
        self.assertIn("if(introPhase==='recruitment'){renderRecruitment();return}", source)
        self.assertIn("CASE CLOSED: OFFICIALLY SOLVED", source)
        self.assertIn("Outstanding deduction, Detective!", source)
        self.assertIn("Good investigative effort!", source)


class SoundDetectiveCreationLaunchUrlTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Sound Detective School", code="SDS")
        self.teacher = User.objects.create(
            custom_id="TCH-SOUND-DETECT", role="teacher", first_name="Sound", last_name="Teacher",
            middle_initial="", suffix="", sex="female", birth_month=1, birth_day=1, birth_year=1990,
            email="sound-teacher@example.com", password_hash="hashed-password", teacher_role="Teacher",
            school_record=self.school,
        )
        self.section = Section.objects.create(
            school=self.school, class_code="SD-SECTION", class_name="Sound Detective Class",
            teacher=self.teacher, subject="Reading", grade_level="1", section="A",
        )
        session = self.client.session
        session.update({"user_id": self.teacher.id, "user_role": "teacher", "email": self.teacher.email})
        session.save()

    def test_assessment_card_template_routes_sound_detective_via_canonical_activity_url(self):
        template_path = Path(__file__).resolve().parent / "templates" / "pabasa_app" / "assessment.html"
        template_html = template_path.read_text(encoding="utf-8")

        self.assertIn("const soundDetectiveUrl = \"{% url 'sound_detective_page' %}\";", template_html)
        self.assertIn("isSoundDetective", template_html)
        self.assertIn("/dashboard/assessment/activity/sound-detective/", template_html)
        self.assertNotIn("/dashboard/assessment/sound-detective/", template_html)
        self.assertNotIn("/dashboard/assessment/sound-detective/", template_html)

    def test_sound_detective_template_uses_isolated_activity_shell(self):
        template_path = Path(__file__).resolve().parent / "templates" / "pabasa_app" / "sound_detective_page.html"
        template_html = template_path.read_text(encoding="utf-8")

        self.assertNotIn("extends 'pabasa_app/base_dashboard.html'", template_html)
        self.assertIn("activity-back", template_html)
        self.assertIn("Back to Assessment", template_html)
        self.assertIn("#soundDetectiveGame", template_html)
        self.assertIn("width: 100vw", template_html)
        self.assertIn("height: 100vh", template_html)
        self.assertIn("max-width: 100vw", template_html)
        self.assertIn("max-height: 100vh", template_html)
        self.assertIn("overflow: hidden", template_html)
        self.assertIn("min-height: 100vh", template_html)

    def test_assessment_card_uses_canonical_sound_detective_url_before_generic_word_route(self):
        template_path = Path(__file__).resolve().parent / "templates" / "pabasa_app" / "assessment.html"
        template_html = template_path.read_text(encoding="utf-8")

        self.assertIn("const soundDetectiveUrl = \"{% url 'sound_detective_page' %}\";", template_html)
        self.assertIn("const soundDetectiveMaterialId = String(m.id ?? '').startsWith('material-') ? String(m.id) : `material-${m.id}`;", template_html)
        self.assertIn("isSoundDetective\n                                ? `${soundDetectiveUrl}?id=${encodeURIComponent(soundDetectiveMaterialId)}&section_id=${encodeURIComponent(sectionId)}`", template_html)
        self.assertLess(template_html.index("isSoundDetective"), template_html.index("isLetterSoundMatching"))
        self.assertLess(template_html.index("isSoundDetective"), template_html.index("urlMap[m.category]"))
        self.assertNotIn("/activity/sound-detective/70/", template_html)
        self.assertNotIn("/dashboard/assessment/sound-detective/?id=material-70&section_id=12", template_html)

    def test_newly_created_material_response_and_listing_use_canonical_launch_url(self):
        bank_set = catalog()["English"]["sets"][0]
        configuration = {
            "activity_type": "sound_detective",
            "language": "English",
            "sound_set": "set_1",
            "selected_word_ids": [item["id"] for item in bank_set["items"]],
            "number_of_questions": len(bank_set["items"]),
            "template_title": "Sound Detective",
            "template_lesson": "Phonological Awareness",
            "template_type": "Sound Detective",
            "template_source": "template",
        }
        response = self.client.post(reverse("add_reading_material"), data=json.dumps({
            "title": "Brand-new Sound Detective",
            "reading_type": "word",
            "content": json.dumps(configuration),
            "status": "published",
            "usage_type": "assessment",
            "section_id": self.section.id,
            "language": "English",
            "source_type": "template",
            "template_title": "Sound Detective",
            "template_lesson": "Phonological Awareness",
        }), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        created = response.json()["material"]
        material_id = created["raw_id"]
        expected = (
            f"/dashboard/assessment/activity/sound-detective/?id=material-{material_id}"
            f"&section_id={self.section.id}"
        )
        self.assertNotIn("launch_url", created)
        self.assertNotIn("launch_url", next(item for item in self.client.get(reverse("get_class_materials"), {"section_id": self.section.id}).json()["all_materials"] if item["raw_id"] == material_id))

        listing = self.client.get(reverse("get_class_materials"), {"section_id": self.section.id})
        self.assertEqual(listing.status_code, 200)
        listed = next(item for item in listing.json()["all_materials"] if item["raw_id"] == material_id)
        self.assertEqual(listed.get("launch_url", expected), expected)
        self.assertNotIn("/dashboard/assessment/sound-detective/", expected)
