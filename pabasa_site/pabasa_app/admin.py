from django.contrib import admin
from .models import (
	User,
	TeacherProfile,
	StudentProfile,
	ReadingClass,
	ClassEnrollment,
	Assessment,
	AssessmentItem,
	AssessmentAttempt,
	AssessmentResult,
	TeacherNote,
	Notification,
)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
	list_display = ("custom_id", "first_name", "last_name", "email", "role", "created_at")
	list_filter = ("role", "sex", "created_at")
	search_fields = ("custom_id", "first_name", "last_name", "email")
	ordering = ("last_name", "first_name")


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
	list_display = ("teacher_code", "user", "teacher_role", "school", "department", "is_active")
	list_filter = ("is_active", "school", "department")
	search_fields = (
		"teacher_code",
		"user__custom_id",
		"user__first_name",
		"user__last_name",
		"school",
	)
	ordering = ("teacher_code",)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
	list_display = (
		"student_code",
		"user",
		"grade_level",
		"section",
		"reading_level",
		"wpm",
		"accuracy",
		"is_active",
	)
	list_filter = ("is_active", "grade_level", "reading_level")
	search_fields = (
		"student_code",
		"user__custom_id",
		"user__first_name",
		"user__last_name",
		"section",
	)
	ordering = ("student_code",)


@admin.register(ReadingClass)
class ReadingClassAdmin(admin.ModelAdmin):
	list_display = ("class_code", "class_name", "teacher", "is_active", "created_at")
	list_filter = ("is_active", "created_at")
	search_fields = ("class_code", "class_name", "teacher__teacher_code", "teacher__user__last_name")
	ordering = ("class_name",)


@admin.register(ClassEnrollment)
class ClassEnrollmentAdmin(admin.ModelAdmin):
	list_display = ("student", "reading_class", "is_active", "joined_at")
	list_filter = ("is_active", "joined_at")
	search_fields = (
		"student__student_code",
		"student__user__last_name",
		"reading_class__class_code",
		"reading_class__class_name",
	)
	ordering = ("-joined_at",)


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
	list_display = ("code", "title", "assessment_type", "teacher", "reading_class", "is_active", "created_at")
	list_filter = ("assessment_type", "is_active", "created_at")
	search_fields = ("code", "title", "teacher__teacher_code", "reading_class__class_code")
	ordering = ("-created_at",)


@admin.register(AssessmentItem)
class AssessmentItemAdmin(admin.ModelAdmin):
	list_display = ("assessment", "order_index", "item_type", "difficulty_level", "is_active")
	list_filter = ("item_type", "is_active")
	search_fields = ("assessment__code", "prompt_text", "expected_answer")
	ordering = ("assessment", "order_index")


@admin.register(AssessmentAttempt)
class AssessmentAttemptAdmin(admin.ModelAdmin):
	list_display = ("student", "assessment", "status", "mic_used", "started_at", "completed_at")
	list_filter = ("status", "mic_used", "started_at")
	search_fields = ("student__student_code", "assessment__code", "device_info")
	ordering = ("-started_at",)


@admin.register(AssessmentResult)
class AssessmentResultAdmin(admin.ModelAdmin):
	list_display = ("attempt", "accuracy", "wpm", "total_score", "passed")
	list_filter = ("passed",)
	search_fields = ("attempt__student__student_code", "attempt__assessment__code")


@admin.register(TeacherNote)
class TeacherNoteAdmin(admin.ModelAdmin):
	list_display = ("teacher", "student", "assessment", "note_type", "created_at")
	list_filter = ("note_type", "created_at")
	search_fields = (
		"teacher__teacher_code",
		"student__student_code",
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
