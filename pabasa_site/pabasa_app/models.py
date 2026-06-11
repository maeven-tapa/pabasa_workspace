from django.db import models
from django.utils import timezone
from datetime import datetime


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
    # Teacher-specific fields
    teacher_role = models.CharField(max_length=50, blank=True, null=True)
    school = models.CharField(max_length=150, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    # Student-specific fields
    grade_level = models.CharField(max_length=20, blank=True, null=True)
    section = models.CharField(max_length=50, blank=True, null=True)
    reading_level = models.CharField(max_length=50, blank=True, null=True)
    parent_contact_no = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.custom_id} - {self.last_name}, {self.first_name}"

    def _get_tags_list(self):
        tags = getattr(self, 'tags', None) or []
        if isinstance(tags, list):
            return tags
        return [tags]

    def add_tag(self, tag):
        if not tag:
            return False

        tags = self._get_tags_list()
        if tag in tags:
            return False

        tags.append(tag)
        self.tags = tags
        self.save(update_fields=['tags', 'updated_at'])
        return True

    def remove_tag(self, tag):
        tags = self._get_tags_list()
        if tag not in tags:
            return False

        self.tags = [entry for entry in tags if entry != tag]
        self.save(update_fields=['tags', 'updated_at'])
        return True


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

    # Stores joined students as JSON entries:
    # {"student_id": ..., "custom_id": ..., "first_name": ..., "last_name": ..., "email": ..., "joined_at": ..., "is_active": ...}
    students = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "sections"
        ordering = ["class_name"]

    def __str__(self):
        return f"{self.class_code} - {self.class_name}"

    def get_tag_label(self):
        return f"{self.class_name} ({self.class_code})"
    
    # Enrollment Management Methods
    def get_enrolled_students(self, active_only=False):
        """Get list of enrolled students, optionally filtering by active status"""
        students = getattr(self, 'students', None) or []
        if not isinstance(students, list):
            return []
        if active_only:
            return [student for student in students if student.get('is_active', True)]
        return students
    
    def has_student(self, user, active_only=True):
        """Check if user is enrolled in this section"""
        if not user or not user.id:
            return False
        
        for entry in self.get_enrolled_students(active_only=active_only):
            if not entry:
                continue
            
            # Try multiple matching strategies
            student_id = entry.get('student_id')
            custom_id = entry.get('custom_id')
            
            # Match by student_id (more reliable - explicit int conversion)
            if student_id is not None:
                try:
                    if int(student_id) == int(user.id):
                        return True
                except (ValueError, TypeError):
                    pass
            
            # Match by custom_id (backup - only if non-empty)
            if custom_id and str(custom_id).strip():
                if str(custom_id).strip() == str(user.custom_id).strip():
                    return True
        
        return False
    
    def get_student_count(self):
        """Get count of actively enrolled students"""
        return len(self.get_enrolled_students(active_only=True))
    
    def _get_student_entry(self, user, joined_at=None, is_active=True):
        """Create a student entry dict for enrollment"""
        return {
            'student_id': user.id,
            'custom_id': user.custom_id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'joined_at': joined_at or timezone.now().isoformat(),
            'is_active': is_active,
        }
    
    def _save_enrollment(self):
        """Save updated students list to database"""
        self.updated_at = timezone.now()
        self.save(update_fields=['students', 'updated_at'])
    
    def add_student(self, user):
        """Enroll a student in this section. Returns True if successful, False if already enrolled."""
        students = self.get_enrolled_students()
        tag_label = self.get_tag_label()
        for index, entry in enumerate(students):
            if (str(entry.get('student_id')) == str(user.id) or 
                entry.get('custom_id') == user.custom_id):
                if entry.get('is_active', True):
                    user.add_tag(tag_label)
                    return False  # Already enrolled
                # Re-activate if previously deactivated
                entry.update(self._get_student_entry(user, entry.get('joined_at'), is_active=True))
                students[index] = entry
                self.students = students
                self._save_enrollment()
                # VERIFY the save committed to database
                self.refresh_from_db()
                if not self.has_student(user, active_only=True):
                    raise Exception(f"Failed to re-enroll student {user.id} in section {self.class_code}")
                user.add_tag(tag_label)
                return True
        
        # Add new enrollment
        students.append(self._get_student_entry(user))
        self.students = students
        self._save_enrollment()
        # VERIFY the save committed to database
        self.refresh_from_db()
        if not self.has_student(user, active_only=True):
            raise Exception(f"Failed to enroll student {user.id} in section {self.class_code}")
        user.add_tag(tag_label)
        return True
    
    def deactivate_student(self, user):
        """Deactivate a student's enrollment in this section. Returns True if changed."""
        students = self.get_enrolled_students()
        tag_label = self.get_tag_label()
        changed = False
        for entry in students:
            if ((str(entry.get('student_id')) == str(user.id) or 
                 entry.get('custom_id') == user.custom_id) and 
                entry.get('is_active', True)):
                entry['is_active'] = False
                changed = True
        if changed:
            self.students = students
            self._save_enrollment()
            user.remove_tag(tag_label)
        return changed
    
    def deactivate_all_students(self):
        """Deactivate all student enrollments in this section. Returns True if changed."""
        students = self.get_enrolled_students()
        tag_label = self.get_tag_label()
        changed = False
        affected_student_ids = set()
        for entry in students:
            if entry.get('is_active', True):
                entry['is_active'] = False
                changed = True
                if entry.get('student_id'):
                    affected_student_ids.add(entry.get('student_id'))
        if changed:
            self.students = students
            self._save_enrollment()
            for student_user in User.objects.filter(id__in=affected_student_ids):
                student_user.remove_tag(tag_label)
        return changed

