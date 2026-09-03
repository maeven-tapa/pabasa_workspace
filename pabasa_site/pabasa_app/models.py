import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, transaction
from django.db.models.functions import Lower
from django.utils import timezone
from datetime import datetime


def _configured_term_for_date(value, phase=''):
    """Return the calendar-configured term containing ``value``."""
    if not value:
        return None
    check_date = timezone.localtime(value).date() if isinstance(value, datetime) and timezone.is_aware(value) else (
        value.date() if isinstance(value, datetime) else value
    )
    phase_event_types = {
        'pretest': ('pre_assessment',),
        'midtest': ('midline_assessment',),
        'posttest': ('post_assessment',),
    }
    assessment_event = CalendarEvent.objects.filter(
        start_date__lte=check_date,
        end_date__gte=check_date,
        event_type__in=phase_event_types.get(
            str(phase or '').strip().lower(),
            ('pre_assessment', 'midline_assessment', 'post_assessment'),
        ),
        school_calendar__is_active=True,
    ).order_by('-school_calendar__updated_at', 'term', 'id').first()
    if assessment_event:
        return assessment_event.term
    term_event = CalendarEvent.objects.filter(
        start_date__lte=check_date,
        end_date__gte=check_date,
        event_type__in=('school_opening', 'school_closing'),
        school_calendar__is_active=True,
    ).order_by('-school_calendar__updated_at', 'term', 'id').first()
    return term_event.term if term_event else None


def default_unlocked_themes():
    return ["sky"]


class User(models.Model):
    ACCOUNT_STATUS_CHOICES = [
        ("active", "Active"),
        ("pending_archive", "Pending Archive"),
        ("archived", "Archived"),
    ]
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
    must_change_password = models.BooleanField(default=False)
    profile_picture = models.CharField(max_length=255, blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)
    preference = models.JSONField(default=dict, blank=True)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    account_status = models.CharField(max_length=20, choices=ACCOUNT_STATUS_CHOICES, default="active")
    # Teacher-specific fields
    teacher_role = models.CharField(max_length=50, blank=True, null=True)
    school = models.CharField(max_length=150, blank=True, null=True)
    school_record = models.ForeignKey(
        "School",
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )
    school_calendar = models.ForeignKey(
        "SchoolCalendar",
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )
    department = models.CharField(max_length=100, blank=True, null=True)
    # Student-specific fields
    lrn = models.CharField(
        "Learner Reference Number",
        max_length=12,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(regex=r"^\d{12}$", message="LRN must contain exactly 12 digits.")],
    )
    grade_level = models.CharField(max_length=20, blank=True, null=True)
    section = models.CharField(max_length=50, blank=True, null=True)
    reading_level = models.CharField(max_length=50, blank=True, null=True)
    available_stars = models.PositiveIntegerField(default=0)
    theme_stars_credited = models.PositiveIntegerField(default=0)
    unlocked_themes = models.JSONField(default=default_unlocked_themes, blank=True)
    equipped_theme = models.CharField(max_length=30, default="sky")
    animal_avatar = models.CharField(max_length=20, default="cat", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"
        ordering = ["last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["school_record"],
                condition=models.Q(role="principal", is_archived=False, school_record__isnull=False),
                name="unique_active_principal_per_school",
            ),
        ]

    def __str__(self):
        return f"{self.custom_id} - {self.last_name}, {self.first_name}"

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password_hash)

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

    def set_account_status(self, status, changed_by=None, reason=""):
        if status not in dict(self.ACCOUNT_STATUS_CHOICES):
            raise ValidationError({"account_status": "Invalid account status."})
        now = timezone.now()
        self.account_status = status
        self.is_archived = status == "archived"
        self.archived_at = now if self.is_archived else None
        self.save(update_fields=["account_status", "is_archived", "archived_at", "updated_at"])
        AccountStatusHistory.objects.create(
            student=self, status=status, changed_by=changed_by, reason=reason
        )

    def sync_legacy_student_fields(self, enrollment=None):
        if self.role != "student":
            return
        enrollment = enrollment or self.enrollments.filter(
            status="active", is_active=True, school_calendar__is_active=True,
            section__is_active=True, grade_level="Grade 2",
        ).select_related("section", "school_calendar", "school").first()
        if enrollment:
            self.grade_level = enrollment.grade_level or "Grade 2"
            self.section = enrollment.section.section if enrollment.section_id else None
            self.school_calendar_id = enrollment.school_calendar_id
            self.school = enrollment.school.name if enrollment.school_id else self.school
        else:
            self.grade_level = "Grade 2"
            self.section = None
            self.school_calendar = None
        self.save(update_fields=["grade_level", "section", "school_calendar", "school", "updated_at"])


class HuntStarAward(models.Model):
    """Immutable, idempotent star deposits made only by Hunt Mode."""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="hunt_star_awards")
    material = models.ForeignKey("Material", on_delete=models.CASCADE, related_name="hunt_star_awards")
    attempt_id = models.CharField(max_length=64)
    award_key = models.CharField(max_length=32)  # word:<index> or completion
    word_index = models.PositiveSmallIntegerField(null=True, blank=True)
    tier = models.CharField(max_length=16, blank=True)
    stars = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hunt_star_awards"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "material", "attempt_id", "award_key"],
                name="unique_hunt_attempt_award",
            )
        ]


