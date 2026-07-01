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
	list_display = (
		"id",
		"title",
		"code",
		"assessment_type",
		"status",
		"scheduled_at",
		"teacher",
		"section",
		"is_active",
		"created_at",
		"updated_at",
		"attempt_count",
		"latest_wpm",
		"latest_fluency_score",
		"latest_accuracy",
		"latest_pronunciation_score",
		"latest_time_score",
		"latest_total_score",
		"latest_crla_level",
	)
	list_filter = ("assessment_type", "is_active", "created_at")
	search_fields = ("code", "title", "teacher__custom_id", "section__class_code")
	ordering = ("-created_at",)

	def _latest_attempt_summary(self, obj):
		return obj.get_latest_attempt_summary() or {}

	def _display_attempt_value(self, value):
		return value if value is not None and value != '' else "-"

	def attempt_count(self, obj):
		return len(obj.get_attempts())
	attempt_count.short_description = "Attempts"

	def latest_wpm(self, obj):
		return self._display_attempt_value(self._latest_attempt_summary(obj).get("wpm"))
	latest_wpm.short_description = "WPM"

	def latest_fluency_score(self, obj):
		return self._display_attempt_value(self._latest_attempt_summary(obj).get("fluency_score"))
	latest_fluency_score.short_description = "Fluency"

	def latest_accuracy(self, obj):
		return self._display_attempt_value(self._latest_attempt_summary(obj).get("accuracy"))
	latest_accuracy.short_description = "Accuracy"

	def latest_pronunciation_score(self, obj):
		return self._display_attempt_value(self._latest_attempt_summary(obj).get("pronunciation_score"))
	latest_pronunciation_score.short_description = "Pronunciation"

	def latest_time_score(self, obj):
		return self._display_attempt_value(self._latest_attempt_summary(obj).get("time_score"))
	latest_time_score.short_description = "Time"

	def latest_total_score(self, obj):
		return self._display_attempt_value(self._latest_attempt_summary(obj).get("total_score"))
	latest_total_score.short_description = "Total Score"

	def latest_crla_level(self, obj):
		return self._display_attempt_value(self._latest_attempt_summary(obj).get("crla_classification"))
	latest_crla_level.short_description = "CRLA Level"

@admin.register(Practice)
class PracticeAdmin(admin.ModelAdmin):
	list_display = all_model_fields(Practice)
	list_filter = ("is_active", "created_at")
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


# Assessment attempts are stored in the Assessment `attempts` JSONField.


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

