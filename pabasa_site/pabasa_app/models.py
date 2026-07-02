import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from datetime import datetime


class User(models.Model):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("principal", "Principal"),
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
    preference = models.JSONField(default=dict, blank=True)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    # Teacher-specific fields
    teacher_role = models.CharField(max_length=50, blank=True, null=True)
    school = models.CharField(max_length=150, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    # Student-specific fields
    grade_level = models.CharField(max_length=20, blank=True, null=True)
    section = models.CharField(max_length=50, blank=True, null=True)
    reading_level = models.CharField(max_length=50, blank=True, null=True)
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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    scheduled_at = models.DateTimeField(null=True, blank=True)  # When assessment becomes published
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="assessments")
    section = models.ForeignKey("Section", on_delete=models.CASCADE, related_name="assessments", null=True, blank=True)
    material = models.ForeignKey("Material", on_delete=models.SET_NULL, related_name="assessment_results", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    attempt_no = models.PositiveIntegerField(default=0)
    source_assessment = models.ForeignKey("self", null=True, blank=True, related_name="attempt_rows", on_delete=models.CASCADE)
    student = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="assessment_attempt_rows")
    attempt_id = models.CharField(max_length=64, blank=True, default="")
    attempt_number = models.PositiveIntegerField(default=1)
    attempt_status = models.CharField(max_length=20, default="started")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    device_info = models.TextField(blank=True, default="")
    mic_used = models.BooleanField(default=False)
    accuracy = models.FloatField(null=True, blank=True)
    wpm = models.FloatField(null=True, blank=True)
    fluency_score = models.FloatField(null=True, blank=True)
    pronunciation_score = models.FloatField(null=True, blank=True)
    time_score = models.FloatField(null=True, blank=True)
    total_score = models.FloatField(null=True, blank=True)
    crla_classification = models.CharField(max_length=100, blank=True, default="")
    classification = models.CharField(max_length=100, blank=True, default="")
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    word_count = models.PositiveIntegerField(null=True, blank=True)
    transcript = models.TextField(blank=True, default="")
    speech_recognition_used = models.BooleanField(default=False)
    needs_manual_review = models.BooleanField(default=False)
    passed = models.BooleanField(null=True, blank=True)
    remarks = models.TextField(blank=True, default="")
    stars_earned = models.PositiveIntegerField(default=0)
    items_completed = models.PositiveIntegerField(default=0)

    @property
    def attempt_history(self):
        return self.get_attempts()

    @attempt_history.setter
    def attempt_history(self, value):
        return None

    @property
    def attempts(self):
        return self.attempt_history

    @attempts.setter
    def attempts(self, value):
        return None

    @staticmethod
    def _attempt_value(attempt, *keys, default=None):
        for key in keys:
            value = attempt.get(key)
            if value is not None and value != '':
                return value
        return default

    @property
    def content(self):
        first_material = self.materials.order_by('created_at').first()
        if first_material:
            return first_material.content_text or first_material.prompt_text or ''
        return ''

    class Meta:
        db_table = "assessments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.title}"
    
    # Attempt Management Methods
    def _group_assessment(self):
        return self.source_assessment or self

    def _build_attempt_code(self, base_code, attempt_number):
        base = (base_code or self.code or 'ASSESSMENT').strip()
        candidate = f"{base}-{attempt_number}"
        while Assessment.objects.filter(code=candidate).exists():
            candidate = f"{base}-{attempt_number}-{uuid.uuid4().hex[:6].upper()}"
        return candidate

    def _serialize_attempt(self):
        return {
            'attempt_id': self.attempt_id or str(self.id),
            'attempt_number': self.attempt_number or self.attempt_no or 1,
            'student_id': self.student_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.attempt_status,
            'device_info': self.device_info,
            'mic_used': self.mic_used,
            'accuracy': self.accuracy,
            'wpm': self.wpm,
            'fluency_score': self.fluency_score,
            'pronunciation_score': self.pronunciation_score,
            'time_score': self.time_score,
            'total_score': self.total_score,
            'crla_classification': self.crla_classification,
            'classification': self.classification,
            'duration_seconds': self.duration_seconds,
            'word_count': self.word_count,
            'transcript': self.transcript,
            'speech_recognition_used': self.speech_recognition_used,
            'needs_manual_review': self.needs_manual_review,
            'passed': self.passed,
            'remarks': self.remarks,
            'stars_earned': self.stars_earned,
            'items_completed': self.items_completed,
        }

    def _sync_attempt_count(self):
        group = self._group_assessment()
        count = Assessment.objects.filter(source_assessment=group).count()
        if group.pk:
            group.attempt_no = count
            group.save(update_fields=['attempt_no', 'updated_at'])

    def _apply_attempt_payload(self, attempt_row, attempt_data):
        status_value = attempt_data.pop('status', None)
        if status_value is not None:
            attempt_row.attempt_status = str(status_value)
        started_at = attempt_data.pop('started_at', None)
        if started_at is not None:
            try:
                attempt_row.started_at = started_at
            except Exception:
                attempt_row.started_at = timezone.now()
        completed_at = attempt_data.pop('completed_at', None)
        if completed_at is not None:
            try:
                attempt_row.completed_at = completed_at
            except Exception:
                attempt_row.completed_at = timezone.now()
        for key, value in attempt_data.items():
            if key in {'attempt_id', 'attempt_number', 'student', 'student_id'}:
                continue
            if key == 'device_info':
                attempt_row.device_info = str(value or '')
            elif key == 'mic_used':
                attempt_row.mic_used = bool(value)
            elif key == 'speech_recognition_used':
                attempt_row.speech_recognition_used = bool(value)
            elif key == 'needs_manual_review':
                attempt_row.needs_manual_review = bool(value)
            elif key == 'passed':
                attempt_row.passed = value
            elif key == 'accuracy':
                attempt_row.accuracy = value
            elif key == 'wpm':
                attempt_row.wpm = value
            elif key == 'fluency_score':
                attempt_row.fluency_score = value
            elif key == 'pronunciation_score':
                attempt_row.pronunciation_score = value
            elif key == 'time_score':
                attempt_row.time_score = value
            elif key == 'total_score':
                attempt_row.total_score = value
            elif key == 'crla_classification':
                attempt_row.crla_classification = str(value or '')
            elif key == 'classification':
                attempt_row.classification = str(value or '')
            elif key == 'duration_seconds':
                attempt_row.duration_seconds = value
            elif key == 'word_count':
                attempt_row.word_count = value
            elif key == 'transcript':
                attempt_row.transcript = str(value or '')
            elif key == 'stars_earned':
                attempt_row.stars_earned = value
            elif key == 'items_completed':
                attempt_row.items_completed = value
            elif key == 'remarks':
                attempt_row.remarks = str(value or '')
            elif key == 'attempt_id':
                attempt_row.attempt_id = str(value or '')
            elif key == 'attempt_number':
                attempt_row.attempt_number = value
            elif key == 'student':
                attempt_row.student = value
        attempt_row.updated_at = timezone.now()
        attempt_row.save()
        return attempt_row

    def get_attempts(self, student=None):
        """Get all attempts, optionally filtered by student."""
        group = self._group_assessment()
        rows = Assessment.objects.filter(source_assessment=group).order_by('attempt_number', 'created_at', 'id')
        if student is not None:
            rows = rows.filter(student_id=student.id)
        return [row._serialize_attempt() for row in rows]

    def get_latest_attempt(self, student=None):
        """Get the most recent attempt for the assessment or a specific student."""
        attempts = self.get_attempts(student)
        return attempts[-1] if attempts else None

    def get_latest_attempt_summary(self, student=None):
        """Return a normalized view of the latest attempt metrics."""
        attempt = self.get_latest_attempt(student)
        if not attempt:
            return {}
        return {
            'student_id': attempt.get('student_id'),
            'wpm': self._attempt_value(attempt, 'wpm', 'words_per_minute', 'reading_wpm'),
            'fluency_score': self._attempt_value(attempt, 'fluency_score', 'fluency'),
            'accuracy': self._attempt_value(attempt, 'accuracy', 'accuracy_score', 'reading_accuracy'),
            'pronunciation_score': self._attempt_value(attempt, 'pronunciation_score', 'pronunciation'),
            'time_score': self._attempt_value(attempt, 'time_score', 'time'),
            'total_score': self._attempt_value(attempt, 'total_score', 'score'),
            'crla_classification': self._attempt_value(attempt, 'crla_classification', 'classification'),
            'status': attempt.get('status'),
            'completed_at': attempt.get('completed_at'),
        }
    
    def get_student_attempt_count(self, student):
        """Get count of attempts for a specific student"""
        return len(self.get_attempts(student))
    
    def has_student_attempted(self, student):
        """Check if a student has attempted this assessment"""
        return any(attempt.get('student_id') == student.id for attempt in self.get_attempts())

    def has_student_completed(self, student):
        """Check if a student has a completed attempt for this assessment."""
        return any(
            attempt.get('student_id') == student.id and attempt.get('status') == 'completed'
            for attempt in self.get_attempts(student)
        )
    
    def record_attempt(self, student, **attempt_data):
        """Record a student's assessment attempt and return the new row."""
        group_assessment = self._group_assessment()
        attempt_id = attempt_data.pop('attempt_id', None) or str(uuid.uuid4())
        attempt_number = attempt_data.pop('attempt_number', None)
        if attempt_number is None:
            attempt_number = self.get_student_attempt_count(student) + 1

        started_at_value = attempt_data.pop('started_at', None) or timezone.now()
        completed_at_value = attempt_data.pop('completed_at', None)
        attempt_row = Assessment.objects.create(
            title=self.title,
            code=self._build_attempt_code(group_assessment.code, attempt_number),
            assessment_type=self.assessment_type,
            status=self.status,
            scheduled_at=self.scheduled_at,
            teacher=self.teacher,
            section=self.section,
            is_active=self.is_active,
            source_assessment=group_assessment,
            student=student,
            attempt_id=str(attempt_id),
            attempt_number=attempt_number,
            attempt_status=str(attempt_data.pop('status', 'completed') or 'completed'),
            started_at=started_at_value,
            completed_at=completed_at_value,
        )

        self._apply_attempt_payload(attempt_row, attempt_data)
        if completed_at_value is None and attempt_row.attempt_status == 'completed':
            attempt_row.completed_at = timezone.now()
            attempt_row.save(update_fields=['completed_at', 'updated_at'])
        self._sync_attempt_count()
        return attempt_row._serialize_attempt()

    def update_attempt(self, student, **update_data):
        """Update the most recent attempt for a student. Returns True if updated."""
        group_assessment = self._group_assessment()
        attempt_row = Assessment.objects.filter(source_assessment=group_assessment, student=student).order_by('-attempt_number', '-created_at', '-id').first()
        if attempt_row is None and group_assessment.student_id == student.id:
            attempt_row = group_assessment
        if attempt_row is None:
            return False
        self._apply_attempt_payload(attempt_row, dict(update_data))
        self._sync_attempt_count()
        return True
    
    def get_student_latest_attempt(self, student):
        """Get the most recent attempt for a student"""
        return self.get_latest_attempt(student)
    
    def deactivate_student_attempts(self, student):
        """Mark all attempts for a student as inactive (soft delete). Returns True if changed."""
        group_assessment = self._group_assessment()
        attempt_rows = Assessment.objects.filter(source_assessment=group_assessment, student=student)
        changed = False
        for attempt_row in attempt_rows:
            if attempt_row.attempt_status != 'cancelled':
                attempt_row.attempt_status = 'cancelled'
                attempt_row.updated_at = timezone.now()
                attempt_row.save(update_fields=['attempt_status', 'updated_at'])
                changed = True
        return changed

    def clear_all_attempts(self):
        """Clear all attempts (hard delete). Used when assessment is deleted."""
        group = self._group_assessment()
        child_rows = Assessment.objects.filter(source_assessment=group)
        if child_rows.exists():
            child_rows.delete()
        if group.pk:
            group.attempt_no = 0
            group.updated_at = timezone.now()
            group.save(update_fields=['attempt_no', 'updated_at'])
            return True
        return False