class School(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, unique=True, blank=True, default="")
    address = models.TextField(blank=True, default="")
    contact_information = models.TextField(blank=True, default="")
    logo = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "schools"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def archive(self):
        self.status = "archived"
        self.is_active = False
        self.save(update_fields=["status", "is_active", "updated_at"])

    def reactivate(self):
        self.status = "active"
        self.is_active = True
        self.save(update_fields=["status", "is_active", "updated_at"])


class Section(models.Model):
    school = models.ForeignKey(
        School,
        on_delete=models.PROTECT,
        related_name="sections",
    )
    school_calendar = models.ForeignKey(
        "SchoolCalendar",
        on_delete=models.PROTECT,
        related_name="sections",
        null=True,
        blank=True,
    )
    class_code = models.CharField(max_length=20, unique=True)
    class_name = models.CharField(max_length=150)
    header = models.CharField(max_length=100, default="Reading Class")
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="sections",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    # Deliberately section-scoped so one section's assessment period never
    # changes another section's learning flow.
    assessment_week_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    subject = models.CharField(max_length=50)
    grade_level = models.CharField(max_length=20, blank=True)
    section = models.CharField(max_length=50, blank=True)

    # Stores joined students as JSON entries:
    # {"student_id": ..., "custom_id": ..., "first_name": ..., "last_name": ..., "email": ..., "joined_at": ..., "is_active": ...}
    students = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "sections"
        ordering = ["class_name"]
        constraints = [
            models.UniqueConstraint(
                "school",
                "school_calendar",
                Lower("grade_level"),
                Lower("section"),
                condition=models.Q(grade_level__gt="", section__gt=""),
                name="unique_school_calendar_canonical_grade_section",
            ),
        ]

    def __str__(self):
        return f"{self.class_code} - {self.class_name}"

    def save(self, *args, **kwargs):
        if self.school_id is None:
            raise ValidationError({"school": "A Section must belong to an explicit School."})
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        self.grade_level = (self.grade_level or "").strip()
        self.section = (self.section or "").strip()
        if self.teacher_id and self.teacher.role != "teacher":
            raise ValidationError({"teacher": "Only a teacher account can be assigned to a section."})
        if self.teacher_id and self.teacher.is_archived:
            raise ValidationError({"teacher": "Archived teachers cannot be assigned to an active section."})

    @property
    def student_count(self):
        return self.get_student_count()

    def active_teacher_name(self):
        if not self.has_active_teacher():
            return ""
        return f"{self.teacher.first_name} {self.teacher.last_name}".strip()

    def has_active_teacher(self):
        """Return whether this Section has an active teacher assignment."""
        return bool(
            self.teacher_id
            and self.teacher
            and self.teacher.role == "teacher"
            and not self.teacher.is_archived
        )

    def teacher_is_available(self):
        return not self.has_active_teacher()

    def sync_legacy_student_fields(self):
        students = self.get_enrolled_students()
        self.students = students
        self._save_enrollment()

    def assign_teacher(self, teacher_user, replace_existing=False):
        if not teacher_user or teacher_user.role != "teacher":
            raise ValidationError({"teacher": "Only a teacher account can be assigned to a section."})
        if teacher_user.is_archived:
            raise ValidationError({"teacher": "Archived teachers cannot be assigned to a section."})

        with transaction.atomic():
            locked_self = Section.objects.select_for_update().get(pk=self.pk)
            conflicting = Section.objects.select_for_update().filter(
                teacher=teacher_user,
                school_calendar_id=locked_self.school_calendar_id,
                is_active=True,
                grade_level__iexact="Grade 2",
            ).exclude(pk=locked_self.pk).first()
            if conflicting:
                raise ValidationError({"teacher": "This teacher is already assigned to another active section."})

            current_teacher = locked_self.teacher
            if locked_self.has_active_teacher() and locked_self.teacher_id != teacher_user.id and not replace_existing:
                raise ValidationError({"teacher": "This section already has an assigned teacher."})

            locked_self.teacher = teacher_user
            locked_self.save(update_fields=["teacher", "updated_at"])
            self.teacher = teacher_user
            return current_teacher

    def unassign_teacher(self):
        if not self.teacher_id:
            # The instance may predate a concurrent assignment or a prior
            # assign_teacher() call that updated the database row.
            self.refresh_from_db(fields=["teacher"])
        if not self.teacher_id:
            return False
        self.teacher = None
        self.save(update_fields=["teacher", "updated_at"])
        return True

    def get_tag_label(self):
        return f"{self.class_name} ({self.class_code})"
    
    # Enrollment Management Methods
    def get_enrolled_students(self, active_only=False):
        """Return student entries derived from relational enrollments."""
        enrollments = self.enrollments.select_related("student").all()
        if active_only:
            enrollments = enrollments.filter(status="active", is_active=True)
        return [self._get_student_entry(e.student, e.joined_at.isoformat() if e.joined_at else None, e.is_active) for e in enrollments]
    
    def has_student(self, user, active_only=True):
        """Check if user is enrolled in this section"""
        if not user or not user.id:
            return False
        
        query = self.enrollments.filter(student_id=user.id)
        if active_only:
            query = query.filter(status="active", is_active=True)
        return query.exists()
    
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
        if not user or user.role != "student":
            raise ValidationError("Only a student account can be enrolled in a section.")

        with transaction.atomic():
            Section.objects.select_for_update().get(pk=self.pk)
            Enrollment.objects.select_for_update().filter(
                student=user, school_calendar_id=self.school_calendar_id,
                status__in=("active", "awaiting_assignment"), is_active=True,
            ).exclude(section=self).update(status="completed", is_active=False)
            enrollment, created = Enrollment.objects.get_or_create(
                student=user,
                section=self,
                defaults={"is_active": True},
            )
            was_active = not created and enrollment.is_active
            if enrollment.status != "active" or not enrollment.is_active:
                enrollment.activate()

            students = self.get_enrolled_students()
            for index, entry in enumerate(students):
                if (str(entry.get('student_id')) == str(user.id) or
                        entry.get('custom_id') == user.custom_id):
                    entry.update(self._get_student_entry(user, entry.get('joined_at'), is_active=True))
                    students[index] = entry
                    break
            else:
                students.append(self._get_student_entry(user, enrollment.joined_at.isoformat()))
            self.students = students
            self._save_enrollment()
            user.grade_level = self.grade_level
            user.section = self.section
            user.school_calendar_id = self.school_calendar_id
            user.school = self.school.name if self.school_id else user.school
            user.save(update_fields=["grade_level", "section", "school_calendar", "school", "updated_at"])
            user.add_tag(self.get_tag_label())
            return not was_active

    def move_student(self, user, destination_section):
        if not user or user.role != "student":
            raise ValidationError("Only a student account can be moved between sections.")
        if not destination_section or destination_section.pk == self.pk:
            return False
        with transaction.atomic():
            source_section = Section.objects.select_for_update().get(pk=self.pk)
            target_section = Section.objects.select_for_update().get(pk=destination_section.pk)
            source_section.deactivate_student(user)
            target_section.add_student(user)
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
        enrollment_changed = Enrollment.objects.filter(
            student=user,
            section=self,
            status__in=("active", "awaiting_assignment"),
            is_active=True,
        ).update(status="completed", is_active=False)
        if changed:
            self.students = students
            self._save_enrollment()
        if changed or enrollment_changed:
            user.remove_tag(tag_label)
        return bool(changed or enrollment_changed)
    
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
        relational_student_ids = set(
            Enrollment.objects.filter(section=self, is_active=True).values_list("student_id", flat=True)
        )
        if changed:
            self.students = students
            self._save_enrollment()
        enrollment_changed = Enrollment.objects.filter(
            section=self, status__in=("active", "awaiting_assignment"), is_active=True
        ).update(status="completed", is_active=False)
        for student_user in User.objects.filter(id__in=affected_student_ids | relational_student_ids):
            student_user.remove_tag(tag_label)
        return bool(changed or enrollment_changed)


