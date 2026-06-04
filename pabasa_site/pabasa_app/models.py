from django.db import models


class User(models.Model):
    ROLE_CHOICES = [
        ("teacher", "Teacher"),
        ("student", "Student"),
    ]

    id = models.BigAutoField(primary_key=True)
    custom_id = models.CharField(max_length=20, unique=True, editable=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    sex = models.CharField(max_length=10)
    birth_month = models.PositiveSmallIntegerField()
    birth_day = models.PositiveSmallIntegerField()
    birth_year = models.PositiveSmallIntegerField()
    email = models.EmailField(unique=True)
    contact_no = models.CharField(max_length=20, blank=True, null=True)
    password_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.custom_id} - {self.last_name}, {self.first_name}"


class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="teacher_profile")
    teacher_code = models.CharField(max_length=20, unique=True, editable=False)
    teacher_role = models.CharField(max_length=50, blank=True)
    school = models.CharField(max_length=150, blank=True)
    department = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "teacher_profiles"
        ordering = ["teacher_code"]

    def __str__(self):
        return f"{self.teacher_code} - {self.user.first_name} {self.user.last_name}" # TCH-XXXX - Firstname Lastname


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    student_code = models.CharField(max_length=20, unique=True, editable=False)
    grade_level = models.CharField(max_length=20, blank=True)
    section = models.CharField(max_length=50, blank=True)
    reading_level = models.CharField(max_length=50, blank=True)
    wpm = models.PositiveIntegerField(default=0)
    accuracy = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    parent_contact_no = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "student_profiles"
        ordering = ["student_code"]

    def __str__(self):
        return f"{self.student_code} - {self.user.first_name} {self.user.last_name}" # G2-XXXX - Firstname Lastname


class ReadingClass(models.Model):
    class_code = models.CharField(max_length=20, unique=True)
    class_name = models.CharField(max_length=150)
    header = models.CharField(max_length=100, default="Reading Class")
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name="reading_classes")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reading_classes"
        ordering = ["class_name"]

    def __str__(self):
        return f"{self.class_code} - {self.class_name}"


class ClassEnrollment(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="enrollments")
    reading_class = models.ForeignKey(ReadingClass, on_delete=models.CASCADE, related_name="enrollments")
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "class_enrollments"
        ordering = ["-joined_at"]
        constraints = [
            models.UniqueConstraint(fields=["student", "reading_class"], name="unique_student_class_enrollment"),
        ]

    def __str__(self):
        return f"{self.student} -> {self.reading_class}"
    

class Assessment(models.Model):
    ASSESSMENT_TYPE_CHOICES = [
        ("word", "Word"),
        ("sentence", "Sentence"),
        ("paragraph", "Paragraph"),
    ]

    title = models.CharField(max_length=150)
    code = models.CharField(max_length=30, unique=True)
    assessment_type = models.CharField(max_length=20, choices=ASSESSMENT_TYPE_CHOICES)
    teacher = models.ForeignKey("TeacherProfile", on_delete=models.CASCADE, related_name="assessments")
    reading_class = models.ForeignKey("ReadingClass", on_delete=models.CASCADE, related_name="assessments", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "assessments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.title}"


class AssessmentItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ("word", "Word"),
        ("sentence", "Sentence"),
        ("paragraph", "Paragraph"),
    ]

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="items")
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    prompt_text = models.TextField()
    order_index = models.PositiveIntegerField()
    expected_answer = models.TextField(blank=True, null=True)
    difficulty_level = models.CharField(max_length=50, blank=True)
    audio_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "assessment_items"
        ordering = ["assessment", "order_index"]
        constraints = [
            models.UniqueConstraint(fields=["assessment", "order_index"], name="unique_assessment_item_order")
        ]

    def __str__(self):
        return f"{self.assessment.code} - {self.item_type} #{self.order_index}"


class AssessmentAttempt(models.Model):
    ATTEMPT_STATUS_CHOICES = [
        ("started", "Started"),
        ("completed", "Completed"),
        ("submitted", "Submitted"),
        ("cancelled", "Cancelled"),
    ]

    student = models.ForeignKey("StudentProfile", on_delete=models.CASCADE, related_name="assessment_attempts")
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="attempts")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=ATTEMPT_STATUS_CHOICES, default="started")
    device_info = models.CharField(max_length=255, blank=True)
    mic_used = models.BooleanField(default=False)

    class Meta:
        db_table = "assessment_attempts"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.student.student_code} - {self.assessment.code}"


class AssessmentResult(models.Model):
    attempt = models.OneToOneField(AssessmentAttempt, on_delete=models.CASCADE, related_name="result")
    accuracy = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    wpm = models.PositiveIntegerField(default=0)
    clarity_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    pronunciation_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    comprehension_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    passed = models.BooleanField(default=False)
    remarks = models.TextField(blank=True)

    class Meta:
        db_table = "assessment_results"

    def __str__(self):
        return f"Result for {self.attempt}"


class TeacherNote(models.Model):
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name="notes")
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="teacher_notes")
    assessment = models.ForeignKey(Assessment, on_delete=models.SET_NULL, related_name="teacher_notes", null=True, blank=True)
    note_text = models.TextField()
    note_type = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "teacher_notes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note by {self.teacher.teacher_code} for {self.student.student_code}"


class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = [
        ("info", "Info"),
        ("success", "Success"),
        ("warning", "Warning"),
        ("error", "Error"),
        ("assessment", "Assessment"),
        ("message", "Message"),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="sent_notifications", null=True, blank=True)
    title = models.CharField(max_length=150)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES, default="info")
    is_read = models.BooleanField(default=False)
    action_url = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} -> {self.recipient.custom_id}"