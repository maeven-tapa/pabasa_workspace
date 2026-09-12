# Generated with Django 6.0.3. Keep replaces metadata for fully migrated legacy databases.
# Data operations are preserved here; this file does not import old migration modules.

import datetime
import django.core.validators
import django.db.migrations.operations.special
import django.db.models.deletion
import django.db.models.functions.text
import pabasa_app.models
import pabasa_app.system_clock
from django.conf import settings
from django.db import migrations, models


from collections import defaultdict
from datetime import datetime as historical_datetime
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations
from django.db import migrations, models
from django.db.models import Count, Q
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from pabasa_app.section_configuration import SALAWAG_GRADE_TWO_SECTIONS
import django.db.models.deletion
import json
import pabasa_app.models
import re
import uuid


# Preserved data migration: 0005_user_section_enrollment_model_update
def m0005__append_profile_tag(user, key, profile_data):
    tags = user.tags or []
    if not isinstance(tags, list):
        tags = [tags]
    for index, entry in enumerate(tags):
        if isinstance(entry, dict) and key in entry:
            tags[index] = {key: profile_data}
            break
    else:
        tags.append({key: profile_data})
    user.tags = tags
    user.save(update_fields=['tags'])


# Preserved data migration: 0005_user_section_enrollment_model_update
def m0005_copy_profiles_to_users(apps, schema_editor):
    User = apps.get_model('pabasa_app', 'User')
    TeacherProfile = apps.get_model('pabasa_app', 'TeacherProfile')
    StudentProfile = apps.get_model('pabasa_app', 'StudentProfile')
    for profile in TeacherProfile.objects.select_related('user').iterator():
        m0005__append_profile_tag(profile.user, 'teacher_profile', {'teacher_code': profile.teacher_code, 'teacher_role': profile.teacher_role, 'school': profile.school, 'department': profile.department, 'is_active': profile.is_active})
    for profile in StudentProfile.objects.select_related('user').iterator():
        m0005__append_profile_tag(profile.user, 'student_profile', {'student_code': profile.student_code, 'grade_level': profile.grade_level, 'section': profile.section, 'reading_level': profile.reading_level, 'wpm': profile.wpm, 'accuracy': str(profile.accuracy), 'parent_contact_no': profile.parent_contact_no, 'is_active': profile.is_active})
    User.objects.exists()


# Preserved data migration: 0005_user_section_enrollment_model_update
def m0005_repoint_profile_foreign_keys(apps, schema_editor):
    quoted = schema_editor.quote_name

    def update_fk(table, column, profile_table):
        schema_editor.execute(f"\n            UPDATE {quoted(table)}\n            SET {quoted(column)} = (\n                SELECT {quoted('user_id')}\n                FROM {quoted(profile_table)}\n                WHERE {quoted(profile_table)}.{quoted('id')} = {quoted(table)}.{quoted(column)}\n            )\n            WHERE {quoted(column)} IS NOT NULL\n            ")
    update_fk('class_enrollments', 'student_id', 'student_profiles')
    update_fk('assessments', 'teacher_id', 'teacher_profiles')
    update_fk('teacher_notes', 'teacher_id', 'teacher_profiles')
    update_fk('teacher_notes', 'student_id', 'student_profiles')


# Preserved data migration: 0006_section_students_json_remove_enrollment
def m0006_copy_enrollments_to_section_students(apps, schema_editor):
    Section = apps.get_model('pabasa_app', 'Section')
    Enrollment = apps.get_model('pabasa_app', 'Enrollment')
    section_students = {}
    enrollments = Enrollment.objects.select_related('student', 'section').iterator()
    for enrollment in enrollments:
        student = enrollment.student
        section_students.setdefault(enrollment.section_id, []).append({'student_id': student.id, 'custom_id': student.custom_id, 'first_name': student.first_name, 'last_name': student.last_name, 'email': student.email, 'joined_at': enrollment.joined_at.isoformat() if enrollment.joined_at else None, 'is_active': enrollment.is_active})
    for section_id, students in section_students.items():
        Section.objects.filter(id=section_id).update(students=students)


# Preserved data migration: 0007_user_teacher_fields
def m0007_migrate_teacher_data(apps, schema_editor):
    """
    Migrate teacher profile data from User.tags['teacher_profile'] 
    to dedicated teacher_role, school, department fields on User model.
    """
    User = apps.get_model('pabasa_app', 'User')
    for user in User.objects.filter(role='teacher').iterator():
        tags = getattr(user, 'tags', None) or []
        teacher_profile_data = {}
        if isinstance(tags, list):
            for entry in tags:
                if isinstance(entry, dict) and 'teacher_profile' in entry:
                    teacher_profile_data = entry.get('teacher_profile', {})
                    break
        if teacher_profile_data:
            user.teacher_role = teacher_profile_data.get('teacher_role', '')
            user.school = teacher_profile_data.get('school', '')
            user.department = teacher_profile_data.get('department', '')
            user.save(update_fields=['teacher_role', 'school', 'department'])


# Preserved data migration: 0007_user_teacher_fields
def m0007_reverse_migrate_teacher_data(apps, schema_editor):
    """
    Reverse migration: move teacher fields back to User.tags['teacher_profile']
    """
    User = apps.get_model('pabasa_app', 'User')
    for user in User.objects.filter(role='teacher').iterator():
        teacher_profile_data = {'teacher_role': user.teacher_role or '', 'school': user.school or '', 'department': user.department or '', 'is_active': True}
        tags = getattr(user, 'tags', None) or []
        if not isinstance(tags, list):
            tags = [tags]
        found = False
        for i, entry in enumerate(tags):
            if isinstance(entry, dict) and 'teacher_profile' in entry:
                tags[i] = {'teacher_profile': teacher_profile_data}
                found = True
                break
        if not found:
            tags.append({'teacher_profile': teacher_profile_data})
        user.tags = tags
        user.save(update_fields=['tags'])


# Preserved data migration: 0007_user_teacher_fields
def m0007_migrate_student_data(apps, schema_editor):
    """
    Migrate student profile data from User.tags['student_profile'] 
    to dedicated grade_level, section, reading_level, parent_contact_no fields on User model.
    """
    User = apps.get_model('pabasa_app', 'User')
    for user in User.objects.filter(role='student').iterator():
        tags = getattr(user, 'tags', None) or []
        student_profile_data = {}
        if isinstance(tags, list):
            for entry in tags:
                if isinstance(entry, dict) and 'student_profile' in entry:
                    student_profile_data = entry.get('student_profile', {})
                    break
        if student_profile_data:
            user.grade_level = student_profile_data.get('grade_level', '')
            user.section = student_profile_data.get('section', '')
            user.reading_level = student_profile_data.get('reading_level', '')
            user.parent_contact_no = student_profile_data.get('parent_contact_no', '')
            user.save(update_fields=['grade_level', 'section', 'reading_level', 'parent_contact_no'])


# Preserved data migration: 0007_user_teacher_fields
def m0007_reverse_migrate_student_data(apps, schema_editor):
    """
    Reverse migration: move student fields back to User.tags['student_profile']
    """
    User = apps.get_model('pabasa_app', 'User')
    for user in User.objects.filter(role='student').iterator():
        student_profile_data = {'grade_level': user.grade_level or '', 'section': user.section or '', 'reading_level': user.reading_level or '', 'parent_contact_no': user.parent_contact_no or '', 'is_active': True}
        tags = getattr(user, 'tags', None) or []
        if not isinstance(tags, list):
            tags = [tags]
        found = False
        for i, entry in enumerate(tags):
            if isinstance(entry, dict) and 'student_profile' in entry:
                tags[i] = {'student_profile': student_profile_data}
                found = True
                break
        if not found:
            tags.append({'student_profile': student_profile_data})
        user.tags = tags
        user.save(update_fields=['tags'])


# Preserved data migration: 0007_user_teacher_fields
def m0007_validate_section_enrollment(apps, schema_editor):
    """
    Validate Section.students enrollment data is properly formatted.
    Ensures all enrollment entries have required fields.
    """
    Section = apps.get_model('pabasa_app', 'Section')
    for section in Section.objects.all():
        students = getattr(section, 'students', None) or []
        if not isinstance(students, list):
            continue
        has_changes = False
        for entry in students:
            if not isinstance(entry, dict):
                continue
            required_fields = ['student_id', 'joined_at', 'is_active']
            for field in required_fields:
                if field not in entry:
                    has_changes = True
                    if field == 'joined_at':
                        entry[field] = None
                    elif field == 'is_active':
                        entry[field] = True
        if has_changes:
            section.save(update_fields=['students'])


# Preserved data migration: 0007_user_teacher_fields
def m0007_reverse_validate_section_enrollment(apps, schema_editor):
    """
    Reverse: no action needed for validation cleanup.
    """
    pass


# Preserved data migration: 0007_user_teacher_fields
def m0007_validate_assessment_attempts(apps, schema_editor):
    """
    Validate Assessment.attempts data is properly formatted.
    Ensures all attempt entries have required fields.
    """
    Assessment = apps.get_model('pabasa_app', 'Assessment')
    for assessment in Assessment.objects.all():
        attempts = getattr(assessment, 'attempts', None) or []
        if not isinstance(attempts, list):
            continue
        has_changes = False
        for entry in attempts:
            if not isinstance(entry, dict):
                continue
            required_fields = ['student_id', 'started_at', 'status']
            for field in required_fields:
                if field not in entry:
                    has_changes = True
                    if field == 'status':
                        entry[field] = 'started'
                    elif field == 'started_at':
                        entry[field] = None
        if has_changes:
            assessment.save(update_fields=['attempts'])


# Preserved data migration: 0007_user_teacher_fields
def m0007_reverse_validate_assessment_attempts(apps, schema_editor):
    """
    Reverse: no action needed for validation cleanup.
    """
    pass


# Preserved data migration: 0007_user_teacher_fields
def m0007_document_pending_teacher_signup_schema(apps, schema_editor):
    """
    Document the schema for pending teacher signup data stored in session.
    
    Session Keys:
    - pending_teacher_signup: {
        'first_name': str,
        'last_name': str,
        'email': str,
        'middle_initial': str (optional),
        'suffix': str (optional),
        'sex': str,
        'birth_month': int,
        'birth_day': int,
        'birth_year': int,
        'password_hash': str (hashed password),
        'contact_no': str (optional),
        'teacher_role': str (optional),
        'school': str (optional),
        'department': str (optional),
      }
    - pending_teacher_signup_otp: str (6-digit OTP code)
    - pending_teacher_signup_otp_created: float (timestamp when OTP was generated)
    
    Lifecycle:
    1. Created in register_teacher() via _store_pending_teacher_signup()
    2. Validated in verify_teacher_otp() for OTP correctness and expiration
    3. User created if OTP valid, data cleared via _clear_pending_teacher_signup()
    
    Note: Data is session-based (temporary) and cleared after verification or timeout.
    """
    pass


# Preserved data migration: 0007_user_teacher_fields
def m0007_document_pending_student_signup_schema(apps, schema_editor):
    """
    Document the schema for pending student signup data stored in session.
    
    Session Keys:
    - pending_student_signup: {
        'first_name': str,
        'last_name': str,
        'email': str,
        'middle_initial': str (optional),
        'suffix': str (optional),
        'sex': str,
        'birth_month': int,
        'birth_day': int,
        'birth_year': int,
        'password_hash': str (hashed password),
        'contact_no': str (optional),
        'grade_level': str (optional),
        'section': str (optional),
        'reading_level': str (optional),
        'parent_contact_no': str (optional),
      }
    - pending_student_signup_otp: str (6-digit OTP code)
    - pending_student_signup_otp_created: float (timestamp when OTP was generated)
    
    Lifecycle:
    1. Created in register_student() via _store_pending_student_signup()
    2. Validated in verify_student_otp() for OTP correctness and expiration
    3. User created if OTP valid, data cleared via _clear_pending_student_signup()
    
    Note: Data is session-based (temporary) and cleared after verification or timeout.
    """
    pass


# Preserved data migration: 0007_user_teacher_fields
def m0007_document_pending_password_reset_schema(apps, schema_editor):
    """
    Document the schema for pending password reset data stored in session.
    
    Session Keys:
    - pending_password_reset: {
        'email': str (user email to reset password for)
      }
    - pending_password_reset_otp: str (6-digit OTP code)
    - pending_password_reset_otp_created: float (timestamp when OTP was generated)
    - password_reset_verified: bool (set to True after OTP verification, before password change)
    - password_reset_email: str (email of user resetting password, set after OTP verification)
    
    Lifecycle:
    1. Created in request_password_reset() via _store_pending_password_reset()
    2. OTP validated in verify_forgot_password_otp() for correctness and expiration
    3. If valid, password_reset_verified set to True
    4. User enters new password in reset_password(), password updated
    5. Data cleared via _clear_pending_password_reset()
    
    Note: Data is session-based (temporary) and cleared after reset or timeout.
    """
    pass


# Preserved data migration: 0007_user_teacher_fields
def m0007_reverse_pending_signup_password_reset(apps, schema_editor):
    """
    Reverse: no action needed. These are session-based, not database-backed.
    """
    pass