class Enrollment(models.Model):
    """A student's membership in a school-year Grade 2 section.

    The nullable school-year fields keep legacy rows usable while the data
    migration fills them from their existing Section relationship.
    """
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("awaiting_assignment", "Awaiting Assignment"),
    ]
    OUTCOME_CHOICES = [
        ("not_finalized", "Not Finalized"),
        ("promoted", "Promoted"),
        ("retained", "Retained"),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="enrollments")
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="enrollments", null=True, blank=True)
    school = models.ForeignKey("School", on_delete=models.PROTECT, related_name="enrollments", null=True, blank=True)
    school_calendar = models.ForeignKey("SchoolCalendar", on_delete=models.PROTECT, related_name="enrollments", null=True, blank=True)
    grade_level = models.CharField(max_length=20, default="Grade 2", blank=True)
    assigned_teacher = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="assigned_enrollments", null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="active")
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, default="not_finalized")
    finalized_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="finalized_enrollments", null=True, blank=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "class_enrollments"
        ordering = ["-joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "section"],
                name="unique_student_section_enrollment",
            ),
            models.UniqueConstraint(
                fields=["student", "school_calendar"],
                condition=models.Q(
                    school_calendar__isnull=False,
                    status__in=["active", "awaiting_assignment"],
                ),
                name="unique_current_student_school_year",
            ),
        ]

    def clean(self):
        super().clean()
        if self.student_id and self.student.role != "student":
            raise ValidationError({"student": "Only a student account can be enrolled in a section."})
        if self.section_id and not self.section.is_active:
            raise ValidationError({"section": "Cannot enroll a student in an inactive section."})
        if self.section_id:
            if self.school_id and self.school_id != self.section.school_id:
                raise ValidationError({"school": "Enrollment school must match its section."})
            if self.school_calendar_id and self.school_calendar_id != self.section.school_calendar_id:
                raise ValidationError({"school_calendar": "Enrollment school year must match its section."})

    def save(self, *args, **kwargs):
        if self.section_id:
            self.school_id = self.school_id or self.section.school_id
            self.school_calendar_id = self.school_calendar_id or self.section.school_calendar_id
            self.grade_level = self.grade_level or self.section.grade_level or "Grade 2"
            self.assigned_teacher_id = self.assigned_teacher_id or self.section.teacher_id
        self.is_active = self.status == "active"
        super().save(*args, **kwargs)

    def activate(self):
        self.status = "active"
        self.is_active = True
        self.save(update_fields=["status", "is_active", "updated_at"])

    def await_assignment(self):
        self.status = "awaiting_assignment"
        self.is_active = False
        self.save(update_fields=["status", "is_active", "updated_at"])

    def complete(self):
        self.status = "completed"
        self.is_active = False
        self.save(update_fields=["status", "is_active", "updated_at"])

    def deactivate(self):
        self.complete()

    def finalize_outcome(self, outcome, finalized_by=None):
        if outcome not in {"promoted", "retained"}:
            raise ValidationError({"outcome": "Outcome must be promoted or retained."})
        with transaction.atomic():
            self.outcome = outcome
            self.status = "completed"
            self.finalized_by = finalized_by
            self.finalized_at = timezone.now()
            self.save(update_fields=["outcome", "status", "is_active", "finalized_by", "finalized_at", "updated_at"])
            self.student.set_account_status(
                "pending_archive" if outcome == "promoted" else "active",
                changed_by=finalized_by,
                reason=f"{outcome.title()} at end of school year",
            )

    def __str__(self):
        return f"{self.student.custom_id} in {self.section.class_code if self.section_id else 'Unassigned'}"


