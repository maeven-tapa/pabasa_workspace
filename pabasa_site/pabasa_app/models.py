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
    middle_initial = models.CharField(max_length=1, blank=True)
    suffix = models.CharField(max_length=10, blank=True)
    sex = models.CharField(max_length=10)
    birth_month = models.PositiveSmallIntegerField()
    birth_day = models.PositiveSmallIntegerField()
    birth_year = models.PositiveSmallIntegerField()
    email = models.EmailField(unique=True)
    contact_no = models.CharField(max_length=20, blank=True, null=True)
    password_hash = models.CharField(max_length=255)
    profile_picture = models.CharField(max_length=255, blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.custom_id} - {self.last_name}, {self.first_name}"


class Section(models.Model):
    class_code = models.CharField(max_length=20, unique=True)
    class_name = models.CharField(max_length=150)
    grade_level = models.CharField(max_length=20)
    section = models.CharField(max_length=50)
    header = models.CharField(max_length=100, default="Reading Class")
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sections")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    subject = models.CharField(max_length=50)

    # many-to-many convenience relationship: User.enrolled_sections via Enrollment
    students = models.ManyToManyField(User, through="Enrollment", related_name="enrolled_sections")

    class Meta:
        db_table = "sections"
        ordering = ["class_name"]

    def __str__(self):
        return f"{self.class_code} - {self.class_name}"


class Enrollment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="enrollments")
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="enrollments")
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "class_enrollments"
        ordering = ["-joined_at"]
        constraints = [
            models.UniqueConstraint(fields=["student", "section"], name="unique_student_section_enrollment"),
        ]

    def __str__(self):
        return f"{self.student} -> {self.section}"
    

class Assessment(models.Model):
    ASSESSMENT_TYPE_CHOICES = [
        ("word", "Word"),
        ("sentence", "Sentence"),
        ("paragraph", "Paragraph"),
    ]

    title = models.CharField(max_length=150)
    code = models.CharField(max_length=30, unique=True)
    assessment_type = models.CharField(max_length=20, choices=ASSESSMENT_TYPE_CHOICES)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="assessments")
    section = models.ForeignKey("Section", on_delete=models.CASCADE, related_name="assessments", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # store attempts and results within the assessments schema as a JSON list
    # each entry can be: {"student_id": ..., "started_at": ..., "completed_at": ..., "status": ..., "device_info": ..., "mic_used": ..., "accuracy": ..., "wpm": ..., "total_score": ..., "passed": ..., "remarks": ...}
    attempts = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "assessments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.title}"


class Material(models.Model):
    ITEM_TYPE_CHOICES = [
        ("word", "Word"),
        ("sentence", "Sentence"),
        ("paragraph", "Paragraph"),
    ]
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="materials")
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    prompt_text = models.TextField()
    order_index = models.PositiveIntegerField()
    expected_answer = models.TextField(blank=True, null=True)
    difficulty_level = models.CharField(max_length=50, blank=True)
    audio_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "materials"
        ordering = ["assessment", "order_index"]
        constraints = [
            models.UniqueConstraint(fields=["assessment", "order_index"], name="unique_assessment_item_order")
        ]

    def __str__(self):
        return f"{self.assessment.code} - {self.item_type} #{self.order_index}"


# Note: AssessmentAttempt and AssessmentResult tables removed. Attempts/results
# are stored inside the Assessment `attempts` JSONField.


class Note(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notes")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="teacher_notes")
    assessment = models.ForeignKey(Assessment, on_delete=models.SET_NULL, related_name="teacher_notes", null=True, blank=True)
    note_text = models.TextField()
    note_type = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note by {self.teacher} for {self.student}"


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