class Practice(models.Model):
    PRACTICE_TYPE_CHOICES = Assessment.ASSESSMENT_TYPE_CHOICES
    STATUS_CHOICES = Assessment.STATUS_CHOICES

    title = models.CharField(max_length=150)
    code = models.CharField(max_length=30, unique=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="practices")
    material = models.OneToOneField(
        "Material",
        on_delete=models.SET_NULL,
        related_name="practice_result",
        null=True,
        blank=True,
    )
    section = models.ForeignKey("Section", on_delete=models.CASCADE, related_name="practices", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    attempts = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "practices"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.title}"

    @property
    def practice_type(self):
        return getattr(self.material, "item_type", "") or getattr(self, "_practice_type", "")

    @practice_type.setter
    def practice_type(self, value):
        value = value or ""
        self._practice_type = value
        if self.material:
            self.material.item_type = value
            self.material.save(update_fields=["item_type"])

    @property
    def difficulty_type(self):
        return getattr(self.material, "difficulty_level", "") or getattr(self, "_difficulty_type", "")

    @difficulty_type.setter
    def difficulty_type(self, value):
        value = value or ""
        self._difficulty_type = value
        if self.material:
            self.material.difficulty_level = value
            self.material.save(update_fields=["difficulty_level"])

    @property
    def prompt_text(self):
        return getattr(self.material, "prompt_text", "") or getattr(self, "_prompt_text", "")

    @prompt_text.setter
    def prompt_text(self, value):
        value = value or ""
        self._prompt_text = value
        if self.material:
            self.material.prompt_text = value
            self.material.save(update_fields=["prompt_text"])

    @property
    def contents(self):
        return getattr(self.material, "content_text", "") or getattr(self, "_contents", "")

    @contents.setter
    def contents(self, value):
        value = value or ""
        self._contents = value
        if self.material:
            self.material.content_text = value
            self.material.save(update_fields=["content_text"])

    def save(self, *args, **kwargs):
        pending_item_type = getattr(self, "_practice_type", None)
        pending_difficulty = getattr(self, "_difficulty_type", None)
        pending_prompt = getattr(self, "_prompt_text", None)
        pending_contents = getattr(self, "_contents", None)

        super().save(*args, **kwargs)

        if not self.material:
            material = Material.objects.create(
                title=self.title or '',
                item_type=pending_item_type or 'word',
                prompt_text=pending_prompt or '',
                content_text=pending_contents or '',
                content_json={},
                type='practice',
                status=self.status or 'draft',
                difficulty_level=pending_difficulty or '',
                section=self.section,
                is_active=self.is_active,
            )
            self.material = material
            super().save(update_fields=['material'])
            return

        updated_fields = []
        if self.material.title != self.title:
            self.material.title = self.title or ''
            updated_fields.append('title')
        if pending_item_type is not None and self.material.item_type != pending_item_type:
            self.material.item_type = pending_item_type or ''
            updated_fields.append('item_type')
        if pending_prompt is not None and self.material.prompt_text != pending_prompt:
            self.material.prompt_text = pending_prompt or ''
            updated_fields.append('prompt_text')
        if pending_contents is not None and self.material.content_text != pending_contents:
            self.material.content_text = pending_contents or ''
            updated_fields.append('content_text')
        if pending_difficulty is not None and self.material.difficulty_level != pending_difficulty:
            self.material.difficulty_level = pending_difficulty or ''
            updated_fields.append('difficulty_level')
        if self.material.status != self.status:
            self.material.status = self.status or 'draft'
            updated_fields.append('status')
        if self.material.is_active != self.is_active:
            self.material.is_active = self.is_active
            updated_fields.append('is_active')
        if self.material.section_id != self.section_id:
            self.material.section = self.section
            updated_fields.append('section')
        if updated_fields:
            self.material.save(update_fields=updated_fields)

    @property
    def difficulty_level(self):
        return getattr(self.material, "difficulty_level", "") or getattr(self, "_difficulty_type", "")

    @property
    def content_text(self):
        return getattr(self.material, "content_text", "") or getattr(self, "_contents", "")

    @content_text.setter
    def content_text(self, value):
        if self.material:
            self.material.content_text = value or ''
            self.material.save(update_fields=["content_text"])
        else:
            self._contents = value or ''

    @property
    def item_type(self):
        return getattr(self.material, "item_type", "") or getattr(self, "_practice_type", "")

    def get_item_type_display(self):
        if self.material and hasattr(self.material, "get_item_type_display"):
            return self.material.get_item_type_display()
        return dict(self.PRACTICE_TYPE_CHOICES).get(self.practice_type or '', '')

    def get_status_display(self):
        if self.material and hasattr(self.material, "get_status_display"):
            return self.material.get_status_display()
        return dict(self.STATUS_CHOICES).get(self.status or '', '')

    def get_practice_type_display(self):
        return self.get_item_type_display()

    def delete(self, *args, **kwargs):
        linked_material = self.material
        super().delete(*args, **kwargs)
        if linked_material:
            try:
                linked_material.delete()
            except Exception:
                pass

    def get_attempts(self, student=None):
        attempts = getattr(self, "attempts", None) or []
        if not isinstance(attempts, list):
            return []
        if student:
            return [a for a in attempts if a.get("student_id") == student.id]
        latest = {}
        for a in attempts:
            sid = a.get("student_id")
            if sid is None:
                continue
            if sid not in latest or a.get("started_at", "") >= latest[sid].get("started_at", ""):
                latest[sid] = a
        return list(latest.values())

    def get_student_latest_attempt(self, student):
        student_attempts = self.get_attempts(student)
        return student_attempts[-1] if student_attempts else None

    def _get_attempt_entry(self, student, status="started", started_at=None, **kwargs):
        entry = {
            "student_id": student.id,
            "started_at": started_at or timezone.now().isoformat(),
            "status": status,
        }
        for key in [
            "completed_at", "device_info", "mic_used", "accuracy", "wpm",
            "fluency_score", "pronunciation_score", "time_score",
            "total_score", "crla_classification", "classification",
            "duration_seconds", "word_count", "transcript",
            "speech_recognition_used", "needs_manual_review",
            "passed", "remarks", "score", "correct_responses",
            "incorrect_responses", "reading_time_seconds",
            "attempt_number", "stars_earned", "items_completed",
            "total_practice_items", "total_read_words", "total_skipped_words",
        ]:
            if key in kwargs:
                entry[key] = kwargs[key]
        return entry

    def _save_attempts(self):
        self.updated_at = timezone.now()
        self.save(update_fields=["attempts", "updated_at"])

    def record_attempt(self, student, replace=True, **attempt_data):
        attempts = getattr(self, "attempts", None) or []
        entry = self._get_attempt_entry(student, **attempt_data)
        if replace:
            attempts = [a for a in attempts if a.get("student_id") != student.id]
            attempts.append(entry)
        else:
            attempts.append(entry)
        self.attempts = attempts
        self._save_attempts()
        return entry

    def deactivate_student_attempts(self, student):
        attempts = getattr(self, "attempts", None) or []
        changed = False
        for attempt in attempts:
            if attempt.get("student_id") == student.id and attempt.get("status") != "cancelled":
                attempt["status"] = "cancelled"
                changed = True
        if changed:
            self.attempts = attempts
            self._save_attempts()
        return changed

    def clear_all_attempts(self):
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

    SOURCE_TYPE_CHOICES = [
        ("personal", "Personal"),
        ("shared", "Shared"),
    ]

    STATUS_CHOICES = [
        ("published", "Published"),
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
    ]

    USAGE_TYPE_CHOICES = [
        ("practice", "Practice"),
        ("assessment", "Assessment"),
        ("both", "Both"),
    ]

    # Materials are the assignable reading content. Assessment rows store
    # student result attempts and point back here through Assessment.material.
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="materials", null=True, blank=True)
    section = models.ForeignKey("Section", on_delete=models.SET_NULL, related_name="materials", null=True, blank=True)
    assigned_sections = models.ManyToManyField("Section", related_name="assigned_materials", blank=True)
    code = models.CharField(max_length=30, unique=True, blank=True, default="")
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="materials", null=True, blank=True)
    title = models.CharField(max_length=150, blank=True, default='')
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    prompt_text = models.TextField(blank=True, default='')
    content_text = models.TextField(blank=True, default='')
    content_json = models.JSONField(default=dict, blank=True)
    type = models.CharField(max_length=20, choices=USAGE_TYPE_CHOICES, default='practice')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES, default='personal')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    difficulty_level = models.CharField(max_length=50, blank=True)
    source_type = models.CharField(
        max_length=20,
        choices=[
            ("personal", "Personal"),
            ("shared", "Shared"),
        ],
        default="personal",
    )
    # Optional week assignment (1-99) for grouping materials by week
    assigned_week = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(99)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "materials"
        ordering = ["section", "created_at"]

    def __str__(self):
        parent = self.code or (self.section.class_code if self.section else 'UNLINKED')
        title_part = f" - {self.title}" if self.title else ''
        return f"{parent} - {self.item_type}{title_part}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_code()
        if self.teacher_id is None and self.section_id and getattr(self.section, "teacher_id", None):
            self.teacher = self.section.teacher
        super().save(*args, **kwargs)

    @classmethod
    def _generate_code(cls):
        candidate = "MAT" + uuid.uuid4().hex[:8].upper()
        while cls.objects.filter(code=candidate).exists():
            candidate = "MAT" + uuid.uuid4().hex[:8].upper()
        return candidate

    def _build_result_code(self, attempt_number):
        base = (self.code or self._generate_code()).strip()
        candidate = f"{base}-R{attempt_number}"
        while Assessment.objects.filter(code=candidate).exists():
            candidate = f"{base}-R{attempt_number}-{uuid.uuid4().hex[:6].upper()}"
        return candidate

    def student_result_count(self, student):
        return self.assessment_results.filter(student=student).count()

    def has_student_completed(self, student):
        return self.assessment_results.filter(student=student, attempt_status="completed").exists()

    def record_assessment_result(self, student, **attempt_data):
        attempt_id = attempt_data.pop("attempt_id", None) or str(uuid.uuid4())
        attempt_number = attempt_data.pop("attempt_number", None)
        if not attempt_number:
            attempt_number = self.student_result_count(student) + 1

        status_value = str(attempt_data.pop("status", "completed") or "completed")
        completed_at_value = attempt_data.pop("completed_at", None)
        if isinstance(completed_at_value, str):
            completed_at_value = timezone.now()
        started_at_value = attempt_data.pop("started_at", None) or timezone.now()
        if isinstance(started_at_value, str):
            started_at_value = timezone.now()

        teacher = self.teacher or (self.section.teacher if self.section_id and self.section else None)
        result = Assessment.objects.create(
            title=self.title or self.prompt_text or "Assessment Result",
            code=self._build_result_code(attempt_number),
            assessment_type=self.item_type,
            status=self.status,
            scheduled_at=self.scheduled_at if self.status == "scheduled" else None,
            teacher=teacher,
            section=self.section,
            material=self,
            student=student,
            attempt_id=str(attempt_id),
            attempt_number=attempt_number,
            attempt_status=status_value,
            started_at=started_at_value,
            completed_at=completed_at_value or (timezone.now() if status_value == "completed" else None),
            is_active=True,
        )
        result._apply_attempt_payload(result, attempt_data)
        return result._serialize_attempt()


# Assessment attempts are stored in the Assessment `attempts` JSONField.


class Course(models.Model):
    """
    Courses group assessments and materials and allow per-section scheduling/tracking.
    A Course is owned by a teacher and can include multiple sections and assessments.
    """
    code = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="courses")
    sections = models.ManyToManyField("Section", related_name="courses", blank=True)
    # assessments and materials are attached directly to Course
    assessments = models.ManyToManyField('Assessment', related_name='courses', blank=True)
    materials = models.ManyToManyField('Material', related_name='courses', blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "courses"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.title}"
    


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