class AccountStatusHistory(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="account_status_history")
    status = models.CharField(max_length=20, choices=User.ACCOUNT_STATUS_CHOICES)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="account_status_changes")
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

class Assessment(models.Model):
    SYSTEM_ASSESSMENT_CHOICES = [
        ("", "Teacher Owned"),
        ("bosy_crla_pretest", "BoSY CRLA Pre-Test"),
        ("midline_crla_midtest", "Midline CRLA Mid-Test"),
        ("eosy_crla_posttest", "EoSY CRLA Post-Test"),
    ]

    ASSESSMENT_TYPE_CHOICES = [
        ("word", "Word"),
        ("vowel", "Vowel"),
        ("sentence", "Sentence"),
        ("paragraph", "Paragraph"),
    ]
    
    STATUS_CHOICES = [
        ("published", "Published"),
        ("draft", "Draft"),
        ("archived", "Archived"),
        ("scheduled", "Scheduled"),
    ]

    title = models.CharField(max_length=150)
    code = models.CharField(max_length=30, unique=True)
    is_system_owned = models.BooleanField(default=False)
    system_assessment_key = models.CharField(max_length=40, choices=SYSTEM_ASSESSMENT_CHOICES, blank=True, default="")
    system_assessment_period = models.CharField(max_length=10, blank=True, default="")
    system_assessment_phase = models.CharField(max_length=10, blank=True, default="")
    official_term = models.PositiveSmallIntegerField(null=True, blank=True)
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
    enrollment = models.ForeignKey("Enrollment", null=True, blank=True, on_delete=models.SET_NULL, related_name="assessment_attempts")
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
    correct_items = models.PositiveIntegerField(null=True, blank=True)
    # Immutable-at-completion CRLA task and Part 2 inputs.  This is kept
    # separate from legacy aggregate score columns so an attempt is auditable.
    crla_score_data = models.JSONField(default=dict, blank=True)

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

    @staticmethod
    def _coerce_attempt_datetime(value):
        if value in (None, ''):
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                parsed_value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                return None
            if timezone.is_naive(parsed_value):
                return timezone.make_aware(parsed_value, timezone.get_default_timezone())
            return parsed_value
        return None

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
            'correct_items': self.correct_items,
            'crla_score_data': self.crla_score_data,
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
                attempt_row.started_at = self._coerce_attempt_datetime(started_at) or started_at
            except Exception:
                attempt_row.started_at = timezone.now()
        completed_at = attempt_data.pop('completed_at', None)
        if completed_at is not None:
            try:
                attempt_row.completed_at = self._coerce_attempt_datetime(completed_at) or completed_at
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
            elif key == 'correct_items':
                attempt_row.correct_items = value
            elif key == 'crla_score_data':
                attempt_row.crla_score_data = value if isinstance(value, dict) else {}
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
            if self.section_id and self.section.school_calendar_id:
                rows = rows.filter(enrollment__student_id=student.id, enrollment__school_calendar_id=self.section.school_calendar_id)
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

        started_at_value = self._coerce_attempt_datetime(attempt_data.pop('started_at', None)) or timezone.now()
        completed_at_value = attempt_data.pop('completed_at', None)
        completed_at_value = self._coerce_attempt_datetime(completed_at_value)
        attempt_completed_at = completed_at_value or timezone.now()
        official_term = _configured_term_for_date(attempt_completed_at, self.system_assessment_phase) if self.is_system_owned else None
        if official_term is None:
            official_term = getattr(self.material, 'official_term', None) if self.material_id else self.official_term
        attempt_enrollment = attempt_data.pop('enrollment', None)
        if attempt_enrollment is None and self.section_id and self.section.school_calendar_id:
            attempt_enrollment = Enrollment.objects.filter(
                student=student, section=self.section,
                school_calendar_id=self.section.school_calendar_id,
            ).order_by('id').first()
        attempt_row = Assessment.objects.create(
            title=self.title,
            code=self._build_attempt_code(group_assessment.code, attempt_number),
            assessment_type=self.assessment_type,
            status=self.status,
            scheduled_at=self.scheduled_at,
            teacher=self.teacher,
            section=self.section,
            is_active=self.is_active,
            is_system_owned=self.is_system_owned,
            system_assessment_key=self.system_assessment_key,
            system_assessment_period=self.system_assessment_period,
            system_assessment_phase=self.system_assessment_phase,
            official_term=official_term,
            source_assessment=group_assessment,
            student=student,
            enrollment=attempt_enrollment,
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
            current = Enrollment.objects.filter(
                student=student, status="active", is_active=True,
                school_calendar__is_active=True, section__is_active=True,
                section=self.section,
            ).order_by("id").first() if self.section_id else None
            if current:
                return [a for a in attempts if a.get("student_id") == student.id and str(a.get("enrollment_id")) == str(current.id)]
            return []
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
        enrollment = kwargs.pop("enrollment", None)
        entry = {
            "student_id": student.id,
            "started_at": started_at or timezone.now().isoformat(),
            "status": status,
        }
        if enrollment is not None:
            entry["enrollment_id"] = enrollment.id
        for key in [
            "completed_at", "device_info", "mic_used", "accuracy", "wpm",
            "fluency_score", "pronunciation_score", "time_score",
            "total_score", "crla_classification", "classification",
            "duration_seconds", "word_count", "transcript",
            "speech_recognition_used", "needs_manual_review",
            "passed", "remarks", "score", "correct_responses",
            "incorrect_responses", "reading_time_seconds",
            "attempt_number", "stars_earned", "items_completed", "correct_items",
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
        if "enrollment" not in attempt_data and self.section_id:
            attempt_data["enrollment"] = Enrollment.objects.filter(
                student=student, section=self.section, status="active", is_active=True,
                school_calendar__is_active=True,
            ).order_by("id").first()
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
        ("vowel", "Vowel"),
        ("sentence", "Sentence"),
        ("paragraph", "Paragraph"),
    ]

    SOURCE_TYPE_CHOICES = [
        ("personal", "Personal"),
        ("shared", "Shared"),
        ("template", "Template"),
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

    ASSESSMENT_SET_CHOICES = [
        ("crla", "CRLA Assessment Set"),
        ("word", "Word Assessment Set"),
        ("sentence", "Sentence Assessment Set"),
        ("paragraph", "Paragraph Assessment Set"),
    ]

    ASSESSMENT_KIND_CHOICES = [
        ("regular", "Regular Reading Material"),
        ("crla", "CRLA Assessment"),
    ]

    # Materials are the assignable reading content. Assessment rows store
    # student result attempts and point back here through Assessment.material.
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="materials", null=True, blank=True)
    section = models.ForeignKey("Section", on_delete=models.SET_NULL, related_name="materials", null=True, blank=True)
    assigned_sections = models.ManyToManyField("Section", related_name="assigned_materials", blank=True)
    code = models.CharField(max_length=30, unique=True, blank=True, default="")
    is_system_owned = models.BooleanField(default=False)
    system_assessment_key = models.CharField(max_length=40, blank=True, default=None, unique=True, null=True)
    system_assessment_period = models.CharField(max_length=10, blank=True, default="")
    system_assessment_phase = models.CharField(max_length=10, blank=True, default="")
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="materials", null=True, blank=True)
    title = models.CharField(max_length=150, blank=True, default='')
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    prompt_text = models.TextField(blank=True, default='')
    content_text = models.TextField(blank=True, default='')
    content_json = models.JSONField(default=dict, blank=True)
    assessment_set = models.CharField(max_length=20, choices=ASSESSMENT_SET_CHOICES, blank=True, default="")
    assessment_kind = models.CharField(max_length=20, choices=ASSESSMENT_KIND_CHOICES, default="regular")
    language = models.CharField(max_length=20, default="English", blank=True)
    type = models.CharField(max_length=20, choices=USAGE_TYPE_CHOICES, default='practice')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES, default='personal')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    is_official_reading = models.BooleanField(default=False)
    official_term = models.PositiveSmallIntegerField(null=True, blank=True)
    official_pdf = models.FileField(upload_to="official_readings/", null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    difficulty_level = models.CharField(max_length=50, blank=True)
    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPE_CHOICES,
        default="personal",
    )
    # Optional week assignment (1-99) for grouping materials by week
    assigned_week = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(99)],
    )
    assigned_weeks = models.JSONField(default=list, blank=True)
    student_access = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "materials"
        ordering = ["section", "created_at"]

    @staticmethod
    def normalize_language_value(value):
        if value is None:
            return "English"

        normalized = str(value).strip()
        if not normalized:
            return "English"

        lowered = normalized.lower()
        if lowered in {"english", "en", "eng"}:
            return "English"
        if lowered in {"filipino", "fil", "filipina", "tl", "tagalog", "tag", "tagalog language", "filipino language"}:
            return "Filipino"
        return normalized

    def get_saved_language(self):
        content_json = self.content_json or {}
        if isinstance(content_json, dict):
            for key in ("language", "language_context", "languageContext"):
                value = content_json.get(key)
                if isinstance(value, str):
                    value = value.strip()
                    if value:
                        return self.normalize_language_value(value)
        return ""

    def get_saved_language_display(self):
        value = self.get_saved_language()
        return value if value else "Not Set"

    def __str__(self):
        parent = self.code or (self.section.class_code if self.section else 'UNLINKED')
        title_part = f" - {self.title}" if self.title else ''
        return f"{parent} - {self.item_type}{title_part}"

    def is_assessment_content(self):
        return str(self.type or "").strip().lower() in {"assessment", "both"} or bool(self.assessment_set)

    def is_protected_system_assessment(self):
        return bool(self.is_system_owned or (self.system_assessment_key or "").strip())

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_code()
        self.language = self.normalize_language_value(self.language or self.get_saved_language())
        if isinstance(self.content_json, dict):
            self.content_json.setdefault("language", self.language)
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
        result_completed_at = completed_at_value or (timezone.now() if status_value == "completed" else None)

        teacher = self.teacher or (self.section.teacher if self.section_id and self.section else None)
        if teacher is None and student is not None:
            try:
                student_section = next(
                    (
                        section for section in Section.objects.filter(is_active=True).select_related('teacher')
                        if section.has_student(student, active_only=True)
                    ),
                    None,
                )
                if student_section and getattr(student_section, 'teacher', None):
                    teacher = student_section.teacher
            except Exception:
                teacher = teacher
        if teacher is None:
            teacher = User.objects.filter(role='teacher', is_archived=False).order_by('id').first()
        if teacher is None:
            teacher = User.objects.filter(role__in=['teacher', 'admin'], is_archived=False).order_by('id').first()
        if teacher is None:
            teacher = User.objects.filter(is_archived=False).order_by('id').first()
        if teacher is None:
            raise ValueError("Unable to resolve a teacher for assessment result recording.")

        system_assessment_period = str(getattr(self, "system_assessment_period", "") or "").strip().lower()
        system_assessment_phase = str(getattr(self, "system_assessment_phase", "") or "").strip().lower()
        if self.is_system_owned and not system_assessment_period:
            system_assessment_period = str(self.system_assessment_key or "").strip().lower().split("_", 1)[0] if self.system_assessment_key else ""
        if self.is_system_owned and not system_assessment_phase:
            system_assessment_phase = str(self.system_assessment_key or "").strip().lower().split("_", 1)[1] if "_" in str(self.system_assessment_key or "") else ""
        if self.is_system_owned and not system_assessment_period:
            system_assessment_period = "bosy"
        if self.is_system_owned and not system_assessment_phase:
            system_assessment_phase = "pretest"
        official_term = _configured_term_for_date(result_completed_at, system_assessment_phase) if self.is_official_reading or self.is_system_owned else None
        if official_term is None:
            official_term = self.official_term

        # Keep each material attempt in the student's active class enrollment.
        # The parent assessment uses this relationship when reporting completion
        # in the student's week-assessment cards.
        result_enrollment = None
        if student is not None:
            enrollment_qs = Enrollment.objects.filter(student=student, is_active=True)
            if self.section_id:
                enrollment_qs = enrollment_qs.filter(section_id=self.section_id)
            else:
                assigned_section_ids = list(self.assigned_sections.values_list('id', flat=True))
                if assigned_section_ids:
                    enrollment_qs = enrollment_qs.filter(section_id__in=assigned_section_ids)
            result_enrollment = enrollment_qs.order_by('-joined_at', '-id').first()
        
        # Ensure parent assessment exists for this material
        parent_assessment = self.assessment
        if parent_assessment is None:
            # Create a parent assessment if one doesn't exist
            # Generate a unique code for the parent assessment
            candidate_code = f"ASS{uuid.uuid4().hex[:8].upper()}"
            while Assessment.objects.filter(code=candidate_code).exists():
                candidate_code = f"ASS{uuid.uuid4().hex[:8].upper()}"
            
            parent_assessment = Assessment.objects.create(
                title=self.title or self.prompt_text or "Assessment",
                code=candidate_code,
                is_system_owned=bool(self.is_system_owned),
                system_assessment_key=self.system_assessment_key or "",
                system_assessment_period=system_assessment_period,
                system_assessment_phase=system_assessment_phase,
                official_term=official_term,
                assessment_type=self.item_type,
                status=self.status,
                scheduled_at=self.scheduled_at if self.status == "scheduled" else None,
                teacher=teacher,
                section=self.section,
                is_active=True,
                source_assessment=None,  # This is a parent assessment
            )
            # Link the material to this parent assessment
            self.assessment = parent_assessment
            self.save(update_fields=['assessment', 'updated_at'])
        
        result = Assessment.objects.create(
            title=self.title or self.prompt_text or "Assessment Result",
            code=self._build_result_code(attempt_number),
            is_system_owned=bool(self.is_system_owned),
            system_assessment_key=self.system_assessment_key or "",
            system_assessment_period=system_assessment_period,
            system_assessment_phase=system_assessment_phase,
            official_term=official_term,
            assessment_type=self.item_type,
            status=self.status,
            scheduled_at=self.scheduled_at if self.status == "scheduled" else None,
            teacher=teacher,
            section=self.section,
            material=self,
            student=student,
            enrollment=result_enrollment,
            attempt_id=str(attempt_id),
            attempt_number=attempt_number,
            attempt_status=status_value,
            started_at=started_at_value,
            completed_at=result_completed_at,
            is_active=True,
            source_assessment=parent_assessment,  # Link to parent assessment
        )
        result._apply_attempt_payload(result, attempt_data)
        return result._serialize_attempt()


