import json

from django.test import TestCase
from django.urls import reverse

from .models import Assessment, Course, Material, School, Section, User


class CourseMaterialAssessmentPhase4Tests(TestCase):
    def setUp(self):
        self.school_a = School.objects.create(name="Phase 4 School A", code="PH4-A")
        self.school_b = School.objects.create(name="Phase 4 School B", code="PH4-B")
        self.teacher_a = self._user("PH4-TA", "ph4-ta@example.com", "teacher", self.school_a)
        self.teacher_same_school = self._user("PH4-TS", "ph4-ts@example.com", "teacher", self.school_a)
        self.teacher_b = self._user("PH4-TB", "ph4-tb@example.com", "teacher", self.school_b)
        self.student_a = self._user("PH4-SA", "ph4-sa@example.com", "student", self.school_a)
        self.student_b = self._user("PH4-SB", "ph4-sb@example.com", "student", self.school_b)
        self.section_a = self._section("PH4-A1", "Section A", self.teacher_a, self.school_a)
        self.section_same_school = self._section("PH4-A2", "Section A2", self.teacher_same_school, self.school_a)
        self.section_b = self._section("PH4-B1", "Section B", self.teacher_b, self.school_b)

    def _user(self, custom_id, email, role, school):
        return User.objects.create(
            custom_id=custom_id,
            role=role,
            first_name=custom_id,
            last_name="User",
            middle_initial="",
            suffix="",
            sex="N/A",
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email=email,
            password_hash="hashed",
            school_record=school,
        )

    def _section(self, code, name, teacher, school):
        return Section.objects.create(
            school=school,
            class_code=code,
            class_name=name,
            subject="Reading",
            teacher=teacher,
            is_active=True,
        )

    def _login(self, user):
        session = self.client.session
        session.update({"user_id": user.id, "user_role": user.role, "email": user.email})
        session.save()

    def _post(self, url_name, payload):
        return self.client.post(
            reverse(url_name),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _material(self, teacher, section, title="Shared Material", source_type="shared"):
        material = Material.objects.create(
            section=section,
            teacher=teacher,
            title=title,
            item_type="word",
            prompt_text="read",
            content_text="read",
            content_json={"items": ["read"]},
            type="assessment",
            source_type=source_type,
            status="published",
            student_access=True,
            is_active=True,
        )
        material.assigned_sections.add(section)
        return material

    def test_teacher_can_create_course_content_with_own_section_id(self):
        self._login(self.teacher_a)

        response = self._post("create_course", {
            "title": "Section ID Course",
            "section_ids": [self.section_a.id],
        })

        self.assertEqual(response.status_code, 200)
        course = Course.objects.get(id=response.json()["course"]["id"])
        self.assertTrue(course.sections.filter(id=self.section_a.id).exists())

    def test_teacher_cannot_target_another_teachers_section(self):
        self._login(self.teacher_a)

        response = self._post("create_course", {
            "title": "Foreign Section Course",
            "section_ids": [self.section_same_school.id, self.section_b.id],
        })

        self.assertEqual(response.status_code, 200)
        course = Course.objects.get(id=response.json()["course"]["id"])
        self.assertFalse(course.sections.exists())

    def test_material_creation_uses_section_id(self):
        self._login(self.teacher_a)

        response = self._post("add_reading_material", {
            "title": "Canonical Material",
            "reading_type": "word",
            "content": "alpha beta",
            "status": "draft",
            "source_type": "personal",
            "section_id": self.section_a.id,
        })

        self.assertEqual(response.status_code, 200)
        material = Material.objects.get(id=response.json()["material"]["raw_id"])
        self.assertEqual(material.section_id, self.section_a.id)
        self.assertTrue(material.assigned_sections.filter(id=self.section_a.id).exists())

    def test_material_sharing_to_authorized_section_still_works(self):
        shared_material = self._material(self.teacher_same_school, self.section_same_school)
        self._login(self.teacher_a)

        response = self._post("add_material_to_course", {
            "course_id": f"section-{self.section_a.id}",
            "section_id": self.section_a.id,
            "material_id": shared_material.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        shared_material.refresh_from_db()
        self.assertTrue(shared_material.assigned_sections.filter(id=self.section_a.id).exists())

    def test_cross_school_material_sharing_is_rejected(self):
        foreign_material = self._material(self.teacher_b, self.section_b, title="Foreign Shared")
        self._login(self.teacher_a)

        response = self._post("add_material_to_course", {
            "course_id": f"section-{self.section_a.id}",
            "section_id": self.section_a.id,
            "material_id": foreign_material.id,
        })

        self.assertEqual(response.status_code, 403)
        self.assertFalse(foreign_material.assigned_sections.filter(id=self.section_a.id).exists())

    def test_assessment_section_selection_uses_section_id(self):
        assessment = Assessment.objects.create(
            title="Section Assessment",
            code="PH4-ASSESS",
            assessment_type="word",
            teacher=self.teacher_a,
            section=self.section_a,
        )
        self._login(self.teacher_a)

        response = self.client.get(reverse("get_teacher_assessments_api"), {
            "course_id": f"section-{self.section_a.id}",
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn(assessment.id, {item["id"] for item in response.json()["assessments"]})

    def test_assessment_api_exposes_persisted_template_title_for_results_label(self):
        assessment = Assessment.objects.create(
            title="Template Assessment",
            code="PH4-TEMPLATE-ASSESS",
            assessment_type="sentence",
            teacher=self.teacher_a,
            section=self.section_a,
        )
        Material.objects.create(
            assessment=assessment,
            section=self.section_a,
            teacher=self.teacher_a,
            title="Custom activity title",
            item_type="sentence",
            type="assessment",
            source_type="template",
            content_json={"template_title": "Phrase Reading Practice"},
        )
        self._login(self.teacher_a)

        response = self.client.get(reverse("get_teacher_assessments_api"), {
            "course_id": f"section-{self.section_a.id}",
        })

        self.assertEqual(response.status_code, 200)
        item = next(row for row in response.json()["assessments"] if row["id"] == assessment.id)
        self.assertEqual(item["source_type"], "template")
        self.assertEqual(item["template_title"], "Phrase Reading Practice")
        self.assertEqual(item["assessment_type"], "sentence")

    def test_results_api_uses_material_id_for_assessment_export(self):
        material = Material.objects.create(
            section=self.section_a,
            teacher=self.teacher_a,
            title="Lost and Found",
            item_type="word",
            prompt_text="read",
            content_text="read",
            content_json={"items": ["read"]},
            type="assessment",
            source_type="personal",
            status="published",
            is_active=True,
        )
        material.assigned_sections.add(self.section_a)
        assessment = Assessment.objects.create(
            title="Lost and Found",
            code="PH4-LOST-FOUND",
            assessment_type="word",
            teacher=self.teacher_a,
            section=self.section_a,
            material=material,
            is_active=True,
        )
        self._login(self.teacher_a)

        response = self.client.get(reverse("get_teacher_assessments_api"), {
            "course_id": f"section-{self.section_a.id}",
        })

        self.assertEqual(response.status_code, 200)
        item = next(row for row in response.json()["assessments"] if row["id"] == assessment.id)
        self.assertEqual(item["title"], "Lost and Found")
        self.assertEqual(item["material_id"], material.id)
        self.assertNotEqual(item["material_id"], assessment.id)

    def test_class_code_only_material_creation_is_rejected(self):
        self._login(self.teacher_a)

        own_response = self._post("add_reading_material", {
            "title": "Compatibility Material",
            "reading_type": "word",
            "content": "compatibility",
            "status": "draft",
            "source_type": "personal",
            "class_code": self.section_a.class_code,
        })
        foreign_response = self._post("add_reading_material", {
            "title": "Foreign Compatibility Material",
            "reading_type": "word",
            "content": "forbidden",
            "status": "draft",
            "source_type": "personal",
            "class_code": self.section_b.class_code,
        })

        self.assertEqual(own_response.status_code, 400)
        self.assertEqual(foreign_response.status_code, 400)

    def test_student_material_visibility_is_unchanged(self):
        material = self._material(self.teacher_a, self.section_a, title="Visible Material", source_type="personal")
        self.section_a.add_student(self.student_a)
        self._login(self.student_a)

        response = self.client.get(reverse("get_class_materials"), {"section_id": self.section_a.id})

        self.assertEqual(response.status_code, 200)
        visible_ids = {
            item["raw_id"]
            for items in response.json()["materials"].values()
            for item in items
            if item.get("record_kind") == "material"
        }
        self.assertIn(material.id, visible_ids)
