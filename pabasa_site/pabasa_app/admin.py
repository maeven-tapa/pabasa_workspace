from django.contrib import admin
from .models import (
	User,
	Section,
	Assessment,
	Material,
	Note,
	Notification,
)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
	list_display = ("custom_id", "first_name", "last_name", "email", "role", "created_at", "tags")
	list_filter = ("role", "sex", "created_at")
	search_fields = ("custom_id", "first_name", "last_name", "email")
	ordering = ("last_name", "first_name")


# TeacherProfile and StudentProfile models not found in current models.py;
# profile-specific admin classes removed. Use `User` admin for core user info.


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
	list_display = ("class_code", "class_name", "teacher", "student_count", "is_active", "created_at")
	list_filter = ("is_active", "created_at")
	search_fields = ("class_code", "class_name", "teacher__custom_id", "teacher__last_name")
	ordering = ("class_name",)

	def student_count(self, obj):
		return len([student for student in (obj.students or []) if student.get("is_active", True)])


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
	list_display = ("code", "title", "assessment_type", "teacher", "section", "is_active", "created_at")
	list_filter = ("assessment_type", "is_active", "created_at")
	search_fields = ("code", "title", "teacher__custom_id", "section__class_code")
	ordering = ("-created_at",)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
	list_display = ("assessment", "order_index", "item_type", "difficulty_level", "is_active")
	list_filter = ("item_type", "is_active")
	search_fields = ("assessment__code", "prompt_text", "expected_answer")
	ordering = ("assessment", "order_index")


# AssessmentAttempt and AssessmentResult removed; attempts stored inside Assessment.attempts JSONField


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
	list_display = ("teacher", "student", "assessment", "note_type", "created_at")
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
	list_display = (
		"title",
		"recipient",
		"created_by",
		"notification_type",
		"is_read",
		"created_at",
	)
	list_filter = ("notification_type", "is_read", "created_at")
	search_fields = (
		"title",
		"message",
		"recipient__custom_id",
		"recipient__last_name",
		"created_by__custom_id",
	)
	ordering = ("-created_at",)