# Assessment attempts are stored in the Assessment `attempts` JSONField.


class StoryReadingProgress(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="story_reading_progress")
    material = models.ForeignKey("Material", on_delete=models.CASCADE, related_name="story_reading_progress")
    enrollment = models.ForeignKey("Enrollment", null=True, blank=True, on_delete=models.SET_NULL, related_name="story_reading_progress")
    story_title = models.CharField(max_length=150, blank=True, default="")
    story_key = models.CharField(max_length=100, blank=True, default="")
    total_words = models.PositiveIntegerField(default=0)
    words_read = models.PositiveIntegerField(default=0)
    correct_words = models.PositiveIntegerField(default=0)
    miscues = models.PositiveIntegerField(default=0)
    accuracy = models.FloatField(default=0)
    wpm = models.FloatField(default=0)
    progress_percent = models.FloatField(default=0)
    correct_sentences = models.PositiveSmallIntegerField(default=0)
    reading_score = models.FloatField(default=0)
    word_alignment = models.JSONField(default=list, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    current_scene = models.PositiveSmallIntegerField(default=1)
    current_time_seconds = models.FloatField(default=0)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "story_reading_progress"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "material"],
                condition=models.Q(enrollment__isnull=True),
                name="unique_legacy_story_reading_progress",
            ),
            models.UniqueConstraint(
                fields=["enrollment", "material"],
                condition=models.Q(enrollment__isnull=False),
                name="unique_enrollment_story_reading_progress",
            ),
        ]


