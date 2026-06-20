from django.contrib import admin
from .models import (
	User,
	Section,
	Assessment,
	Practice,
	Material,
	Note,
	Notification,
	Course,
)


def all_model_fields(model):
	return [f.name for f in model._meta.fields]


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
	list_display = all_model_fields(User)
	list_filter = ("role", "is_archived", "sex", "created_at")
	search_fields = ("custom_id", "first_name", "last_name", "email")
	ordering = ("last_name", "first_name")


# TeacherProfile and StudentProfile models not found in current models.py;
# profile-specific admin classes removed. Use `User` admin for core user info.


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
	list_display = all_model_fields(Section)
	list_filter = ("is_active", "created_at")
	search_fields = ("class_code", "class_name", "teacher__custom_id", "teacher__last_name")
	ordering = ("class_name",)

	def student_count(self, obj):
		return len([student for student in (obj.students or []) if student.get("is_active", True)])


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
	list_display = all_model_fields(Assessment)
	list_filter = ("assessment_type", "is_active", "created_at")
	search_fields = ("code", "title", "teacher__custom_id", "section__class_code")
	ordering = ("-created_at",)


@admin.register(Practice)
class PracticeAdmin(admin.ModelAdmin):
	list_display = all_model_fields(Practice)
	list_filter = ("practice_type", "is_active", "created_at")
	search_fields = ("code", "title", "teacher__custom_id", "section__class_code")
	ordering = ("-created_at",)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
	list_display = all_model_fields(Material)
	list_filter = ("item_type", "status", "is_active", "created_at")
	search_fields = ("assessment__code", "section__class_code", "prompt_text", "content_text", "title")
	ordering = ("section", "created_at")

	def content_preview(self, obj):
		if not obj.content_text:
			return ""
		return obj.content_text[:80] + ("..." if len(obj.content_text) > 80 else "")

	content_preview.short_description = "Content"


# AssessmentAttempt and AssessmentResult removed; attempts stored inside Assessment.attempts JSONField


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
	list_display = all_model_fields(Note)
	list_filter = ("note_type", "created_at")
	search_fields = (
		"teacher__custom_id",
		"student__custom_id",
		"assessment__code",
		"note_text",
	)
	ordering = ("-created_at",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
	list_display = all_model_fields(Notification)
	list_filter = ("notification_type", "is_read", "created_at")
	search_fields = (
		"title",
		"message",
		"recipient__custom_id",
		"recipient__last_name",
		"created_by__custom_id",
	)
	ordering = ("-created_at",)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
	list_display = all_model_fields(Course)
	list_filter = ("is_active", "created_at")
	search_fields = ("code", "title", "teacher__custom_id")
	ordering = ("-created_at",)