class Assessment(models.Model):
    ASSESSMENT_TYPE_CHOICES = [
        ("word", "Word"),
        ("sentence", "Sentence"),
        ("paragraph", "Paragraph"),
    ]
    
    STATUS_CHOICES = [
        ("published", "Published"),
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
    ]

    title = models.CharField(max_length=150)
    code = models.CharField(max_length=30, unique=True)
    assessment_type = models.CharField(max_length=20, choices=ASSESSMENT_TYPE_CHOICES)
    content = models.TextField(blank=True, default='')  # The actual reading material text
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    scheduled_at = models.DateTimeField(null=True, blank=True)  # When material becomes published
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
    
    # Attempt Management Methods
    def get_attempts(self, student=None):
        """Get all attempts, optionally filtered by student"""
        attempts = getattr(self, 'attempts', None) or []
        if not isinstance(attempts, list):
            return []
        if student:
            return [a for a in attempts if a.get('student_id') == student.id]
        return attempts
    
    def get_student_attempt_count(self, student):
        """Get count of attempts for a specific student"""
        return len(self.get_attempts(student))
    
    def has_student_attempted(self, student):
        """Check if a student has attempted this assessment"""
        return any(a.get('student_id') == student.id for a in self.get_attempts())
    
    def _get_attempt_entry(self, student, status='started', started_at=None, **kwargs):
        """Create an attempt entry dict"""
        entry = {
            'student_id': student.id,
            'started_at': started_at or timezone.now().isoformat(),
            'status': status,
        }
        # Add optional fields if provided
        for key in ['completed_at', 'device_info', 'mic_used', 'accuracy', 'wpm', 'total_score', 'passed', 'remarks']:
            if key in kwargs:
                entry[key] = kwargs[key]
        return entry
    
    def _save_attempts(self):
        """Save updated attempts list to database"""
        self.updated_at = timezone.now()
        self.save(update_fields=['attempts', 'updated_at'])
    
    def record_attempt(self, student, **attempt_data):
        """Record a student's assessment attempt. Returns the attempt entry."""
        attempts = self.get_attempts()
        entry = self._get_attempt_entry(student, **attempt_data)
        attempts.append(entry)
        self.attempts = attempts
        self._save_attempts()
        return entry
    
    def update_attempt(self, student, **update_data):
        """Update the most recent attempt for a student. Returns True if updated."""
        attempts = self.get_attempts()
        for i in range(len(attempts) - 1, -1, -1):  # Search from latest to earliest
            if attempts[i].get('student_id') == student.id:
                attempts[i].update(update_data)
                attempts[i]['updated_at'] = timezone.now().isoformat()
                self.attempts = attempts
                self._save_attempts()
                return True
        return False
    
    def get_student_latest_attempt(self, student):
        """Get the most recent attempt for a student"""
        student_attempts = self.get_attempts(student)
        return student_attempts[-1] if student_attempts else None
    
    def deactivate_student_attempts(self, student):
        """Mark all attempts for a student as inactive (soft delete). Returns True if changed."""
        attempts = self.get_attempts()
        changed = False
        for attempt in attempts:
            if attempt.get('student_id') == student.id and attempt.get('status') != 'cancelled':
                attempt['status'] = 'cancelled'
                changed = True
        if changed:
            self.attempts = attempts
            self._save_attempts()
        return changed
    
    def clear_all_attempts(self):
        """Clear all attempts (hard delete). Used when assessment is deleted."""
        if self.attempts:
            self.attempts = []
            self._save_attempts()
            return True
        return False


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