class StoryResponseSubmission(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending Grade"),
        ("graded", "Graded"),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="story_response_submissions")
    material = models.ForeignKey("Material", on_delete=models.CASCADE, related_name="story_response_submissions")
    enrollment = models.ForeignKey("Enrollment", null=True, blank=True, on_delete=models.SET_NULL, related_name="story_response_submissions")
    story_material = models.ForeignKey("Material", null=True, blank=True, on_delete=models.SET_NULL, related_name="story_response_source_submissions")
    prompt = models.TextField(blank=True, default="")
    response_text = models.TextField(blank=True, default="")
    audio_file = models.FileField(upload_to="story_responses/%Y/%m/%d/", null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    grade = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(5)])
    graded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="graded_story_response_submissions")
    graded_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "story_response_submissions"
        constraints = [
            models.UniqueConstraint(fields=["student", "material"], name="unique_story_response_student_material"),
        ]


class SchoolCalendar(models.Model):
    TERM_CHOICES = [(1, "Term 1"), (2, "Term 2"), (3, "Term 3"), (4, "Term 4")]

    school_year = models.CharField(max_length=20, unique=True)
    current_term = models.PositiveSmallIntegerField(
        choices=TERM_CHOICES
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "school_calendars"
        ordering = ["-is_active", "-created_at"]

    def __str__(self):
        return self.school_year


class CalendarEvent(models.Model):
    SCOPE_GLOBAL = "global"
    SCOPE_SCHOOL = "school"
    SCOPE_CHOICES = [(SCOPE_GLOBAL, "Global"), (SCOPE_SCHOOL, "School-local")]
    EVENT_TYPE_CHOICES = [
        ("start_of_classes", "Start of Classes"),
        ("end_of_classes", "End of Classes"),
        ("school_opening", "Opening Block"),
        ("school_closing", "End-of-Term Block"),
        ("pre_assessment", "Pre-Assessment Week"),
        ("midline_assessment", "Midline Assessment Week"),
        ("post_assessment", "Post-Assessment Week"),
        ("holiday", "Holiday"),
        ("examination", "Examination Week"),
        ("other", "Other Activity"),
    ]

    school_calendar = models.ForeignKey(
        SchoolCalendar,
        on_delete=models.CASCADE,
        related_name="events",
    )
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default=SCOPE_GLOBAL)
    school = models.ForeignKey(
        "School", null=True, blank=True, on_delete=models.PROTECT,
        related_name="calendar_events",
    )
    term = models.PositiveSmallIntegerField(
        choices=SchoolCalendar.TERM_CHOICES,
        default=1,
    )
    title = models.CharField(max_length=150)
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "calendar_events"
        ordering = ["start_date", "end_date"]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(scope="global", school__isnull=True) | models.Q(scope="school", school__isnull=False)),
                name="calendar_event_scope_school_consistent",
            ),
        ]

    def __str__(self):
        return f"{self.school_calendar.school_year} - {self.get_event_type_display()}"


