# Migration to add teacher and student-specific fields to User model
# and migrate data from User.tags JSONField + validate enrollment/attempt data\
# Along with cleanup of old Enrollment model and consolidation of enrollment/attempt data into JSONFields on Section and Assessment models.

from django.db import migrations, models


def migrate_teacher_data(apps, schema_editor):
    """
    Migrate teacher profile data from User.tags['teacher_profile'] 
    to dedicated teacher_role, school, department fields on User model.
    """
    User = apps.get_model('pabasa_app', 'User')
    
    for user in User.objects.filter(role='teacher').iterator():
        tags = getattr(user, 'tags', None) or []
        
        # Find teacher_profile entry in tags
        teacher_profile_data = {}
        if isinstance(tags, list):
            for entry in tags:
                if isinstance(entry, dict) and 'teacher_profile' in entry:
                    teacher_profile_data = entry.get('teacher_profile', {})
                    break
        
        # Set fields from extracted data
        if teacher_profile_data:
            user.teacher_role = teacher_profile_data.get('teacher_role', '')
            user.school = teacher_profile_data.get('school', '')
            user.department = teacher_profile_data.get('department', '')
            user.save(update_fields=['teacher_role', 'school', 'department'])


def reverse_migrate_teacher_data(apps, schema_editor):
    """
    Reverse migration: move teacher fields back to User.tags['teacher_profile']
    """
    User = apps.get_model('pabasa_app', 'User')
    
    for user in User.objects.filter(role='teacher').iterator():
        # Build teacher_profile dict from fields
        teacher_profile_data = {
            'teacher_role': user.teacher_role or '',
            'school': user.school or '',
            'department': user.department or '',
            'is_active': True,  # Default value
        }
        
        # Add/update teacher_profile in tags
        tags = getattr(user, 'tags', None) or []
        if not isinstance(tags, list):
            tags = [tags]
        
        # Find and update or create teacher_profile entry
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


def migrate_student_data(apps, schema_editor):
    """
    Migrate student profile data from User.tags['student_profile'] 
    to dedicated grade_level, section, reading_level, parent_contact_no fields on User model.
    """
    User = apps.get_model('pabasa_app', 'User')
    
    for user in User.objects.filter(role='student').iterator():
        tags = getattr(user, 'tags', None) or []
        
        # Find student_profile entry in tags
        student_profile_data = {}
        if isinstance(tags, list):
            for entry in tags:
                if isinstance(entry, dict) and 'student_profile' in entry:
                    student_profile_data = entry.get('student_profile', {})
                    break
        
        # Set fields from extracted data
        if student_profile_data:
            user.grade_level = student_profile_data.get('grade_level', '')
            user.section = student_profile_data.get('section', '')
            user.reading_level = student_profile_data.get('reading_level', '')
            user.parent_contact_no = student_profile_data.get('parent_contact_no', '')
            user.save(update_fields=['grade_level', 'section', 'reading_level', 'parent_contact_no'])


def reverse_migrate_student_data(apps, schema_editor):
    """
    Reverse migration: move student fields back to User.tags['student_profile']
    """
    User = apps.get_model('pabasa_app', 'User')
    
    for user in User.objects.filter(role='student').iterator():
        # Build student_profile dict from fields
        student_profile_data = {
            'grade_level': user.grade_level or '',
            'section': user.section or '',
            'reading_level': user.reading_level or '',
            'parent_contact_no': user.parent_contact_no or '',
            'is_active': True,  # Default value
        }
        
        # Add/update student_profile in tags
        tags = getattr(user, 'tags', None) or []
        if not isinstance(tags, list):
            tags = [tags]
        
        # Find and update or create student_profile entry
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


def validate_section_enrollment(apps, schema_editor):
    """
    Validate Section.students enrollment data is properly formatted.
    Ensures all enrollment entries have required fields.
    """
    Section = apps.get_model('pabasa_app', 'Section')
    
    for section in Section.objects.all():
        students = getattr(section, 'students', None) or []
        if not isinstance(students, list):
            continue
        
        # Validate and normalize enrollment entries
        has_changes = False
        for entry in students:
            if not isinstance(entry, dict):
                continue
            
            # Ensure required fields exist
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


def reverse_validate_section_enrollment(apps, schema_editor):
    """
    Reverse: no action needed for validation cleanup.
    """
    pass


def validate_assessment_attempts(apps, schema_editor):
    """
    Validate Assessment.attempts data is properly formatted.
    Ensures all attempt entries have required fields.
    """
    Assessment = apps.get_model('pabasa_app', 'Assessment')
    
    for assessment in Assessment.objects.all():
        attempts = getattr(assessment, 'attempts', None) or []
        if not isinstance(attempts, list):
            continue
        
        # Validate and normalize attempt entries
        has_changes = False
        for entry in attempts:
            if not isinstance(entry, dict):
                continue
            
            # Ensure required fields exist
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


def reverse_validate_assessment_attempts(apps, schema_editor):
    """
    Reverse: no action needed for validation cleanup.
    """
    pass


def document_pending_teacher_signup_schema(apps, schema_editor):
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


def document_pending_student_signup_schema(apps, schema_editor):
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


def document_pending_password_reset_schema(apps, schema_editor):
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


def reverse_pending_signup_password_reset(apps, schema_editor):
    """
    Reverse: no action needed. These are session-based, not database-backed.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('pabasa_app', '0006_section_students_json_remove_enrollment'),
    ]

    operations = [
        # Add student-specific fields
        migrations.AddField(
            model_name='user',
            name='grade_level',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='section',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='reading_level',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='parent_contact_no',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        # Add teacher-specific fields
        migrations.AddField(
            model_name='user',
            name='teacher_role',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='school',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='department',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        # Migrate profile data from JSONField to dedicated fields
        migrations.RunPython(migrate_teacher_data, reverse_migrate_teacher_data),
        migrations.RunPython(migrate_student_data, reverse_migrate_student_data),
        # Validate and consolidate enrollment/attempt data in JSONFields
        migrations.RunPython(validate_section_enrollment, reverse_validate_section_enrollment),
        migrations.RunPython(validate_assessment_attempts, reverse_validate_assessment_attempts),
        # Document pending signup and password reset session-based schemas
        migrations.RunPython(document_pending_teacher_signup_schema, reverse_pending_signup_password_reset),
        migrations.RunPython(document_pending_student_signup_schema, reverse_pending_signup_password_reset),
        migrations.RunPython(document_pending_password_reset_schema, reverse_pending_signup_password_reset),
    ]