# Preserved data migration: 0010_make_material_created_at_aware
def m0010_make_created_at_aware(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    tz = timezone.get_current_timezone()
    for m in Material.objects.exclude(created_at__isnull=True):
        ca = m.created_at
        try:
            if timezone.is_naive(ca):
                m.created_at = timezone.make_aware(ca, tz)
                m.save(update_fields=['created_at'])
        except Exception:
            continue


# Preserved data migration: 0011_change_material_constraint_and_ordering
def m0011_renumber_material_order(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    pairs = Material.objects.values('section_id', 'item_type').distinct()
    for pair in pairs:
        sec_id = pair['section_id']
        itype = pair['item_type']
        qs = Material.objects.filter(section_id=sec_id, item_type=itype).order_by('created_at', 'id')
        idx = 1
        for m in qs:
            if m.order_index != idx:
                m.order_index = idx
                m.save(update_fields=['order_index'])
            idx += 1


# Preserved data migration: 0012_convert_assessments_to_materials
def m0012_convert_assessments_to_materials(apps, schema_editor):
    import re
    from django.db import transaction
    from django.db.models import Max
    Assessment = apps.get_model('pabasa_app', 'Assessment')
    Material = apps.get_model('pabasa_app', 'Material')
    for asm in Assessment.objects.filter(section__isnull=False):
        if Material.objects.filter(assessment_id=asm.id).exists():
            continue
        content = (asm.content or '').strip()
        if not content:
            continue
        if asm.assessment_type == 'word':
            tokens = re.findall("\\b[\\w']+\\b", content, flags=re.UNICODE)
        elif asm.assessment_type == 'sentence':
            tokens = [s.strip() for s in re.split('(?<=[.!?])\\s+', content) if s.strip()]
        elif asm.assessment_type == 'paragraph':
            tokens = [p.strip() for p in re.split('\\n{2,}', content) if p.strip()]
        else:
            tokens = [content]
        if not tokens:
            continue
        max_idx = Material.objects.filter(section_id=asm.section_id, item_type=asm.assessment_type).aggregate(m=Max('order_index'))['m'] or 0
        next_index = int(max_idx) + 1
        with transaction.atomic():
            for token in tokens:
                Material.objects.create(assessment_id=asm.id, section_id=asm.section_id, item_type=asm.assessment_type, prompt_text=token, order_index=next_index, expected_answer=None, difficulty_level='', audio_url=None, is_active=asm.is_active)
                next_index += 1


# Preserved data migration: 0015_add_admin_role_and_account
m0015_ADMIN_CUSTOM_ID = 'ADM-0001'


# Preserved data migration: 0015_add_admin_role_and_account
m0015_ADMIN_PASSWORD = 'PBSADM1@2026'


# Preserved data migration: 0015_add_admin_role_and_account
def m0015_create_admin_account(apps, schema_editor):
    User = apps.get_model('pabasa_app', 'User')
    admin_defaults = {'role': 'admin', 'first_name': 'PABASA', 'last_name': 'Admin', 'middle_initial': '', 'suffix': '', 'sex': 'N/A', 'birth_month': 1, 'birth_day': 1, 'birth_year': 2026, 'email': 'admin@pabasa.local', 'contact_no': '', 'password_hash': make_password(m0015_ADMIN_PASSWORD)}
    admin_user, created = User.objects.get_or_create(custom_id=m0015_ADMIN_CUSTOM_ID, defaults=admin_defaults)
    if not created:
        for field, value in admin_defaults.items():
            setattr(admin_user, field, value)
        admin_user.save()


# Preserved data migration: 0015_add_admin_role_and_account
def m0015_remove_admin_account(apps, schema_editor):
    User = apps.get_model('pabasa_app', 'User')
    User.objects.filter(custom_id=m0015_ADMIN_CUSTOM_ID, role='admin').delete()


# Preserved data migration: 0023_create_default_test_accounts
def m0023_create_default_test_accounts(apps, schema_editor):
    pass


# Preserved data migration: 0023_create_default_test_accounts
def m0023_delete_default_test_accounts(apps, schema_editor):
    pass


# Preserved data migration: 0024_update_default_test_accounts
def m0024_update_default_test_accounts(apps, schema_editor):
    pass


# Preserved data migration: 0024_update_default_test_accounts
def m0024_revert_default_test_accounts(apps, schema_editor):
    pass


# Preserved data migration: 0025_material_assigned_week_integer
def m0025__parse_week_from_legacy(raw):
    if raw is None:
        return None
    value = str(raw).strip()
    if not value or value.lower() in {'unassigned', 'none', 'null'}:
        return None
    match = re.match('^(?:week\\s*)?(\\d{1,2})$', value, re.IGNORECASE)
    if not match:
        return None
    week = int(match.group(1))
    if 1 <= week <= 99:
        return week
    return None


# Preserved data migration: 0025_material_assigned_week_integer
def m0025_populate_assigned_week_integer(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    for material in Material.objects.all().iterator():
        week = m0025__parse_week_from_legacy(material.assigned_week)
        Material.objects.filter(pk=material.pk).update(assigned_week_integer=week)


# Preserved data migration: 0027_add_practice_material
def m0027__create_practice_materials(apps, schema_editor):
    Practice = apps.get_model('pabasa_app', 'Practice')
    Material = apps.get_model('pabasa_app', 'Material')
    for practice in Practice.objects.all():
        material = Material.objects.create(title=practice.title or '', item_type=practice.practice_type or 'word', prompt_text=practice.prompt_text or '', content_text=practice.contents or '', content_json={}, type='practice', status=practice.status or 'draft', difficulty_level=practice.difficulty_type or '', section=practice.section, is_active=practice.is_active)
        practice.material = material
        practice.save(update_fields=['material'])


# Preserved data migration: 0027_add_practice_material
def m0027__remove_practice_materials(apps, schema_editor):
    Practice = apps.get_model('pabasa_app', 'Practice')
    for practice in Practice.objects.filter(material__isnull=False):
        practice.material = None
        practice.save(update_fields=['material'])


# Preserved data migration: 0029_remove_practice_content_fields
def m0029_create_practice_materials(apps, schema_editor):
    Practice = apps.get_model('pabasa_app', 'Practice')
    Material = apps.get_model('pabasa_app', 'Material')
    for practice in Practice.objects.filter(material__isnull=True):
        material = Material.objects.create(title=practice.title or '', item_type=practice.practice_type or 'word', prompt_text=practice.prompt_text or '', content_text=practice.contents or '', content_json={}, type='practice', status=practice.status or 'draft', difficulty_level=practice.difficulty_type or '', section=practice.section, is_active=practice.is_active)
        practice.material = material
        practice.save(update_fields=['material'])


# Preserved data migration: 0032_assessment_attempts_table
def m0032__parse_datetime(value):
    if not value:
        return None
    if isinstance(value, historical_datetime):
        return value
    parsed = parse_datetime(str(value))
    if parsed is not None:
        return parsed
    return None


# Preserved data migration: 0032_assessment_attempts_table
def m0032_backfill_assessment_attempts(apps, schema_editor):
    Assessment = apps.get_model('pabasa_app', 'Assessment')
    connection = schema_editor.connection
    if 'assessment_attempts' not in connection.introspection.table_names():
        return
    with connection.cursor() as cursor:
        cursor.execute('\n            SELECT\n                assessment_id,\n                student_id,\n                started_at,\n                completed_at,\n                status,\n                device_info,\n                mic_used,\n                accuracy,\n                wpm,\n                fluency_score,\n                pronunciation_score,\n                time_score,\n                total_score,\n                crla_classification,\n                classification,\n                duration_seconds,\n                word_count,\n                transcript,\n                speech_recognition_used,\n                needs_manual_review,\n                passed,\n                remarks,\n                updated_at\n            FROM assessment_attempts\n            ORDER BY started_at, id\n            ')
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
    grouped_attempts = defaultdict(list)
    for row in rows:
        record = dict(zip(columns, row))
        assessment_id = record.get('assessment_id')
        student_id = record.get('student_id')
        if assessment_id is None or student_id is None:
            continue
        attempt = {'student_id': student_id, 'started_at': m0032__parse_datetime(record.get('started_at')) or timezone.now(), 'completed_at': m0032__parse_datetime(record.get('completed_at')), 'status': record.get('status') or 'started', 'device_info': record.get('device_info') or {}, 'mic_used': bool(record.get('mic_used', False)), 'accuracy': record.get('accuracy'), 'wpm': record.get('wpm'), 'fluency_score': record.get('fluency_score'), 'pronunciation_score': record.get('pronunciation_score'), 'time_score': record.get('time_score'), 'total_score': record.get('total_score'), 'crla_classification': record.get('crla_classification') or '', 'classification': record.get('classification') or '', 'duration_seconds': record.get('duration_seconds'), 'word_count': record.get('word_count'), 'transcript': record.get('transcript') or '', 'speech_recognition_used': bool(record.get('speech_recognition_used', False)), 'needs_manual_review': bool(record.get('needs_manual_review', False)), 'passed': bool(record.get('passed', False)), 'remarks': record.get('remarks') or ''}
        grouped_attempts[assessment_id].append(attempt)
    for assessment in Assessment.objects.all().iterator():
        attempts = grouped_attempts.get(assessment.id, [])
        if not attempts:
            continue
        assessment.attempts = attempts
        assessment.save(update_fields=['attempts'])


# Preserved data migration: 0032_assessment_attempts_table
def m0032_drop_legacy_assessment_attempt_table(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('DROP TABLE IF EXISTS assessment_attempts')


# Preserved data migration: 0035_material_code_teacher_assessment_material
def m0035__material_code(Material, preferred=None):
    base = (preferred or '').strip()
    if base and (not Material.objects.filter(code=base).exists()):
        return base
    candidate = 'MAT' + uuid.uuid4().hex[:8].upper()
    while Material.objects.filter(code=candidate).exists():
        candidate = 'MAT' + uuid.uuid4().hex[:8].upper()
    return candidate


# Preserved data migration: 0035_material_code_teacher_assessment_material
def m0035_populate_material_metadata(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    Assessment = apps.get_model('pabasa_app', 'Assessment')
    for material in Material.objects.select_related('assessment', 'section').all().iterator():
        preferred_code = ''
        teacher_id = None
        if material.assessment_id:
            try:
                preferred_code = material.assessment.code
                teacher_id = material.assessment.teacher_id
            except Assessment.DoesNotExist:
                pass
        if teacher_id is None and material.section_id:
            teacher_id = material.section.teacher_id
        updates = {}
        if not material.code:
            updates['code'] = m0035__material_code(Material, preferred_code)
        if material.teacher_id is None and teacher_id is not None:
            updates['teacher_id'] = teacher_id
        if updates:
            Material.objects.filter(pk=material.pk).update(**updates)
    for assessment in Assessment.objects.filter(material__isnull=True).iterator():
        parent_id = assessment.source_assessment_id or assessment.id
        material = Material.objects.filter(assessment_id=parent_id).order_by('id').first()
        if material:
            Assessment.objects.filter(pk=assessment.pk).update(material_id=material.id)


# Preserved data migration: 0037_sync_user_theme_shop_columns
def m0037_add_missing_user_theme_columns(apps, schema_editor):
    User = apps.get_model('pabasa_app', 'User')
    table_name = User._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        existing_columns = {column.name for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)}
    fields = [('available_stars', models.PositiveIntegerField(default=0)), ('theme_stars_credited', models.PositiveIntegerField(default=0)), ('unlocked_themes', models.JSONField(blank=True, default=pabasa_app.models.default_unlocked_themes)), ('equipped_theme', models.CharField(default='sky', max_length=30))]
    for name, field in fields:
        if name in existing_columns:
            continue
        field.set_attributes_from_name(name)
        schema_editor.add_field(User, field)


# Preserved data migration: 0038_normalize_material_language_to_filipino
def m0038_normalize_material_language_to_filipino(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    for material in Material.objects.all():
        content_json = material.content_json or {}
        if not isinstance(content_json, dict):
            continue
        updated = False
        normalized_content_json = dict(content_json)
        for key in ('language', 'language_context', 'languageContext'):
            value = normalized_content_json.get(key)
            if not isinstance(value, str):
                continue
            text = value.strip()
            lowered = text.lower()
            if lowered in {'tagalog', 'tl', 'tag', 'tagalog language'}:
                normalized_content_json[key] = 'Filipino'
                updated = True
            elif lowered in {'filipino', 'fil', 'filipina', 'filipino language'}:
                normalized_content_json[key] = 'Filipino'
                updated = True
        if updated:
            material.content_json = normalized_content_json
            material.save(update_fields=['content_json', 'updated_at'])


# Preserved data migration: 0046_material_language
def m0046_backfill_practice_language(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    Material.objects.filter(type='practice').update(language='English')


# Preserved data migration: 0050_material_assessment_kind
def m0050_set_existing_materials_regular(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    Material.objects.filter(assessment_kind__isnull=True).update(assessment_kind='regular')


# Preserved data migration: 0059_supporting_documentation_links_json
def m0059__convert_supporting_documentation(apps, schema_editor):
    OverrideRequest = apps.get_model('pabasa_app', 'OfficialReadingIntegrityOverrideRequest')
    with schema_editor.connection.cursor() as cursor:
        for request in OverrideRequest.objects.all().only('id', 'supporting_documentation'):
            value = request.supporting_documentation
            if isinstance(value, list):
                json_value = json.dumps(value)
            elif value in (None, ''):
                json_value = json.dumps([])
            else:
                json_value = json.dumps([str(value).strip()])
            safe_json = json_value.replace("'", "''")
            cursor.execute(f"UPDATE official_reading_integrity_override_requests SET supporting_documentation = '{safe_json}' WHERE id = {request.id}")


# Preserved data migration: 0061_seed_official_crla_assessments
m0061_OFFICIAL_CRLA_CONTENT = {'bosy_crla_pretest': {'code': 'CRLA-BOSY', 'title': 'Beginning of School Year (BoSY) CRLA Pre-Test', 'period': 'bosy', 'phase': 'pretest', 'words': ['Binti', 'Pito', 'Tubig', 'Pagod', 'Kanta', 'Regalo', 'Butiki', 'Halaman', 'Malapot', 'Gagamba'], 'sentences': ['Naglalaba si Tatay sa palanggana.', 'Magpapalit ako ng kamiseta mamaya.', 'Nilinis nila ang agiw rito.', 'Bumili kami ng bagong suklay.'], 'passages': [{'title': 'Isang Kakaibang Araw', 'content': "Iba't ibang tao ang sumasakay sa jeepney ni Tatay. May mga estudyanteng papasok ng eskuwela. May aleng mamamalengke. May nanay na may kasamang anak.\n\nPero may isang taong sumakay na bukod-tangi. Ang suot niya'y makulay at maluwang na damit. Napakalaki ng sapatos niyang pula! Pula rin ang ilong niya. Puting-puti ang mukha niya at asul ang kulot niyang buhok.\n\nHindi ko siya mapigilang tingnan. Tinititigan din siya ng katabi niya.\n\nNgumiti siya sabay-labas ng limang bola mula sa kaniyang bulsa. Isa-isa niyang itinapon ang mga bola pataas at sinalo. Paulit-ulit niya itong ginawa. Napapalakpak kaming lahat!"}]}, 'eosy_crla_posttest': {'code': 'CRLA-EOSY', 'title': 'End of School Year (EoSY) CRLA Post-Test', 'period': 'eosy', 'phase': 'posttest', 'words': ['Binti', 'Pito', 'Tubig', 'Pagod', 'Kanta', 'Regalo', 'Butiki', 'Halaman', 'Malapot', 'Gagamba'], 'sentences': ['Naglalaba si Tatay sa palanggana.', 'Magpapalit ako ng kamiseta mamaya.', 'Nilinis nila ang agiw rito.', 'Bumili kami ng bagong suklay.'], 'passages': [{'title': 'Ang Pagong at ang Kuneho', 'content': '"Ako ang pinakamabilis tumakbo," sabi ni Kuneho. "Wala nang bibilis pa sa akin!"\n\n"Naku, Kuneho, wala ka nang ibang sinabi kung hindi gaano ka kabilis tumakbo," sabi ni Pagong. "Hinahamon kita sa isang paligsahan."\n\n"Hindi mo ako matatalo!" sabi ni Kuneho. "Dahil mas mabilis akong tumakbo!"\n\n"Malalaman natin \'yan bukas ng umaga," sabi naman ni Pagong.\n\n"Kapana-panabik ito!" sabi ni Buwaya.\n\n"Kawawa naman si Pagong kasi ang bagal niyang gumalaw," sabi naman ni Elepante.\n\n"Kahit mabagal siya ay hindi naman siya tumitigil," sabi ni Unggoy.\n\nKinabukasan, dumating ang lahat ng hayop upang manood ng paligsahan.'}]}}


# Preserved data migration: 0061_seed_official_crla_assessments
def m0061_seed_official_crla_assessments(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    User = apps.get_model('pabasa_app', 'User')
    admin_user = User.objects.filter(role='admin', is_archived=False).order_by('id').first()
    for key, payload in m0061_OFFICIAL_CRLA_CONTENT.items():
        ordered_items = [{'type': 'word', 'text': word} for word in payload['words']] + [{'type': 'sentence', 'text': sentence} for sentence in payload['sentences']] + [{'type': 'paragraph', 'text': passage['content'], 'title': passage['title']} for passage in payload['passages']]
        content_json = {'assessment_key': key, 'language': 'Filipino', 'words': payload['words'], 'sentences': payload['sentences'], 'passages': payload['passages'], 'items': ordered_items}
        Material.objects.update_or_create(system_assessment_key=key, defaults={'is_system_owned': True, 'is_official_reading': True, 'system_assessment_period': payload['period'], 'system_assessment_phase': payload['phase'], 'teacher': admin_user, 'section': None, 'code': payload['code'], 'title': payload['title'], 'item_type': 'paragraph', 'prompt_text': payload['title'], 'content_text': '\n'.join([*payload['words'], *payload['sentences'], *[p['content'] for p in payload['passages']]]), 'content_json': content_json, 'assessment_set': 'crla', 'assessment_kind': 'crla', 'language': 'Filipino', 'type': 'assessment', 'source_type': 'shared', 'status': 'published', 'student_access': True, 'is_active': True})


# Preserved data migration: 0062_update_official_crla_story_sets
def m0062_update_official_crla_story_sets(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    bosy = Material.objects.filter(system_assessment_key='bosy_crla_pretest').first()
    if bosy:
        bosy.content_json = {'assessment_key': 'bosy_crla_pretest', 'language': 'Filipino', 'words': ['Binti', 'Pito', 'Tubig', 'Pagod', 'Kanta', 'Regalo', 'Butiki', 'Halaman', 'Malapot', 'Gagamba'], 'sentences': ['Naglalaba si Tatay sa palanggana.', 'Magpapalit ako ng kamiseta mamaya.', 'Nilinis nila ang agiw rito.', 'Bumili kami ng bagong suklay.'], 'passages': [{'title': 'Isang Kakaibang Araw', 'content': "Iba't ibang tao ang sumasakay sa jeepney ni Tatay. May mga estudyanteng papasok ng eskuwela. May aleng mamamalengke. May nanay na may kasamang anak.\n\nPero may isang taong sumakay na bukod-tangi. Ang suot niya'y makulay at maluwang na damit. Napakalaki ng sapatos niyang pula! Pula rin ang ilong niya. Puting-puti ang mukha niya at asul ang kulot niyang buhok.\n\nHindi ko siya mapigilang tingnan. Tinititigan din siya ng katabi niya.\n\nNgumiti siya sabay-labas ng limang bola mula sa kaniyang bulsa. Isa-isa niyang itinapon ang mga bola pataas at sinalo. Paulit-ulit niya itong ginawa. Napapalakpak kaming lahat!"}, {'title': 'Ang Pagong at ang Kuneho', 'content': '"Ako ang pinakamabilis tumakbo," sabi ni Kuneho. "Wala nang bibilis pa sa akin!"\n\n"Naku, Kuneho, wala ka nang ibang sinabi kung hindi gaano ka kabilis tumakbo," sabi ni Pagong. "Hinahamon kita sa isang paligsahan."\n\n"Hindi mo ako matatalo!" sabi ni Kuneho. "Dahil mas mabilis akong tumakbo!"\n\n"Malalaman natin \'yan bukas ng umaga," sabi naman ni Pagong.\n\n"Kapana-panabik ito!" sabi ni Buwaya.\n\n"Kawawa naman si Pagong kasi ang bagal niyang gumalaw," sabi naman ni Elepante.\n\n"Kahit mabagal siya ay hindi naman siya tumitigil," sabi ni Unggoy.\n\nKinabukasan, dumating ang lahat ng hayop upang manood ng paligsahan.'}], 'story_qas': [{'story_title': 'Isang Kakaibang Araw', 'question': 'Sino ang nagmamaneho ng jeepney?', 'answer': 'Si Tatay.'}, {'story_title': 'Isang Kakaibang Araw', 'question': 'Ano ang suot ng taong sumakay na bukod-tangi?', 'answer': 'Makulay at maluwang na damit.'}, {'story_title': 'Isang Kakaibang Araw', 'question': 'Anong kulay ang malaking sapatos niya?', 'answer': 'Pula.'}, {'story_title': 'Isang Kakaibang Araw', 'question': 'Ano ang kulay ng kaniyang ilong?', 'answer': 'Pula.'}, {'story_title': 'Isang Kakaibang Araw', 'question': 'Ilang bola ang inilabas niya mula sa kaniyang bulsa?', 'answer': 'Limang bola.'}, {'story_title': 'Isang Kakaibang Araw', 'question': 'Ano ang ginawa ng mga tao nang saluhin niya ang mga bola?', 'answer': 'Napalakpak silang lahat.'}, {'story_title': 'Ang Pagong at ang Kuneho', 'question': 'Sino ang nagsabing siya ang pinakamabilis tumakbo?', 'answer': 'Si Kuneho.'}, {'story_title': 'Ang Pagong at ang Kuneho', 'question': 'Sino ang humamon kay Kuneho sa isang paligsahan?', 'answer': 'Si Pagong.'}, {'story_title': 'Ang Pagong at ang Kuneho', 'question': 'Kailan sinabi ni Pagong na gaganapin ang paligsahan?', 'answer': 'Bukas ng umaga.'}, {'story_title': 'Ang Pagong at ang Kuneho', 'question': 'Sino ang nagsabing kapana-panabik ang paligsahan?', 'answer': 'Si Buwaya.'}, {'story_title': 'Ang Pagong at ang Kuneho', 'question': 'Sino ang nagsabing kawawa si Pagong dahil mabagal siyang gumalaw?', 'answer': 'Si Elepante.'}, {'story_title': 'Ang Pagong at ang Kuneho', 'question': 'Ano ang sinabi ni Unggoy tungkol kay Pagong?', 'answer': 'Kahit mabagal siya ay hindi naman siya tumitigil.'}], 'items': [{'type': 'word', 'text': word} for word in ['Binti', 'Pito', 'Tubig', 'Pagod', 'Kanta', 'Regalo', 'Butiki', 'Halaman', 'Malapot', 'Gagamba']] + [{'type': 'sentence', 'text': sentence} for sentence in ['Naglalaba si Tatay sa palanggana.', 'Magpapalit ako ng kamiseta mamaya.', 'Nilinis nila ang agiw rito.', 'Bumili kami ng bagong suklay.']] + [{'type': 'paragraph', 'text': passage['content'], 'title': passage['title']} for passage in [{'title': 'Isang Kakaibang Araw', 'content': "Iba't ibang tao ang sumasakay sa jeepney ni Tatay. May mga estudyanteng papasok ng eskuwela. May aleng mamamalengke. May nanay na may kasamang anak.\n\nPero may isang taong sumakay na bukod-tangi. Ang suot niya'y makulay at maluwang na damit. Napakalaki ng sapatos niyang pula! Pula rin ang ilong niya. Puting-puti ang mukha niya at asul ang kulot niyang buhok.\n\nHindi ko siya mapigilang tingnan. Tinititigan din siya ng katabi niya.\n\nNgumiti siya sabay-labas ng limang bola mula sa kaniyang bulsa. Isa-isa niyang itinapon ang mga bola pataas at sinalo. Paulit-ulit niya itong ginawa. Napapalakpak kaming lahat!"}, {'title': 'Ang Pagong at ang Kuneho', 'content': '"Ako ang pinakamabilis tumakbo," sabi ni Kuneho. "Wala nang bibilis pa sa akin!"\n\n"Naku, Kuneho, wala ka nang ibang sinabi kung hindi gaano ka kabilis tumakbo," sabi ni Pagong. "Hinahamon kita sa isang paligsahan."\n\n"Hindi mo ako matatalo!" sabi ni Kuneho. "Dahil mas mabilis akong tumakbo!"\n\n"Malalaman natin \'yan bukas ng umaga," sabi naman ni Pagong.\n\n"Kapana-panabik ito!" sabi ni Buwaya.\n\n"Kawawa naman si Pagong kasi ang bagal niyang gumalaw," sabi naman ni Elepante.\n\n"Kahit mabagal siya ay hindi naman siya tumitigil," sabi ni Unggoy.\n\nKinabukasan, dumating ang lahat ng hayop upang manood ng paligsahan.'}]], 'is_system_owned': True, 'is_official_reading': True, 'system_assessment_period': 'bosy', 'system_assessment_phase': 'pretest', 'assessment_set': 'crla', 'assessment_kind': 'crla', 'language': 'Filipino', 'type': 'assessment', 'source_type': 'shared', 'status': 'published', 'student_access': True, 'is_active': True}
        bosy.save()
    eosy = Material.objects.filter(system_assessment_key='eosy_crla_posttest').first()
    if eosy:
        eosy.content_json = {'assessment_key': 'eosy_crla_posttest', 'language': 'Filipino', 'words': ['Binti', 'Pito', 'Tubig', 'Pagod', 'Kanta', 'Regalo', 'Butiki', 'Halaman', 'Malapot', 'Gagamba'], 'sentences': ['Naglalaba si Tatay sa palanggana.', 'Magpapalit ako ng kamiseta mamaya.', 'Nilinis nila ang agiw rito.', 'Bumili kami ng bagong suklay.'], 'passages': [{'title': 'Ang Pagong at ang Kuneho', 'content': '"Ako ang pinakamabilis tumakbo," sabi ni Kuneho. "Wala nang bibilis pa sa akin!"\n\n"Naku, Kuneho, wala ka nang ibang sinabi kung hindi gaano ka kabilis tumakbo," sabi ni Pagong. "Hinahamon kita sa isang paligsahan."\n\n"Hindi mo ako matatalo!" sabi ni Kuneho. "Dahil mas mabilis akong tumakbo!"\n\n"Malalaman natin \'yan bukas ng umaga," sabi naman ni Pagong.\n\n"Kapana-panabik ito!" sabi ni Buwaya.\n\n"Kawawa naman si Pagong kasi ang bagal niyang gumalaw," sabi naman ni Elepante.\n\n"Kahit mabagal siya ay hindi naman siya tumitigil," sabi ni Unggoy.\n\nKinabukasan, dumating ang lahat ng hayop upang manood ng paligsahan.'}, {'title': 'Isang Kakaibang Araw', 'content': "Iba't ibang tao ang sumasakay sa jeepney ni Tatay. May mga estudyanteng papasok ng eskuwela. May aleng mamamalengke. May nanay na may kasamang anak.\n\nPero may isang taong sumakay na bukod-tangi. Ang suot niya'y makulay at maluwang na damit. Napakalaki ng sapatos niyang pula! Pula rin ang ilong niya. Puting-puti ang mukha niya at asul ang kulot niyang buhok.\n\nHindi ko siya mapigilang tingnan. Tinititigan din siya ng katabi niya.\n\nNgumiti siya sabay-labas ng limang bola mula sa kaniyang bulsa. Isa-isa niyang itinapon ang mga bola pataas at sinalo. Paulit-ulit niya itong ginawa. Napapalakpak kaming lahat!"}], 'story_qas': [{'story_title': 'Ang Pagong at ang Kuneho', 'question': 'Sino ang nagsabing siya ang pinakamabilis tumakbo?', 'answer': 'Si Kuneho.'}, {'story_title': 'Ang Pagong at ang Kuneho', 'question': 'Sino ang humamon kay Kuneho sa isang paligsahan?', 'answer': 'Si Pagong.'}, {'story_title': 'Ang Pagong at ang Kuneho', 'question': 'Kailan sinabi ni Pagong na gaganapin ang paligsahan?', 'answer': 'Bukas ng umaga.'}, {'story_title': 'Ang Pagong at ang Kuneho', 'question': 'Sino ang nagsabing kapana-panabik ang paligsahan?', 'answer': 'Si Buwaya.'}, {'story_title': 'Ang Pagong at ang Kuneho', 'question': 'Sino ang nagsabing kawawa si Pagong dahil mabagal siyang gumalaw?', 'answer': 'Si Elepante.'}, {'story_title': 'Ang Pagong at ang Kuneho', 'question': 'Ano ang sinabi ni Unggoy tungkol kay Pagong?', 'answer': 'Kahit mabagal siya ay hindi naman siya tumitigil.'}, {'story_title': 'Isang Kakaibang Araw', 'question': 'Sino ang nagmamaneho ng jeepney?', 'answer': 'Si Tatay.'}, {'story_title': 'Isang Kakaibang Araw', 'question': 'Ano ang suot ng taong sumakay na bukod-tangi?', 'answer': 'Makulay at maluwang na damit.'}, {'story_title': 'Isang Kakaibang Araw', 'question': 'Anong kulay ang malaking sapatos niya?', 'answer': 'Pula.'}, {'story_title': 'Isang Kakaibang Araw', 'question': 'Ano ang kulay ng kaniyang ilong?', 'answer': 'Pula.'}, {'story_title': 'Isang Kakaibang Araw', 'question': 'Ilang bola ang inilabas niya mula sa kaniyang bulsa?', 'answer': 'Limang bola.'}, {'story_title': 'Isang Kakaibang Araw', 'question': 'Ano ang ginawa ng mga tao nang saluhin niya ang mga bola?', 'answer': 'Napalakpak silang lahat.'}], 'items': [{'type': 'word', 'text': word} for word in ['Binti', 'Pito', 'Tubig', 'Pagod', 'Kanta', 'Regalo', 'Butiki', 'Halaman', 'Malapot', 'Gagamba']] + [{'type': 'sentence', 'text': sentence} for sentence in ['Naglalaba si Tatay sa palanggana.', 'Magpapalit ako ng kamiseta mamaya.', 'Nilinis nila ang agiw rito.', 'Bumili kami ng bagong suklay.']] + [{'type': 'paragraph', 'text': passage['content'], 'title': passage['title']} for passage in [{'title': 'Ang Pagong at ang Kuneho', 'content': '"Ako ang pinakamabilis tumakbo," sabi ni Kuneho. "Wala nang bibilis pa sa akin!"\n\n"Naku, Kuneho, wala ka nang ibang sinabi kung hindi gaano ka kabilis tumakbo," sabi ni Pagong. "Hinahamon kita sa isang paligsahan."\n\n"Hindi mo ako matatalo!" sabi ni Kuneho. "Dahil mas mabilis akong tumakbo!"\n\n"Malalaman natin \'yan bukas ng umaga," sabi naman ni Pagong.\n\n"Kapana-panabik ito!" sabi ni Buwaya.\n\n"Kawawa naman si Pagong kasi ang bagal niyang gumalaw," sabi naman ni Elepante.\n\n"Kahit mabagal siya ay hindi naman siya tumitigil," sabi ni Unggoy.\n\nKinabukasan, dumating ang lahat ng hayop upang manood ng paligsahan.'}, {'title': 'Isang Kakaibang Araw', 'content': "Iba't ibang tao ang sumasakay sa jeepney ni Tatay. May mga estudyanteng papasok ng eskuwela. May aleng mamamalengke. May nanay na may kasamang anak.\n\nPero may isang taong sumakay na bukod-tangi. Ang suot niya'y makulay at maluwang na damit. Napakalaki ng sapatos niyang pula! Pula rin ang ilong niya. Puting-puti ang mukha niya at asul ang kulot niyang buhok.\n\nHindi ko siya mapigilang tingnan. Tinititigan din siya ng katabi niya.\n\nNgumiti siya sabay-labas ng limang bola mula sa kaniyang bulsa. Isa-isa niyang itinapon ang mga bola pataas at sinalo. Paulit-ulit niya itong ginawa. Napapalakpak kaming lahat!"}]], 'is_system_owned': True, 'is_official_reading': True, 'system_assessment_period': 'eosy', 'system_assessment_phase': 'posttest', 'assessment_set': 'crla', 'assessment_kind': 'crla', 'language': 'Filipino', 'type': 'assessment', 'source_type': 'shared', 'status': 'published', 'student_access': True, 'is_active': True}
        eosy.save()


# Preserved data migration: 0065_remove_preadded_accounts
m0065_PRESEEDED_CUSTOM_IDS = ('TCH-9999', 'G2-9999', 'TCH-TEST', 'STD-TEST')


# Preserved data migration: 0065_remove_preadded_accounts
def m0065_remove_preseeded_accounts(apps, schema_editor):
    pass


# Preserved data migration: 0066_backfill_official_crla_story_qas
def m0066_backfill_official_crla_story_qas(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    try:
        from pabasa_app.management.commands.seed_official_crla_assessments import OFFICIAL_CRLA_CONTENT
    except Exception:
        OFFICIAL_CRLA_CONTENT = {}
    if not OFFICIAL_CRLA_CONTENT:
        return
    seed_by_key = {}
    for key, payload in OFFICIAL_CRLA_CONTENT.items():
        story_qas = []
        for item in payload.get('story_qas') or []:
            if not isinstance(item, dict):
                continue
            story_title = str(item.get('story_title') or '').strip()
            question = str(item.get('question') or '').strip()
            answer = str(item.get('answer') or '').strip()
            if story_title and question and answer:
                story_qas.append({'story_title': story_title, 'question': question, 'answer': answer})
        seed_by_key[key] = story_qas
    for material in Material.objects.filter(is_official_reading=True):
        content_json = material.content_json or {}
        if not isinstance(content_json, dict):
            continue
        if content_json.get('story_qas'):
            continue
        assessment_key = str(content_json.get('assessment_key') or getattr(material, 'system_assessment_key', '') or '').strip().lower()
        story_qas = seed_by_key.get(assessment_key)
        if not story_qas:
            continue
        updated_content_json = dict(content_json)
        updated_content_json['story_qas'] = story_qas
        material.content_json = updated_content_json
        material.save(update_fields=['content_json', 'updated_at'])


# Preserved data migration: 0066_backfill_official_crla_story_qas
def m0066_noop_reverse(apps, schema_editor):
    return


# Preserved data migration: 0067_backfill_official_crla_terms
m0067_OFFICIAL_CRLA_TERMS = {'bosy_crla_pretest': 1, 'midline_crla_midtest': 2, 'eosy_crla_posttest': 3}


# Preserved data migration: 0067_backfill_official_crla_terms
def m0067_backfill_official_crla_terms(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    for assessment_key, term in m0067_OFFICIAL_CRLA_TERMS.items():
        Material.objects.filter(system_assessment_key=assessment_key, is_official_reading=True).update(official_term=term)


# Preserved data migration: 0067_backfill_official_crla_terms
def m0067_clear_official_crla_terms(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    Material.objects.filter(system_assessment_key__in=m0067_OFFICIAL_CRLA_TERMS, is_official_reading=True).update(official_term=None)


# Preserved data migration: 0068_assessment_official_term
def m0068_backfill_attempt_terms(apps, schema_editor):
    Assessment = apps.get_model('pabasa_app', 'Assessment')
    CalendarEvent = apps.get_model('pabasa_app', 'CalendarEvent')
    Material = apps.get_model('pabasa_app', 'Material')
    Material.objects.filter(is_system_owned=True, is_official_reading=True).update(official_term=None)
    attempts = Assessment.objects.filter(student__isnull=False, attempt_status='completed', completed_at__isnull=False).filter(models.Q(is_system_owned=True) | models.Q(material__is_official_reading=True) | models.Q(source_assessment__is_system_owned=True))
    for attempt in attempts.iterator():
        completed_date = attempt.completed_at.date()
        phase = str(attempt.system_assessment_phase or '').strip().lower()
        event_types = {'pretest': ('pre_assessment',), 'midtest': ('midline_assessment',), 'posttest': ('post_assessment',)}.get(phase, ('pre_assessment', 'midline_assessment', 'post_assessment'))
        event = CalendarEvent.objects.filter(start_date__lte=completed_date, end_date__gte=completed_date, event_type__in=event_types, school_calendar__is_active=True).order_by('-school_calendar__updated_at', 'term', 'id').first()
        if event:
            Assessment.objects.filter(pk=attempt.pk).update(official_term=event.term)


# Preserved data migration: 0070_canonical_sections_and_enrollments
def m0070_prepare_canonical_sections_and_enrollments(apps, schema_editor):
    Section = apps.get_model('pabasa_app', 'Section')
    Enrollment = apps.get_model('pabasa_app', 'Enrollment')
    User = apps.get_model('pabasa_app', 'User')
    claimed_identities = set()
    for section in Section.objects.order_by('id').iterator():
        grade_level = (section.grade_level or '').strip()
        section_name = (section.section or '').strip()
        identity = (grade_level.casefold(), section_name.casefold())
        if grade_level and section_name and (identity in claimed_identities):
            grade_level = ''
            section_name = ''
        elif grade_level and section_name:
            claimed_identities.add(identity)
        Section.objects.filter(pk=section.pk).update(grade_level=grade_level, section=section_name)
        entries = section.students if isinstance(section.students, list) else []
        seen_student_ids = set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            raw_student_id = entry.get('student_id')
            student = None
            if raw_student_id is not None:
                try:
                    student = User.objects.filter(pk=int(raw_student_id), role='student').first()
                except (TypeError, ValueError):
                    student = None
            if student is None and entry.get('custom_id'):
                student = User.objects.filter(custom_id=entry['custom_id'], role='student').first()
            if student is None or student.pk in seen_student_ids:
                continue
            seen_student_ids.add(student.pk)
            enrollment, _ = Enrollment.objects.get_or_create(student_id=student.pk, section_id=section.pk, defaults={'is_active': bool(entry.get('is_active', True))})
            desired_active = bool(entry.get('is_active', True))
            if enrollment.is_active != desired_active:
                Enrollment.objects.filter(pk=enrollment.pk).update(is_active=desired_active)


# Preserved data migration: 0071_school_and_school_scoped_sections
def m0071_forwards(apps, schema_editor):
    School = apps.get_model('pabasa_app', 'School')
    Section = apps.get_model('pabasa_app', 'Section')
    school = School.objects.filter(name='Default School').first()
    if not school:
        school = School.objects.create(name='Default School', code='DEFAULT-SCHOOL', status='active', is_active=True)
    Section.objects.filter(school__isnull=True).update(school=school)


# Preserved data migration: 0071_school_and_school_scoped_sections
def m0071_backwards(apps, schema_editor):
    Section = apps.get_model('pabasa_app', 'Section')
    School = apps.get_model('pabasa_app', 'School')
    default_school = School.objects.filter(name='Default School').first()
    if default_school:
        Section.objects.filter(school=default_school).update(school=None)
        default_school.delete()


# Preserved data migration: 0073_user_school_record
def m0073_backfill_user_schools(apps, schema_editor):
    User = apps.get_model('pabasa_app', 'User')
    Section = apps.get_model('pabasa_app', 'Section')
    Enrollment = apps.get_model('pabasa_app', 'Enrollment')
    School = apps.get_model('pabasa_app', 'School')
    for user in User.objects.filter(school_record__isnull=True):
        school_ids = set(Section.objects.filter(teacher_id=user.id, school__isnull=False).values_list('school_id', flat=True))
        school_ids.update(Enrollment.objects.filter(student_id=user.id, section__school__isnull=False).values_list('section__school_id', flat=True))
        if len(school_ids) == 1:
            user.school_record_id = next(iter(school_ids))
            user.save(update_fields=['school_record'])
            continue
        legacy_name = (user.school or '').strip()
        if legacy_name:
            matches = list(School.objects.filter(name__iexact=legacy_name).values_list('id', flat=True)[:2])
            if len(matches) == 1:
                user.school_record_id = matches[0]
                user.save(update_fields=['school_record'])


# Preserved data migration: 0074_migrate_salawag_default_school
m0074_SALAWAG_NAME = 'Salawag Elementary School'


# Preserved data migration: 0074_migrate_salawag_default_school
m0074_LEGACY_DEFAULT_NAME = 'Default School'


# Preserved data migration: 0074_migrate_salawag_default_school
def m0074_forwards(apps, schema_editor):
    School = apps.get_model('pabasa_app', 'School')
    Section = apps.get_model('pabasa_app', 'Section')
    User = apps.get_model('pabasa_app', 'User')
    Enrollment = apps.get_model('pabasa_app', 'Enrollment')
    Material = apps.get_model('pabasa_app', 'Material')
    Assessment = apps.get_model('pabasa_app', 'Assessment')
    salawag = School.objects.filter(name=m0074_SALAWAG_NAME).first()
    if not salawag:
        salawag = School.objects.create(name=m0074_SALAWAG_NAME, code='SALAWAG-ES', status='active', is_active=True)
    default_school = School.objects.filter(name=m0074_LEGACY_DEFAULT_NAME).first()
    if not default_school:
        return
    clearly_salawag_sections = set(Section.objects.filter(school=default_school, teacher_id__isnull=False).values_list('id', flat=True))
    clearly_salawag_sections.update(Enrollment.objects.filter(section__school=default_school, is_active=True).values_list('section_id', flat=True))
    clearly_salawag_sections.update(Material.objects.filter(section__school=default_school, section__isnull=False).values_list('section_id', flat=True))
    clearly_salawag_sections.update(Assessment.objects.filter(section__school=default_school, section__isnull=False).values_list('section_id', flat=True))
    clearly_salawag_sections.discard(None)
    migrated_sections = Section.objects.filter(id__in=clearly_salawag_sections, school=default_school)
    migrated_section_ids = list(migrated_sections.values_list('id', flat=True))
    migrated_sections.update(school=salawag)
    migrated_teacher_ids = set(Section.objects.filter(id__in=migrated_section_ids, teacher_id__isnull=False).values_list('teacher_id', flat=True))
    migrated_student_ids = set(Enrollment.objects.filter(section_id__in=migrated_section_ids).values_list('student_id', flat=True))
    migrated_user_ids = migrated_teacher_ids | migrated_student_ids
    migrated_user_ids.update(User.objects.filter(school__iexact=m0074_SALAWAG_NAME).values_list('id', flat=True))
    for user in User.objects.filter(id__in=migrated_user_ids):
        updates = []
        if user.school_record_id != salawag.id:
            user.school_record_id = salawag.id
            updates.append('school_record')
        if user.school != m0074_SALAWAG_NAME:
            user.school = m0074_SALAWAG_NAME
            updates.append('school')
        if updates:
            user.save(update_fields=updates)


# Preserved data migration: 0074_migrate_salawag_default_school
def m0074_backwards(apps, schema_editor):
    School = apps.get_model('pabasa_app', 'School')
    Section = apps.get_model('pabasa_app', 'Section')
    User = apps.get_model('pabasa_app', 'User')
    salawag = School.objects.filter(name=m0074_SALAWAG_NAME).first()
    default_school = School.objects.filter(name=m0074_LEGACY_DEFAULT_NAME).first()
    if not salawag or not default_school:
        return
    Section.objects.filter(school=salawag).update(school=default_school)
    User.objects.filter(school_record=salawag).update(school_record=default_school)


# Preserved data migration: 0075_require_section_school
def m0075_reject_unowned_sections(apps, schema_editor):
    Section = apps.get_model('pabasa_app', 'Section')
    if Section.objects.filter(school_id__isnull=True).exists():
        raise ValidationError('Cannot require Section.school while unowned Sections still exist. Assign each Section to a School explicitly first.')


# Preserved data migration: 0077_backfill_principal_school_record
def m0077_forwards(apps, schema_editor):
    User = apps.get_model('pabasa_app', 'User')
    School = apps.get_model('pabasa_app', 'School')
    schools = {school.name.casefold(): school for school in School.objects.exclude(name='Default School')}
    for user in User.objects.filter(role='principal', school_record__isnull=True):
        legacy_name = str(user.school or '').strip().casefold()
        school = schools.get(legacy_name)
        if school is None:
            continue
        if User.objects.filter(role='principal', school_record=school, is_archived=False).exists():
            continue
        user.school_record_id = school.id
        user.school = school.name
        user.save(update_fields=['school_record', 'school'])


# Preserved data migration: 0082_normalize_calendar_event_titles_and_dates
def m0082_normalize_calendar_events(apps, schema_editor):
    CalendarEvent = apps.get_model('pabasa_app', 'CalendarEvent')
    legacy_global = CalendarEvent.objects.filter(scope='global', school__isnull=True)
    legacy_global.filter(event_type='school_opening', title='School Opening').update(title='Opening Block')
    legacy_global.filter(event_type='school_closing', title='School Closing').update(title='End-of-Term Block')
    legacy_global.filter(event_type='school_closing', title='End-of-Term Block', end_date__lt=models.F('start_date')).update(end_date=models.F('start_date'))


# Preserved data migration: 0083_course_school
def m0083_backfill_course_school(apps, schema_editor):
    Course = apps.get_model('pabasa_app', 'Course')
    for course in Course.objects.select_related('teacher').prefetch_related('sections'):
        school_ids = {section.school_id for section in course.sections.all() if section.school_id}
        if len(school_ids) == 1:
            course.school_id = school_ids.pop()
            course.save(update_fields=['school'])
        elif not school_ids and course.teacher.school_record_id:
            course.school_id = course.teacher.school_record_id
            course.save(update_fields=['school'])


# Preserved data migration: 0084_classify_legacy_practice
def m0084_classify_known_admin_practice(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    Material.objects.filter(id=5, title='Free Easy Level 1', type='practice', section__isnull=True, teacher__isnull=True, source_type='personal', is_system_owned=False, difficulty_level='easy', language='English', content_json__mode='free', content_json__difficulty='easy', content_json__level='level_1').update(is_system_owned=True, source_type='shared')


# Preserved data migration: 0090_school_year_enrollment_and_account_status
def m0090_backfill_school_year_enrollments(apps, schema_editor):
    User = apps.get_model('pabasa_app', 'User')
    Enrollment = apps.get_model('pabasa_app', 'Enrollment')
    User.objects.filter(is_archived=True).update(account_status='archived')
    User.objects.filter(is_archived=False).update(account_status='active')
    for enrollment in Enrollment.objects.select_related('section').all().iterator():
        section = enrollment.section
        Enrollment.objects.filter(pk=enrollment.pk).update(school_id=section.school_id, school_calendar_id=section.school_calendar_id, grade_level=section.grade_level or 'Grade 2', assigned_teacher_id=section.teacher_id, status='active' if enrollment.is_active else 'completed', outcome='not_finalized')


# Preserved data migration: 0091_enrollment_integrity
def m0091_refuse_ambiguous_current_enrollments(apps, schema_editor):
    Enrollment = apps.get_model('pabasa_app', 'Enrollment')
    duplicates = Enrollment.objects.filter(school_calendar__isnull=False, status__in=['active', 'awaiting_assignment']).values('student_id', 'school_calendar_id').annotate(total=Count('id')).filter(total__gt=1)
    if duplicates.exists():
        details = list(duplicates.values_list('student_id', 'school_calendar_id', 'total'))
        raise RuntimeError('Ambiguous current enrollments exist; run audit_enrollment_integrity and resolve them before migrating: ' + repr(details))


# Preserved data migration: 0092_school_year_learning_records
def m0092_backfill_enrollments(apps, schema_editor):
    Enrollment = apps.get_model('pabasa_app', 'Enrollment')
    Assessment = apps.get_model('pabasa_app', 'Assessment')
    StoryProgress = apps.get_model('pabasa_app', 'StoryReadingProgress')
    Practice = apps.get_model('pabasa_app', 'Practice')
    for row in Assessment.objects.filter(student__isnull=False, section__isnull=False, enrollment__isnull=True).select_related('section'):
        matches = Enrollment.objects.filter(student_id=row.student_id, section_id=row.section_id, school_calendar_id=row.section.school_calendar_id)
        if matches.count() == 1:
            row.enrollment_id = matches.first().id
            row.save(update_fields=['enrollment'])
    for practice in Practice.objects.filter(section__isnull=False).select_related('section'):
        attempts = practice.attempts if isinstance(practice.attempts, list) else []
        changed = False
        for attempt in attempts:
            if attempt.get('enrollment_id') or not attempt.get('student_id'):
                continue
            matches = Enrollment.objects.filter(student_id=attempt['student_id'], section_id=practice.section_id, school_calendar_id=practice.section.school_calendar_id)
            if matches.count() == 1:
                attempt['enrollment_id'] = matches.first().id
                changed = True
        if changed:
            practice.save(update_fields=['attempts', 'updated_at'])
    for row in StoryProgress.objects.filter(enrollment__isnull=True).select_related('material'):
        section_id = getattr(row.material, 'section_id', None)
        if not section_id:
            continue
        section = row.material.section
        matches = Enrollment.objects.filter(student_id=row.student_id, section_id=section_id, school_calendar_id=section.school_calendar_id)
        if matches.count() == 1:
            row.enrollment_id = matches.first().id
            row.save(update_fields=['enrollment'])


# Preserved data migration: 0093_seed_salawag_grade_two_sections
def m0093_seed_salawag_grade_two_sections(apps, schema_editor):
    School = apps.get_model('pabasa_app', 'School')
    SchoolCalendar = apps.get_model('pabasa_app', 'SchoolCalendar')
    Section = apps.get_model('pabasa_app', 'Section')
    school, _ = School.objects.get_or_create(name='Salawag Elementary School', defaults={'code': '107912', 'address': '4114 Paliparan Road Dasmariñas Calabarzon', 'status': 'active', 'is_active': True})
    active_calendar = SchoolCalendar.objects.filter(is_active=True).order_by('-updated_at', '-created_at').first()
    if not active_calendar:
        return
    existing_names = {str(name).upper() for name in Section.objects.filter(school=school, school_calendar=active_calendar, grade_level__iexact='Grade 2').values_list('section', flat=True)}
    for position, name in enumerate(SALAWAG_GRADE_TWO_SECTIONS, start=1):
        if name in existing_names:
            continue
        Section.objects.create(school=school, school_calendar=active_calendar, class_code=f'SAL-G2-{position:02d}', class_name=f'Grade 2 - {name}', subject='Reading', grade_level='Grade 2', section=name, is_active=True)


# Preserved data migration: 0098_mark_five_w_story_questions
def m0098_mark_five_w_materials(apps, schema_editor):
    Material = apps.get_model('pabasa_app', 'Material')
    for material in Material.objects.filter(item_type='paragraph'):
        content = material.content_json if isinstance(material.content_json, dict) else {}
        template_values = {str(content.get(key) or '').strip().lower() for key in ('template_title', 'template_type', 'template_activity_name')}
        if "5w's story questions" not in template_values:
            continue
        if content.get('activity_variant') == 'five_w_story_questions':
            continue
        content['activity_variant'] = 'five_w_story_questions'
        material.content_json = content
        material.save(update_fields=['content_json'])


# Preserved data migration: 0100_backfill_assessment_week_enabled_default
def m0100_backfill_assessment_week_enabled(apps, schema_editor):
    """Ensure all Section records have assessment_week_enabled set to False (not NULL or True).
    
    The Assessment Week feature should start OFF by default for all existing and new sections.
    This backfill handles three cases:
    1. NULL values (from the initial migration) → False
    2. True values (manually set or from old logic) → False  
    3. False values (correct) → no change
    """
    Section = apps.get_model('pabasa_app', 'Section')
    Section.objects.exclude(assessment_week_enabled=False).update(assessment_week_enabled=False)


# Preserved data migration: 0100_backfill_assessment_week_enabled_default
def m0100_reverse_backfill(apps, schema_editor):
    """No need to reverse this as we're just ensuring a sensible default."""
    pass


# Preserved data migration: 0108_backfill_crla_reading_profile
m0108_OFFICIAL_CRLA_KEYS = ('bosy_crla_pretest', 'midline_crla_midtest', 'eosy_crla_posttest')


# Preserved data migration: 0108_backfill_crla_reading_profile
def m0108__profile_input(score_data):
    data = score_data if isinstance(score_data, dict) else {}
    part1_total = data.get('part1_total_score')
    if part1_total in (None, ''):
        task1 = data.get('task1_score', data.get('task1_correct_words'))
        task2 = data.get('task2_score')
        try:
            task1 = int(task1)
            task2 = int(task2)
        except (TypeError, ValueError):
            task1 = task2 = None
        if task1 is not None and task2 is not None:
            if 'h' in str(data.get('task2_type') or '').lower():
                task2 = (0, 3, 5, 7, 10)[max(0, min(4, int(data.get('sentences_read', task2) or 0)))]
            part1_total = task1 + task2
    return (part1_total, data.get('story_number'), data.get('passage_accuracy_percent', data.get('story_read_percent')), data.get('comprehension_correct', data.get('correct_answers')))


# Preserved data migration: 0108_backfill_crla_reading_profile
def m0108_backfill_final_crla_profiles(apps, schema_editor):
    from pabasa_app.scoring import crla_reading_profile
    Assessment = apps.get_model('pabasa_app', 'Assessment')
    candidates = Assessment.objects.filter(student__isnull=False, attempt_status='completed', completed_at__isnull=False).filter(Q(source_assessment__system_assessment_key__in=m0108_OFFICIAL_CRLA_KEYS) | Q(material__assessment_kind='crla', material__is_official_reading=True))
    for attempt in candidates.iterator():
        profile = crla_reading_profile(*m0108__profile_input(attempt.crla_score_data))
        if profile and attempt.crla_classification != profile:
            Assessment.objects.filter(pk=attempt.pk).update(crla_classification=profile)


# Preserved data migration: 0113_prevent_unsaved_practice_level_reservations
def m0113_remove_incomplete_admin_practice_materials(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    replaces = [('pabasa_app', '0001_initial'), ('pabasa_app', '0002_readingclass_grade_level_readingclass_section'), ('pabasa_app', '0003_readingclass_subject'), ('pabasa_app', '0004_user_middle_initial_user_suffix'), ('pabasa_app', '0005_user_section_enrollment_model_update'), ('pabasa_app', '0006_section_students_json_remove_enrollment'), ('pabasa_app', '0007_user_teacher_fields'), ('pabasa_app', '0008_assessment_content_status'), ('pabasa_app', '0009_material_created_at_material_section_and_more'), ('pabasa_app', '0010_make_material_created_at_aware'), ('pabasa_app', '0011_change_material_constraint_and_ordering'), ('pabasa_app', '0012_convert_assessments_to_materials'), ('pabasa_app', '0013_material_assigned_sections_material_content_json_and_more'), ('pabasa_app', '0014_alter_material_options_and_more'), ('pabasa_app', '0015_add_admin_role_and_account'), ('pabasa_app', '0016_user_archive_fields'), ('pabasa_app', '0017_material_type'), ('pabasa_app', '0018_create_practice'), ('pabasa_app', '0019_remove_section_grade_level'), ('pabasa_app', '0020_add_assigned_week'), ('pabasa_app', '0021_add_practice_status_prompt'), ('pabasa_app', '0022_course_courseassessmentassignment'), ('pabasa_app', '0023_create_default_test_accounts'), ('pabasa_app', '0024_update_default_test_accounts'), ('pabasa_app', '0025_material_assigned_week_integer'), ('pabasa_app', '0026_add_preference_and_remove_parent_contact_no'), ('pabasa_app', '0027_add_practice_material'), ('pabasa_app', '0028_add_material_source_type'), ('pabasa_app', '0029_remove_practice_content_fields'), ('pabasa_app', '0030_remove_assessment_content_alter_practice_status_and_more'), ('pabasa_app', '0027_material_source_type'), ('pabasa_app', '0031_merge_20260701_1351'), ('pabasa_app', '0032_assessment_attempts_table'), ('pabasa_app', '0033_alter_assessment_attempts_and_more'), ('pabasa_app', '0034_remove_assessment_attempt_history_and_more'), ('pabasa_app', '0035_material_code_teacher_assessment_material'), ('pabasa_app', '0036_user_theme_shop_fields'), ('pabasa_app', '0037_sync_user_theme_shop_columns'), ('pabasa_app', '0038_normalize_material_language_to_filipino'), ('pabasa_app', '0039_hunt_star_award'), ('pabasa_app', '0040_live_assessment_session'), ('pabasa_app', '0041_alter_assessment_assessment_type_and_more'), ('pabasa_app', '0042_liveassessmentsession_activity_log_and_more'), ('pabasa_app', '0043_assessment_correct_items'), ('pabasa_app', '0044_alter_liveassessmentsession_status_and_more'), ('pabasa_app', '0045_user_lrn'), ('pabasa_app', '0046_material_language'), ('pabasa_app', '0047_material_student_access'), ('pabasa_app', '0048_user_animal_avatar'), ('pabasa_app', '0049_assessmentwindowsetting_material_assessment_set'), ('pabasa_app', '0050_material_assessment_kind'), ('pabasa_app', '0051_system_owned_crla_assessments'), ('pabasa_app', '0052_assessment_window_period_phase'), ('pabasa_app', '0053_schoolcalendar_and_more'), ('pabasa_app', '0054_official_reading_assessments'), ('pabasa_app', '0055_remove_assessmentwindowsetting_active_window_and_more'), ('pabasa_app', '0056_calendar_event_title_and_labels'), ('pabasa_app', '0057_calendarevent_term'), ('pabasa_app', '0058_official_reading_integrity_override_workflow'), ('pabasa_app', '0059_supporting_documentation_links_json'), ('pabasa_app', '0060_official_reading_override_security_lockout'), ('pabasa_app', '0061_seed_official_crla_assessments'), ('pabasa_app', '0062_update_official_crla_story_sets'), ('pabasa_app', '0063_material_assigned_weeks_template_source'), ('pabasa_app', '0064_alter_calendarevent_event_type_and_more'), ('pabasa_app', '0065_remove_preadded_accounts'), ('pabasa_app', '0066_backfill_official_crla_story_qas'), ('pabasa_app', '0067_backfill_official_crla_terms'), ('pabasa_app', '0068_assessment_official_term'), ('pabasa_app', '0069_section_grade_level_section'), ('pabasa_app', '0070_canonical_sections_and_enrollments'), ('pabasa_app', '0071_school_and_school_scoped_sections'), ('pabasa_app', '0072_remove_global_section_uniqueness'), ('pabasa_app', '0073_user_school_record'), ('pabasa_app', '0074_migrate_salawag_default_school'), ('pabasa_app', '0075_require_section_school'), ('pabasa_app', '0076_unique_active_principal_per_school'), ('pabasa_app', '0077_backfill_principal_school_record'), ('pabasa_app', '0078_user_must_change_password'), ('pabasa_app', '0079_calendarevent_scope_school'), ('pabasa_app', '0079_assessment_crla_score_data'), ('pabasa_app', '0080_merge_0079_migrations'), ('pabasa_app', '0081_alter_assessment_system_assessment_key_and_more'), ('pabasa_app', '0082_normalize_calendar_event_titles_and_dates'), ('pabasa_app', '0083_course_school'), ('pabasa_app', '0084_classify_legacy_practice'), ('pabasa_app', '0085_storyreadingprogress'), ('pabasa_app', '0086_storyreadingplayerprogress'), ('pabasa_app', '0087_storyreadingscore'), ('pabasa_app', '0088_storyreadingprogress_word_metrics'), ('pabasa_app', '0089_school_calendar_section_and_user'), ('pabasa_app', '0090_school_year_enrollment_and_account_status'), ('pabasa_app', '0091_enrollment_integrity'), ('pabasa_app', '0092_school_year_learning_records'), ('pabasa_app', '0093_seed_salawag_grade_two_sections'), ('pabasa_app', '0094_teacher_aral_schedule'), ('pabasa_app', '0094_section_assessment_week_enabled'), ('pabasa_app', '0095_merge_0094_section_assessment_week_enabled_0094_teacher_aral_schedule'), ('pabasa_app', '0096_liveassessmentsession_section'), ('pabasa_app', '0097_storyresponsesubmission'), ('pabasa_app', '0098_mark_five_w_story_questions'), ('pabasa_app', '0099_liveassessmentsession_batches'), ('pabasa_app', '0100_student_session_lock'), ('pabasa_app', '0101_alter_accountstatushistory_id_alter_assessment_id_and_more'), ('pabasa_app', '0102_alter_accountstatushistory_id_alter_assessment_id_and_more'), ('pabasa_app', '0100_backfill_assessment_week_enabled_default'), ('pabasa_app', '0103_merge_20260904_1005'), ('pabasa_app', '0104_alter_section_assessment_week_enabled_not_null'), ('pabasa_app', '0105_liveassessmentsession_state_version'), ('pabasa_app', '0106_systemtimeoverride'), ('pabasa_app', '0107_activitylog'), ('pabasa_app', '0108_backfill_crla_reading_profile'), ('pabasa_app', '0109_liveassessmentsession_batch_loaded_status'), ('pabasa_app', '0110_classcrlafinalization'), ('pabasa_app', '0111_dropped_statuses'), ('pabasa_app', '0112_alter_accountstatushistory_status'), ('pabasa_app', '0113_prevent_unsaved_practice_level_reservations')]

    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name='Assessment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=150)),
                ('code', models.CharField(max_length=30, unique=True)),
                ('assessment_type', models.CharField(choices=[('word', 'Word'), ('sentence', 'Sentence'), ('paragraph', 'Paragraph')], max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'assessments', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='ReadingClass',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('class_code', models.CharField(max_length=20, unique=True)),
                ('class_name', models.CharField(max_length=150)),
                ('header', models.CharField(default='Reading Class', max_length=100)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'reading_classes', 'ordering': ['class_name']},
        ),
        migrations.CreateModel(
            name='StudentProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('student_code', models.CharField(editable=False, max_length=20, unique=True)),
                ('grade_level', models.CharField(blank=True, max_length=20)),
                ('section', models.CharField(blank=True, max_length=50)),
                ('reading_level', models.CharField(blank=True, max_length=50)),
                ('wpm', models.PositiveIntegerField(default=0)),
                ('accuracy', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('parent_contact_no', models.CharField(blank=True, max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'student_profiles', 'ordering': ['student_code']},
        ),
        migrations.CreateModel(
            name='TeacherProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('teacher_code', models.CharField(editable=False, max_length=20, unique=True)),
                ('teacher_role', models.CharField(blank=True, max_length=50)),
                ('school', models.CharField(blank=True, max_length=150)),
                ('department', models.CharField(blank=True, max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'teacher_profiles', 'ordering': ['teacher_code']},
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('custom_id', models.CharField(editable=False, max_length=20, unique=True)),
                ('role', models.CharField(choices=[('teacher', 'Teacher'), ('student', 'Student')], max_length=20)),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('sex', models.CharField(max_length=10)),
                ('birth_month', models.PositiveSmallIntegerField()),
                ('birth_day', models.PositiveSmallIntegerField()),
                ('birth_year', models.PositiveSmallIntegerField()),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('contact_no', models.CharField(blank=True, max_length=20, null=True)),
                ('password_hash', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('middle_initial', models.CharField(blank=True, max_length=1)),
                ('suffix', models.CharField(blank=True, max_length=10)),
                ('profile_picture', models.CharField(blank=True, max_length=255, null=True)),
                ('tags', models.JSONField(blank=True, default=list)),
            ],
            options={'db_table': 'users', 'ordering': ['last_name', 'first_name']},
        ),
        migrations.CreateModel(
            name='AssessmentAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('started', 'Started'), ('completed', 'Completed'), ('submitted', 'Submitted'), ('cancelled', 'Cancelled')], default='started', max_length=20)),
                ('device_info', models.CharField(blank=True, max_length=255)),
                ('mic_used', models.BooleanField(default=False)),
                ('assessment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempts', to='pabasa_app.assessment')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessment_attempts', to='pabasa_app.studentprofile')),
            ],
            options={'db_table': 'assessment_attempts', 'ordering': ['-started_at']},
        ),
        migrations.CreateModel(
            name='AssessmentResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accuracy', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('wpm', models.PositiveIntegerField(default=0)),
                ('clarity_score', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('pronunciation_score', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('comprehension_score', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('total_score', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('passed', models.BooleanField(default=False)),
                ('remarks', models.TextField(blank=True)),
                ('attempt', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='result', to='pabasa_app.assessmentattempt')),
            ],
            options={'db_table': 'assessment_results'},
        ),
        migrations.AddField(model_name='assessment', name='reading_class',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='assessments', to='pabasa_app.readingclass')),
        migrations.CreateModel(
            name='TeacherNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('note_text', models.TextField()),
                ('note_type', models.CharField(blank=True, max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assessment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='teacher_notes', to='pabasa_app.assessment')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_notes', to='pabasa_app.studentprofile')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notes', to='pabasa_app.teacherprofile')),
            ],
            options={'db_table': 'teacher_notes', 'ordering': ['-created_at']},
        ),
        migrations.AddField(model_name='readingclass', name='teacher',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reading_classes', to='pabasa_app.teacherprofile')),
        migrations.AddField(model_name='assessment', name='teacher',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessments', to='pabasa_app.teacherprofile')),
        migrations.AddField(model_name='teacherprofile', name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_profile', to='pabasa_app.user')),
        migrations.AddField(model_name='studentprofile', name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='student_profile', to='pabasa_app.user')),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=150)),
                ('message', models.TextField()),
                ('notification_type', models.CharField(choices=[('info', 'Info'), ('success', 'Success'), ('warning', 'Warning'), ('error', 'Error'), ('assessment', 'Assessment'), ('message', 'Message')], default='info', max_length=20)),
                ('is_read', models.BooleanField(default=False)),
                ('action_url', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sent_notifications', to='pabasa_app.user')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='pabasa_app.user')),
            ],
            options={'db_table': 'notifications', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='AssessmentItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item_type', models.CharField(choices=[('word', 'Word'), ('sentence', 'Sentence'), ('paragraph', 'Paragraph')], max_length=20)),
                ('prompt_text', models.TextField()),
                ('order_index', models.PositiveIntegerField()),
                ('expected_answer', models.TextField(blank=True, null=True)),
                ('difficulty_level', models.CharField(blank=True, max_length=50)),
                ('audio_url', models.URLField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('assessment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='pabasa_app.assessment')),
            ],
            options={'db_table': 'assessment_items', 'ordering': ['assessment', 'order_index'], 'constraints': [models.UniqueConstraint(fields=('assessment', 'order_index'), name='unique_assessment_item_order')]},
        ),
        migrations.CreateModel(
            name='ClassEnrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('reading_class', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='pabasa_app.readingclass')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='pabasa_app.studentprofile')),
            ],
            options={'db_table': 'class_enrollments', 'ordering': ['-joined_at'], 'constraints': [models.UniqueConstraint(fields=('student', 'reading_class'), name='unique_student_class_enrollment')]},
        ),
        migrations.AddField(model_name='readingclass', name='grade_level',
            field=models.CharField(default='Grade 1', max_length=20), preserve_default=False),
        migrations.AddField(model_name='readingclass', name='section',
            field=models.CharField(default='Sampaguita', max_length=50), preserve_default=False),
        migrations.AddField(model_name='readingclass', name='subject',
            field=models.CharField(default='English', max_length=50), preserve_default=False),
        migrations.RunPython(code=m0005_copy_profiles_to_users,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.DeleteModel(name='AssessmentResult'),
        migrations.DeleteModel(name='AssessmentAttempt'),
        migrations.AddField(model_name='assessment', name='attempts', field=models.JSONField(blank=True, default=list)),
        migrations.RenameModel(old_name='ReadingClass', new_name='Section'),
        migrations.RenameModel(old_name='ClassEnrollment', new_name='Enrollment'),
        migrations.RenameModel(old_name='AssessmentItem', new_name='Material'),
        migrations.RenameModel(old_name='TeacherNote', new_name='Note'),
        migrations.RemoveConstraint(model_name='enrollment', name='unique_student_class_enrollment'),
        migrations.RenameField(model_name='assessment', old_name='reading_class', new_name='section'),
        migrations.RenameField(model_name='enrollment', old_name='reading_class', new_name='section'),
        migrations.RunPython(code=m0005_repoint_profile_foreign_keys,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AlterField(model_name='section', name='teacher',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='pabasa_app.user')),
        migrations.AlterField(model_name='enrollment', name='student',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='pabasa_app.user')),
        migrations.AlterField(model_name='enrollment', name='section',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='pabasa_app.section')),
        migrations.AlterField(model_name='assessment', name='teacher',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessments', to='pabasa_app.user')),
        migrations.AlterField(model_name='assessment', name='section',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='assessments', to='pabasa_app.section')),
        migrations.AlterField(model_name='note', name='teacher',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notes', to='pabasa_app.user')),
        migrations.AlterField(model_name='note', name='student',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_notes', to='pabasa_app.user')),
        migrations.AlterField(model_name='material', name='assessment',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='materials', to='pabasa_app.assessment')),
        migrations.AddConstraint(model_name='enrollment',
            constraint=models.UniqueConstraint(fields=('student', 'section'), name='unique_student_section_enrollment')),
        migrations.AlterModelTable(name='section', table='sections'),
        migrations.AlterModelTable(name='material', table='materials'),
        migrations.AlterModelTable(name='note', table='notes'),
        migrations.AlterModelOptions(name='section', options={'ordering': ['class_name']}),
        migrations.AlterModelOptions(name='enrollment', options={'ordering': ['-joined_at']}),
        migrations.AlterModelOptions(name='material', options={'ordering': ['assessment', 'order_index']}),
        migrations.AlterModelOptions(name='note', options={'ordering': ['-created_at']}),
        migrations.DeleteModel(name='TeacherProfile'),
        migrations.DeleteModel(name='StudentProfile'),
        migrations.AddField(model_name='section', name='students', field=models.JSONField(blank=True, default=list)),
        migrations.RunPython(code=m0006_copy_enrollments_to_section_students,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.DeleteModel(name='Enrollment'),
        migrations.AddField(model_name='user', name='grade_level',
            field=models.CharField(blank=True, max_length=20, null=True)),
        migrations.AddField(model_name='user', name='section',
            field=models.CharField(blank=True, max_length=50, null=True)),
        migrations.AddField(model_name='user', name='reading_level',
            field=models.CharField(blank=True, max_length=50, null=True)),
        migrations.AddField(model_name='user', name='parent_contact_no',
            field=models.CharField(blank=True, max_length=20, null=True)),
        migrations.AddField(model_name='user', name='teacher_role',
            field=models.CharField(blank=True, max_length=50, null=True)),
        migrations.AddField(model_name='user', name='school',
            field=models.CharField(blank=True, max_length=150, null=True)),
        migrations.AddField(model_name='user', name='department',
            field=models.CharField(blank=True, max_length=100, null=True)),
        migrations.RunPython(code=m0007_migrate_teacher_data, reverse_code=m0007_reverse_migrate_teacher_data),
        migrations.RunPython(code=m0007_migrate_student_data, reverse_code=m0007_reverse_migrate_student_data),
        migrations.RunPython(code=m0007_validate_section_enrollment,
            reverse_code=m0007_reverse_validate_section_enrollment),
        migrations.RunPython(code=m0007_validate_assessment_attempts,
            reverse_code=m0007_reverse_validate_assessment_attempts),
        migrations.RunPython(code=m0007_document_pending_teacher_signup_schema,
            reverse_code=m0007_reverse_pending_signup_password_reset),
        migrations.RunPython(code=m0007_document_pending_student_signup_schema,
            reverse_code=m0007_reverse_pending_signup_password_reset),
        migrations.RunPython(code=m0007_document_pending_password_reset_schema,
            reverse_code=m0007_reverse_pending_signup_password_reset),
        migrations.AddField(model_name='assessment', name='content', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='assessment', name='status',
            field=models.CharField(choices=[('published', 'Published'), ('draft', 'Draft'), ('scheduled', 'Scheduled')], default='published', max_length=20)),
        migrations.AddField(model_name='assessment', name='scheduled_at',
            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='material', name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=datetime.datetime(2026, 6, 12, 15, 54, 49, 378798)),
            preserve_default=False),
        migrations.AddField(model_name='material', name='section',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials', to='pabasa_app.section')),
        migrations.AddField(model_name='material', name='updated_at', field=models.DateTimeField(auto_now=True)),
        migrations.AlterField(model_name='material', name='assessment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='materials', to='pabasa_app.assessment')),
        migrations.AddField(model_name='material', name='assigned_week',
            field=models.CharField(blank=True, default='', max_length=20)),
        migrations.RunPython(code=m0010_make_created_at_aware,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.RunPython(code=m0011_renumber_material_order,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.RemoveConstraint(model_name='material', name='unique_assessment_item_order'),
        migrations.AddConstraint(model_name='material',
            constraint=models.UniqueConstraint(fields=('section', 'item_type', 'order_index'), name='unique_section_item_order')),
        migrations.AlterModelOptions(name='material',
            options={'db_table': 'materials', 'ordering': ['section', 'order_index']}),
        migrations.RunPython(code=m0012_convert_assessments_to_materials,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AddField(model_name='material', name='assigned_sections',
            field=models.ManyToManyField(blank=True, related_name='assigned_materials', to='pabasa_app.section')),
        migrations.AddField(model_name='material', name='content_json',
            field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name='material', name='content_text', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='material', name='scheduled_at',
            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='material', name='status',
            field=models.CharField(choices=[('published', 'Published'), ('draft', 'Draft'), ('scheduled', 'Scheduled')], default='published', max_length=20)),
        migrations.AddField(model_name='material', name='title',
            field=models.CharField(blank=True, default='', max_length=150)),
        migrations.AlterField(model_name='material', name='prompt_text',
            field=models.TextField(blank=True, default='')),
        migrations.AlterModelOptions(name='material', options={'ordering': ['section', 'created_at']}),
        migrations.RemoveConstraint(model_name='material', name='unique_section_item_order'),
        migrations.RemoveField(model_name='material', name='audio_url'),
        migrations.RemoveField(model_name='material', name='expected_answer'),
        migrations.RemoveField(model_name='material', name='order_index'),
        migrations.AlterField(model_name='user', name='role',
            field=models.CharField(choices=[('admin', 'Admin'), ('teacher', 'Teacher'), ('student', 'Student')], max_length=20)),
        migrations.RunPython(code=m0015_create_admin_account, reverse_code=m0015_remove_admin_account),
        migrations.AddField(model_name='user', name='is_archived', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='user', name='archived_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='material', name='type',
            field=models.CharField(choices=[('practice', 'Practice'), ('assessment', 'Assessment'), ('both', 'Both')], default='practice', max_length=20)),
        migrations.RemoveField(model_name='section', name='grade_level'),
        migrations.RemoveField(model_name='section', name='section'),
        migrations.AddField(model_name='material', name='assigned_week',
            field=models.CharField(blank=True, default='', max_length=20)),
        migrations.CreateModel(
            name='Practice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=150)),
                ('code', models.CharField(max_length=30, unique=True)),
                ('practice_type', models.CharField(choices=[('word', 'Word'), ('sentence', 'Sentence'), ('paragraph', 'Paragraph')], max_length=20)),
                ('difficulty_type', models.CharField(blank=True, max_length=50)),
                ('contents', models.TextField(blank=True, default='')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('attempts', models.JSONField(blank=True, default=list)),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='practices', to='pabasa_app.user')),
                ('section', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='practices', to='pabasa_app.section')),
                ('prompt_text', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('published', 'Published'), ('draft', 'Draft'), ('scheduled', 'Scheduled')], default='published', max_length=20)),
            ],
            options={'db_table': 'practices', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=40, unique=True)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('sections', models.ManyToManyField(blank=True, related_name='courses', to='pabasa_app.section')),
                ('assessments', models.ManyToManyField(blank=True, related_name='courses', to='pabasa_app.assessment')),
                ('materials', models.ManyToManyField(blank=True, related_name='courses', to='pabasa_app.material')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='courses', to='pabasa_app.user')),
            ],
            options={'db_table': 'courses', 'ordering': ['-created_at']},
        ),
        migrations.RunPython(code=m0023_create_default_test_accounts, reverse_code=m0023_delete_default_test_accounts),
        migrations.RunPython(code=m0024_update_default_test_accounts, reverse_code=m0024_revert_default_test_accounts),
        migrations.AddField(model_name='material', name='assigned_week_integer',
            field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(99)])),
        migrations.RunPython(code=m0025_populate_assigned_week_integer,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.RemoveField(model_name='material', name='assigned_week'),
        migrations.RenameField(model_name='material', old_name='assigned_week_integer', new_name='assigned_week'),
        migrations.AddField(model_name='user', name='preference', field=models.JSONField(blank=True, default=dict)),
        migrations.RemoveField(model_name='user', name='parent_contact_no'),
        migrations.AddField(model_name='practice', name='material',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='practice_result', to='pabasa_app.material')),
        migrations.RunPython(code=m0027__create_practice_materials, reverse_code=m0027__remove_practice_materials),
        migrations.AddField(model_name='material', name='source_type',
            field=models.CharField(choices=[('personal', 'Personal'), ('shared', 'Shared')], default='personal', max_length=20)),
        migrations.RunPython(code=m0029_create_practice_materials,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.RemoveField(model_name='practice', name='practice_type'),
        migrations.RemoveField(model_name='practice', name='difficulty_type'),
        migrations.RemoveField(model_name='practice', name='contents'),
        migrations.RemoveField(model_name='practice', name='prompt_text'),
        migrations.RemoveField(model_name='assessment', name='content'),
        migrations.AlterField(model_name='practice', name='status',
            field=models.CharField(choices=[('published', 'Published'), ('draft', 'Draft'), ('scheduled', 'Scheduled')], default='draft', max_length=20)),
        migrations.AlterField(model_name='user', name='role',
            field=models.CharField(choices=[('admin', 'Admin'), ('principal', 'Principal'), ('teacher', 'Teacher'), ('student', 'Student')], max_length=20)),
        migrations.AddField(model_name='material', name='source_type',
            field=models.CharField(choices=[('personal', 'Personal'), ('shared', 'Shared')], default='personal', max_length=20)),
        migrations.AddField(model_name='assessment', name='attempts', field=models.JSONField(blank=True, default=list)),
        migrations.RunPython(code=m0032_backfill_assessment_attempts,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.RunPython(code=m0032_drop_legacy_assessment_attempt_table,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AddField(model_name='assessment', name='attempt_no', field=models.PositiveIntegerField(default=0)),
        migrations.RenameField(model_name='assessment', old_name='attempts', new_name='attempt_history'),
        migrations.RemoveField(model_name='assessment', name='attempt_history'),
        migrations.AddField(model_name='assessment', name='accuracy', field=models.FloatField(blank=True, null=True)),
        migrations.AddField(model_name='assessment', name='attempt_id',
            field=models.CharField(blank=True, default='', max_length=64)),
        migrations.AddField(model_name='assessment', name='attempt_number',
            field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='assessment', name='attempt_status',
            field=models.CharField(default='started', max_length=20)),
        migrations.AddField(model_name='assessment', name='classification',
            field=models.CharField(blank=True, default='', max_length=100)),
        migrations.AddField(model_name='assessment', name='completed_at',
            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='assessment', name='crla_classification',
            field=models.CharField(blank=True, default='', max_length=100)),
        migrations.AddField(model_name='assessment', name='device_info',
            field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='assessment', name='duration_seconds',
            field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name='assessment', name='fluency_score',
            field=models.FloatField(blank=True, null=True)),
        migrations.AddField(model_name='assessment', name='items_completed',
            field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='assessment', name='mic_used', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='assessment', name='needs_manual_review',
            field=models.BooleanField(default=False)),
        migrations.AddField(model_name='assessment', name='passed', field=models.BooleanField(blank=True, null=True)),
        migrations.AddField(model_name='assessment', name='pronunciation_score',
            field=models.FloatField(blank=True, null=True)),
        migrations.AddField(model_name='assessment', name='remarks', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='assessment', name='source_assessment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='attempt_rows', to='pabasa_app.assessment')),
        migrations.AddField(model_name='assessment', name='speech_recognition_used',
            field=models.BooleanField(default=False)),
        migrations.AddField(model_name='assessment', name='stars_earned', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='assessment', name='started_at',
            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='assessment', name='student',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assessment_attempt_rows', to='pabasa_app.user')),
        migrations.AddField(model_name='assessment', name='time_score', field=models.FloatField(blank=True, null=True)),
        migrations.AddField(model_name='assessment', name='total_score',
            field=models.FloatField(blank=True, null=True)),
        migrations.AddField(model_name='assessment', name='transcript', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='assessment', name='word_count',
            field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name='assessment', name='wpm', field=models.FloatField(blank=True, null=True)),
        migrations.AddField(model_name='material', name='code',
            field=models.CharField(blank=True, max_length=30, null=True, unique=True)),
        migrations.AddField(model_name='material', name='teacher',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials', to='pabasa_app.user')),
        migrations.AddField(model_name='assessment', name='material',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assessment_results', to='pabasa_app.material')),
        migrations.RunPython(code=m0035_populate_material_metadata,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AlterField(model_name='material', name='code',
            field=models.CharField(blank=True, default='', max_length=30, unique=True)),
        migrations.AddField(model_name='user', name='available_stars', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='user', name='theme_stars_credited',
            field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='user', name='unlocked_themes',
            field=models.JSONField(blank=True, default=pabasa_app.models.default_unlocked_themes)),
        migrations.AddField(model_name='user', name='equipped_theme',
            field=models.CharField(default='sky', max_length=30)),
        migrations.RunPython(code=m0037_add_missing_user_theme_columns,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.RunPython(code=m0038_normalize_material_language_to_filipino,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.CreateModel(
            name='HuntStarAward',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attempt_id', models.CharField(max_length=64)),
                ('award_key', models.CharField(max_length=32)),
                ('word_index', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('tier', models.CharField(blank=True, max_length=16)),
                ('stars', models.PositiveSmallIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hunt_star_awards', to='pabasa_app.material')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hunt_star_awards', to='pabasa_app.user')),
            ],
            options={'db_table': 'hunt_star_awards', 'constraints': [models.UniqueConstraint(fields=('student', 'material', 'attempt_id', 'award_key'), name='unique_hunt_attempt_award')]},
        ),
        migrations.AlterField(model_name='assessment', name='assessment_type',
            field=models.CharField(choices=[('word', 'Word'), ('vowel', 'Vowel'), ('sentence', 'Sentence'), ('paragraph', 'Paragraph')], max_length=20)),
        migrations.AlterField(model_name='material', name='item_type',
            field=models.CharField(choices=[('word', 'Word'), ('vowel', 'Vowel'), ('sentence', 'Sentence'), ('paragraph', 'Paragraph')], max_length=20)),
        migrations.AddField(model_name='assessment', name='correct_items',
            field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.CreateModel(
            name='LiveAssessmentSession',
            fields=[
                ('id', models.CharField(max_length=64, primary_key=True, serialize=False)),
                ('student_ids', models.JSONField(blank=True, default=list)),
                ('student_count', models.IntegerField(default=0)),
                ('status', models.CharField(choices=[('waiting', 'Waiting'), ('countdown', 'Countdown'), ('started', 'Started'), ('paused', 'Paused'), ('ended', 'Ended'), ('cancelled', 'Cancelled')], default='waiting', max_length=20)),
                ('start_at', models.DateTimeField(blank=True, null=True)),
                ('countdown_seconds', models.IntegerField(default=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='live_assessment_sessions', to='pabasa_app.course')),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='live_assessment_sessions', to='pabasa_app.material')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='live_assessment_sessions', to='pabasa_app.user')),
                ('activity_log', models.JSONField(blank=True, default=list)),
                ('duration_seconds', models.IntegerField(blank=True, null=True)),
                ('ends_at', models.DateTimeField(blank=True, null=True)),
                ('student_states', models.JSONField(blank=True, default=dict)),
                ('timing_mode', models.CharField(choices=[('none', 'No Limit'), ('duration', 'Duration')], default='none', max_length=20)),
            ],
            options={'db_table': 'live_assessment_sessions', 'ordering': ['-created_at']},
        ),
        migrations.AddField(model_name='user', name='lrn',
            field=models.CharField(blank=True, max_length=12, null=True, unique=True, validators=[django.core.validators.RegexValidator(message='LRN must contain exactly 12 digits.', regex='^\\d{12}$')], verbose_name='Learner Reference Number')),
        migrations.AddField(model_name='material', name='language',
            field=models.CharField(blank=True, default='English', max_length=20)),
        migrations.RunPython(code=m0046_backfill_practice_language,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AddField(model_name='material', name='student_access', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='user', name='animal_avatar',
            field=models.CharField(blank=True, default='cat', max_length=20)),
        migrations.AddField(model_name='material', name='assessment_set',
            field=models.CharField(blank=True, choices=[('crla', 'CRLA Assessment Set'), ('word', 'Word Assessment Set'), ('sentence', 'Sentence Assessment Set'), ('paragraph', 'Paragraph Assessment Set')], default='', max_length=20)),
        migrations.CreateModel(
            name='AssessmentWindowSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(default='assessment_window_active', max_length=50, unique=True)),
                ('active_window', models.CharField(choices=[('bosy', 'Beginning of School Year'), ('mosy', 'Middle of School Year'), ('eosy', 'End of School Year')], default='bosy', max_length=10)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assessment_window_updates', to='pabasa_app.user')),
            ],
            options={'db_table': 'assessment_window_settings'},
        ),
        migrations.AddField(model_name='material', name='assessment_kind',
            field=models.CharField(choices=[('regular', 'Regular Reading Material'), ('crla', 'CRLA Assessment')], default='regular', max_length=20)),
        migrations.RunPython(code=m0050_set_existing_materials_regular,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AddField(model_name='assessment', name='is_system_owned', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='assessment', name='system_assessment_key',
            field=models.CharField(blank=True, choices=[('', 'Teacher Owned'), ('bosy_crla_pretest', 'BoSY CRLA Pre-Test'), ('eosy_crla_posttest', 'EoSY CRLA Post-Test')], default='', max_length=40)),
        migrations.AddField(model_name='assessment', name='system_assessment_period',
            field=models.CharField(blank=True, default='', max_length=10)),
        migrations.AddField(model_name='assessment', name='system_assessment_phase',
            field=models.CharField(blank=True, default='', max_length=10)),
        migrations.AddField(model_name='material', name='is_system_owned', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='material', name='system_assessment_key',
            field=models.CharField(blank=True, default=None, max_length=40, null=True, unique=True)),
        migrations.AddField(model_name='material', name='system_assessment_period',
            field=models.CharField(blank=True, default='', max_length=10)),
        migrations.AddField(model_name='material', name='system_assessment_phase',
            field=models.CharField(blank=True, default='', max_length=10)),
        migrations.AddField(model_name='assessmentwindowsetting', name='active_period',
            field=models.CharField(choices=[('bosy', 'Beginning of School Year'), ('mosy', 'Middle of School Year'), ('eosy', 'End of School Year')], default='bosy', max_length=10)),
        migrations.AddField(model_name='assessmentwindowsetting', name='active_phase',
            field=models.CharField(choices=[('pretest', 'Pre-Test'), ('posttest', 'Post-Test')], default='pretest', max_length=10)),
        migrations.AddField(model_name='material', name='system_assessment_period',
            field=models.CharField(blank=True, default='', max_length=10)),
        migrations.AddField(model_name='material', name='system_assessment_phase',
            field=models.CharField(blank=True, default='', max_length=10)),
        migrations.AddField(model_name='assessment', name='system_assessment_period',
            field=models.CharField(blank=True, default='', max_length=10)),
        migrations.AddField(model_name='assessment', name='system_assessment_phase',
            field=models.CharField(blank=True, default='', max_length=10)),
        migrations.CreateModel(
            name='SchoolCalendar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('school_year', models.CharField(max_length=20, unique=True)),
                ('current_term', models.PositiveSmallIntegerField(choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')])),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'school_calendars', 'ordering': ['-is_active', '-created_at']},
        ),
        migrations.AddField(model_name='material', name='is_official_reading',
            field=models.BooleanField(default=False)),
        migrations.AddField(model_name='material', name='official_term',
            field=models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField(model_name='material', name='official_pdf',
            field=models.FileField(blank=True, null=True, upload_to='official_readings/')),
        migrations.RemoveField(model_name='assessmentwindowsetting', name='active_window'),
        migrations.AlterField(model_name='assessment', name='status',
            field=models.CharField(choices=[('published', 'Published'), ('draft', 'Draft'), ('archived', 'Archived'), ('scheduled', 'Scheduled')], default='published', max_length=20)),
        migrations.AlterField(model_name='material', name='status',
            field=models.CharField(choices=[('published', 'Published'), ('draft', 'Draft'), ('scheduled', 'Scheduled')], default='published', max_length=20)),
        migrations.AlterField(model_name='practice', name='status',
            field=models.CharField(choices=[('published', 'Published'), ('draft', 'Draft'), ('archived', 'Archived'), ('scheduled', 'Scheduled')], default='draft', max_length=20)),
        migrations.CreateModel(
            name='CalendarEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('school_opening', 'School Opening'), ('school_closing', 'School Closing'), ('pre_assessment', 'Pre-Assessment Week'), ('post_assessment', 'Post-Assessment Week'), ('holiday', 'Holiday'), ('examination', 'Examination Week'), ('other', 'Other Activity')], max_length=30)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('description', models.TextField(blank=True)),
                ('is_published', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('school_calendar', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='pabasa_app.schoolcalendar')),
                ('title', models.CharField(max_length=150)),
                ('term', models.PositiveSmallIntegerField(choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')], default=1)),
            ],
            options={'db_table': 'calendar_events', 'ordering': ['start_date', 'end_date']},
        ),
        migrations.CreateModel(
            name='OfficialReadingIntegrityOverrideRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_id', models.CharField(max_length=40, unique=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('expired', 'Expired'), ('used', 'Used')], default='pending', max_length=20)),
                ('deped_reference', models.TextField()),
                ('material_change', models.TextField()),
                ('justification', models.TextField()),
                ('supporting_documentation', models.TextField(blank=True, default='')),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_decision', models.CharField(blank=True, default='', max_length=20)),
                ('rejection_reason', models.TextField(blank=True, default='')),
                ('authorized_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('audit_payload', models.JSONField(blank=True, default=dict)),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='official_override_requests', to='pabasa_app.material')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='official_override_requests', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_official_override_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'official_reading_integrity_override_requests', 'ordering': ['-submitted_at', '-id']},
        ),
        migrations.CreateModel(
            name='OfficialReadingIntegrityAuthorization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('authorized_at', models.DateTimeField()),
                ('expires_at', models.DateTimeField()),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('audit_payload', models.JSONField(blank=True, default=dict)),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='official_integrity_authorizations', to='pabasa_app.material')),
                ('authorized_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='official_integrity_authorizations', to=settings.AUTH_USER_MODEL)),
                ('request', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='authorization', to='pabasa_app.officialreadingintegrityoverriderequest')),
            ],
            options={'db_table': 'official_reading_integrity_authorizations'},
        ),
        migrations.RunPython(code=m0059__convert_supporting_documentation,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AlterField(model_name='officialreadingintegrityoverriderequest', name='supporting_documentation',
            field=models.JSONField(blank=True, default=list)),
        migrations.CreateModel(
            name='OfficialReadingOverrideSecurityLockout',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('failed_attempt_count', models.PositiveSmallIntegerField(default=0)),
                ('last_failed_at', models.DateTimeField(blank=True, null=True)),
                ('lockout_expires_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('audit_payload', models.JSONField(blank=True, default=dict)),
                ('reviewer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='official_override_security_lockout', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'official_reading_override_security_lockouts'},
        ),
        migrations.RunPython(code=m0061_seed_official_crla_assessments,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.RunPython(code=m0062_update_official_crla_story_sets,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AddField(model_name='material', name='assigned_weeks',
            field=models.JSONField(blank=True, default=list)),
        migrations.AlterField(model_name='material', name='source_type',
            field=models.CharField(choices=[('personal', 'Personal'), ('shared', 'Shared'), ('template', 'Template')], default='personal', max_length=20)),
        migrations.AlterField(model_name='calendarevent', name='event_type',
            field=models.CharField(choices=[('start_of_classes', 'Start of Classes'), ('end_of_classes', 'End of Classes'), ('school_opening', 'Opening Block'), ('school_closing', 'End-of-Term Block'), ('pre_assessment', 'Pre-Assessment Week'), ('post_assessment', 'Post-Assessment Week'), ('holiday', 'Holiday'), ('examination', 'Examination Week'), ('other', 'Other Activity')], max_length=30)),
        migrations.AlterField(model_name='calendarevent', name='term',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3'), (4, 'Term 4')], default=1)),
        migrations.AlterField(model_name='officialreadingintegrityauthorization', name='authorized_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='official_integrity_authorizations', to='pabasa_app.user')),
        migrations.AlterField(model_name='officialreadingintegrityoverriderequest', name='requested_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='official_override_requests', to='pabasa_app.user')),
        migrations.AlterField(model_name='officialreadingintegrityoverriderequest', name='reviewed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_official_override_requests', to='pabasa_app.user')),
        migrations.AlterField(model_name='officialreadingoverridesecuritylockout', name='reviewer',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='official_override_security_lockout', to='pabasa_app.user')),
        migrations.AlterField(model_name='schoolcalendar', name='current_term',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3'), (4, 'Term 4')])),
        migrations.DeleteModel(name='AssessmentWindowSetting'),
        migrations.RunPython(code=m0065_remove_preseeded_accounts,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.RunPython(code=m0066_backfill_official_crla_story_qas, reverse_code=m0066_noop_reverse),
        migrations.RunPython(code=m0067_backfill_official_crla_terms, reverse_code=m0067_clear_official_crla_terms),
        migrations.AddField(model_name='assessment', name='official_term',
            field=models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.RunPython(code=m0068_backfill_attempt_terms,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AddField(model_name='section', name='grade_level',
            field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name='section', name='section', field=models.CharField(blank=True, max_length=50)),
        migrations.AlterField(model_name='section', name='teacher',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sections', to='pabasa_app.user')),
        migrations.CreateModel(
            name='Enrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='pabasa_app.section')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='pabasa_app.user')),
            ],
            options={'db_table': 'class_enrollments', 'ordering': ['-joined_at'], 'constraints': [models.UniqueConstraint(fields=('student', 'section'), name='unique_student_section_enrollment')]},
        ),
        migrations.RunPython(code=m0070_prepare_canonical_sections_and_enrollments,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AddConstraint(model_name='section',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower('grade_level'), django.db.models.functions.text.Lower('section'), condition=models.Q(('grade_level__gt', ''), ('section__gt', '')), name='unique_canonical_grade_section')),
        migrations.CreateModel(
            name='School',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True)),
                ('code', models.CharField(blank=True, default='', max_length=50, unique=True)),
                ('address', models.TextField(blank=True, default='')),
                ('contact_information', models.TextField(blank=True, default='')),
                ('logo', models.CharField(blank=True, max_length=255, null=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('archived', 'Archived')], default='active', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'schools', 'ordering': ['name']},
        ),
        migrations.AddField(model_name='section', name='school',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='sections', to='pabasa_app.school')),
        migrations.AddConstraint(model_name='section',
            constraint=models.UniqueConstraint(models.F('school'), django.db.models.functions.text.Lower('grade_level'), django.db.models.functions.text.Lower('section'), condition=models.Q(('grade_level__gt', ''), ('section__gt', '')), name='unique_school_canonical_grade_section')),
        migrations.RunPython(code=m0071_forwards, reverse_code=m0071_backwards),
        migrations.RemoveConstraint(model_name='section', name='unique_canonical_grade_section'),
        migrations.AddField(model_name='user', name='school_record',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='users', to='pabasa_app.school')),
        migrations.RunPython(code=m0073_backfill_user_schools,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.RunPython(code=m0074_forwards, reverse_code=m0074_backwards),
        migrations.RunPython(code=m0075_reject_unowned_sections,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AlterField(model_name='section', name='school',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sections', to='pabasa_app.school')),
        migrations.AddConstraint(model_name='user',
            constraint=models.UniqueConstraint(condition=models.Q(('is_archived', False), ('role', 'principal'), ('school_record__isnull', False)), fields=('school_record',), name='unique_active_principal_per_school')),
        migrations.RunPython(code=m0077_forwards, reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AddField(model_name='user', name='must_change_password', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='calendarevent', name='scope',
            field=models.CharField(choices=[('global', 'Global'), ('school', 'School-local')], default='global', max_length=10)),
        migrations.AddField(model_name='calendarevent', name='school',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='calendar_events', to='pabasa_app.school')),
        migrations.AddConstraint(model_name='calendarevent',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('school__isnull', True), ('scope', 'global')), models.Q(('school__isnull', False), ('scope', 'school')), _connector='OR'), name='calendar_event_scope_school_consistent')),
        migrations.AddField(model_name='assessment', name='crla_score_data',
            field=models.JSONField(blank=True, default=dict)),
        migrations.AlterField(model_name='assessment', name='system_assessment_key',
            field=models.CharField(blank=True, choices=[('', 'Teacher Owned'), ('bosy_crla_pretest', 'BoSY CRLA Pre-Test'), ('midline_crla_midtest', 'Midline CRLA Mid-Test'), ('eosy_crla_posttest', 'EoSY CRLA Post-Test')], default='', max_length=40)),
        migrations.AlterField(model_name='calendarevent', name='event_type',
            field=models.CharField(choices=[('start_of_classes', 'Start of Classes'), ('end_of_classes', 'End of Classes'), ('school_opening', 'Opening Block'), ('school_closing', 'End-of-Term Block'), ('pre_assessment', 'Pre-Assessment Week'), ('midline_assessment', 'Midline Assessment Week'), ('post_assessment', 'Post-Assessment Week'), ('holiday', 'Holiday'), ('examination', 'Examination Week'), ('other', 'Other Activity')], max_length=30)),
        migrations.RunPython(code=m0082_normalize_calendar_events,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AddField(model_name='course', name='school',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='courses', to='pabasa_app.school')),
        migrations.RunPython(code=m0083_backfill_course_school,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.RunPython(code=m0084_classify_known_admin_practice,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.CreateModel(
            name='StoryReadingProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('story_title', models.CharField(blank=True, default='', max_length=150)),
                ('total_words', models.PositiveIntegerField(default=0)),
                ('words_read', models.PositiveIntegerField(default=0)),
                ('progress_percent', models.FloatField(default=0)),
                ('duration_seconds', models.PositiveIntegerField(blank=True, null=True)),
                ('completed', models.BooleanField(default=False)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='story_reading_progress', to='pabasa_app.material')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='story_reading_progress', to='pabasa_app.user')),
                ('story_key', models.CharField(blank=True, default='', max_length=100)),
                ('current_scene', models.PositiveSmallIntegerField(default=1)),
                ('current_time_seconds', models.FloatField(default=0)),
                ('correct_sentences', models.PositiveSmallIntegerField(default=0)),
                ('reading_score', models.FloatField(default=0)),
                ('correct_words', models.PositiveIntegerField(default=0)),
                ('miscues', models.PositiveIntegerField(default=0)),
                ('accuracy', models.FloatField(default=0)),
                ('wpm', models.FloatField(default=0)),
                ('word_alignment', models.JSONField(blank=True, default=list)),
            ],
            options={'db_table': 'story_reading_progress', 'constraints': [models.UniqueConstraint(fields=('student', 'material'), name='unique_story_reading_progress')]},
        ),
        migrations.AddField(model_name='section', name='school_calendar',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='sections', to='pabasa_app.schoolcalendar')),
        migrations.AddField(model_name='user', name='school_calendar',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='users', to='pabasa_app.schoolcalendar')),
        migrations.RemoveConstraint(model_name='section', name='unique_school_canonical_grade_section'),
        migrations.AddConstraint(model_name='section',
            constraint=models.UniqueConstraint(models.F('school'), models.F('school_calendar'), django.db.models.functions.text.Lower('grade_level'), django.db.models.functions.text.Lower('section'), condition=models.Q(('grade_level__gt', ''), ('section__gt', '')), name='unique_school_calendar_canonical_grade_section')),
        migrations.AddField(model_name='user', name='account_status',
            field=models.CharField(choices=[('active', 'Active'), ('pending_archive', 'Pending Archive'), ('archived', 'Archived')], default='active', max_length=20)),
        migrations.AlterField(model_name='enrollment', name='section',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='pabasa_app.section')),
        migrations.AddField(model_name='enrollment', name='school',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='enrollments', to='pabasa_app.school')),
        migrations.AddField(model_name='enrollment', name='school_calendar',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='enrollments', to='pabasa_app.schoolcalendar')),
        migrations.AddField(model_name='enrollment', name='grade_level',
            field=models.CharField(blank=True, default='Grade 2', max_length=20)),
        migrations.AddField(model_name='enrollment', name='assigned_teacher',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_enrollments', to='pabasa_app.user')),
        migrations.AddField(model_name='enrollment', name='status',
            field=models.CharField(choices=[('active', 'Active'), ('completed', 'Completed'), ('awaiting_assignment', 'Awaiting Assignment')], default='active', max_length=30)),
        migrations.AddField(model_name='enrollment', name='outcome',
            field=models.CharField(choices=[('not_finalized', 'Not Finalized'), ('promoted', 'Promoted'), ('retained', 'Retained')], default='not_finalized', max_length=20)),
        migrations.AddField(model_name='enrollment', name='finalized_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='finalized_enrollments', to='pabasa_app.user')),
        migrations.AddField(model_name='enrollment', name='finalized_at',
            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='enrollment', name='updated_at', field=models.DateTimeField(auto_now=True)),
        migrations.CreateModel(
            name='AccountStatusHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('active', 'Active'), ('pending_archive', 'Pending Archive'), ('archived', 'Archived')], max_length=20)),
                ('reason', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='account_status_changes', to='pabasa_app.user')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='account_status_history', to='pabasa_app.user')),
            ],
            options={'ordering': ['-created_at', '-id']},
        ),
        migrations.RunPython(code=m0090_backfill_school_year_enrollments,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.RunPython(code=m0091_refuse_ambiguous_current_enrollments,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AddConstraint(model_name='enrollment',
            constraint=models.UniqueConstraint(condition=models.Q(('school_calendar__isnull', False), ('status__in', ['active', 'awaiting_assignment'])), fields=('student', 'school_calendar'), name='unique_current_student_school_year')),
        migrations.AddField(model_name='assessment', name='enrollment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assessment_attempts', to='pabasa_app.enrollment')),
        migrations.AddField(model_name='storyreadingprogress', name='enrollment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='story_reading_progress', to='pabasa_app.enrollment')),
        migrations.RunPython(code=m0092_backfill_enrollments,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.RemoveConstraint(model_name='storyreadingprogress', name='unique_story_reading_progress'),
        migrations.AddConstraint(model_name='storyreadingprogress',
            constraint=models.UniqueConstraint(condition=models.Q(('enrollment__isnull', True)), fields=('student', 'material'), name='unique_legacy_story_reading_progress')),
        migrations.AddConstraint(model_name='storyreadingprogress',
            constraint=models.UniqueConstraint(condition=models.Q(('enrollment__isnull', False)), fields=('enrollment', 'material'), name='unique_enrollment_story_reading_progress')),
        migrations.RunPython(code=m0093_seed_salawag_grade_two_sections,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.CreateModel(
            name='TeacherAralSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weekday', models.PositiveSmallIntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')], validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(6)])),
                ('remark', models.CharField(max_length=200)),
                ('applies_to', models.CharField(choices=[('current', 'Current Term'), ('all', 'All Terms')], default='current', max_length=10)),
                ('term', models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3'), (4, 'Term 4')], null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('school_calendar', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_aral_schedules', to='pabasa_app.schoolcalendar')),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_aral_schedules', to='pabasa_app.section')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='aral_schedules', to='pabasa_app.user')),
            ],
            options={'db_table': 'teacher_aral_schedules', 'ordering': ['weekday', 'section__class_name', 'id'], 'constraints': [models.CheckConstraint(condition=models.Q(models.Q(('applies_to', 'all'), ('term__isnull', True)), models.Q(('applies_to', 'current'), ('term__isnull', False)), _connector='OR'), name='teacher_aral_schedule_term_matches_scope')]},
        ),
        migrations.AddField(model_name='section', name='assessment_week_enabled',
            field=models.BooleanField(default=False)),
        migrations.AddField(model_name='liveassessmentsession', name='section',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='live_assessment_sessions', to='pabasa_app.section')),
        migrations.CreateModel(
            name='StoryResponseSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prompt', models.TextField(blank=True, default='')),
                ('response_text', models.TextField(blank=True, default='')),
                ('audio_file', models.FileField(blank=True, null=True, upload_to='story_responses/%Y/%m/%d/')),
                ('duration_seconds', models.PositiveIntegerField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending Grade'), ('graded', 'Graded')], default='pending', max_length=20)),
                ('grade', models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(5)])),
                ('graded_at', models.DateTimeField(blank=True, null=True)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('enrollment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='story_response_submissions', to='pabasa_app.enrollment')),
                ('graded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='graded_story_response_submissions', to='pabasa_app.user')),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='story_response_submissions', to='pabasa_app.material')),
                ('story_material', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='story_response_source_submissions', to='pabasa_app.material')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='story_response_submissions', to='pabasa_app.user')),
            ],
            options={'db_table': 'story_response_submissions', 'constraints': [models.UniqueConstraint(fields=('student', 'material'), name='unique_story_response_student_material')]},
        ),
        migrations.RunPython(code=m0098_mark_five_w_materials,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AddField(model_name='liveassessmentsession', name='batch_assignments',
            field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name='liveassessmentsession', name='batch_size',
            field=models.IntegerField(default=10)),
        migrations.AddField(model_name='liveassessmentsession', name='current_batch',
            field=models.IntegerField(default=1)),
        migrations.AddField(model_name='liveassessmentsession', name='total_batches',
            field=models.IntegerField(default=0)),
        migrations.AddField(model_name='user', name='active_session_key',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True)),
        migrations.AddField(model_name='user', name='active_session_created_at',
            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='user', name='last_activity', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='assessment', name='attempt_session_key',
            field=models.CharField(blank=True, default='', max_length=64)),
        migrations.AlterField(model_name='section', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='accountstatushistory', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='assessment', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.CreateModel(
            name='AssessmentRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('declined', 'Declined')], default='pending', max_length=20)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_assessment_requests', to='pabasa_app.user')),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessment_requests', to='pabasa_app.section')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessment_requests', to='pabasa_app.user')),
            ],
            options={'db_table': 'assessment_requests', 'ordering': ['requested_at', 'id'], 'constraints': [models.UniqueConstraint(condition=models.Q(('status', 'pending')), fields=('student', 'section'), name='one_pending_assessment_request')]},
        ),
        migrations.AlterField(model_name='calendarevent', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='course', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='enrollment', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='huntstaraward', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='material', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='note', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='notification', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='officialreadingintegrityauthorization', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='officialreadingintegrityoverriderequest', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='officialreadingoverridesecuritylockout', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='practice', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='school', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='schoolcalendar', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='storyreadingprogress', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='storyresponsesubmission', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AlterField(model_name='teacheraralschedule', name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.RunPython(code=m0100_backfill_assessment_week_enabled, reverse_code=m0100_reverse_backfill),
        migrations.RunSQL(sql='UPDATE sections SET assessment_week_enabled = 0 WHERE assessment_week_enabled IS NULL',
            reverse_sql='UPDATE sections SET assessment_week_enabled = NULL WHERE assessment_week_enabled = 0'),
        migrations.AlterField(model_name='section', name='assessment_week_enabled',
            field=models.BooleanField(default=False)),
        migrations.AddField(model_name='liveassessmentsession', name='state_version',
            field=models.PositiveIntegerField(default=0)),
        migrations.CreateModel(
            name='SystemTimeOverride',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ('enabled', models.BooleanField(default=False)),
                ('reference_time', models.DateTimeField(blank=True, null=True)),
                ('configured_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={'db_table': 'system_time_override'},
        ),
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('notification', 'Notification'), ('system_time_debug', 'System Time Debug')], max_length=32)),
                ('title', models.CharField(max_length=150)),
                ('message', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(db_index=True, default=pabasa_app.system_clock.real_now, editable=False)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='activity_log_entries', to='pabasa_app.user')),
            ],
            options={'db_table': 'activity_logs', 'ordering': ['-created_at', '-id']},
        ),
        migrations.RunPython(code=m0108_backfill_final_crla_profiles,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AlterField(model_name='liveassessmentsession', name='status',
            field=models.CharField(choices=[('waiting', 'Waiting'), ('batch_loaded', 'Batch Loaded'), ('countdown', 'Countdown'), ('started', 'Started'), ('paused', 'Paused'), ('ended', 'Ended'), ('cancelled', 'Cancelled')], default='waiting', max_length=20)),
        migrations.CreateModel(
            name='ClassCrlaFinalization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('finalized_at', models.DateTimeField(default=pabasa_app.system_clock.now)),
                ('finalized_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='crla_finalizations', to='pabasa_app.user')),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_finalizations', to='pabasa_app.material')),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='crla_finalizations', to='pabasa_app.section')),
            ],
            options={'constraints': [models.UniqueConstraint(fields=('section', 'material'), name='unique_section_crla_finalization')]},
        ),
        migrations.AlterField(model_name='user', name='account_status',
            field=models.CharField(choices=[('active', 'Active'), ('pending_archive', 'Pending Archive'), ('dropped', 'Dropped'), ('archived', 'Archived')], default='active', max_length=20)),
        migrations.AlterField(model_name='enrollment', name='status',
            field=models.CharField(choices=[('active', 'Active'), ('completed', 'Completed'), ('awaiting_assignment', 'Awaiting Assignment'), ('dropped', 'Dropped')], default='active', max_length=30)),
        migrations.AlterField(model_name='accountstatushistory', name='status',
            field=models.CharField(choices=[('active', 'Active'), ('pending_archive', 'Pending Archive'), ('dropped', 'Dropped'), ('archived', 'Archived')], max_length=20)),
        migrations.RunPython(code=m0113_remove_incomplete_admin_practice_materials,
            reverse_code=django.db.migrations.operations.special.RunPython.noop),
        migrations.AddConstraint(model_name='material',
            constraint=models.UniqueConstraint(models.F('language'), models.F('content_json__mode'), models.F('content_json__difficulty'), models.F('content_json__level'), condition=models.Q(('is_system_owned', True), ('section__isnull', True), ('source_type', 'shared'), ('teacher__isnull', True), ('type', 'practice'), models.Q(('content_text', ''), _negated=True)), name='uniq_valid_admin_practice_slot')),
    ]