class TeacherAralSchedule(models.Model):
    WEEKDAY_CHOICES = [(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")]
    APPLIES_TO_CURRENT = "current"
    APPLIES_TO_ALL = "all"
    APPLIES_TO_CHOICES = [
        (APPLIES_TO_CURRENT, "Current Term"),
        (APPLIES_TO_ALL, "All Terms"),
    ]

    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="aral_schedules")
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="teacher_aral_schedules")
    school_calendar = models.ForeignKey(SchoolCalendar, on_delete=models.CASCADE, related_name="teacher_aral_schedules")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES, validators=[MinValueValidator(0), MaxValueValidator(6)])
    remark = models.CharField(max_length=200)
    applies_to = models.CharField(max_length=10, choices=APPLIES_TO_CHOICES, default=APPLIES_TO_CURRENT)
    term = models.PositiveSmallIntegerField(choices=SchoolCalendar.TERM_CHOICES, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "teacher_aral_schedules"
        ordering = ["weekday", "section__class_name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(applies_to="all", term__isnull=True)
                    | models.Q(applies_to="current", term__isnull=False)
                ),
                name="teacher_aral_schedule_term_matches_scope",
            ),
        ]

    def clean(self):
        super().clean()
        if self.teacher_id and self.teacher.role != "teacher":
            raise ValidationError({"teacher": "Only a teacher account can own an ARAL schedule."})
        if self.section_id and self.teacher_id and self.section.teacher_id != self.teacher_id:
            raise ValidationError({"section": "ARAL schedules may only use the teacher's assigned sections."})
        if self.section_id and self.school_calendar_id and self.section.school_calendar_id != self.school_calendar_id:
            raise ValidationError({"school_calendar": "The schedule calendar must match the section calendar."})
        if self.applies_to == self.APPLIES_TO_ALL:
            self.term = None
        elif self.applies_to == self.APPLIES_TO_CURRENT and self.term is None:
            raise ValidationError({"term": "Current Term schedules require a term."})

    def __str__(self):
        return f"{self.teacher} - {self.section} - {self.get_weekday_display()}"


