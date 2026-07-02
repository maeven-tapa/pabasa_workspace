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
		"code",
		"material",
		"title",
		"assessment_type",
		"student",
		"attempt_number",
		"attempt_status",
		"accuracy",
		"wpm",
		"fluency_score",
		"pronunciation_score",
		"time_score",
		"total_score",
		"crla_classification",
		"completed_at",
	)
	list_filter = ("assessment_type", "attempt_status", "completed_at", "created_at")
	search_fields = ("code", "title", "student__custom_id", "student__last_name", "material__code", "material__title")
	ordering = ("-created_at",)

	def get_queryset(self, request):
		"""Display assessment result rows. Legacy parent rows are hidden."""
		qs = super().get_queryset(request).select_related("material", "student", "section", "teacher")
		return qs.filter(student__isnull=False)

@admin.register(Practice)
class PracticeAdmin(admin.ModelAdmin):
	list_display = all_model_fields(Practice)
	list_filter = ("is_active", "created_at")
	search_fields = ("code", "title", "teacher__custom_id", "section__class_code")
	ordering = ("-created_at",)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"code",
		"title",
		"type",
		"item_type",
		"status",
		"teacher",
		"section",
		"assigned_week",
		"is_active",
		"result_count",
		"created_at",
		"updated_at",
		"content_preview",
	)
	list_filter = ("type", "item_type", "status", "is_active", "teacher", "section", "created_at")
	search_fields = ("code", "section__class_code", "teacher__custom_id", "teacher__last_name", "prompt_text", "content_text", "title")
	ordering = ("section", "created_at")

	def content_preview(self, obj):
		if not obj.content_text:
			return ""
		return obj.content_text[:80] + ("..." if len(obj.content_text) > 80 else "")

	content_preview.short_description = "Content"

	def result_count(self, obj):
		return obj.assessment_results.count()

	result_count.short_description = "Results"


# Assessment rows represent student result attempts linked back to Material.


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
