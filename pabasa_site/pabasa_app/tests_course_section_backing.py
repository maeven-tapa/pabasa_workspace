import json
import uuid

from django.test import TestCase
from django.urls import reverse

from .models import (
    Assessment, Course, Enrollment, Material, School, SchoolCalendar, Section,
    SupplementaryMaterialPublication, User,
)


def test_section_create(**kwargs):
    school = kwargs.pop("school", None)
    if school is None:
        suffix = uuid.uuid4().hex.upper()
        school = School.objects.create(name=f"Fixture School {suffix}", code=f"FIXTURE-{suffix}")
    return Section.objects.create(school=school, **kwargs)


class SectionBackedCoursesRegressionTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Section Course School", code="SCS-001")
        self.teacher = User.objects.create(
            custom_id="TCH-SECTION-COURSES", role="teacher",
            first_name="Section", last_name="Owner", middle_initial="", suffix="",
            sex="female", birth_month=1, birth_day=1, birth_year=1990,
            email="section-courses@example.com", password_hash="hashed-password",
            teacher_role="Teacher",
            school_record=self.school,
        )
        self.section = test_section_create(
            class_code="SEC-COURSES", class_name="Grade 2", header="Reading Class",
            description="", teacher=self.teacher, subject="English", is_active=True,
        )
        session = self.client.session
        session.update({
            "user_id": self.teacher.id, "user_role": "teacher",
            "email": self.teacher.email, "custom_id": self.teacher.custom_id,
        })
        session.save()

    def test_personal_courses_returns_owned_section_without_course_row(self):
        response = self.client.get(reverse("get_teacher_courses_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Course.objects.filter(teacher=self.teacher).count(), 0)
        self.assertEqual(response.json()["courses"][0]["id"], f"section-{self.section.id}")
        self.assertEqual(response.json()["courses"][0]["title"], "Grade 2")

    def test_supplementary_course_materials_follow_current_term_publications(self):
        calendar = SchoolCalendar.objects.create(
            school_year="2026-2027", current_term=1, is_active=True,
        )
        self.section.school_calendar = calendar
        self.section.grade_level = "Grade 2"
        self.section.section = "A"
        self.section.save(update_fields=["school_calendar", "grade_level", "section"])
        term_one = Material.objects.create(
            teacher=self.teacher, section=self.section, title="Term One Supplementary",
            item_type="paragraph", content_text="story", content_json={
                "activity_type": "letter_sound_matching",
            }, status="published", is_active=True,
        )
        term_two = Material.objects.create(
            teacher=self.teacher, section=self.section, title="Term Two Supplementary",
            item_type="paragraph", content_text="story", content_json={
                "activity_type": "sound_detective",
            }, status="published", is_active=True,
        )
        SupplementaryMaterialPublication.objects.create(
            material=term_one, school_calendar=calendar, term=1,
            section=self.section, is_active=True,
        )
        SupplementaryMaterialPublication.objects.create(
            material=term_two, school_calendar=calendar, term=2,
            section=self.section, is_active=True,
        )

        term_one_response = self.client.get(reverse("get_teacher_courses_api"))
        self.assertEqual(term_one_response.status_code, 200)
        term_one_titles = {item["title"] for item in term_one_response.json()["courses"][0]["materials"]}
        self.assertIn(term_one.title, term_one_titles)
        self.assertNotIn(term_two.title, term_one_titles)

        calendar.current_term = 2
        calendar.save(update_fields=["current_term"])
        term_two_response = self.client.get(reverse("get_teacher_courses_api"))
        self.assertEqual(term_two_response.status_code, 200)
        term_two_titles = {item["title"] for item in term_two_response.json()["courses"][0]["materials"]}
        self.assertNotIn(term_one.title, term_two_titles)
        self.assertIn(term_two.title, term_two_titles)

    def test_reading_practice_card16_material_follows_current_term_publication(self):
        calendar = SchoolCalendar.objects.create(
            school_year="2026-2027", current_term=1, is_active=True,
        )
        self.section.school_calendar = calendar
        self.section.save(update_fields=["school_calendar"])
        reading_practice = Material.objects.create(
            teacher=self.teacher, section=self.section, title="Card 16 Reading Practice",
            item_type="word", content_text="isa", content_json={
                "activity_type": "reading_practice", "items": ["isa"],
            }, type="assessment", source_type="personal", status="published", is_active=True,
        )
        SupplementaryMaterialPublication.objects.create(
            material=reading_practice, school_calendar=calendar, term=1,
            section=self.section, is_active=True,
        )

        term_one = self.client.get(reverse("get_teacher_courses_api"))
        term_one_titles = {item["title"] for item in term_one.json()["courses"][0]["materials"]}
        self.assertIn(reading_practice.title, term_one_titles)

        calendar.current_term = 2
        calendar.save(update_fields=["current_term"])
        term_two = self.client.get(reverse("get_teacher_courses_api"))
        term_two_titles = {item["title"] for item in term_two.json()["courses"][0]["materials"]}
        self.assertNotIn(reading_practice.title, term_two_titles)

    def test_supplementary_course_materials_exclude_inactive_and_other_calendar_publications(self):
        calendar = SchoolCalendar.objects.create(
            school_year="2026-2027", current_term=1, is_active=True,
        )
        other_calendar = SchoolCalendar.objects.create(
            school_year="2027-2028", current_term=1, is_active=True,
        )
        self.section.school_calendar = calendar
        self.section.grade_level = "Grade 2"
        self.section.save(update_fields=["school_calendar", "grade_level"])
        materials = []
        for title, publication_calendar, active in (
            ("Current Supplementary", calendar, True),
            ("Inactive Supplementary", calendar, False),
            ("Other Year Supplementary", other_calendar, True),
        ):
            material = Material.objects.create(
                teacher=self.teacher, section=self.section, title=title,
                item_type="paragraph", content_text="story", content_json={
                    "activity_type": "letter_sound_matching",
                }, status="published", is_active=True,
            )
            SupplementaryMaterialPublication.objects.create(
                material=material, school_calendar=publication_calendar, term=1,
                section=self.section, is_active=active,
            )
            materials.append(material)

        response = self.client.get(reverse("get_teacher_courses_api"))
        self.assertEqual(response.status_code, 200)
        titles = {item["title"] for item in response.json()["courses"][0]["materials"]}
        self.assertIn(materials[0].title, titles)
        self.assertNotIn(materials[1].title, titles)
        self.assertNotIn(materials[2].title, titles)

    def test_courses_context_is_section_backed(self):
        response = self.client.get(reverse("courses"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["teacher_courses"][0]["id"], f"section-{self.section.id}")

    def test_shared_mode_remains_legacy_course_backed(self):
        other_teacher = User.objects.create(
            custom_id="TCH-SHARED-COURSES", role="teacher",
            first_name="Shared", last_name="Owner", middle_initial="", suffix="",
            sex="female", birth_month=1, birth_day=1, birth_year=1990,
            email="shared-courses@example.com", password_hash="hashed-password",
            teacher_role="Teacher",
            school_record=self.school,
        )
        shared_course = Course.objects.create(
            code="SHARED-COURSE", title="Shared Course", teacher=other_teacher,
        )
        self.assertIsNone(shared_course.school_id)
        self.assertEqual(shared_course.teacher.school_record_id, self.school.id)
        self.assertFalse(shared_course.sections.exists())

        response = self.client.get(reverse("get_teacher_courses_api"), {"shared": "true"})

        self.assertEqual(response.status_code, 200)
        ids = {course["id"] for course in response.json()["courses"]}
        # NULL-school legacy Courses remain owner-compatible but are excluded
        # from school-wide/shared discovery.
        self.assertNotIn(shared_course.id, ids)
        self.assertNotIn(f"section-{self.section.id}", ids)

    def test_section_identifier_scopes_assessments(self):
        assessment = Assessment.objects.create(
            title="Section Assessment", code="ASM-SECTION", assessment_type="word",
            status="published", teacher=self.teacher, section=self.section,
            is_active=True, attempt_no=1,
        )

        response = self.client.get(
            reverse("get_teacher_assessments_api"),
            {"course_id": f"section-{self.section.id}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(assessment.id, {item["id"] for item in response.json()["assessments"]})

    def test_section_identifier_adds_and_removes_material_without_course(self):
        material = Material.objects.create(
            teacher=self.teacher, title="Section Material", item_type="word",
            content_text="read", content_json={"items": ["read"]},
            type="practice", source_type="personal", status="published", is_active=True,
        )
        identifier = f"section-{self.section.id}"

        added = self.client.post(
            reverse("add_material_to_course"),
            json.dumps({"course_id": identifier, "material_id": material.id}),
            content_type="application/json",
        )
        self.assertEqual(added.status_code, 200)
        material.refresh_from_db()
        self.assertEqual(material.section_id, self.section.id)
        self.assertTrue(material.assigned_sections.filter(id=self.section.id).exists())

        removed = self.client.post(
            reverse("remove_material_from_course"),
            json.dumps({"course_id": identifier, "material_id": material.id}),
            content_type="application/json",
        )
        self.assertEqual(removed.status_code, 200)
        material.refresh_from_db()
        self.assertIsNone(material.section_id)
        self.assertFalse(material.assigned_sections.filter(id=self.section.id).exists())

    def test_section_backed_course_can_start_live_assessment(self):
        student = self._user("SCS-STUDENT", "scs-student@example.com", "student", self.school)
        Enrollment.objects.create(student=student, section=self.section, assigned_teacher=self.teacher)
        material = Material.objects.create(
            teacher=self.teacher, section=self.section, title="Live Section Material",
            item_type="word", content_text="read", content_json={"items": ["read"]},
            type="assessment", source_type="personal", status="published", is_active=True,
        )
        picker_response = self.client.get(
            reverse("get_assist_students"),
            {"course_id": "", "section_id": self.section.id, "material_id": material.id},
        )

        self.assertEqual(picker_response.status_code, 200)
        self.assertEqual(picker_response.json()["students"][0]["id"], student.id)

        response = self.client.post(
            reverse("start_live_assessment"),
            json.dumps({
                "course_id": None,
                "section_id": self.section.id,
                "material_id": material.id,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["session"]["available_students"][0]["id"], student.id)