class Course(models.Model):
    """
    Courses group assessments and materials and allow per-section scheduling/tracking.
    A Course is owned by a teacher and can include multiple sections and assessments.
    """
    code = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    school = models.ForeignKey(
        School,
        on_delete=models.PROTECT,
        related_name="courses",
        null=True,
        blank=True,
    )
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

    def clean(self):
        super().clean()
        if self.school_id and self.teacher_id and self.teacher.school_record_id != self.school_id:
            raise ValidationError({"school": "Course school must match the teacher's school."})
        if self.pk and self.school_id:
            invalid_sections = self.sections.filter(
                ~models.Q(school_id=self.school_id) | ~models.Q(teacher_id=self.teacher_id)
            )
            if invalid_sections.exists():
                raise ValidationError({"sections": "All Course sections must belong to the Course school."})

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


class OfficialReadingIntegrityOverrideRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
        ("used", "Used"),
    ]

    request_id = models.CharField(max_length=40, unique=True)
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="official_override_requests")
    material = models.ForeignKey("Material", on_delete=models.CASCADE, related_name="official_override_requests")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    deped_reference = models.TextField()
    material_change = models.TextField()
    justification = models.TextField()
    supporting_documentation = models.JSONField(default=list, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_official_override_requests")
    review_decision = models.CharField(max_length=20, blank=True, default="")
    rejection_reason = models.TextField(blank=True, default="")
    authorized_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    audit_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "official_reading_integrity_override_requests"
        ordering = ["-submitted_at", "-id"]


class OfficialReadingIntegrityAuthorization(models.Model):
    request = models.OneToOneField(OfficialReadingIntegrityOverrideRequest, on_delete=models.CASCADE, related_name="authorization")
    material = models.ForeignKey("Material", on_delete=models.CASCADE, related_name="official_integrity_authorizations")
    authorized_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="official_integrity_authorizations")
    authorized_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    audit_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "official_reading_integrity_authorizations"


class OfficialReadingOverrideSecurityLockout(models.Model):
    reviewer = models.OneToOneField(User, on_delete=models.CASCADE, related_name="official_override_security_lockout")
    failed_attempt_count = models.PositiveSmallIntegerField(default=0)
    last_failed_at = models.DateTimeField(null=True, blank=True)
    lockout_expires_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    audit_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "official_reading_override_security_lockouts"


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


class LiveAssessmentSession(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('countdown', 'Countdown'),
        ('started', 'Started'),
        ('paused', 'Paused'),
        ('ended', 'Ended'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.CharField(max_length=64, primary_key=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='live_assessment_sessions')
    course = models.ForeignKey('Course', on_delete=models.SET_NULL, related_name='live_assessment_sessions', null=True, blank=True)
    section = models.ForeignKey('Section', on_delete=models.SET_NULL, related_name='live_assessment_sessions', null=True, blank=True)
    material = models.ForeignKey('Material', on_delete=models.CASCADE, related_name='live_assessment_sessions')
    student_ids = models.JSONField(default=list, blank=True)
    student_count = models.IntegerField(default=0)
    student_states = models.JSONField(default=dict, blank=True)
    batch_assignments = models.JSONField(default=dict, blank=True)
    current_batch = models.IntegerField(default=1)
    total_batches = models.IntegerField(default=0)
    batch_size = models.IntegerField(default=10)
    activity_log = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    start_at = models.DateTimeField(null=True, blank=True)
    countdown_seconds = models.IntegerField(default=10)
    timing_mode = models.CharField(max_length=20, choices=[('none', 'No Limit'), ('duration', 'Duration')], default='none')
    duration_seconds = models.IntegerField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'live_assessment_sessions'
        ordering = ['-created_at']

    def __str__(self):
        return f"Live assessment session {self.id} ({self.status})"
