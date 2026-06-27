from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth import authenticate, login
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.db import IntegrityError
from django.db.models import Q
from functools import wraps
import logging
import json
import os
from pathlib import Path
import random
import traceback
import ssl
import time
import uuid
import zipfile
from .forms import AdminPracticeMaterialForm, parse_practice_items
from django.db import transaction
import re
import traceback
from .models import User, Section, Assessment, Material, Practice, Note, Notification, Course
from .reading_material_utils import format_assigned_week_display, parse_assigned_week

# Utilities for profile-like data now stored on `User.tags` (JSONField)
def _get_profile_dict(user, key):
    if not user:
        return {}
    # Prefer a dedicated `preference` JSONField when available (new storage),
    # fall back to legacy `tags` storage for backward compatibility.
    try:
        prefs = getattr(user, 'preference', None) or {}
        if isinstance(prefs, dict) and key in prefs:
            return prefs.get(key) or {}
    except Exception:
        pass

    tags = getattr(user, 'tags', None) or []
    if isinstance(tags, dict):
        return tags.get(key, {})
    for entry in tags:
        if isinstance(entry, dict) and key in entry:
            return entry.get(key) or {}
    return {}

def _set_profile_dict(user, key, profile_dict):
    tags = getattr(user, 'tags', None) or []
    if not isinstance(tags, list):
        tags = [tags]
    replaced = False
    for i, entry in enumerate(tags):
        if isinstance(entry, dict) and key in entry:
            tags[i] = {key: profile_dict}
            replaced = True
            break
    if not replaced:
        tags.append({key: profile_dict})
    user.tags = tags

    # Also persist into the new `preference` JSONField when available so
    # settings changes are stored in a dedicated column.
    try:
        pref = getattr(user, 'preference', None) or {}
        if not isinstance(pref, dict):
            pref = {}
        pref[key] = profile_dict
        user.preference = pref
        user.save(update_fields=['tags', 'preference', 'updated_at'])
    except Exception:
        user.save()

def _parse_prefixed_id(val):
    """
    Robustly extract an integer ID from a value that might be 
    prefixed (e.g., 'material-123', 'assessment-45') or a raw ID.
    Returns (prefix, integer_id).
    """
    if val is None:
        return None, None
    if isinstance(val, int):
        return None, val
    
    s = str(val).strip()
    if not s or s.lower() == 'null' or s.lower() == 'undefined':
        return None, None
        
    if '-' in s:
        parts = s.split('-', 1)
        prefix = parts[0].lower()
        try:
            return prefix, int(parts[1])
        except (ValueError, TypeError):
            return prefix, None
    
    try:
        return None, int(s)
    except (ValueError, TypeError):
        return None, None

def _section_students(section, active_only=False):
    """Delegate to Section model method"""
    return section.get_enrolled_students(active_only=active_only)

def _student_entry_matches(entry, user):
    """Helper to check if entry matches user (DEPRECATED - use section.has_student instead)"""
    return str(entry.get('student_id')) == str(user.id) or entry.get('custom_id') == user.custom_id

def _section_has_student(section, user, active_only=True):
    """Delegate to Section model method"""
    return section.has_student(user, active_only=active_only)

def _section_student_count(section):
    """Delegate to Section model method"""
    return section.get_student_count()

def _student_section_entry(user, joined_at=None, is_active=True):
    """DEPRECATED - this method is now on Section model"""
    return {
        'student_id': user.id,
        'custom_id': user.custom_id,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'joined_at': joined_at or timezone.now().isoformat(),
        'is_active': is_active,
    }

def _save_section_students(section, students):
    """DEPRECATED - use section._save_enrollment() instead"""
    section.students = students
    section._save_enrollment()

def _add_student_to_section(section, user):
    """Delegate to Section model method"""
    return section.add_student(user)

def _deactivate_student_in_section(section, user):
    """Delegate to Section model method"""
    return section.deactivate_student(user)

def _deactivate_all_section_students(section):
    """Delegate to Section model method"""
    return section.deactivate_all_students()

# ===== Assessment Attempt Helper Functions (DEPRECATED - use Assessment model methods) =====

def _get_assessment_attempts(assessment, student=None):
    """Delegate to Assessment model method"""
    return assessment.get_attempts(student)

def _get_student_attempt_count(assessment, student):
    """Delegate to Assessment model method"""
    return assessment.get_student_attempt_count(student)

def _has_student_attempted(assessment, student):
    """Delegate to Assessment model method"""
    return assessment.has_student_attempted(student)

def _record_attempt(assessment, student, **attempt_data):
    """Delegate to Assessment model method"""
    return assessment.record_attempt(student, **attempt_data)

def _update_attempt(assessment, student, **update_data):
    """Delegate to Assessment model method"""
    return assessment.update_attempt(student, **update_data)

def _get_student_latest_attempt(assessment, student):
    """Delegate to Assessment model method"""
    return assessment.get_student_latest_attempt(student)

def _deactivate_student_attempts(assessment, student):
    """Delegate to Assessment model method"""
    return assessment.deactivate_student_attempts(student)

def _clear_all_assessment_attempts(assessment):
    """Delegate to Assessment model method"""
    return assessment.clear_all_attempts()

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from datetime import timedelta, datetime
from django.db.models import Max, Count, Q


logger = logging.getLogger(__name__)

PROFILE_PHOTOS_DIR = settings.BASE_DIR / 'pabasa_app' / 'static' / 'pabasa_app' / 'uploads' / 'profiles'

# Authentication decorator
def login_required(role=None):
    """Decorator to check if user is authenticated and optionally check role"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Detect AJAX/JSON requests so we can return JSON responses
            is_ajax = False
            try:
                accept = request.META.get('HTTP_ACCEPT', '') or ''
                # Prefer the standardized request.headers when available, fall back to META
                x_requested = None
                try:
                    x_requested = request.headers.get('X-Requested-With')
                except Exception:
                    x_requested = request.META.get('HTTP_X_REQUESTED_WITH')

                is_ajax = (x_requested == 'XMLHttpRequest') or accept.startswith('application/json')
            except Exception:
                is_ajax = False

            if 'user_id' not in request.session:
                if is_ajax:
                    return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
                return redirect('auth')
            if role and request.session.get('user_role') != role:
                if is_ajax:
                    return JsonResponse({'success': False, 'error': 'Forbidden: insufficient role'}, status=403)
                return redirect('auth')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def csrf_failure(request, reason=''):
    """Custom CSRF failure handler that returns JSON for AJAX/JSON requests."""
    try:
        accept = request.META.get('HTTP_ACCEPT', '') or ''
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or accept.startswith('application/json')
    except Exception:
        is_ajax = False

    if is_ajax:
        return JsonResponse({'success': False, 'error': 'CSRF token missing or invalid.'}, status=403)
    return HttpResponseForbidden('<h1>403 Forbidden</h1>')

def _current_user(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    return User.objects.filter(id=user_id).first()

def _admin_users():
    return User.objects.filter(role='admin', is_archived=False)

def _create_notification(recipient, title, message, notification_type='info', action_url='', created_by=None, email_subject=None, email_body=None):
    if not recipient:
        return None
    notification = Notification.objects.create(
        recipient=recipient,
        created_by=created_by,
        title=title,
        message=message,
        notification_type=notification_type,
        action_url=action_url or '',
    )

    # REAL-TIME EMAIL DISPATCH: Send email immediately if user preference allows
    try:
        settings_dict = _notification_settings_for_user(recipient)
        if settings_dict.get('email_notifications') is True:
            send_mail(
                email_subject if email_subject is not None else title,
                email_body if email_body is not None else message,
                settings.DEFAULT_FROM_EMAIL,
                [recipient.email],
                fail_silently=True
            )
    except Exception as e:
        logger.error(f"Failed to send real-time notification email: {e}")

    return notification

def _notify_admins(title, message, notification_type='info', action_url='', created_by=None):
    for admin_user in _admin_users():
        _create_notification(admin_user, title, message, notification_type, action_url, created_by)

def _resolve_assessment_class_name(assessment=None, material=None, class_code=None):
    """Resolve a human-readable class name for assessment completion alerts."""
    if material and material.section:
        return material.section.class_name
    if assessment and assessment.section:
        return assessment.section.class_name
    if class_code:
        section = Section.objects.filter(class_code__iexact=str(class_code).strip(), is_active=True).first()
        if section:
            return section.class_name
    if material and hasattr(material, 'assigned_sections'):
        assigned = material.assigned_sections.filter(is_active=True).first()
        if assigned:
            return assigned.class_name
    return None

def _teachers_for_assessment_completion(assessment=None, material=None, student_user=None):
    """Collect teacher recipients for an assessment completion event."""
    teachers = []
    seen_ids = set()

    def add_teacher(user):
        if user and user.id not in seen_ids:
            seen_ids.add(user.id)
            teachers.append(user)

    if assessment and assessment.teacher:
        add_teacher(assessment.teacher)
    if material:
        if material.assessment and material.assessment.teacher:
            add_teacher(material.assessment.teacher)
        if material.section and material.section.teacher:
            add_teacher(material.section.teacher)
        if hasattr(material, 'assigned_sections'):
            for section in material.assigned_sections.filter(is_active=True).select_related('teacher'):
                if section.teacher:
                    add_teacher(section.teacher)

    if not teachers and student_user:
        for section in Section.objects.filter(is_active=True).select_related('teacher'):
            if not section.teacher or not section.has_student(student_user, active_only=True):
                continue
            if assessment and assessment.section_id == section.id:
                add_teacher(section.teacher)
            elif material and (
                material.section_id == section.id
                or material.assigned_sections.filter(id=section.id).exists()
            ):
                add_teacher(section.teacher)
            elif assessment and assessment.teacher_id == section.teacher_id:
                add_teacher(section.teacher)

    return teachers

def _assessment_completion_message(student_name, title_text, class_name=None):
    """Build the in-app notification body for a completed assessment."""
    safe_title = title_text or 'an assessment'
    if class_name:
        return f"{student_name} completed the assessment '{safe_title}' in {class_name}."
    return f"{student_name} completed the assessment '{safe_title}'."

def _assessment_completion_notif_exists(recipient, student_user, message, is_retake=False):
    """Prevent duplicate in-app notifications for the same completion event."""
    window_start = timezone.now() - timedelta(minutes=10)
    qs = Notification.objects.filter(
        recipient=recipient,
        created_by=student_user,
        notification_type='assessment',
        message=message,
        created_at__gte=window_start,
    )
    if is_retake:
        qs = qs.filter(title__icontains='Retook')
    else:
        qs = qs.exclude(title__icontains='Retook')
    return qs.exists()

def _student_completed_assessment_before(assessment, material, student_user):
    """Return True if the student already has a completed attempt recorded."""
    if assessment and assessment.has_student_completed(student_user):
        return True
    if material and material.assessment and material.assessment.has_student_completed(student_user):
        return True
    return False

def _section_active_students(section):
    student_ids = [
        entry.get('student_id')
        for entry in _section_students(section, active_only=True)
        if entry.get('student_id')
    ]
    return User.objects.filter(id__in=student_ids, role='student', is_archived=False)

# Authentication functions
def generate_custom_id(role):
    """Generate unique custom ID based on role"""
    if role == 'admin':
        prefix = 'ADM'
    elif role == 'teacher':
        prefix = 'TCH'
    else:  # student
        prefix = 'G2'
    
    # Get the count of existing users with this role
    count = User.objects.filter(role=role).count() + 1
    return f"{prefix}-{count:04d}"

def generate_otp(length=6):
    return ''.join(random.choice('0123456789') for _ in range(length))

CLASS_CODE_PATTERN = re.compile(r'^[A-Z]{4}-\d{3}$')


def normalize_class_code(code):
    return (code or '').strip().upper()


def is_valid_class_code_format(code):
    return bool(CLASS_CODE_PATTERN.match(normalize_class_code(code)))


def generate_unique_class_code():
    """
    Generates a unique 4-letter and 3-digit class code (e.g., ABCD-123).
    Automatically checks the database to ensure no duplicates exist.
    """
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "0123456789"
    
    while True:
        # Follow the existing format: 4 uppercase letters followed by 3 digits
        prefix = "".join(random.choices(letters, k=4))
        suffix = "".join(random.choices(digits, k=3))
        code = f"{prefix}-{suffix}"
        
        # Uniqueness Check: Ensure this code does not already exist in the database
        # This prevents duplicate classrooms even across different teachers
        if not Section.objects.filter(class_code=code).exists():
            return code
        # If exists, the loop continues to generate a fresh candidate


def resolve_class_code_for_creation(provided_code=None):
    """
    Return a unique class code for a new section.
    Uses the teacher-provided code when valid and available; otherwise generates one.
    """
    if provided_code:
        code = normalize_class_code(provided_code)
        if not is_valid_class_code_format(code):
            raise ValueError('Invalid class code format. Expected 4 letters, a dash, then 3 numbers (e.g., ABCD-123).')
        if Section.objects.filter(class_code__iexact=code).exists():
            raise ValueError('Class code already exists. Please generate a new code.')
        return code
    return generate_unique_class_code()


def generate_unique_course_code():
    """Generate a short unique course code like CRSE-XXXX"""
    prefix = "CRS"
    digits = "0123456789"
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    while True:
        part = "".join(random.choices(letters, k=3))
        suffix = "".join(random.choices(digits, k=3))
        code = f"{prefix}-{part}-{suffix}"
        if not Course.objects.filter(code=code).exists():
            return code

# ===== Pending Signup/Reset Session Management (Temporary Storage) =====
# Note: These store temporary data during signup/password reset flows.
# Session is appropriate for temporary, short-lived data (OTPs, form data).

def _get_pending_data(request, key):
    """Retrieve pending data from session"""
    return request.session.get(key)

def _set_pending_data(request, key, value):
    """Store pending data in session"""
    request.session[key] = value
    request.session.modified = True

def _clear_pending_data(request, *keys):
    """Clear one or more keys from session. Can clear multiple keys in one call."""
    for key in keys:
        request.session.pop(key, None)
    if keys:
        request.session.modified = True

def _get_pending_otp(request, data_key):
    """Get OTP for pending data (e.g. 'pending_teacher_signup' -> 'pending_teacher_signup_otp')"""
    otp_key = f"{data_key}_otp"
    return _get_pending_data(request, otp_key)

def _get_pending_otp_created_time(request, data_key):
    """Get OTP creation timestamp for pending data"""
    timestamp_key = f"{data_key}_otp_created"
    return _get_pending_data(request, timestamp_key)

def _store_pending_teacher_signup(request, data):
    """Store teacher signup form data and OTP in session"""
    otp = generate_otp()
    _set_pending_data(request, 'pending_teacher_signup', {
        'first_name': data.get('first_name'),
        'last_name': data.get('last_name'),
        'email': data.get('email'),
        'middle_initial': data.get('middle_initial', ''),
        'suffix': data.get('suffix', ''),
        'sex': data.get('sex'),
        'birth_month': int(data.get('birth_month', 0)),
        'birth_day': int(data.get('birth_day', 0)),
        'birth_year': int(data.get('birth_year', 0)),
        'password_hash': make_password(data.get('password')),
        'contact_no': data.get('contact_no', ''),
        'teacher_role': data.get('teacher_role', ''),
        'school': data.get('school', ''),
        'department': data.get('department', ''),
    })
    _set_pending_data(request, 'pending_teacher_signup_otp', otp)
    _set_pending_data(request, 'pending_teacher_signup_otp_created', time.time())
    return otp

def _store_pending_student_signup(request, data):
    """Store student signup form data and OTP in session"""
    otp = generate_otp()
    _set_pending_data(request, 'pending_student_signup', {
        'first_name': data.get('first_name'),
        'last_name': data.get('last_name'),
        'email': data.get('email'),
        'middle_initial': data.get('middle_initial', ''),
        'suffix': data.get('suffix', ''),
        'sex': data.get('sex'),
        'birth_month': int(data.get('birth_month', 0)),
        'birth_day': int(data.get('birth_day', 0)),
        'birth_year': int(data.get('birth_year', 0)),
        'password_hash': make_password(data.get('password')),
        'contact_no': data.get('contact_no', ''),
        'grade_level': data.get('grade_level', ''),
        'section': data.get('section', ''),
        'reading_level': data.get('reading_level', ''),
    })
    _set_pending_data(request, 'pending_student_signup_otp', otp)
    _set_pending_data(request, 'pending_student_signup_otp_created', time.time())
    return otp

def _clear_pending_teacher_signup(request):
    """Clear teacher signup data from session"""
    _clear_pending_data(request, 'pending_teacher_signup', 'pending_teacher_signup_otp', 'pending_teacher_signup_otp_created')

def _clear_pending_student_signup(request):
    """Clear student signup data from session"""
    _clear_pending_data(request, 'pending_student_signup', 'pending_student_signup_otp', 'pending_student_signup_otp_created')

def send_teacher_signup_otp_email(request, email, otp, first_name):
    auth_url = request.build_absolute_uri(reverse('auth'))
    subject = "PABASA Teacher Signup OTP"
    message = (
        f"Hello {first_name},\n\n"
        f"Use the following One-Time Password (OTP) to complete your PABASA teacher account registration:\n\n"
        f"{otp}\n\n"
        "This OTP is valid for 10 minutes.\n\n"
        "If you did not request this, please ignore this email.\n\n"
        f"You can log in after verification at: {auth_url}\n\n"
        "Thank you,\nPABASA Team"
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)

def send_teacher_confirmation_email(request, user, teacher_code):
    auth_url = request.build_absolute_uri(reverse('auth'))
    subject = "Your PABASA Teacher Account is Ready"
    message = (
        f"Hello {user.first_name},\n\n"
        "Your PABASA teacher account has been created successfully.\n\n"
        f"User ID: {user.custom_id}\n"
        f"Teacher Code: {teacher_code}\n"
        f"Email: {user.email}\n\n"
        f"You can now log in at: {auth_url}\n\n"
        "Thank you for joining PABASA.\n"
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)

def send_student_signup_otp_email(request, email, otp, first_name):
    auth_url = request.build_absolute_uri(reverse('auth'))
    subject = "PABASA Student Signup OTP"
    message = (
        f"Hello {first_name},\n\n"
        f"Use the following One-Time Password (OTP) to complete your PABASA student account registration:\n\n"
        f"{otp}\n\n"
        "This OTP is valid for 10 minutes.\n\n"
        "If you did not request this, please ignore this email.\n\n"
        f"You can log in after verification at: {auth_url}\n\n"
        "Thank you,\nPABASA Team"
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)

def send_student_confirmation_email(request, user):
    auth_url = request.build_absolute_uri(reverse('auth'))
    subject = "Your PABASA Student Account is Ready"
    message = (
        f"Hello {user.first_name},\n\n"
        "Your PABASA student account has been created successfully.\n\n"
        f"User ID: {user.custom_id}\n"
        f"Email: {user.email}\n\n"
        f"You can now log in at: {auth_url}\n\n"
        "Thank you for joining PABASA.\n"
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


def _store_pending_password_reset(request, email):
    """Store password reset email and OTP in session"""
    otp = generate_otp()
    _set_pending_data(request, 'pending_password_reset', {'email': email})
    _set_pending_data(request, 'pending_password_reset_otp', otp)
    _set_pending_data(request, 'pending_password_reset_otp_created', time.time())
    return otp

def _clear_pending_password_reset(request):
    """Clear password reset data from session"""
    _clear_pending_data(request, 'pending_password_reset', 'pending_password_reset_otp', 'pending_password_reset_otp_created', 'password_reset_verified', 'password_reset_email')


def send_password_reset_otp_email(request, email, otp, first_name):
    otp_url = request.build_absolute_uri(reverse('forgot_password_otp'))
    subject = "PABASA Password Reset OTP"
    message = (
        f"Hello {first_name},\n\n"
        "We received a request to reset your PABASA password. Use the code below to continue:\n\n"
        f"{otp}\n\n"
        "This OTP is valid for 10 minutes.\n\n"
        f"If you did not request this, please ignore this email.\n\n"
        f"Open the following link to verify the code: {otp_url}\n\n"
        "Thank you,\nPABASA Team"
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)


def send_password_reset_confirmation_email(request, user):
    auth_url = request.build_absolute_uri(reverse('auth'))
    subject = "Your PABASA Password Has Been Reset"
    message = (
        f"Hello {user.first_name},\n\n"
        "Your password has been successfully reset.\n\n"
        f"You can now log in at: {auth_url}\n\n"
        "If you did not make this change, please contact support immediately.\n\n"
        "Thank you,\nPABASA Team"
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


@csrf_protect
@require_http_methods(["POST"])
def request_password_reset(request):
    email = request.POST.get('email', '').strip()
    if not email:
        return render(request, 'pabasa_app/forgot_password.html', {
            'error': 'Email is required',
            'email': email
        })

    user = User.objects.filter(email__iexact=email).first()
    if not user:
        return render(request, 'pabasa_app/forgot_password.html', {
            'error': 'No account found with that email address.',
            'email': email
        })

    _store_pending_password_reset(request, user.email)
    send_password_reset_otp_email(request, user.email, request.session['pending_password_reset_otp'], user.first_name)
    return redirect(f"{reverse('forgot_password_otp')}?email={user.email}")


@csrf_protect
@require_http_methods(["POST"])
def verify_forgot_password_otp(request):
    email = request.POST.get('email', '').strip()
    otp = request.POST.get('otp', '').strip()

    if not email or not otp:
        return render(request, 'pabasa_app/forgot_password_otp.html', {
            'error': 'Email and OTP are required.',
            'email': email
        })

    pending = request.session.get('pending_password_reset')
    expected_otp = request.session.get('pending_password_reset_otp')
    otp_created = request.session.get('pending_password_reset_otp_created')

    if not pending or pending.get('email') != email or not expected_otp or not otp_created:
        _clear_pending_password_reset(request)
        return render(request, 'pabasa_app/forgot_password_otp.html', {
            'error': 'No pending password reset found. Please start again.',
            'email': email
        })

    if time.time() - otp_created > 10 * 60:
        _clear_pending_password_reset(request)
        return render(request, 'pabasa_app/forgot_password_otp.html', {
            'error': 'OTP expired. Please request a new code.',
            'email': email
        })

    if otp != expected_otp:
        return render(request, 'pabasa_app/forgot_password_otp.html', {
            'error': 'Invalid OTP. Please try again.',
            'email': email
        })

    request.session['password_reset_verified'] = True
    request.session['password_reset_email'] = email
    request.session.modified = True
    return redirect(f"{reverse('forgot_password_reset')}?email={email}")


@csrf_protect
@require_http_methods(["GET"])
def resend_password_reset_otp(request):
    pending = request.session.get('pending_password_reset')
    if not pending:
        return redirect('forgot_password')

    otp = generate_otp()
    request.session['pending_password_reset_otp'] = otp
    request.session['pending_password_reset_otp_created'] = time.time()
    request.session.modified = True

    user = User.objects.filter(email__iexact=pending.get('email')).first()
    if user:
        send_password_reset_otp_email(request, user.email, otp, user.first_name)

    return redirect(f"{reverse('forgot_password_otp')}?email={pending.get('email')}")


@csrf_protect
@require_http_methods(["GET"])
def forgot_password_reset(request):
    email = request.GET.get('email', '')
    if not email:
        email = request.session.get('password_reset_email', '')

    if not request.session.get('password_reset_verified') or not email:
        return redirect('forgot_password')

    return render(request, 'pabasa_app/forgot_password_reset.html', {
        'email': email
    })


@csrf_protect
@require_http_methods(["POST"])
def reset_password(request):
    email = request.POST.get('email', '').strip()
    password = request.POST.get('password', '')
    confirm_password = request.POST.get('confirm_password', '')

    if not email or not password or not confirm_password:
        return render(request, 'pabasa_app/forgot_password_reset.html', {
            'error': 'All fields are required.',
            'email': email
        })

    if password != confirm_password:
        return render(request, 'pabasa_app/forgot_password_reset.html', {
            'error': 'Passwords do not match.',
            'email': email
        })

    if not request.session.get('password_reset_verified') or request.session.get('password_reset_email') != email:
        return redirect('forgot_password')

    user = User.objects.filter(email__iexact=email).first()
    if not user:
        return render(request, 'pabasa_app/forgot_password_reset.html', {
            'error': 'No account found with that email address.',
            'email': email
        })

    user.password_hash = make_password(password)
    user.save()
    send_password_reset_confirmation_email(request, user)
    _clear_pending_password_reset(request)

    return render(request, 'pabasa_app/forgot_password_reset.html', {
        'email': email,
        'success': True
    })


@csrf_protect
@require_http_methods(["POST"])
def register_teacher(request):
    """Register a new teacher"""
    try:
        data = request.POST
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'email', 'password', 'confirm_password', 
                         'sex', 'birth_month', 'birth_day', 'birth_year']
        
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({'success': False, 'error': f'{field} is required'}, status=400)
        
        # Validate password match
        if data.get('password') != data.get('confirm_password'):
            return JsonResponse({'success': False, 'error': 'Passwords do not match'}, status=400)
        
        # Check if email already exists
        if User.objects.filter(email=data.get('email')).exists():
            return JsonResponse({'success': False, 'error': 'Email already registered'}, status=400)
        
        # Create pending signup and send OTP
        otp = _store_pending_teacher_signup(request, data)
        send_teacher_signup_otp_email(request, data.get('email'), otp, data.get('first_name'))

        return JsonResponse({
            'success': True,
            'message': 'OTP sent to your email. Enter it below to finish registration.',
            'email': data.get('email')
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_protect
@require_http_methods(["POST"])
def register_student(request):
    """Register a new student"""
    try:
        data = request.POST
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'email', 'password', 'confirm_password',
                         'sex', 'birth_month', 'birth_day', 'birth_year']
        
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({'success': False, 'error': f'{field} is required'}, status=400)
        
        # Validate password match
        if data.get('password') != data.get('confirm_password'):
            return JsonResponse({'success': False, 'error': 'Passwords do not match'}, status=400)
        
        # Check if email already exists
        if User.objects.filter(email=data.get('email')).exists():
            return JsonResponse({'success': False, 'error': 'Email already registered'}, status=400)
        
        # Store pending signup and send OTP email (student must verify OTP to complete)
        otp = _store_pending_student_signup(request, data)
        send_student_signup_otp_email(request, data.get('email'), otp, data.get('first_name'))

        return JsonResponse({
            'success': True,
            'message': 'OTP sent to your email. Enter it below to finish registration.',
            'email': data.get('email')
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_protect
@require_http_methods(["POST"])
def verify_teacher_otp(request):
    try:
        otp = request.POST.get('otp', '').strip()
        if not otp:
            return JsonResponse({'success': False, 'error': 'OTP is required'}, status=400)


        pending = request.session.get('pending_teacher_signup')
        expected_otp = request.session.get('pending_teacher_signup_otp')
        otp_created = request.session.get('pending_teacher_signup_otp_created')

        if not pending or not expected_otp or not otp_created:
            return JsonResponse({'success': False, 'error': 'No pending signup found. Please start registration again.'}, status=400)

        if time.time() - otp_created > 10 * 60:
            _clear_pending_teacher_signup(request)
            return JsonResponse({'success': False, 'error': 'OTP expired. Please request a new code.'}, status=400)

        if otp != expected_otp:
            return JsonResponse({'success': False, 'error': 'Invalid OTP. Please try again.'}, status=400)

        if User.objects.filter(email=pending['email']).exists():
            _clear_pending_teacher_signup(request)
            return JsonResponse({'success': False, 'error': 'Email already registered'}, status=400)

        custom_id = generate_custom_id('teacher')
        user = User.objects.create(
            custom_id=custom_id,
            role='teacher',
            first_name=pending['first_name'],
            last_name=pending['last_name'],
            email=pending['email'],
            middle_initial=pending.get('middle_initial', ''),
            suffix=pending.get('suffix', ''),
            sex=pending['sex'],
            birth_month=pending['birth_month'],
            birth_day=pending['birth_day'],
            birth_year=pending['birth_year'],
            password_hash=pending['password_hash'],
            contact_no=pending['contact_no'],
            teacher_role=pending.get('teacher_role', ''),
            school=pending.get('school', ''),
            department=pending.get('department', ''),
        )

        teacher_code = custom_id

        send_teacher_confirmation_email(request, user, custom_id)
        _notify_admins(
            'New teacher account',
            f'{user.first_name} {user.last_name} created a teacher account.',
            'success',
            reverse('admin_teacher_detail', args=[user.id]),
            user,
        )
        _clear_pending_teacher_signup(request)

        return JsonResponse({
            'success': True,
            'message': 'Teacher registered successfully',
            'custom_id': custom_id,
            'teacher_code': custom_id
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_protect
@require_http_methods(["POST"])
def resend_teacher_signup_otp(request):
    try:
        pending = request.session.get('pending_teacher_signup')
        if not pending:
            return JsonResponse({'success': False, 'error': 'No pending signup found. Please start registration again.'}, status=400)

        otp = generate_otp()
        request.session['pending_teacher_signup_otp'] = otp
        request.session['pending_teacher_signup_otp_created'] = time.time()
        request.session.modified = True

        send_teacher_signup_otp_email(request, pending['email'], otp, pending['first_name'])
        return JsonResponse({'success': True, 'message': 'A new OTP has been sent to your email.'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_protect
@require_http_methods(["POST"])
def verify_student_otp(request):
    try:
        otp = request.POST.get('otp', '').strip()
        if not otp:
            return JsonResponse({'success': False, 'error': 'OTP is required'}, status=400)

        pending = request.session.get('pending_student_signup')
        expected_otp = request.session.get('pending_student_signup_otp')
        otp_created = request.session.get('pending_student_signup_otp_created')

        if not pending or not expected_otp or not otp_created:
            return JsonResponse({'success': False, 'error': 'No pending signup found. Please start registration again.'}, status=400)

        if time.time() - otp_created > 10 * 60:
            _clear_pending_student_signup(request)
            return JsonResponse({'success': False, 'error': 'OTP expired. Please request a new code.'}, status=400)

        if otp != expected_otp:
            return JsonResponse({'success': False, 'error': 'Invalid OTP. Please try again.'}, status=400)

        if User.objects.filter(email=pending['email']).exists():
            _clear_pending_student_signup(request)
            return JsonResponse({'success': False, 'error': 'Email already registered'}, status=400)

        custom_id = generate_custom_id('student')
        user = User.objects.create(
            custom_id=custom_id,
            role='student',
            first_name=pending['first_name'],
            last_name=pending['last_name'],
            email=pending['email'],
            middle_initial=pending.get('middle_initial', ''),   
            suffix=pending.get('suffix', ''),                  
            sex=pending['sex'],
            birth_month=pending['birth_month'],
            birth_day=pending['birth_day'],
            birth_year=pending['birth_year'],
            password_hash=pending['password_hash'],
            contact_no=pending.get('contact_no', ''),
            grade_level=pending.get('grade_level', ''),
            section=pending.get('section', ''),
            reading_level=pending.get('reading_level', ''),
        )

        send_student_confirmation_email(request, user)
        _notify_admins(
            'New student account',
            f'{user.first_name} {user.last_name} created a student account.',
            'success',
            reverse('admin_student_detail', args=[user.id]),
            user,
        )
        _clear_pending_student_signup(request)

        return JsonResponse({
            'success': True,
            'message': 'Student registered successfully',
            'custom_id': custom_id
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_protect
@require_http_methods(["POST"])
def resend_student_signup_otp(request):
    try:
        pending = request.session.get('pending_student_signup')
        if not pending:
            return JsonResponse({'success': False, 'error': 'No pending signup found. Please start registration again.'}, status=400)

        otp = generate_otp()
        request.session['pending_student_signup_otp'] = otp
        request.session['pending_student_signup_otp_created'] = time.time()
        request.session.modified = True

        send_student_signup_otp_email(request, pending['email'], otp, pending['first_name'])
        return JsonResponse({'success': True, 'message': 'A new OTP has been sent to your email.'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_protect
@require_http_methods(["POST"])
def login_user(request):
    """Authenticate user and create session"""
    try:
        data = request.POST
        custom_id = data.get('custom_id', '').strip()
        password = data.get('password', '')
        
        if not custom_id or not password:
            return JsonResponse({'success': False, 'error': 'Custom ID and password are required'}, status=400)
        
        # Find user by custom_id
        try:
            user = User.objects.get(custom_id=custom_id)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid custom ID or password'}, status=401)
        
        # Verify password
        if not check_password(password, user.password_hash):
            return JsonResponse({'success': False, 'error': 'Invalid custom ID or password'}, status=401)

        if getattr(user, 'is_archived', False):
            return JsonResponse({'success': False, 'error': 'This account has been archived. Please contact an administrator.'}, status=403)

        # Verify account activity status
        if user.role == 'admin':
            # Admins are considered active by default.
            pass
        elif user.role == 'teacher':
            # Teachers are considered active by default unless explicitly deactivated
            pass
        elif user.role == 'student':
            # Students are considered active by default
            pass
            
        # Create session
        request.session['user_id'] = user.id
        request.session['custom_id'] = user.custom_id
        request.session['user_role'] = user.role
        request.session['first_name'] = user.first_name
        request.session['last_name'] = user.last_name
        request.session['email'] = user.email
        
        if user.role == 'admin':
            redirect_url = '/dashboard/admin/'
        elif user.role == 'principal':
            redirect_url = '/dashboard/principal/'
        elif user.role == 'teacher':
            redirect_url = '/dashboard/teacher/'
        else:
            redirect_url = '/dashboard/'
        
        return JsonResponse({
            'success': True,
            'message': 'Login successful',
            'role': user.role,
            'redirect_url': redirect_url,
            'custom_id': user.custom_id,
            'email': user.email,
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def logout_user(request):
    """Logout user and destroy session"""
    request.session.flush()
    return redirect('home')

def _check_auth(request):
    """Check if user is authenticated"""
    return 'user_id' in request.session


# REPLACE the entire _dashboard_context function:
def _dashboard_context(request, nav_role=None, extra=None):
    user = User.objects.filter(id=request.session.get('user_id')).first()
    first_name = user.first_name if user else request.session.get('first_name', '')
    last_name = user.last_name if user else request.session.get('last_name', '')
    _mi = user.middle_initial if user else ''
    _sx = user.suffix if user else ''
    _name_parts = [first_name, _mi, last_name, _sx]
    full_name = ' '.join(p for p in _name_parts if p).strip() or request.session.get('custom_id', 'User')
    teacher_role = ''
    initials = "".join(part[:1] for part in full_name.split()[:2]).upper() or "PA"
    profile_photo_url = None
    username = ''

    if user:
        if user.role == 'teacher':
            teacher_role = user.teacher_role or ''

        username = f"{user.first_name}_{user.last_name}".lower().replace(" ", "_")
        if PROFILE_PHOTOS_DIR.exists():
            for file in PROFILE_PHOTOS_DIR.glob(f'profile_photo_{username}.*'):
                profile_photo_url = f'/static/pabasa_app/uploads/profiles/{file.name}'
                break

    joined_classes = []
    user_role = user.role if user else request.session.get('user_role', 'student')
    effective_role = nav_role or user_role

    if user and user.role == 'student':
        student_user = user
        classes = Section.objects.filter(is_active=True).order_by('class_name')
        for cls in classes:
            if not _section_has_student(cls, student_user):
                continue
            joined_classes.append({
                'code': cls.class_code,
                'name': cls.class_name,
                'student_count': _section_student_count(cls),
            })
    # Catch anyone who is not a student (Teachers and Admins) so they can see 
    # the sections they have created/own in the sidebar and dashboard.
    elif user and (user.role in ['teacher', 'admin'] or effective_role in ['teacher', 'admin']):
        classes = Section.objects.filter(teacher=user, is_active=True).order_by('class_name')
        for cls in classes:
            joined_classes.append({
                'code': cls.class_code,
                'name': cls.class_name,
                'student_count': _section_student_count(cls),
                'subject': cls.subject,
            })

    context = {
        'nav_role': nav_role or request.session.get('user_role', 'student'),
        'user_id': request.session.get('custom_id'),
        'first_name': first_name,
        'last_name': last_name,
        'user_full_name': full_name,
        'email': request.session.get('email', ''),
        'teacher_role': teacher_role,
        'role_display': teacher_role or (nav_role or request.session.get('user_role', 'student')).title(),
        'profile_photo_url': profile_photo_url,
        'initials': initials,
        'joined_classes': joined_classes,
    }
    # Compute an account activity status label + class for UI chips
    account_status_label = 'Unknown'
    account_status_class = ''
    account_status_tooltip = ''
    try:
        if user:
            # Default: pending if teacher has no classes/materials/activity
            last_activity = None
            has_activity = False
            if user.role == 'teacher':
                tp_user = user
                # Check for classes, materials, and joined students stored in sections
                has_classes = Section.objects.filter(teacher=tp_user, is_active=True).exists()
                # Materials are now stored in the `materials` table. Detect
                # posted materials by checking the Section->Material relation.
                has_materials = Material.objects.filter(
                        Q(section__teacher=tp_user) | Q(assigned_sections__teacher=tp_user) | Q(assessment__teacher=tp_user),
                        is_active=True
                    ).distinct().exists()
                has_joined_students = any(
                    _section_student_count(cls) > 0
                    for cls in Section.objects.filter(teacher=tp_user, is_active=True)
                )
                has_attempts = Assessment.objects.filter(teacher=tp_user).exists()
                has_activity = has_classes or has_materials or has_joined_students or has_attempts

                # Get latest timestamps
                candidate_dates = []
                if getattr(tp_user, 'updated_at', None):
                    candidate_dates.append(tp_user.updated_at)
                cls_max = Section.objects.filter(teacher=tp_user).aggregate(m=Max('updated_at'))['m']
                if cls_max:
                    candidate_dates.append(cls_max)
                asm_max = Assessment.objects.filter(teacher=tp_user).aggregate(m=Max('updated_at'))['m']
                if asm_max:
                    candidate_dates.append(asm_max)
                # Include latest material timestamp for teacher (if any)
                mat_max = Material.objects.filter(
                    Q(section__teacher=tp_user) | Q(assigned_sections__teacher=tp_user) | Q(assessment__teacher=tp_user),
                ).aggregate(m=Max('updated_at'))['m']
                if mat_max:
                    candidate_dates.append(mat_max)
                if candidate_dates:
                    last_activity = max(candidate_dates)

            else:
                # For students, use student user updated or enrollment timestamps
                sp_user = user
                if sp_user:
                    has_activity = True
                    candidate_dates = [d for d in [getattr(sp_user, 'updated_at', None), getattr(sp_user, 'created_at', None)] if d]
                    joined_sections = [
                        cls for cls in Section.objects.filter(is_active=True)
                        if _section_has_student(cls, sp_user)
                    ]
                    candidate_dates.extend(
                        cls.updated_at for cls in joined_sections if getattr(cls, 'updated_at', None)
                    )
                    if candidate_dates:
                        last_activity = max(candidate_dates)

            if not has_activity and not last_activity:
                account_status_label = 'Pending'
                account_status_class = 'status-pending'
                account_status_tooltip = 'No activity recorded yet.'
            else:
                now = timezone.now()
                if last_activity:
                    delta = now - last_activity
                    days = delta.days
                    if user.role == 'teacher':
                        # keep existing teacher granularity
                        if days <= 7:
                            account_status_label = 'Active'
                            account_status_class = 'status-active'
                        elif 8 <= days <= 30:
                            account_status_label = 'Idle'
                            account_status_class = 'status-idle'
                        else:
                            account_status_label = 'Inactive'
                            account_status_class = 'status-inactive'
                    else:
                        # Student: Pending (no activity handled earlier), Active = 1-7 days, Inactive = 8+ days
                        if days <= 7:
                            account_status_label = 'Active'
                            account_status_class = 'status-active'
                        else:
                            account_status_label = 'Inactive'
                            account_status_class = 'status-inactive'
                    account_status_tooltip = f'Last activity: {last_activity.strftime("%Y-%m-%d %H:%M")}'
                else:
                    account_status_label = 'Pending'
                    account_status_class = 'status-pending'
                    account_status_tooltip = 'No activity recorded yet.'
    except Exception:
        account_status_label = 'Unknown'
        account_status_class = ''

    context.update({
        'account_status_label': account_status_label,
        'account_status_class': account_status_class,
        'account_status_tooltip': account_status_tooltip,
    })
    if extra:
        context.update(extra)
    return context

def home(request):
    return render(request, 'pabasa_app/home.html')

def auth(request):
    return render(request, 'pabasa_app/auth.html')

def forgot_password(request):
    return render(request, 'pabasa_app/forgot_password.html')

def forgot_password_otp(request):
    email = request.GET.get('email', '')
    return render(request, 'pabasa_app/forgot_password_otp.html', {'email': email})

def signup(request):
    return render(request, 'pabasa_app/signup.html')

def pabasa_info(request):
    return render(request, 'pabasa_app/pabasa_info.html')

def about(request):
    return render(request, 'pabasa_app/about.html')

def teacher_signup(request):
    return render(request, 'pabasa_app/teacher_signup.html')

def student_signup(request):
    return render(request, 'pabasa_app/student_signup.html')

def dashboard(request):
    if not _check_auth(request):
        return redirect('auth')
    if request.session.get('user_role') != 'student':
        return redirect('auth')
    
    return render(request, 'pabasa_app/dashboard.html', _dashboard_context(request, 'student'))

def dashboard_teacher(request):
    if not _check_auth(request):
        return redirect('auth')
    if request.session.get('user_role') != 'teacher':
        return redirect('auth')
    
    return render(request, 'pabasa_app/dashboard_teacher.html', _dashboard_context(request, 'teacher'))

def dashboard_admin(request):
    if not _check_auth(request):
        return redirect('auth')
    if request.session.get('user_role') != 'admin':
        return redirect('auth')

    context = _admin_context(request, 'Dashboard', [])
    dashboard_data = _get_dashboard_data()
    context.update(dashboard_data)
    
    return render(request, 'pabasa_app/admin_dashboard.html', context)

def _admin_context(request, page_title, table_headers):
    return {
        'admin_username': request.session.get('custom_id', ''),
        'first_name': request.session.get('first_name', ''),
        'last_name': request.session.get('last_name', ''),
        'page_title': page_title,
        'table_headers': table_headers,
    }

def _notification_settings_defaults(user):
    return {
        'push_enabled': True,
        'email_notifications': True,
        'new_materials': True,
        'reading_reminders': getattr(user, 'role', '') == 'student',
        'progress_updates': True,
    }

def _notification_settings_for_user(user):
    return {
        **_notification_settings_defaults(user),
        **_get_profile_dict(user, 'notification_settings'),
    }

def _posted_notification_settings(request):
    return {
        'push_enabled': request.POST.get('push_enabled') == 'on',
        'email_notifications': request.POST.get('email_notifications') == 'on',
        'new_materials': request.POST.get('new_materials') == 'on',
        'reading_reminders': request.POST.get('reading_reminders') == 'on',
        'progress_updates': request.POST.get('progress_updates') == 'on',
    }

def _get_dashboard_data():
    """
    Compute dashboard statistics and recent activities.
    Returns a dictionary with 'stats' and 'activities' keys.
    All queries use verified field names from models.
    Querysets are passed directly to template (no list conversion for efficiency).
    """
    dashboard_data = {
        'stats': {
            # User statistics (verified fields: role, is_archived)
            'active_students': User.objects.filter(role='student', is_archived=False).count(),
            'active_teachers': User.objects.filter(role='teacher', is_archived=False).count(),
            'archived_users': User.objects.filter(is_archived=True).count(),
            
            # Section statistics (verified fields: is_active)
            'active_classes': Section.objects.filter(is_active=True).count(),
            
            # Material statistics (verified fields: is_active, status, item_type)
            'active_materials': Material.objects.filter(is_active=True).count(),
            'published_materials': Material.objects.filter(status='published', is_active=True).count(),
            'draft_materials': Material.objects.filter(status='draft', is_active=True).count(),
            'word_count': Material.objects.filter(item_type='word', is_active=True).count(),
            'sentence_count': Material.objects.filter(item_type='sentence', is_active=True).count(),
            'paragraph_count': Material.objects.filter(item_type='paragraph', is_active=True).count(),
            
            # Assessment statistics (verified fields: is_active, status)
            'active_assessments': Assessment.objects.filter(is_active=True).count(),
            'published_assessments': Assessment.objects.filter(status='published', is_active=True).count(),
        },
        
        'activities': {
            # Last 5 students (fields: custom_id, first_name, last_name, created_at)
            'recent_students': User.objects.filter(role='student', is_archived=False)
                .order_by('-created_at')
                .values('custom_id', 'first_name', 'last_name', 'created_at')[:5],
            
            # Last 5 teachers (fields: custom_id, first_name, last_name, created_at)
            'recent_teachers': User.objects.filter(role='teacher', is_archived=False)
                .order_by('-created_at')
                .values('custom_id', 'first_name', 'last_name', 'created_at')[:5],
            
            # Last 5 classes (fields: class_code, class_name, created_at)
            'recent_classes': Section.objects.filter(is_active=True)
                .order_by('-created_at')
                .values('class_code', 'class_name', 'created_at')[:5],
            
            # Last 5 materials (fields: title, item_type, status, created_at)
            'recent_materials': Material.objects.filter(is_active=True)
                .order_by('-created_at')
                .values('title', 'item_type', 'status', 'created_at')[:5],
        }
    }
    
    return dashboard_data

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not _check_auth(request):
            return redirect('auth')
        if request.session.get('user_role') != 'admin':
            return redirect('auth')
        return view_func(request, *args, **kwargs)
    return wrapper

@admin_required
def admin_students(request):
    return render(request, 'pabasa_app/admin_students.html', _admin_users_context(request, 'student', 'Students'))

@admin_required
def admin_teachers(request):
    return render(request, 'pabasa_app/admin_teachers.html', _admin_users_context(request, 'teacher', 'Teachers'))

def _admin_user_status(user):
    return 'Archived' if getattr(user, 'is_archived', False) else 'Active'

def _admin_user_full_name(user):
    return ' '.join(part for part in [
        user.first_name,
        user.middle_initial,
        user.last_name,
        user.suffix,
    ] if part).strip()

def _admin_users_context(request, role, page_title):
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all').strip().lower()

    users = User.objects.filter(role=role)
    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(custom_id__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    if status_filter == 'active':
        users = users.filter(is_archived=False)
    elif status_filter == 'archived':
        users = users.filter(is_archived=True)

    context = _admin_context(request, page_title, [
        'Name',
        'ID',
        'Username',
        'Email',
        'Status',
        'Actions',
    ])
    context.update({
        'managed_role': role,
        'users': users.order_by('last_name', 'first_name'),
        'search_query': search_query,
        'status_filter': status_filter,
        'status_options': [
            ('all', 'All Statuses'),
            ('active', 'Active'),
            ('archived', 'Archived'),
        ],
    })
    return context

def _admin_user_redirect_name(role):
    return 'admin_students' if role == 'student' else 'admin_teachers'

def _admin_user_template_context(request, user, page_title):
    context = _admin_context(request, page_title, [])
    context.update({
        'managed_user': user,
        'managed_user_name': _admin_user_full_name(user),
        'managed_user_status': _admin_user_status(user),
        'managed_role': user.role,
        'back_url_name': _admin_user_redirect_name(user.role),
    })
    return context

def _get_managed_user(user_id, role):
    return User.objects.filter(id=user_id, role=role).first()

@admin_required
def admin_student_detail(request, user_id):
    user = _get_managed_user(user_id, 'student')
    if not user:
        return redirect('admin_students')
    return render(request, 'pabasa_app/admin_user_detail.html', _admin_user_template_context(request, user, 'Student Details'))

@admin_required
def admin_teacher_detail(request, user_id):
    user = _get_managed_user(user_id, 'teacher')
    if not user:
        return redirect('admin_teachers')
    return render(request, 'pabasa_app/admin_user_detail.html', _admin_user_template_context(request, user, 'Teacher Details'))

@admin_required
@require_http_methods(["GET", "POST"])
def admin_student_edit(request, user_id):
    return _admin_edit_user(request, user_id, 'student')

@admin_required
@require_http_methods(["GET", "POST"])
def admin_teacher_edit(request, user_id):
    return _admin_edit_user(request, user_id, 'teacher')

def _admin_edit_user(request, user_id, role):
    user = _get_managed_user(user_id, role)
    if not user:
        return redirect(_admin_user_redirect_name(role))

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        username = request.POST.get('custom_id', '').strip()
        if not username:
            context = _admin_user_template_context(request, user, f'Edit {role.title()}')
            context['error_message'] = 'Username is required.'
            return render(request, 'pabasa_app/admin_user_edit.html', context, status=400)
        if User.objects.filter(custom_id__iexact=username).exclude(id=user.id).exists():
            context = _admin_user_template_context(request, user, f'Edit {role.title()}')
            context['error_message'] = 'Username is already used by another account.'
            return render(request, 'pabasa_app/admin_user_edit.html', context, status=400)
        if email and User.objects.filter(email__iexact=email).exclude(id=user.id).exists():
            context = _admin_user_template_context(request, user, f'Edit {role.title()}')
            context['error_message'] = 'Email is already used by another account.'
            return render(request, 'pabasa_app/admin_user_edit.html', context, status=400)

        user.custom_id = username
        user.first_name = request.POST.get('first_name', '').strip()
        user.middle_initial = request.POST.get('middle_initial', '').strip()[:1]
        user.last_name = request.POST.get('last_name', '').strip()
        user.suffix = request.POST.get('suffix', '').strip()
        user.email = email

        user.save()
        return redirect('admin_student_detail' if role == 'student' else 'admin_teacher_detail', user_id=user.id)

    return render(request, 'pabasa_app/admin_user_edit.html', _admin_user_template_context(request, user, f'Edit {role.title()}'))

@admin_required
@require_http_methods(["POST"])
def admin_student_archive(request, user_id):
    return _admin_archive_user(request, user_id, 'student')

@admin_required
@require_http_methods(["POST"])
def admin_teacher_archive(request, user_id):
    return _admin_archive_user(request, user_id, 'teacher')

def _admin_archive_user(request, user_id, role):
    user = _get_managed_user(user_id, role)
    if not user:
        return redirect(_admin_user_redirect_name(role))

    if user.id == request.session.get('user_id'):
        return redirect(_admin_user_redirect_name(role))

    if not user.is_archived:
        user.is_archived = True
        user.archived_at = timezone.now()
        user.save(update_fields=['is_archived', 'archived_at', 'updated_at'])

    return redirect(_admin_user_redirect_name(role))

@admin_required
def admin_classes(request):
    """List all classes with search and filter options."""
    return render(request, 'pabasa_app/admin_classes.html', _admin_sections_context(request, 'Classes'))

def _get_managed_section(section_id):
    """Retrieve a section by ID. Returns None if not found."""
    try:
        return Section.objects.get(id=section_id)
    except Section.DoesNotExist:
        return None

def _admin_sections_context(request, page_title):
    """
    Build context for admin class list view with search and filter.
    Supports search by class_code, class_name, subject, and teacher name.
    Supports filter by status (active, archived, all).
    """
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all').strip().lower()

    sections = Section.objects.all()
    
    if search_query:
        sections = sections.filter(
            Q(class_code__icontains=search_query) |
            Q(class_name__icontains=search_query) |
            Q(subject__icontains=search_query) |
            Q(teacher__first_name__icontains=search_query) |
            Q(teacher__last_name__icontains=search_query)
        )
    
    if status_filter == 'active':
        sections = sections.filter(is_active=True)
    elif status_filter == 'archived':
        sections = sections.filter(is_active=False)

    context = _admin_context(request, page_title, [
        'Class Name',
        'Subject',
        'Teacher',
        'Student Count',
        'Status',
        'Actions',
    ])
    context.update({
        'sections': sections.order_by('class_name'),
        'search_query': search_query,
        'status_filter': status_filter,
    })
    return context

def _admin_section_template_context(request, section, page_title):
    """Build context for section detail and edit templates."""
    student_count = section.get_student_count()
    enrolled_students = section.get_enrolled_students(active_only=True)
    
    context = _admin_context(request, page_title, [])
    context.update({
        'section': section,
        'teacher': section.teacher,
        'student_count': student_count,
        'enrolled_students': enrolled_students,
        'status': 'Active' if section.is_active else 'Archived',
    })
    return context

@admin_required
def admin_class_detail(request, section_id):
    """View class details including enrolled students."""
    section = _get_managed_section(section_id)
    if not section:
        return redirect('admin_classes')
    return render(request, 'pabasa_app/admin_class_detail.html', 
                  _admin_section_template_context(request, section, 'Class Details'))

@admin_required
@require_http_methods(["GET", "POST"])
def admin_class_edit(request, section_id):
    """Edit class information."""
    return _admin_edit_section(request, section_id)

def _admin_edit_section(request, section_id):
    """Handle GET/POST for section edit view."""
    section = _get_managed_section(section_id)
    if not section:
        return redirect('admin_classes')

    if request.method == 'POST':
        class_name = request.POST.get('class_name', '').strip()
        subject = request.POST.get('subject', '').strip()
        # Per-class `section` field removed from Section model — ignore any posted value
        header = request.POST.get('header', '').strip()
        description = request.POST.get('description', '').strip()

        # Validation
        if not class_name:
            context = _admin_section_template_context(request, section, 'Edit Class')
            context['error_message'] = 'Class name is required.'
            return render(request, 'pabasa_app/admin_class_edit.html', context, status=400)
        
        if not subject:
            context = _admin_section_template_context(request, section, 'Edit Class')
            context['error_message'] = 'Subject is required.'
            return render(request, 'pabasa_app/admin_class_edit.html', context, status=400)

        # Update section
        section.class_name = class_name
        section.subject = subject
        section.header = header
        section.description = description
        section.save()
        
        return redirect('admin_class_detail', section_id=section.id)

    return render(request, 'pabasa_app/admin_class_edit.html', 
                  _admin_section_template_context(request, section, 'Edit Class'))

@admin_required
@require_http_methods(["POST"])
def admin_class_deactivate(request, section_id):
    """Deactivate a class (soft delete with status flag)."""
    return _admin_deactivate_section(request, section_id)

def _admin_deactivate_section(request, section_id):
    """Handle POST for section deactivate action."""
    section = _get_managed_section(section_id)
    if not section:
        return redirect('admin_classes')

    action = request.POST.get('action', 'deactivate').strip().lower()
    
    if action == 'deactivate' and section.is_active:
        section.is_active = False
        section.deactivate_all_students()
        section.save()
    elif action == 'reactivate' and not section.is_active:
        section.is_active = True
        section.save()

    return redirect('admin_classes')

@admin_required
def admin_courses(request):
    return render(request, 'pabasa_app/admin_courses.html', _admin_materials_context(request, 'Courses'))

def _admin_course_queryset():
    return Material.objects.select_related(
        'section',
        'section__teacher',
        'assessment',
        'assessment__teacher',
    ).filter(
        Q(section__isnull=False) |
        Q(assessment__isnull=False) |
        Q(assigned_sections__isnull=False)
    ).distinct()

def _get_managed_material(material_id):
    """Retrieve a material by ID. Returns None if not found."""
    return _admin_course_queryset().filter(id=material_id).first()

def _admin_material_status(material):
    return 'Archived' if not getattr(material, 'is_active', False) else material.get_status_display()

def _admin_materials_context(request, page_title):
    """
    Build context for admin course/material list view.
    Supports search by title, status filtering, and material type filtering.
    """
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all').strip().lower()
    type_filter = request.GET.get('type', 'all').strip().lower()

    materials = _admin_course_queryset()

    if search_query:
        materials = materials.filter(title__icontains=search_query)

    valid_statuses = {choice[0] for choice in Material.STATUS_CHOICES}
    if status_filter in valid_statuses:
        materials = materials.filter(status=status_filter, is_active=True)
    elif status_filter == 'archived':
        materials = materials.filter(is_active=False)
    elif status_filter == 'active':
        materials = materials.filter(is_active=True)

    valid_types = {choice[0] for choice in Material.ITEM_TYPE_CHOICES}
    if type_filter in valid_types:
        materials = materials.filter(item_type=type_filter)

    context = _admin_context(request, page_title, [
        'Title',
        'Created By',
        'Created At',
        'Updated At',
        'Status',
        'Actions',
    ])
    context.update({
        'materials': materials.order_by('-created_at', 'title'),
        'search_query': search_query,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'status_options': [('all', 'All Statuses'), ('active', 'Active')] + list(Material.STATUS_CHOICES) + [('archived', 'Archived')],
        'type_options': [('all', 'All Types')] + list(Material.ITEM_TYPE_CHOICES),
    })
    return context

def _admin_material_template_context(request, material, page_title):
    context = _admin_context(request, page_title, [])
    context.update({
        'material': material,
        'material_status': _admin_material_status(material),
        'section': material.section,
        'assessment': material.assessment,
        'sections': Section.objects.filter(is_active=True).order_by('class_name', 'class_code'),
        'status_options': Material.STATUS_CHOICES,
        'type_options': Material.ITEM_TYPE_CHOICES,
    })
    return context

@admin_required
def admin_course_detail(request, material_id):
    material = _get_managed_material(material_id)
    if not material:
        return redirect('admin_courses')
    return render(request, 'pabasa_app/admin_course_detail.html',
                  _admin_material_template_context(request, material, 'Course Details'))

@admin_required
@require_http_methods(["GET", "POST"])
def admin_course_edit(request, material_id):
    material = _get_managed_material(material_id)
    if not material:
        return redirect('admin_courses')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        item_type = request.POST.get('item_type', '').strip()
        status = request.POST.get('status', '').strip()
        section_id = request.POST.get('section_id', '').strip()
        prompt_text = request.POST.get('prompt_text', '').strip()
        content_text = request.POST.get('content_text', '').strip()
        difficulty_level = request.POST.get('difficulty_level', '').strip()
        scheduled_at_value = request.POST.get('scheduled_at', '').strip()

        valid_types = {choice[0] for choice in Material.ITEM_TYPE_CHOICES}
        valid_statuses = {choice[0] for choice in Material.STATUS_CHOICES}
        error_message = ''

        if not title:
            error_message = 'Title is required.'
        elif item_type not in valid_types:
            error_message = 'Material type is required.'
        elif status not in valid_statuses:
            error_message = 'Status is required.'

        section = None
        if not error_message and section_id:
            section = Section.objects.filter(id=section_id).first()
            if not section:
                error_message = 'Selected section was not found.'

        scheduled_at = None
        if not error_message and status == 'scheduled':
            if not scheduled_at_value:
                error_message = 'Scheduled date and time is required.'
            else:
                scheduled_at = parse_datetime(scheduled_at_value)
                if not scheduled_at:
                    scheduled_at = parse_datetime(f'{scheduled_at_value}:00')
                if scheduled_at and not timezone.is_aware(scheduled_at):
                    scheduled_at = timezone.make_aware(scheduled_at)
                if not scheduled_at:
                    error_message = 'Scheduled date and time is invalid.'

        if error_message:
            context = _admin_material_template_context(request, material, 'Edit Course')
            context['error_message'] = error_message
            return render(request, 'pabasa_app/admin_course_edit.html', context, status=400)

        material.title = title
        material.item_type = item_type
        material.status = status
        material.section = section
        material.prompt_text = prompt_text
        material.content_text = content_text
        material.difficulty_level = difficulty_level
        material.scheduled_at = scheduled_at if status == 'scheduled' else None
        material.is_active = (status in ['published', 'scheduled'])
        material.save()

        material.assigned_sections.clear()
        if section:
            material.assigned_sections.add(section)
            for student_user in _section_active_students(section):
                _create_notification(
                    student_user,
                    'Assigned content updated',
                    f'"{material.title}" was updated for {section.class_name}.',
                    'info',
                    reverse('assessment'),
                    request.user if hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False) else _current_user(request),
                )

        return redirect('admin_course_detail', material_id=material.id)

    return render(request, 'pabasa_app/admin_course_edit.html',
                  _admin_material_template_context(request, material, 'Edit Course'))

@admin_required
@require_http_methods(["POST"])
def admin_course_archive(request, material_id):
    material = _get_managed_material(material_id)
    if not material:
        return redirect('admin_courses')

    action = request.POST.get('action', 'archive').strip().lower()
    if action == 'archive' and material.is_active:
        material.is_active = False
        material.save(update_fields=['is_active', 'updated_at'])
        if material.section:
            for student_user in _section_active_students(material.section):
                _create_notification(
                    student_user,
                    'Assigned content removed',
                    f'"{material.title}" is no longer available in {material.section.class_name}.',
                    'warning',
                    reverse('assessment'),
                    _current_user(request),
                )
    elif action == 'restore' and not material.is_active:
        material.is_active = True
        material.save(update_fields=['is_active', 'updated_at'])

    return redirect('admin_courses')

@admin_required
def admin_practice_assessment(request):
    return render(request, 'pabasa_app/admin_practice_assessment.html', _admin_practice_context(request, 'Practice'))

def _practice_difficulty_values():
    return [value for value, _label in AdminPracticeMaterialForm.DIFFICULTY_CHOICES]

def _admin_practice_queryset():
    # Practices are standalone and managed via the Practice model
    return Practice.objects.filter(
        section__isnull=True,
        difficulty_type__in=_practice_difficulty_values(),
    )

def _get_admin_practice_material(practice_id):
    return _admin_practice_queryset().filter(id=practice_id).first()

def _admin_practice_status(material):
    return 'Archived' if not material.is_active else material.get_status_display()

def _practice_material_items(material):
    if not material:
        return []
    return parse_practice_items(material.content_text, material.item_type)

def _admin_practice_context(request, page_title):
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all').strip().lower()
    difficulty_filter = request.GET.get('difficulty', 'all').strip().lower()
    type_filter = request.GET.get('type', 'all').strip().lower()

    practice_items = _admin_practice_queryset()

    if search_query:
        practice_items = practice_items.filter(title__icontains=search_query)

    if status_filter == 'active':
        practice_items = practice_items.filter(is_active=True)
    elif status_filter == 'archived':
        practice_items = practice_items.filter(is_active=False)
    elif status_filter in {value for value, _label in AdminPracticeMaterialForm.STATUS_CHOICES}:
        practice_items = practice_items.filter(status=status_filter, is_active=True)

    if difficulty_filter in _practice_difficulty_values():
        practice_items = practice_items.filter(difficulty_type=difficulty_filter)

    valid_types = {choice[0] for choice in Material.ITEM_TYPE_CHOICES}
    if type_filter in valid_types:
        practice_items = practice_items.filter(practice_type=type_filter)

    context = _admin_context(request, page_title, [
        'Title',
        'Difficulty',
        'Practice Type',
        'Status',
        'Created At',
        'Actions',
    ])
    context.update({
        'practice_items': practice_items.order_by('difficulty_type', '-created_at'),
        'search_query': search_query,
        'status_filter': status_filter,
        'difficulty_filter': difficulty_filter,
        'type_filter': type_filter,
        'status_options': [('all', 'All Statuses'), ('active', 'Active')] + AdminPracticeMaterialForm.STATUS_CHOICES + [('archived', 'Archived')],
        'difficulty_options': [('all', 'All Difficulties')] + AdminPracticeMaterialForm.DIFFICULTY_CHOICES,
        'type_options': [('all', 'All Types')] + list(Material.ITEM_TYPE_CHOICES),
    })
    return context

def _admin_practice_template_context(request, material=None, page_title='Practice'):
    initial = {}
    if material:
        initial = {
            'title': material.title,
            'difficulty_level': material.difficulty_level,
            'item_type': material.item_type,
            'status': material.status if getattr(material, 'status', None) in dict(AdminPracticeMaterialForm.STATUS_CHOICES) else 'draft',
            'prompt_text': getattr(material, 'prompt_text', ''),
            'content_text': material.content_text,
        }

    form = AdminPracticeMaterialForm(initial=initial)
    context = _admin_context(request, page_title, [])
    context.update({
        'form': form,
        'practice': material,
        'practice_status': _admin_practice_status(material) if material else '',
        'practice_item_count': len(_practice_material_items(material)),
    })
    return context

def _save_admin_practice_material(form, material=None, request=None):
    cleaned = form.cleaned_data
    # Save as a Practice record (admin practice library). We accept an existing
    # Practice instance in `material` or create a new one.
    practice = None
    if material and isinstance(material, Practice):
        practice = material
    else:
        practice = Practice()

    practice.title = cleaned['title']
    practice.practice_type = cleaned['item_type']
    practice.prompt_text = cleaned.get('prompt_text', '')
    # Keep canonical storage in `contents` and provide content_text alias on model
    practice.contents = cleaned['content_text']
    practice.status = cleaned['status']
    # store difficulty into existing DB column difficulty_type
    practice.difficulty_type = cleaned['difficulty_level']
    practice.section = None
    practice.is_active = (practice.status in ['published', 'scheduled'])

    # Ensure a unique code
    if not getattr(practice, 'code', None):
        import uuid
        code = 'PR' + uuid.uuid4().hex[:8].upper()
        while Practice.objects.filter(code=code).exists():
            code = 'PR' + uuid.uuid4().hex[:8].upper()
        practice.code = code

    # Attach current admin user as owner if available
    admin_user = _current_user(request) if request is not None else None
    if not getattr(practice, 'teacher', None) and admin_user:
        practice.teacher = admin_user

    practice.save()
    return practice

@admin_required
@require_http_methods(["GET", "POST"])
def admin_practice_create(request):
    if request.method == 'POST':
        form = AdminPracticeMaterialForm(request.POST)
        if form.is_valid():
            practice = _save_admin_practice_material(form, None, request)
            return redirect('admin_practice_detail', practice_id=practice.id)
        context = _admin_context(request, 'Add Practice Content', [])
        context.update({'form': form, 'practice': None})
        return render(request, 'pabasa_app/admin_practice_create.html', context, status=400)

    return render(request, 'pabasa_app/admin_practice_create.html',
                  _admin_practice_template_context(request, None, 'Add Practice Content'))

@admin_required
def admin_practice_detail(request, practice_id):
    material = _get_admin_practice_material(practice_id)
    if not material:
        return redirect('admin_practice_assessment')
    return render(request, 'pabasa_app/admin_practice_detail.html',
                  _admin_practice_template_context(request, material, 'Practice Details'))

@admin_required
@require_http_methods(["GET", "POST"])
def admin_practice_edit(request, practice_id):
    material = _get_admin_practice_material(practice_id)
    if not material:
        return redirect('admin_practice_assessment')

    if request.method == 'POST':
        form = AdminPracticeMaterialForm(request.POST)
        if form.is_valid():
            practice = _save_admin_practice_material(form, material, request)
            return redirect('admin_practice_detail', practice_id=practice.id)
        context = _admin_context(request, 'Edit Practice Content', [])
        context.update({'form': form, 'practice': material, 'practice_status': _admin_practice_status(material)})
        return render(request, 'pabasa_app/admin_practice_edit.html', context, status=400)

    return render(request, 'pabasa_app/admin_practice_edit.html',
                  _admin_practice_template_context(request, material, 'Edit Practice Content'))

@admin_required
@require_http_methods(["POST"])
def admin_practice_archive(request, practice_id):
    material = _get_admin_practice_material(practice_id)
    if not material:
        return redirect('admin_practice_assessment')

    action = request.POST.get('action', 'archive').strip().lower()
    if action == 'archive' and material.is_active:
        material.is_active = False
        material.save(update_fields=['is_active', 'updated_at'])
    elif action == 'restore' and not material.is_active:
        material.is_active = True
        material.save(update_fields=['is_active', 'updated_at'])

    return redirect('admin_practice_assessment')

@admin_required
@csrf_protect
@require_http_methods(["GET", "POST"])
def admin_settings(request):
    user = User.objects.filter(id=request.session.get('user_id')).first()
    if not user:
        request.session.flush()
        return redirect('auth')

    notification_settings = _notification_settings_for_user(user)
    context = _admin_context(request, 'Settings', [])

    if request.method == 'POST':
        action = request.POST.get('settings_action', '').strip()

        if action == 'change_password':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not current_password or not new_password or not confirm_password:
                context['settings_error'] = 'All password fields are required.'
            elif not check_password(current_password, user.password_hash):
                context['settings_error'] = 'Current password is incorrect.'
            elif new_password != confirm_password:
                context['settings_error'] = 'New passwords do not match.'
            elif len(new_password) < 8:
                context['settings_error'] = 'Password must be at least 8 characters.'
            else:
                user.password_hash = make_password(new_password)
                user.save(update_fields=['password_hash', 'updated_at'])
                context['settings_success'] = 'Password changed successfully.'

        elif action == 'save_notifications':
            notification_settings = _posted_notification_settings(request)
            _set_profile_dict(user, 'notification_settings', notification_settings)
            context['settings_success'] = 'Push notification preferences saved.'

        else:
            context['settings_error'] = 'Unknown settings action.'

    context['notification_settings'] = notification_settings
    return render(request, 'pabasa_app/admin_settings.html', context)

def courses(request):
    if not _check_auth(request):
        return redirect('auth')
    
    role = str(request.session.get('user_role', 'student')).lower()
    
    if role in ['teacher', 'admin']:
        return course_teacher_view(request)
    elif role == 'student':
        return course_student_view(request)
    
    return redirect('dashboard')

def assessment(request):
    if not _check_auth(request):
        return redirect('auth')
    return render(request, 'pabasa_app/assessment.html', _dashboard_context(request, 'student'))

def reading_word_page(request):
    return render(request, 'pabasa_app/reading_word_page.html', _dashboard_context(request))

def reading_sentence_page(request):
    return render(request, 'pabasa_app/reading_sentence_page.html', _dashboard_context(request))

def reading_para_page(request):
    return render(request, 'pabasa_app/reading_para_page.html', _dashboard_context(request))

def _student_practice_queryset():
    return Practice.objects.filter(
        section__isnull=True,
        difficulty_type__in=_practice_difficulty_values(),
        status='published',
        is_active=True,
    ).order_by('difficulty_type', 'practice_type', 'title')

def _serialize_student_practice_material(material):
    return {
        'id': f"practice-{material.id}",
        'title': material.title,
        'difficulty': material.difficulty_level,
        'type': material.item_type,
        'status': material.status,
        'prompt': material.prompt_text,
        'content': material.content_text,
        'items': _practice_material_items(material),
        'created_at': material.created_at.isoformat() if material.created_at else '',
    }

def _student_practice_context(request, mode=None):
    context = _dashboard_context(request, 'student')
    materials = [_serialize_student_practice_material(material) for material in _student_practice_queryset()]
    context.update({
        'practice_materials': materials,
        'practice_difficulties': AdminPracticeMaterialForm.DIFFICULTY_CHOICES,
        'selected_practice_mode': mode or '',
        'selected_practice_difficulty': request.GET.get('difficulty', '').strip().lower(),
    })
    return context

def practice_word_page(request):
    return render(request, 'pabasa_app/practice_word_page.html', _student_practice_context(request, 'word'))

def practice_sentence_page(request):
    return render(request, 'pabasa_app/practice_sentence_page.html', _student_practice_context(request, 'sentence'))

def practice_para_page(request):
    return render(request, 'pabasa_app/practice_para_page.html', _student_practice_context(request, 'paragraph'))

# REPLACE the entire course_teacher_view function:
def course_teacher_view(request):
    if not _check_auth(request):
        return redirect('auth')
    if request.session.get('user_role') not in ['teacher', 'admin']:
        return redirect('auth')
    return render(request, 'pabasa_app/courses.html', _dashboard_context(request, 'teacher'))

def course_student_view(request):
    return render(request, 'pabasa_app/course_student_view.html', _dashboard_context(request))

def students(request):
    return render(request, 'pabasa_app/students.html', _dashboard_context(request, 'teacher'))

def student_detail(request):
    return render(request, 'pabasa_app/student_detail.html')

def calendar(request):
    return render(request, 'pabasa_app/calendar.html', _dashboard_context(request))

@csrf_protect
@require_http_methods(["GET", "POST"])
def settings_view(request):
    if not _check_auth(request):
        return redirect('auth')

    user = User.objects.filter(id=request.session.get('user_id')).first()
    if not user:
        request.session.flush()
        return redirect('auth')

    nav_role = user.role
    notification_settings = _notification_settings_for_user(user)
    context = _dashboard_context(request, nav_role)

    if request.method == 'POST':
        action = request.POST.get('settings_action', '').strip()

        if action == 'change_password':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not current_password or not new_password or not confirm_password:
                context['settings_error'] = 'All password fields are required.'
            elif not check_password(current_password, user.password_hash):
                context['settings_error'] = 'Current password is incorrect.'
            elif new_password != confirm_password:
                context['settings_error'] = 'New passwords do not match.'
            elif len(new_password) < 8:
                context['settings_error'] = 'Password must be at least 8 characters.'
            else:
                user.password_hash = make_password(new_password)
                user.save(update_fields=['password_hash', 'updated_at'])
                context['settings_success'] = 'Password changed successfully.'

        elif action == 'save_notifications':
            notification_settings = _posted_notification_settings(request)
            _set_profile_dict(user, 'notification_settings', notification_settings)
            context['settings_success'] = 'Push notification preferences saved.'

        else:
            context['settings_error'] = 'Unknown settings action.'

    context['notification_settings'] = notification_settings
    return render(request, 'pabasa_app/settings.html', context)

def practice(request):
    return render(request, 'pabasa_app/practice.html', _student_practice_context(request))

@csrf_protect
@require_http_methods(["GET", "POST"])
def profile(request):
    nav_role = request.GET.get('role', 'student')
    if not _check_auth(request):
        return redirect('auth')

    user = User.objects.filter(id=request.session.get('user_id')).first()
    if not user:
        request.session.flush()
        return redirect('auth')

    nav_role = user.role
    name_parts = [
        user.first_name,
        user.middle_initial if user.middle_initial else '',
        user.last_name,
        user.suffix if user.suffix else '',
    ]
    full_name = ' '.join(part for part in name_parts if part).strip()
    username = f"{user.first_name}_{user.last_name}".lower().replace(" ", "_")
    pabasa_id = user.custom_id
    role_display = "Teacher"

    if user.role == "teacher":
        teacher_role = user.teacher_role or ''
        role_display = f"Teacher - {teacher_role}" if teacher_role else "Teacher"
    else:
        grade_level = user.grade_level or ''
        role_display = f"Student - {grade_level}" if grade_level else "Student"

    initials = "".join(part[:1] for part in full_name.split()[:2]).upper() or "PA"
    
    # Check if user has a profile photo
    profile_photo_url = None
    photos_dir = PROFILE_PHOTOS_DIR
    if photos_dir.exists():
        for file in photos_dir.glob(f'profile_photo_{username}.*'):
            profile_photo_url = f'/static/pabasa_app/uploads/profiles/{file.name}'
            break
    
    # Get user bio from tags (profile information)
    bio = ''
    if user.role == 'teacher':
        profile_info = _get_profile_dict(user, 'profile_info')
        bio = profile_info.get('bio', 'Creates reading materials, manages class codes, and monitors student reading levels.')
    
    if request.method == 'POST':
        # Check for profile save first (most common action)
        if request.POST.get('save_account_details') == 'true':
            try:
                # Update basic user information
                first_name = request.POST.get('first_name', '').strip()
                last_name = request.POST.get('last_name', '').strip()
                middle_initial = request.POST.get('middle_initial', '').strip()
                suffix = request.POST.get('suffix', '').strip()
                email = request.POST.get('email', '').strip()
                bio = request.POST.get('bio', '').strip()
                
                # Validate required fields
                if not first_name or not last_name:
                    return JsonResponse({'success': False, 'error': 'First name and last name are required'})
                
                if not email:
                    return JsonResponse({'success': False, 'error': 'Email is required'})
                
                # Check if email is already used by another user
                if email != user.email and User.objects.filter(email=email).exists():
                    return JsonResponse({'success': False, 'error': 'This email is already in use'})
                
                # Update user fields
                user.first_name = first_name
                user.last_name = last_name
                user.middle_initial = middle_initial if middle_initial else ''
                user.suffix = suffix if suffix else ''
                user.email = email
                request.session['first_name'] = user.first_name
                request.session['last_name'] = user.last_name
                request.session['email'] = user.email
                
                # Store bio in tags for profile information
                if bio:
                    _set_profile_dict(user, 'profile_info', {'bio': bio})
                
                user.save()
                request.session.modified = True
                
                logger.info(f"Profile updated for user {user.custom_id}: {first_name} {last_name} ({email})")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Profile updated successfully',
                    'full_name': f"{first_name} {middle_initial} {last_name} {suffix}".replace('  ', ' ').strip()
                })
            except IntegrityError as e:
                logger.error(f"IntegrityError saving profile for {user.custom_id}: {str(e)}")
                return JsonResponse({'success': False, 'error': 'Email is already in use'})
            except Exception as e:
                logger.error(f"Error saving profile for {user.custom_id}: {str(e)}")
                return JsonResponse({'success': False, 'error': str(e)})
        
        # Handle password change
        elif request.POST.get('change_password') == 'true':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not current_password or not new_password or not confirm_password:
                return JsonResponse({'success': False, 'error': 'All password fields are required'})

            if not check_password(current_password, user.password_hash):
                return JsonResponse({'success': False, 'error': 'Current password is incorrect'})

            if new_password != confirm_password:
                return JsonResponse({'success': False, 'error': 'New passwords do not match'})

            if len(new_password) < 8:
                return JsonResponse({'success': False, 'error': 'Password must be at least 8 characters'})

            user.password_hash = make_password(new_password)
            user.save()
            logger.info(f"Password changed for user {user.custom_id}")
            return JsonResponse({'success': True, 'message': 'Password changed successfully'})

        # Handle account deactivation
        elif request.POST.get('deactivate_account') == 'true':
            try:
                if user.role == "teacher":
                    Section.objects.filter(teacher=user, is_active=True).update(is_active=False)
                else:
                    for class_section in Section.objects.filter(is_active=True):
                        _deactivate_student_in_section(class_section, user)
                logger.info(f"Account deactivated for user {user.custom_id}")
                request.session.flush()
                return JsonResponse({'success': True, 'redirect_url': reverse('auth')})
            except Exception as e:
                logger.error(f"Error deactivating account for {user.custom_id}: {str(e)}")
                return JsonResponse({'success': False, 'error': str(e)})

        # Handle account deletion
        elif request.POST.get('delete_account') == 'true':
            try:
                photos_dir = PROFILE_PHOTOS_DIR
                if photos_dir.exists():
                    for file in photos_dir.glob(f'profile_photo_{username}.*'):
                        try:
                            file.unlink()
                        except:
                            pass
                custom_id = user.custom_id
                user.delete()
                logger.info(f"Account deleted for user {custom_id}")
                request.session.flush()
                return JsonResponse({'success': True, 'redirect_url': reverse('home')})
            except Exception as e:
                logger.error(f"Error deleting account: {str(e)}")
                return JsonResponse({'success': False, 'error': str(e)})
        
        # Handle photo removal
        elif request.POST.get('remove_photo') == 'true':
            try:
                photos_dir = PROFILE_PHOTOS_DIR
                
                # Find and delete any profile photo for this user
                if photos_dir.exists():
                    for file in photos_dir.glob(f'profile_photo_{username}.*'):
                        file.unlink()
                
                logger.info(f"Profile photo removed for user {user.custom_id}")
                return JsonResponse({'success': True, 'message': 'Photo removed successfully'})
            
            except Exception as e:
                logger.error(f"Error removing photo for {user.custom_id}: {str(e)}")
                return JsonResponse({'success': False, 'error': str(e)})
        
        # Handle photo upload
        elif request.POST.get('upload_photo') == 'true' and 'profile_photo' in request.FILES:
            try:
                photo_file = request.FILES['profile_photo']
                
                # Validate file size (max 5MB)
                if photo_file.size > 5 * 1024 * 1024:
                    return JsonResponse({'success': False, 'error': 'File size must be less than 5MB'})
                
                # Validate file type
                allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
                file_ext = photo_file.name.split('.')[-1].lower()
                if file_ext not in allowed_extensions:
                    return JsonResponse({'success': False, 'error': 'Only image files are allowed'})
                
                # Create photos directory if it doesn't exist
                photos_dir = PROFILE_PHOTOS_DIR
                photos_dir.mkdir(parents=True, exist_ok=True)
                
                filename = f"profile_photo_{username}.{file_ext}"
                filepath = photos_dir / filename
                
                # Delete any previous photos with different extensions
                for file in photos_dir.glob(f'profile_photo_{username}.*'):
                    try:
                        file.unlink()
                    except:
                        pass
                
                # Save the file
                with open(filepath, 'wb') as f:
                    for chunk in photo_file.chunks():
                        f.write(chunk)
                
                photo_url = f'/static/pabasa_app/uploads/profiles/{filename}'
                logger.info(f"Profile photo uploaded for user {user.custom_id}: {filename}")
                return JsonResponse({'success': True, 'message': 'Photo uploaded successfully', 'photo_url': photo_url})
            
            except Exception as e:
                logger.error(f"Error uploading photo for {user.custom_id}: {str(e)}")
                return JsonResponse({'success': False, 'error': str(e)})
        
        # Handle photo upload via XMLHttpRequest with file in request.FILES (for direct file submission)
        elif request.headers.get('X-Requested-With') == 'XMLHttpRequest' and 'profile_photo' in request.FILES:
            try:
                photo_file = request.FILES['profile_photo']
                
                # Validate file size (max 5MB)
                if photo_file.size > 5 * 1024 * 1024:
                    return JsonResponse({'success': False, 'error': 'File size must be less than 5MB'})
                
                # Validate file type
                allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
                file_ext = photo_file.name.split('.')[-1].lower()
                if file_ext not in allowed_extensions:
                    return JsonResponse({'success': False, 'error': 'Only image files are allowed'})
                
                # Create photos directory if it doesn't exist
                photos_dir = PROFILE_PHOTOS_DIR
                photos_dir.mkdir(parents=True, exist_ok=True)
                
                filename = f"profile_photo_{username}.{file_ext}"
                filepath = photos_dir / filename
                
                # Delete any previous photos with different extensions
                for file in photos_dir.glob(f'profile_photo_{username}.*'):
                    try:
                        file.unlink()
                    except:
                        pass
                
                # Save the file
                with open(filepath, 'wb') as f:
                    for chunk in photo_file.chunks():
                        f.write(chunk)
                
                photo_url = f'/static/pabasa_app/uploads/profiles/{filename}'
                logger.info(f"Profile photo uploaded (AJAX) for user {user.custom_id}: {filename}")
                return JsonResponse({'success': True, 'message': 'Photo uploaded successfully', 'photo_url': photo_url})
            
            except Exception as e:
                logger.error(f"Error uploading photo (AJAX) for {user.custom_id}: {str(e)}")
                return JsonResponse({'success': False, 'error': str(e)})
    
    return render(request, 'pabasa_app/profile.html', {
        'nav_role': nav_role,
        'profile_photo_url': profile_photo_url,
        'username': username,
        'full_name': full_name,
        'first_name': user.first_name,
        'middle_initial': user.middle_initial,
        'last_name': user.last_name,
        'suffix': user.suffix,
        'email': user.email,
        'pabasa_id': pabasa_id,
        'role_display': role_display,
        'initials': initials,
        'bio': bio,
    })

def notifications(request):
    nav_role = request.GET.get('role', 'teacher')
    return render(request, 'pabasa_app/notifications.html', _dashboard_context(request, nav_role))

@csrf_protect
@require_http_methods(["POST"])
def send_parent_email(request):
    """Backend API to send emails to parents using pabasa.tupc@gmail.com"""
    if not _check_auth(request):
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=401)
    
    try:
        data = json.loads(request.body)
        recipient = data.get('email')
        subject = data.get('subject')
        message = data.get('message')
        html_message = data.get('html_message')

        if not recipient or (not message and not html_message):
            return JsonResponse({'success': False, 'error': 'Missing recipient or message content'})

        # Debugging SSL context and Environment
        logger.debug(f"PABASA SMTP: Attempting send to {recipient}")
        logger.debug(f"PABASA SSL: OpenSSL Version: {ssl.OPENSSL_VERSION}")
        logger.debug(f"PABASA SSL: Default Verify Paths: {ssl.get_default_verify_paths()}")

        # Explicitly use the sender email requested
        sender = getattr(settings, 'DEFAULT_FROM_EMAIL', 'pabasa.tupc@gmail.com')
        
        if html_message:
            email = EmailMultiAlternatives(subject, message or "Reading Report", sender, [recipient])
            email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=False)
        else:
            send_mail(subject, message, sender, [recipient], fail_silently=False)
        return JsonResponse({'success': True})

    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(f"PABASA SMTP Error Details:\n{error_detail}")
        return JsonResponse({'success': False, 'error': f"SMTP Error: {str(e)}"}, status=500)


@csrf_protect
@require_http_methods(["POST"])
@login_required(role='student') # Only students can join classes
def join_class(request):
    """
    Allows a student to join a class by storing membership in Section.students.
    Expects a JSON payload with 'class_code'.
    Returns full class data so frontend can render immediately from database.
    """
    try:
        data = json.loads(request.body)
        class_code = data.get('class_code', '').strip().upper()

        if not class_code:
            return JsonResponse({'success': False, 'error': 'Class code is required'}, status=400)

        user_id = request.session.get('user_id')
        student_user = User.objects.filter(id=user_id).first()

        if not student_user:
            return JsonResponse({'success': False, 'error': 'Student not found or inactive'}, status=404)

        section = Section.objects.filter(class_code__iexact=class_code, is_active=True).first()

        if not section:
            return JsonResponse({'success': False, 'error': 'Invalid class code.'}, status=404)

        if _section_has_student(section, student_user):
            student_user.add_tag(section.get_tag_label())
            return JsonResponse({'success': False, 'error': 'You have already joined this class.'}, status=409)

        # Attempt to add student (will raise exception if verification fails)
        _add_student_to_section(section, student_user)
        
        # Refresh section from database to ensure we have latest data
        section.refresh_from_db()
        
        # Verify student was actually added
        if not section.has_student(student_user, active_only=True):
            raise Exception(f"Student {student_user.id} was not enrolled in section {class_code}")

        # Prepare full class data for frontend
        class_data = {
            'code': section.class_code,
            'name': section.class_name,
            'subject': section.subject or '',
            'description': section.description or '',
            'header': section.header or section.class_code[:4],
            'teacher_id': section.teacher.custom_id,
            'teacher_name': f"{section.teacher.first_name} {section.teacher.last_name}",
        }

        logger.info(f"Student {student_user.custom_id} successfully joined class {class_code}")
        student_name = f"{student_user.first_name} {student_user.last_name}"
        class_url = f"{reverse('class_management')}?code={section.class_code}"
        _create_notification(
            section.teacher,
            'Student Enrolled in a Class',
            f'• {student_name} joined {section.class_name}.',
            'success',
            class_url,
            student_user,
        )
        _notify_admins(
            'Student joined a class',
            f'{student_name} joined {section.class_name} ({section.class_code}).',
            'info',
            reverse('admin_class_detail', args=[section.id]),
            student_user,
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully joined class {class_code}',
            'class_data': class_data
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload'}, status=400)
    except Exception as e:
        logger.error(f"Error joining class: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Failed to join class. Please try again.'}, status=500)


@csrf_protect
@require_http_methods(["POST"])
@login_required(role='student')
def unenroll_class(request):
    """Student unenroll endpoint: deactivates the student entry inside Section.students."""
    try:
        data = json.loads(request.body)
        class_code = data.get('class_code', '').strip().upper()
        if not class_code:
            return JsonResponse({'success': False, 'error': 'Class code is required'}, status=400)

        user_id = request.session.get('user_id')
        student_user = User.objects.filter(id=user_id).first()
        if not student_user:
            return JsonResponse({'success': False, 'error': 'Student not found'}, status=404)

        section = Section.objects.filter(class_code=class_code).first()
        if not section:
            return JsonResponse({'success': False, 'error': 'Class not found'}, status=404)

        if not _section_has_student(section, student_user):
            return JsonResponse({'success': False, 'error': 'Class membership not found'}, status=404)

        with transaction.atomic():
            _deactivate_student_in_section(section, student_user)

            # Create an in-app notification for the teacher
            teacher_user = section.teacher
            title = 'Student Unenrolled from a Class'
            message = f"• {student_user.first_name} {student_user.last_name} unenrolled from {section.class_name}."
            Notification.objects.create(
                recipient=teacher_user,
                created_by=student_user,
                title=title,
                message=message,
                notification_type='info',
                action_url=f"{reverse('class_management')}?code={section.class_code}",
            )
            _notify_admins(
                'Student unenrolled from a class',
                f"{student_user.first_name} {student_user.last_name} unenrolled from {section.class_name} ({section.class_code}).",
                'warning',
                reverse('admin_class_detail', args=[section.id]),
                student_user,
            )

            # Send email to teacher (best-effort)
            try:
                subject = f"Student unenrolled from {section.class_name}"
                send_mail(subject, message, getattr(settings, 'DEFAULT_FROM_EMAIL', None), [teacher_user.email], fail_silently=True)
            except Exception:
                logger.exception('Failed to send unenroll email')

        return JsonResponse({'success': True, 'message': 'Unenrolled successfully'})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload'}, status=400)
    except Exception as e:
        logger.error(f"Error unenrolling class: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'An unexpected error occurred'}, status=500)


@csrf_protect
@require_http_methods(["GET"])
@login_required(role='teacher')
def generate_class_code(request):
    """Return a new unique class code for the create-class form."""
    return JsonResponse({
        'success': True,
        'class_code': generate_unique_class_code(),
    })


@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def create_reading_class(request):
    """
    Backend endpoint for creating a classroom.
    Ensures that the class code is unique via database verification.
    """
    try:
        data = json.loads(request.body)
        class_name = data.get('class_name', '').strip()
        header = data.get('header', '').strip() or "Reading Class"
        description = data.get('description', '').strip()
        # 'grade_level' removed from Section model; ignore any incoming value
        section_name = data.get('section', '').strip() or "N/A"
        requested_class_code = data.get('class_code', '').strip()

        if not class_name:
            return JsonResponse({'success': False, 'error': 'Title is required'}, status=400)

        # Retrieve the teacher user for the logged-in user
        user_id = request.session.get('user_id')
        teacher_user = User.objects.filter(id=user_id).first()
        if not teacher_user or teacher_user.role != 'teacher':
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        try:
            unique_code = resolve_class_code_for_creation(requested_class_code or None)
        except ValueError as exc:
            return JsonResponse({'success': False, 'error': str(exc)}, status=400)

        new_class = Section.objects.create(
            teacher=teacher_user,
            class_code=unique_code,
            class_name=class_name,
            header=header,
            description=description,
            subject=data.get('subject', '').strip(),
        )

        teacher_user.add_tag(new_class.get_tag_label())

        return JsonResponse({
            'success': True,
            'message': 'Classroom created successfully',
            'class_code': unique_code,
            'class_name': new_class.class_name
        })
    except Exception as e:
        logger.error(f"Class creation error: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)

@login_required(role='teacher')
def class_management_view(request):
    """View to manage specific class details and student enrollment"""
    class_code = request.GET.get('code', '').strip()
    if not class_code:
        return redirect('dashboard_teacher')

    user_id = request.session.get('user_id')
    teacher_user = User.objects.filter(id=user_id).first()
    if not teacher_user:
        return redirect('auth')

    section = Section.objects.filter(class_code=class_code, teacher=teacher_user, is_active=True).first()
    if not section:
        return redirect('dashboard_teacher')

    # Fetch all active classes for the switcher dropdown
    all_sections = Section.objects.filter(teacher=teacher_user, is_active=True).order_by('class_name')

    # Get students enrolled in this section and enrich from User model
    enrolled_entries = section.get_enrolled_students(active_only=True)
    student_ids = [s.get('student_id') for s in enrolled_entries if s.get('student_id')]
    users_data = User.objects.filter(id__in=student_ids).in_bulk()
    
    students_table = []
    for entry in enrolled_entries:
        user = users_data.get(entry.get('student_id'))
        if not user: continue
        
        # Extract only the date part (YYYY-MM-DD) from the ISO timestamp string
        joined_raw = entry.get('joined_at', section.created_at.isoformat())
        joined_date = joined_raw.split('T')[0] if 'T' in joined_raw else joined_raw
        
        students_table.append({
            'name': f"{user.first_name} {user.last_name}",
            'pabasa_id': user.custom_id,
            'email': user.email,
            'reading_level': user.reading_level or "Developing",
            'joined_at': joined_date
        })
        
    # Fetch all students for the "Add Student" popup
    # We exclude students who are already actively enrolled in this class
    enrolled_pabasa_ids = [s['pabasa_id'] for s in students_table]
    available_students_qs = User.objects.filter(role='student').exclude(custom_id__in=enrolled_pabasa_ids).order_by('last_name', 'first_name')
    
    available_students = []
    for s in available_students_qs:
        available_students.append({
            'id': s.id,
            'name': f"{s.first_name} {s.last_name}",
            'pabasa_id': s.custom_id,
            'grade': s.grade_level or "N/A"
        })

    extra = {
        'section': section,
        'sections': all_sections,
        'available_students': available_students,
        'students_table': students_table,
        'page_title': f"Manage {section.class_name}"
    }
    return render(request, 'pabasa_app/class_management.html', _dashboard_context(request, 'teacher', extra))


# ===== Course APIs =====
@require_http_methods(["GET"])
@login_required()
def get_teacher_courses_api(request):
    try:
        session_user = User.objects.filter(id=request.session.get('user_id')).first()
        # Determine the teacher whose courses should be returned.
        teacher_user = None
        if session_user and session_user.role == 'teacher':
            teacher_user = session_user
        elif session_user and session_user.role == 'admin':
            # Admins must provide a teacher identifier (id or custom_id) via query params.
            tid = request.GET.get('teacher_id') or request.GET.get('teacher_custom_id') or request.GET.get('teacher')
            if not tid:
                return JsonResponse({'success': False, 'error': 'Missing teacher_id parameter for admin'}, status=400)
            try:
                teacher_user = User.objects.filter(Q(id=int(tid)) | Q(custom_id__iexact=str(tid)), role='teacher').first()
            except Exception:
                teacher_user = User.objects.filter(custom_id__iexact=str(tid), role='teacher').first()
            if not teacher_user:
                return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)
        else:
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        # Prefetch related objects to avoid N+1 queries
        courses_qs = Course.objects.filter(teacher=teacher_user, is_active=True).select_related('teacher').prefetch_related(
            'sections', 'materials', 'assessments', 'assessments__materials'
        ).order_by('-created_at')

        course_list = []
        for c in courses_qs:
            course_sections = list(c.sections.all())
            secs = [{'id': s.id, 'code': s.class_code, 'name': s.class_name} for s in course_sections]

            # Serialize assessments with helpful metadata used by the frontend
            assessments_list = []
            course_assessments_qs = Assessment.objects.filter(
                Q(courses=c) |
                Q(section__in=course_sections, teacher=teacher_user)
            ).prefetch_related('materials').distinct()
            for a in course_assessments_qs:
                if not getattr(a, 'is_active', True):
                    continue
                items = 0
                minutes = 0
                try:
                    for mat in a.materials.all():
                        cj = getattr(mat, 'content_json', None) or {}
                        if isinstance(cj, dict) and 'items' in cj:
                            val = cj.get('items')
                            if isinstance(val, list):
                                items += len(val)
                            elif isinstance(val, int):
                                items += int(val)
                        else:
                            ct = getattr(mat, 'content_text', '') or ''
                            if ct:
                                if getattr(mat, 'item_type', '') == 'word':
                                    items += max(1, ct.count('\n') + 1)
                                else:
                                    items += 1
                        try:
                            minutes += int(cj.get('minutes', 0) or 0)
                        except Exception:
                            pass
                except Exception:
                    items = 0

                avg = None
                try:
                    attempts = getattr(a, 'attempts', None) or []
                    accs = [att.get('accuracy') for att in attempts if isinstance(att.get('accuracy'), (int, float))]
                    if accs:
                        avg = round(sum(accs) / len(accs))
                except Exception:
                    avg = None

                assessments_list.append({
                    'id': a.id,
                    'raw_id': a.id,
                    'action_id': f"assessment-{a.id}",
                    'code': a.code,
                    'title': a.title,
                    'assessment_type': a.assessment_type,
                    'level': a.get_assessment_type_display() if hasattr(a, 'get_assessment_type_display') else (a.assessment_type or ''),
                    'items': items,
                    'items_count': items,
                    'minutes': minutes,
                    'average': f"{avg}%" if avg is not None else None,
                    'dueDate': a.scheduled_at.isoformat() if getattr(a, 'scheduled_at', None) else None,
                    'status': 'archived' if not a.is_active else a.status,
                    'is_active': a.is_active,
                    'created_at': a.created_at.isoformat() if getattr(a, 'created_at', None) else None,
                })

            # Serialize materials with normalized metadata
            materials_list = []
            for m in c.materials.all():
                if not getattr(m, 'is_active', True):
                    continue
                cj = getattr(m, 'content_json', None) or {}
                items_count = 0
                items_array = None
                try:
                    if isinstance(cj, dict) and 'items' in cj:
                        val = cj.get('items')
                        if isinstance(val, list):
                            items_array = val
                            items_count = len(val)
                        elif isinstance(val, int):
                            items_count = int(val)
                except Exception:
                    items_count = 0

                if items_count == 0:
                    ct = getattr(m, 'content_text', '') or ''
                    if ct:
                        if getattr(m, 'item_type', '') == 'word':
                            items_count = max(1, ct.count('\n') + 1)
                        else:
                            items_count = 1

                materials_list.append({
                    'id': m.id,
                    'raw_id': m.id,
                    'action_id': f"material-{m.id}",
                    'record_kind': 'material',
                    'assessment_id': m.assessment_id,
                    'code': m.assessment.code if m.assessment else None,
                    'title': m.title,
                    'item_type': getattr(m, 'item_type', ''),
                    'type': getattr(m, 'type', ''),
                    'content': getattr(m, 'content_text', '') or getattr(m, 'prompt_text', '') or '',
                    'content_text': getattr(m, 'content_text', '') or getattr(m, 'prompt_text', '') or '',
                    'status': getattr(m, 'status', ''),
                    'schedule': timezone.localtime(m.scheduled_at, timezone.get_default_timezone()).strftime('%Y-%m-%dT%H:%M') if getattr(m, 'scheduled_at', None) else None,
                    'items': items_array,
                    'items_count': items_count,
                    'created_at': m.created_at.isoformat() if getattr(m, 'created_at', None) else None,
                    'assigned_sections': [s.class_code for s in m.assigned_sections.all()] if hasattr(m, 'assigned_sections') else [],
                    'assigned_week': m.assigned_week,
                    'assigned_week_display': format_assigned_week_display(m.assigned_week),
                })

            # Practices (normalized)
            practices_list = []
            try:
                practices_qs = Practice.objects.filter(
                    Q(section__in=course_sections) |
                    Q(teacher=c.teacher) |
                    Q(section__isnull=True, teacher__role='admin')
                ).order_by('-created_at')[:100]
                for p in practices_qs:
                    items_cnt = len(_practice_material_items(p)) if callable(_practice_material_items) else None
                    practices_list.append({
                        'id': f"practice-{p.id}",
                        'raw_id': p.id,
                        'action_id': f"practice-{p.id}",
                        'record_kind': 'practice',
                        'title': p.title,
                        'item_type': getattr(p, 'item_type', getattr(p, 'practice_type', '')),
                        'status': getattr(p, 'status', ''),
                        'items': None,
                        'items_count': items_cnt,
                        'created_at': p.created_at.isoformat() if getattr(p, 'created_at', None) else None,
                        'code': getattr(p, 'code', None),
                        'content': p.content_text if hasattr(p, 'content_text') else getattr(p, 'contents', ''),
                    })
            except Exception:
                practices_list = []

            course_list.append({
                'id': c.id,
                'code': c.code,
                'title': c.title,
                'description': c.description,
                'sections': secs,
                'assessments': assessments_list,
                'materials': materials_list,
                'practices': practices_list,
            })

        return JsonResponse({'success': True, 'courses': course_list})
    except Exception as e:
        logger.exception('Unhandled error in get_teacher_courses_api')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
@login_required(role='teacher')
def get_teacher_assessment_api(request, assessment_id):
    """Return detailed data for a single assessment (teacher-only)."""
    try:
        user_id = request.session.get('user_id')
        teacher_user = User.objects.filter(id=user_id).first()
        if not teacher_user:
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        assessment = Assessment.objects.filter(id=assessment_id).first()
        if not assessment:
            return JsonResponse({'success': False, 'error': 'Assessment not found'}, status=404)

        # Ownership check: allow if teacher created it or is owner of the linked section
        if assessment.teacher_id != teacher_user.id and not (getattr(assessment.section, 'teacher_id', None) == teacher_user.id):
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)

        # materials linked to this assessment
        mats = []
        for m in assessment.materials.all():
            cj = getattr(m, 'content_json', None) or {}
            mats.append({
                'id': m.id,
                'title': m.title,
                'item_type': getattr(m, 'item_type', ''),
                'items': len(cj.get('items')) if isinstance(cj.get('items'), list) else (cj.get('items') if isinstance(cj.get('items'), int) else None),
                'status': m.status,
                'created_at': m.created_at.isoformat() if getattr(m, 'created_at', None) else None,
            })

        attempts = getattr(assessment, 'attempts', None) or []
        if not isinstance(attempts, list):
            attempts = []
        student_ids = {
            att.get('student_id')
            for att in attempts
            if isinstance(att, dict) and att.get('student_id')
        }
        students_by_id = {
            student.id: student
            for student in User.objects.filter(id__in=student_ids)
        }
        enriched_attempts = []
        for att in attempts:
            if not isinstance(att, dict):
                continue
            student = students_by_id.get(att.get('student_id'))
            student_name = ''
            if student:
                student_name = f"{student.first_name} {student.last_name}".strip() or student.custom_id or student.email or f"Student {student.id}"
            words_correct = (
                att.get('words_correct')
                or att.get('correct_words')
                or att.get('correct_count')
                or att.get('total_score')
                or att.get('score')
            )
            enriched_attempt = dict(att)
            enriched_attempt.update({
                'student_name': student_name or f"Student {att.get('student_id')}",
                'student_email': getattr(student, 'email', '') if student else '',
                'words_correct': words_correct,
            })
            enriched_attempts.append(enriched_attempt)
        avg = None
        try:
            accs = [
                att.get('accuracy')
                for att in attempts
                if isinstance(att, dict) and isinstance(att.get('accuracy'), (int, float))
            ]
            if accs:
                avg = round(sum(accs) / len(accs))
        except Exception:
            avg = None

        payload = {
            'id': assessment.id,
            'code': assessment.code,
            'title': assessment.title,
            'type': assessment.assessment_type,
            'level': assessment.get_assessment_type_display() if hasattr(assessment, 'get_assessment_type_display') else assessment.assessment_type,
            'items': sum((m.get('items') or 0) for m in mats),
            'minutes': 0,
            'average': f"{avg}%" if avg is not None else None,
            'dueDate': assessment.scheduled_at.isoformat() if getattr(assessment, 'scheduled_at', None) else None,
            'status': 'archived' if not assessment.is_active else assessment.status,
            'is_active': assessment.is_active,
            'materials': mats,
            'attempts': enriched_attempts,
        }
        return JsonResponse({'success': True, 'assessment': payload})
    except Exception as e:
        logger.exception('Error in get_teacher_assessment_api')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def teacher_update_assessment(request):
    """Allow teacher to update assessment metadata (title, status, scheduled_at)."""
    try:
        data = json.loads(request.body)
        raw = data.get('assessment_id') or data.get('id')
        _, aid = _parse_prefixed_id(raw)
        if not aid:
            return JsonResponse({'success': False, 'error': 'Invalid assessment id'}, status=400)

        user_id = request.session.get('user_id')
        teacher_user = User.objects.filter(id=user_id).first()
        if not teacher_user:
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        assessment = Assessment.objects.filter(id=aid).first()
        if not assessment:
            return JsonResponse({'success': False, 'error': 'Assessment not found'}, status=404)

        if assessment.teacher_id != teacher_user.id and not (getattr(assessment.section, 'teacher_id', None) == teacher_user.id):
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)

        title = (data.get('title') or '').strip()
        status = data.get('status')
        scheduled_at_str = data.get('scheduled_at')

        if title:
            assessment.title = title
        if status:
            assessment.status = status
            assessment.is_active = (status in ['published', 'scheduled'])

        if scheduled_at_str:
            try:
                dt = parse_datetime(scheduled_at_str if 'T' in scheduled_at_str else scheduled_at_str + ':00')
                if dt and not timezone.is_aware(dt):
                    dt = timezone.make_aware(dt)
                assessment.scheduled_at = dt
            except Exception:
                pass
        else:
            assessment.scheduled_at = None

        assessment.save()
        try:
            for material in assessment.materials.all():
                material.title = assessment.title
                material.status = assessment.status
                material.scheduled_at = assessment.scheduled_at
                material.is_active = assessment.is_active
                material.save(update_fields=['title', 'status', 'scheduled_at', 'is_active', 'updated_at'])
        except Exception:
            logger.exception('Failed to synchronize materials for assessment %s', assessment.id)
        return JsonResponse({'success': True, 'message': 'Assessment updated'})
    except Exception as e:
        logger.exception('Error in teacher_update_assessment')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def teacher_archive_assessment(request):
    """Archive (soft-delete) an assessment and detach it from courses owned by the teacher."""
    try:
        data = json.loads(request.body)
        raw = data.get('assessment_id') or data.get('id')
        _, aid = _parse_prefixed_id(raw)
        if not aid:
            return JsonResponse({'success': False, 'error': 'Invalid assessment id'}, status=400)

        user_id = request.session.get('user_id')
        teacher_user = User.objects.filter(id=user_id).first()
        if not teacher_user:
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        assessment = Assessment.objects.filter(id=aid).first()
        if not assessment:
            return JsonResponse({'success': False, 'error': 'Assessment not found'}, status=404)

        if assessment.teacher_id != teacher_user.id and not (getattr(assessment.section, 'teacher_id', None) == teacher_user.id):
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)

        # soft delete
        assessment.is_active = False
        assessment.save()
        try:
            for material in assessment.materials.all():
                material.is_active = False
                material.save(update_fields=['is_active', 'updated_at'])
        except Exception:
            logger.exception('Failed to archive materials for assessment %s', assessment.id)

        # remove from any courses owned by this teacher
        try:
            for course in Course.objects.filter(teacher=teacher_user, assessments=assessment):
                course.assessments.remove(assessment)
        except Exception:
            pass

        return JsonResponse({'success': True, 'message': 'Assessment archived'})
    except Exception as e:
        logger.exception('Error in teacher_archive_assessment')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def create_course(request):
    try:
        data = json.loads(request.body)
        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        section_ids = data.get('sections') or []

        if not title:
            return JsonResponse({'success': False, 'error': 'Title is required'}, status=400)

        teacher_user = User.objects.filter(id=request.session.get('user_id')).first()
        if not teacher_user or teacher_user.role != 'teacher':
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        code = generate_unique_course_code()
        course = Course.objects.create(
            code=code,
            title=title,
            description=description,
            teacher=teacher_user,
        )
        if section_ids:
            # Accept either numeric ids or class_code strings
            for sid in section_ids:
                try:
                    if isinstance(sid, int) or str(sid).isdigit():
                        sec = Section.objects.filter(id=int(sid), teacher=teacher_user).first()
                    else:
                        sec = Section.objects.filter(class_code=str(sid).strip(), teacher=teacher_user).first()
                    if sec:
                        course.sections.add(sec)
                except Exception:
                    continue

        return JsonResponse({'success': True, 'course': {'id': course.id, 'code': course.code, 'title': course.title}})
    except Exception as e:
        logger.exception('Error creating course')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def _compute_teacher_overview(teacher_user):
    """Helper: compute the same overview payload returned by get_teacher_overview."""
    try:
        classes_count = Section.objects.filter(teacher=teacher_user, is_active=True).count()
        active_sections = Section.objects.filter(teacher=teacher_user, is_active=True)
        unique_student_ids = set()
        for section in active_sections:
            for entry in section.get_enrolled_students(active_only=True):
                if entry.get('student_id'):
                    unique_student_ids.add(entry.get('student_id'))
        total_students = len(unique_student_ids)

        assessments_posted = Assessment.objects.filter(
            Q(teacher=teacher_user) | Q(section__teacher=teacher_user),
            is_active=True
        ).distinct().count()

        materials_posted = Material.objects.filter(
            Q(section__teacher=teacher_user) | Q(assigned_sections__teacher=teacher_user),
            is_active=True,
            assessment__isnull=True,
        ).distinct().count()

        reports_generated = Note.objects.filter(teacher=teacher_user).count()

        return {
            'classes_count': classes_count,
            'total_students': total_students,
            'materials_posted': materials_posted,
            'assessments_posted': assessments_posted,
            'reports_generated': reports_generated,
        }
    except Exception:
        return {
            'classes_count': 0,
            'total_students': 0,
            'materials_posted': 0,
            'assessments_posted': 0,
            'reports_generated': 0,
        }



@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def add_material_to_course(request):
    """Attach an existing Material (and its Assessment, if any) to a Course owned by the teacher."""
    try:
        data = json.loads(request.body)
        course_id = data.get('course_id')
        material_id = data.get('material_id')

        user_id = request.session.get('user_id')
        teacher_user = User.objects.filter(id=user_id).first()
        if not teacher_user or teacher_user.role != 'teacher':
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        course = Course.objects.filter(id=course_id, teacher=teacher_user).first()
        if not course:
            return JsonResponse({'success': False, 'error': 'Course not found or not owned by you'}, status=404)

        material = Material.objects.filter(id=material_id).first()
        if not material:
            return JsonResponse({'success': False, 'error': 'Material not found'}, status=404)

        # Basic ownership check: allow if material is unassigned (section=None) or belongs to one of the teacher's sections
        if material.section and material.section.teacher_id != teacher_user.id:
            # Also allow if the underlying assessment (if any) belongs to the teacher
            if not (getattr(material, 'assessment', None) and material.assessment.teacher_id == teacher_user.id):
                return JsonResponse({'success': False, 'error': 'You do not have permission to use this material'}, status=403)

        course.materials.add(material)
        # If material has an attached Assessment, also link it for convenience
        if getattr(material, 'assessment', None):
            try:
                course.assessments.add(material.assessment)
            except Exception:
                pass

        return JsonResponse({'success': True, 'material': {'id': material.id, 'title': material.title, 'item_type': getattr(material, 'item_type', '' )}})
    except Exception as e:
        logger.exception('Error adding material to course')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def remove_material_from_course(request):
    """Detach a Material from a Course."""
    try:
        data = json.loads(request.body)
        course_id = data.get('course_id')
        material_id = data.get('material_id')

        user_id = request.session.get('user_id')
        teacher_user = User.objects.filter(id=user_id).first()
        if not teacher_user or teacher_user.role != 'teacher':
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        course = Course.objects.filter(id=course_id, teacher=teacher_user).first()
        if not course:
            return JsonResponse({'success': False, 'error': 'Course not found or not owned by you'}, status=404)

        material = Material.objects.filter(id=material_id).first()
        if not material:
            return JsonResponse({'success': False, 'error': 'Material not found'}, status=404)

        course.materials.remove(material)
        # Also attempt to remove linked assessment if present
        if getattr(material, 'assessment', None):
            try:
                course.assessments.remove(material.assessment)
            except Exception:
                pass

        return JsonResponse({'success': True})
    except Exception as e:
        logger.exception('Error removing material from course')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)




@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def update_class_info(request):
    """API to update class metadata"""
    try:
        data = json.loads(request.body)
        section = Section.objects.filter(class_code=data.get('class_code'), teacher_id=request.session.get('user_id')).first()
        if not section: return JsonResponse({'success': False, 'error': 'Class not found'}, status=404)
        section.class_name = data.get('class_name', '').strip()
        # 'grade_level' and per-class 'section' fields removed from the model; only update fields that remain
        section.description = data.get('description', '').strip()
        section.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def teacher_add_student(request):
    """Backend endpoint for teachers to manually enroll a student"""
    try:
        data = json.loads(request.body)
        class_code = data.get('class_code')
        student_id = data.get('student_id')
        
        user_id = request.session.get('user_id')
        section = Section.objects.filter(class_code=class_code, teacher_id=user_id).first()
        student = User.objects.filter(id=student_id, role='student').first()
        
        if not section or not student:
            return JsonResponse({'success': False, 'error': 'Class or Student not found'}, status=404)
        
        if section.add_student(student):
            student_name = f"{student.first_name} {student.last_name}"
            _create_notification(
                student,
                'Added to class',
                f'You were added to {section.class_name}.',
                'success',
                reverse('dashboard'),
                section.teacher,
            )
            _create_notification(
                section.teacher,
                'Student Enrolled in a Class',
                f'• {student_name} joined {section.class_name}.',
                'success',
                f"{reverse('class_management')}?code={section.class_code}",
                section.teacher,
            )
            _notify_admins(
                'Student joined a class',
                f'{student_name} was added to {section.class_name} ({section.class_code}).',
                'info',
                reverse('admin_class_detail', args=[section.id]),
                section.teacher,
            )
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Student is already enrolled.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def teacher_remove_student(request):
    """Backend endpoint for teachers to remove a student from a class"""
    try:
        data = json.loads(request.body)
        class_code = data.get('class_code')
        student_id_val = data.get('student_id')
        
        user_id = request.session.get('user_id')
        teacher_user = User.objects.filter(id=user_id).first()
        section = Section.objects.filter(class_code=class_code, teacher=teacher_user, is_active=True).first()
        
        if not section:
            return JsonResponse({'success': False, 'error': 'Class not found'}, status=404)
        
        # Match by internal database ID or the custom Pabasa ID
        student = User.objects.filter(Q(id=student_id_val) | Q(custom_id=student_id_val), role='student').first()
        
        if not student:
            return JsonResponse({'success': False, 'error': 'Student not found'}, status=404)

        if section.deactivate_student(student):
            _create_notification(
                student,
                'Removed from class',
                f'You were removed from {section.class_name} by your teacher.',
                'warning',
                reverse('dashboard'),
                teacher_user,
            )
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Student is not enrolled or already removed.'})
    except Exception as e:
        logger.error(f"Error removing student from class: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@require_http_methods(["GET"])
@login_required(role='teacher')
def get_teacher_classes(request):
    try:
        user_id = request.session.get('user_id')  # ← this is already the session-bound user
        teacher_user = User.objects.filter(id=user_id).first()
        if not teacher_user or teacher_user.role != 'teacher':
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        classes = Section.objects.filter(
            teacher=teacher_user,
            is_active=True
        ).order_by('class_name')

        class_list = []
        for cls in classes:
            student_count = _section_student_count(cls)
            class_list.append({
                'id': cls.id,
                'code': cls.class_code,
                'name': cls.class_name,
                'subject': cls.subject,
                'grade_level': getattr(cls, 'grade_level', '') if hasattr(cls, 'grade_level') else '',
                'section': getattr(cls, 'section', '') if hasattr(cls, 'section') else '',
                'description': cls.description,
                'header': cls.header,
                'students': student_count,
                'teacher_email': request.session.get('email', ''),
            })

        return JsonResponse({'success': True, 'classes': class_list})
    except Exception as e:
        # Log full traceback and return JSON so client-side can inspect error details
        logger.exception("Unhandled error in get_teacher_classes")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
@login_required(role='student')
def get_student_joined_classes(request):
    """
    Return all classes the student has joined by querying the database directly.
    This provides the authoritative source of truth for enrolled classes.
    """
    try:
        user_id = request.session.get('user_id')
        student_user = User.objects.filter(id=user_id).first()
        
        if not student_user:
            return JsonResponse({'success': False, 'error': 'Student not found'}, status=404)
        
        if student_user.role != 'student':
            return JsonResponse({'success': False, 'error': 'Not a student account'}, status=403)
        
        # Get all active sections where this student is enrolled
        sections = Section.objects.filter(is_active=True).order_by('class_name')
        joined_classes = []
        
        for section in sections:
            # Check if student is actively enrolled in this section
            if section.has_student(student_user, active_only=True):
                joined_classes.append({
                    'code': section.class_code,
                    'name': section.class_name,
                    'subject': section.subject or '',
                    'description': section.description or '',
                    'header': section.header or section.class_code[:4],
                    'teacher_id': section.teacher.custom_id,
                    'teacher_name': f"{section.teacher.first_name} {section.teacher.last_name}",
                    'student_count': section.get_student_count(),
                    'created_at': section.created_at.isoformat(),
                })
        
        logger.debug(f"Retrieved {len(joined_classes)} joined classes for student {student_user.custom_id}")
        
        return JsonResponse({'success': True, 'classes': joined_classes})
    
    except Exception as e:
        logger.error(f"Error getting student joined classes: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Failed to retrieve classes'}, status=500)


@require_http_methods(["GET"])
@login_required(role='teacher')
def get_teacher_overview(request):
    """
    Return aggregated teacher overview stats: active classes, total students,
    materials posted (assessments), and reports generated (teacher notes).
    """
    try:
        user_id = request.session.get('user_id')
        teacher_user = User.objects.filter(id=user_id).first()
        if not teacher_user or teacher_user.role != 'teacher':
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        classes_count = Section.objects.filter(teacher=teacher_user, is_active=True).count()
        
        # Authoritative unique student count
        active_sections = Section.objects.filter(teacher=teacher_user, is_active=True)
        unique_student_ids = set()
        for section in active_sections:
            for entry in section.get_enrolled_students(active_only=True):
                if entry.get('student_id'):
                    unique_student_ids.add(entry.get('student_id'))
        total_students = len(unique_student_ids)

        # Separate materials vs assessments counts so they are not conflated
        assessments_posted = Assessment.objects.filter(
            Q(teacher=teacher_user) | Q(section__teacher=teacher_user),
            is_active=True
        ).distinct().count()

        # Materials that are standalone (not representing an Assessment)
        materials_posted = Material.objects.filter(
            Q(section__teacher=teacher_user) | Q(assigned_sections__teacher=teacher_user),
            is_active=True,
            assessment__isnull=True,
        ).distinct().count()

        reports_generated = Note.objects.filter(teacher=teacher_user).count()

        return JsonResponse({
            'success': True,
            'classes_count': classes_count,
            'total_students': total_students,
            'materials_posted': materials_posted,
            'assessments_posted': assessments_posted,
            'reports_generated': reports_generated,
        })
    except Exception as e:
        logger.error('Error computing teacher overview: %s', e, exc_info=True)
        return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)


@require_http_methods(["GET"])
def get_class_materials(request):
    """
    Returns all materials (assessments) for a class, organized by reading type.
    Accessible by both teachers (owners) and students (enrolled in class).
    Query params: class_code (required)
    Returns: { 'success': True, 'materials': { word: [...], sentence: [...], paragraph: [...] } }
    """
    try:
        class_code = request.GET.get('class_code', '').strip()
        if not class_code:
            return JsonResponse({'success': False, 'error': 'class_code parameter required'}, status=400)
        
        # Get the section (class) by code
        section = Section.objects.filter(
            class_code__iexact=class_code,
            is_active=True
        ).first()
        
        if not section:
            return JsonResponse({'success': False, 'error': 'Class not found'}, status=404)
        
        # Include materials directly linked to section, assigned via ManyToMany,
        # or attached to a Course that includes this section.
        materials_qs = Material.objects.filter(
            Q(section=section) | Q(assigned_sections=section) | Q(courses__sections=section)
        ).distinct()
        # Avoid duplication: exclude assessments that are already represented by a Material record.
        # Material records act as the primary container for metadata like "Assigned Week".
        represented_asm_ids = materials_qs.exclude(assessment=None).values_list('assessment_id', flat=True)
        assessments_qs = Assessment.objects.filter(section=section).exclude(id__in=represented_asm_ids)
        # Practice sets: include those that belong to this section or were created by the
        # class' teacher (so teacher-created practice sets show up in their class view)
        practices_qs = Practice.objects.filter(
            Q(section=section) |
            Q(teacher=section.teacher) |
            Q(section__isnull=True, teacher=section.teacher) |
            Q(section__isnull=True, teacher__role='admin')
        ).order_by('-created_at')
        user_id = request.session.get('user_id')
        teacher_user = User.objects.filter(id=user_id).first() if user_id else None
        # Requesting user (could be student or teacher) used to compute attempt counts
        request_user = User.objects.filter(id=user_id).first() if user_id else None
        is_requesting_student = bool(request_user and request_user.role == 'student')
        # Archived records should not appear in class/course readings, even for the owning teacher.
        materials_qs = materials_qs.filter(is_active=True)
        assessments_qs = assessments_qs.filter(is_active=True)
        practices_qs = practices_qs.filter(is_active=True)

        # If requester is not the class owner teacher, only include published practice items
        if not (teacher_user and teacher_user.role == 'teacher' and section.teacher_id == teacher_user.id):
            practices_qs = practices_qs.filter(status='published')

        # Limit practice sets to the most recent 100 to avoid payload bloat
        practices_qs = practices_qs[:100]

        # Build combined list sorted by created_at descending
        combined = []
        for mat in materials_qs:
            combined.append(('material', mat))
        for a in assessments_qs:
            combined.append(('assessment', a))
        for p in practices_qs:
            combined.append(('practice', p))
        combined.sort(key=lambda tup: getattr(tup[1], 'created_at', timezone.now()), reverse=True)

        all_materials_flat = []
        materials = {'word': [], 'sentence': [], 'paragraph': []}

        for kind, obj in combined:
            if kind == 'material':
                m = obj
                content_value = m.content_text or m.prompt_text or ''
                title_value = m.title or (content_value[:150] + '...' if len(content_value) > 150 else content_value)
                items_count = 1
                if isinstance(m.content_json, dict) and isinstance(m.content_json.get('items'), list):
                    items_count = len(m.content_json.get('items'))

                # compute attempt count: for materials linked to an Assessment use that Assessment's attempts
                attempt_count = 0
                if m.assessment:
                    if is_requesting_student and request_user:
                        attempt_count = m.assessment.get_student_attempt_count(request_user)
                    elif teacher_user and teacher_user.role == 'teacher':
                        # Teachers see 0 completions for themselves on the hub
                        attempt_count = 0
                    else:
                        attempt_count = 0

                item = {
                    'id': f"material-{m.id}",
                    'raw_id': m.id,
                    'action_id': f"material-{m.id}",
                    'record_kind': 'material',
                    'assessment_id': m.assessment_id,
                    'code': m.assessment.code if m.assessment else None,
                    'title': title_value,
                    'item_type': m.item_type,
                    'type': m.type,
                    'content': content_value,
                    'content_text': content_value,
                    'status': 'archived' if not m.is_active else (m.status or 'published'),
                    'schedule': timezone.localtime(m.scheduled_at, timezone.get_default_timezone()).strftime('%Y-%m-%dT%H:%M') if getattr(m, 'scheduled_at', None) else None,
                    'items': items_count,
                    'created_at': m.created_at.isoformat() if getattr(m, 'created_at', None) else None,
                    'attempt_count': attempt_count,
                    'assigned_sections': [s.class_code for s in m.assigned_sections.all()] if hasattr(m, 'assigned_sections') else [],
                    'assigned_week': m.assigned_week,
                    'assigned_week_display': format_assigned_week_display(m.assigned_week),
                }
            elif kind == 'assessment':
                a = obj
                content_value = a.content or ''
                title_value = a.title or (content_value[:150] + '...' if len(content_value) > 150 else content_value)
                items_count = 1
                # compute attempt count for this assessment
                if is_requesting_student and request_user:
                    attempt_count = a.get_student_attempt_count(request_user)
                elif teacher_user and teacher_user.role == 'teacher':
                    # Teachers see 0 completions for themselves on the hub
                    attempt_count = 0
                else:
                    attempt_count = 0

                item = {
                    'id': f"assessment-{a.id}",
                    'code': a.code,
                    'title': title_value,
                    'item_type': a.assessment_type,
                    'type': 'assessment',
                    'content': content_value,
                    'content_text': content_value,
                    'status': 'archived' if not a.is_active else (a.status or 'published'),
                    'schedule': timezone.localtime(a.scheduled_at, timezone.get_default_timezone()).strftime('%Y-%m-%dT%H:%M') if getattr(a, 'scheduled_at', None) else None,
                    'items': items_count,
                    'created_at': a.created_at.isoformat() if getattr(a, 'created_at', None) else None,
                    'attempt_count': attempt_count,
                    'assigned_sections': [a.section.class_code] if a.section else [],
                    'assigned_week': None,
                    'assigned_week_display': format_assigned_week_display(None),
                }
            else:
                # practice
                p = obj
                content_value = p.content_text or ''
                title_value = p.title or (content_value[:150] + '...' if len(content_value) > 150 else content_value)
                items_count = len(_practice_material_items(p))
                # compute attempt count for practice
                if is_requesting_student and request_user:
                    attempt_count = len(p.get_attempts(request_user))
                else:
                    attempt_count = len(p.get_attempts())

                item = {
                    'id': f"practice-{p.id}",
                    'code': p.code,
                    'title': title_value,
                    'item_type': p.item_type,
                    'type': 'practice',
                    'content': content_value,
                    'content_text': content_value,
                    'status': 'archived' if not p.is_active else (p.status or 'published'),
                    'schedule': None,
                    'items': items_count,
                    'created_at': p.created_at.isoformat() if getattr(p, 'created_at', None) else None,
                    'attempt_count': attempt_count,
                    'assigned_sections': [],
                    'assigned_week': None,
                    'assigned_week_display': format_assigned_week_display(None),
                }

            if item.get('item_type') in materials:
                materials[item.get('item_type')].append(item)
            all_materials_flat.append(item)
        
        logger.debug(f"Retrieved materials for class {class_code}: {sum(len(m) for m in materials.values())} total")
        
        return JsonResponse({
            'success': True,
            'materials': materials,
            'all_materials': all_materials_flat,
            'class_code': section.class_code,
            'class_name': section.class_name,
            'subject': section.subject or 'Reading',
        })
    
    except Exception as e:
        logger.error(f"Error getting class materials: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Failed to retrieve materials'}, status=500)

@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def delete_reading_class(request):
    """
    Backend endpoint for deleting a classroom.
    Expects JSON: { class_code }
    """
    try:
        data = json.loads(request.body)
        class_code = data.get('class_code', '').strip()

        if not class_code:
            return JsonResponse({'success': False, 'error': 'Class code is required'}, status=400)

        # Retrieve the teacher user for the logged-in user
        user_id = request.session.get('user_id')
        teacher_user = User.objects.filter(id=user_id).first()
        if not teacher_user or teacher_user.role != 'teacher':
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        # Find the section
        section = Section.objects.filter(
            teacher=teacher_user,
            class_code=class_code,
            is_active=True
        ).first()

        if not section:
            return JsonResponse({'success': False, 'error': 'Class not found'}, status=404)

        # Soft delete: capture affected students before deactivating
        affected_student_ids = [
            entry.get('student_id')
            for entry in _section_students(section, active_only=True)
            if entry.get('student_id')
        ]
        affected_students = list(User.objects.filter(id__in=affected_student_ids))

        with transaction.atomic():
            _deactivate_all_section_students(section)
            section.is_active = False
            section.save()
            teacher_user.remove_tag(section.get_tag_label())

            # Deactivate assessments and materials tied to this section
            Assessment.objects.filter(section=section, is_active=True).update(is_active=False)
            Material.objects.filter(section=section, is_active=True).update(is_active=False)

            # Notify affected students (in-app + email)
            teacher_name = f"{teacher_user.first_name} {teacher_user.last_name}" if teacher_user else 'Your teacher'
            for student_user in affected_students:
                try:
                    title = 'Class removed by teacher'
                    message = (
                        f"{teacher_name} has removed the class '{section.class_name}'. "
                        "Visit your account to completely remove the class."
                    )
                    Notification.objects.create(
                        recipient=student_user,
                        created_by=teacher_user,
                        title=title,
                        message=message,
                        notification_type='warning',
                        action_url=reverse('dashboard'),
                    )

                    # Best-effort email to student
                    try:
                        subject = f"Class removed: {section.class_name}"
                        send_mail(subject, message, getattr(settings, 'DEFAULT_FROM_EMAIL', None), [student_user.email], fail_silently=True)
                    except Exception:
                        logger.exception('Failed to send class-deleted email to student %s', student_user.email)
                except Exception:
                    logger.exception('Failed to notify a student for class deletion')
            _notify_admins(
                'Teacher removed a class',
                f"{teacher_user.first_name} {teacher_user.last_name} removed {section.class_name} ({section.class_code}).",
                'warning',
                reverse('admin_classes'),
                teacher_user,
            )

        return JsonResponse({
            'success': True,
            'message': 'Class deleted successfully',
            'class_code': class_code
        })
    except Exception as e:
        logger.error(f"Class deletion error: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)

@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def extract_reading_material_file(request):
    """Extract text snippets from an uploaded PDF, DOCX, or text file for the Add Material modal."""
    upload = request.FILES.get('file')
    if not upload:
        return JsonResponse({'success': False, 'error': 'Please choose a PDF, DOCX, or text file.'}, status=400)

    filename = upload.name or ''
    ext = Path(filename).suffix.lower()
    if ext not in {'.txt', '.docx', '.pdf'}:
        return JsonResponse({'success': False, 'error': 'Only PDF, DOCX, and text files are supported.'}, status=400)

    if upload.size and upload.size > 8 * 1024 * 1024:
        return JsonResponse({'success': False, 'error': 'File is too large. Please upload a file under 8 MB.'}, status=400)

    def excerpt_items(text):
        cleaned = re.sub(r'[ \t]+', ' ', (text or '').replace('\r', '\n'))
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
        if not cleaned:
            return []

        numbered_text = re.sub(r'\s*(\d{1,3})\.\s+', r'\n\1. ', cleaned)
        numbered_items = [
            re.sub(r'^\d{1,3}\.\s+', '', item).strip()
            for item in re.split(r'\n(?=\d{1,3}\.\s+)', numbered_text)
            if item.strip()
        ]
        if len(numbered_items) > 1:
            raw_items = numbered_items
        else:
            paragraphs = [re.sub(r'^\d{1,3}\.\s+', '', p).strip() for p in re.split(r'\n\s*\n', cleaned) if p.strip()]
            if len(paragraphs) > 1:
                raw_items = paragraphs
            else:
                lines = [re.sub(r'^\d{1,3}\.\s+', '', line).strip() for line in cleaned.split('\n') if line.strip()]
                if len(lines) > 1:
                    raw_items = lines
                else:
                    sentences = [
                        re.sub(r'^\d{1,3}\.\s+', '', s).strip()
                        for s in re.split(r'(?<=[.!?])\s+', cleaned)
                        if s.strip()
                    ]
                    raw_items = sentences if len(sentences) > 1 else re.split(r'[,\s]+', cleaned)

        items = []
        seen = set()
        for raw_item in raw_items:
            item = re.sub(r'\s+', ' ', raw_item).strip()
            key = item.lower()
            if not item or key in seen:
                continue
            seen.add(key)
            if len(item) > 220:
                item = item[:217].strip() + '...'
            items.append(item)
            if len(items) >= 80:
                break
        return items

    try:
        if ext == '.txt':
            raw = upload.read()
            text = raw.decode('utf-8', errors='replace')
        elif ext == '.docx':
            with zipfile.ZipFile(upload) as docx_zip:
                xml = docx_zip.read('word/document.xml').decode('utf-8', errors='ignore')
            text = re.sub(r'</w:p[^>]*>', '\n', xml)
            text = re.sub(r'<[^>]+>', '', text)
            text = (
                text.replace('&amp;', '&')
                    .replace('&lt;', '<')
                    .replace('&gt;', '>')
                    .replace('&quot;', '"')
                    .replace('&apos;', "'")
            )
        else:
            try:
                from pypdf import PdfReader
            except ImportError:
                return JsonResponse({
                    'success': False,
                    'error': 'PDF extraction needs the pypdf package installed. DOCX and text uploads are ready now.'
                }, status=400)
            reader = PdfReader(upload)
            text = '\n\n'.join((page.extract_text() or '') for page in reader.pages)

        items = excerpt_items(text)
        if not items:
            return JsonResponse({'success': False, 'error': 'No readable text was found in that file.'}, status=400)
        return JsonResponse({'success': True, 'items': items, 'text': text[:12000], 'filename': filename})
    except zipfile.BadZipFile:
        return JsonResponse({'success': False, 'error': 'That DOCX file could not be read.'}, status=400)
    except Exception as e:
        logger.error('Material file extraction failed: %s', e, exc_info=True)
        return JsonResponse({'success': False, 'error': 'Could not extract text from that file.'}, status=500)


@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def add_reading_material(request):
    """
    Creates a new reading material (Assessment) linked to a class.
    Expects JSON: { title, reading_type, content, status, class_code, scheduled_at? }
    """
    try:
        data = json.loads(request.body)
        title        = (data.get('title') or '').strip()
        content      = (data.get('content') or '').strip()
        status       = (data.get('status') or 'published').strip()          # published | draft | scheduled
        usage_type   = (data.get('usage_type') or 'practice').strip()        # practice | assessment | both
        class_code   = (data.get('class_code') or '').strip()
        scheduled_at_str = (data.get('scheduled_at') or '').strip()
        assigned_week_raw = data.get('assigned_week')
        assigned_week, week_error = parse_assigned_week(assigned_week_raw)

        logger.debug(f"add_reading_material received: title={title}, status={status}, class_code={class_code}")

        # ── server-side validation ──────────────────────────────────────────
        errors = {}
        if not title:
            errors['title'] = 'Material title is required.'
        if not content:
            errors['content'] = 'Material content is required.'
        if usage_type not in ('practice', 'assessment', 'both'):
            errors['usage_type'] = 'Valid usage type is required.'
        if status not in ('published', 'draft', 'scheduled'):
            errors['status'] = 'Status is required.'
        if status == 'scheduled' and not scheduled_at_str:
            errors['scheduled_at'] = 'Scheduled date & time is required.'
        if week_error:
            errors['assigned_week'] = week_error

        if errors:
            logger.warning(f"add_reading_material validation failed: {errors}")
            return JsonResponse({'success': False, 'errors': errors}, status=400)

        # ── Auto-detect reading_type (Category) ──────────────────────────
        # Since we removed the field, we determine it by analyzing the content
        def detect_reading_type(text):
            # If there are double newlines, it's likely a paragraph
            if len(re.split(r'\n{2,}', text.strip())) > 1:
                return 'paragraph'
            # If there are sentence delimiters and more than 3 words, it's likely a sentence
            if re.search(r'[.!?]', text) and len(text.split()) > 3:
                return 'sentence'
            # Otherwise, treat as a word list
            return 'word'

        reading_type = detect_reading_type(content)

        def split_content(text, rtype):
            if not text:
                return []
            if rtype == 'word':
                return re.findall(r"\b[\w']+\b", text, flags=re.UNICODE)
            if rtype == 'sentence':
                return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
            if rtype == 'paragraph':
                return [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
            return [text]
        
        tokens = split_content(content, reading_type)

        # ── resolve teacher & class ─────────────────────────────────────────
        user_id = request.session.get('user_id')
        teacher_user = User.objects.filter(id=user_id).first()
        if not teacher_user or teacher_user.role != 'teacher':
            return JsonResponse({'success': False, 'error': 'Teacher not found.'}, status=404)

        section = None
        if class_code:
            section = Section.objects.filter(
                class_code=class_code,
                teacher=teacher_user,
                is_active=True
            ).first()
            if not section:
                return JsonResponse({'success': False, 'error': 'Class not found or does not belong to you.'}, status=404)

        # ── parse scheduled_at datetime if provided ─────────────────────────
        scheduled_at = None
        if status == 'scheduled' and scheduled_at_str:
            # Frontend sends ISO format from datetime-local: "2026-06-15T14:30"
            # Convert to Django timezone-aware datetime
            try:
                # datetime-local format doesn't include timezone, so add 'Z' for UTC
                if 'T' in scheduled_at_str and scheduled_at_str.count(':') >= 1:
                    # Format: "2026-06-15T14:30" or "2026-06-15T14:30:00"
                    scheduled_at = parse_datetime(scheduled_at_str + ':00' if scheduled_at_str.count(':') == 1 else scheduled_at_str)
                    if not scheduled_at:
                        # If parse_datetime fails, try adding Z for UTC
                        scheduled_at = parse_datetime(scheduled_at_str + ':00Z' if scheduled_at_str.count(':') == 1 else scheduled_at_str + 'Z')
                    if scheduled_at and not timezone.is_aware(scheduled_at):
                        # Make it timezone-aware using default timezone
                        scheduled_at = timezone.make_aware(scheduled_at)
            except Exception as e:
                logger.warning(f"Failed to parse scheduled_at: {scheduled_at_str}, error: {e}")
                return JsonResponse({'success': False, 'error': 'Invalid scheduled date & time format.'}, status=400)

        if not tokens:
            return JsonResponse({'success': False, 'error': 'No items found in content to create.'}, status=400)

        with transaction.atomic():
            # If this material is intended to be an assessment (or both), create
            # an authoritative Assessment record first and attach it to the
            # created Material so attempts can be persisted there.
            assessment_obj = None
            if usage_type in ('assessment', 'both'):
                # create a short unique assessment code
                code = 'AS' + uuid.uuid4().hex[:8].upper()
                while Assessment.objects.filter(code=code).exists():
                    code = 'AS' + uuid.uuid4().hex[:8].upper()
                assessment_obj = Assessment.objects.create(
                    title=title,
                    code=code,
                    assessment_type=reading_type,
                    content=content,
                    status=status,
                    scheduled_at=scheduled_at if status == 'scheduled' else None,
                    teacher=teacher_user,
                    section=section,
                    is_active=(status in ['published', 'scheduled'])
                )

            m = Material.objects.create(
                assessment=assessment_obj,
                section=section,
                item_type=reading_type,
                title=title,
                prompt_text=(tokens[0] if tokens else title) or title,
                content_text=content,
                content_json={'items': tokens},
                type=usage_type,
                status=status,
                scheduled_at=scheduled_at if status == 'scheduled' else None,
                difficulty_level='', # This field is not set in this context, consider if it should be
                assigned_week=assigned_week,
                is_active=(status in ['published', 'scheduled'])
            )
            if section is not None:
                m.assigned_sections.add(section)
                # Only notify students via database immediately if the material is live.
                # Scheduled materials will trigger notifications via JS once the time is reached.
                if status == 'published':
                    action_url = reverse('assessment')
                    for student_user in _section_active_students(section):
                        # In-app notification content
                        in_app_title = 'New Reading Material Available'
                        in_app_message = f'"{m.title}" is now available in {section.class_name}.'

                        # Email notification content
                        email_subject = f'Start Reading: {m.title} Is Now Available'
                        email_body = (
                            f'Hello {student_user.first_name},\n\n'
                            f'A new learning material, "{m.title}", has been published in {section.class_name} by {teacher_user.first_name} {teacher_user.last_name}.\n\n'
                            f'Log in to PABASA to access the material and continue your learning journey.\n\n'
                            f'Happy learning!\nThe PABASA Team'
                        )
                        _create_notification(
                            student_user,
                            in_app_title,
                            in_app_message,
                            'assessment',
                            action_url,
                            teacher_user,
                            email_subject=email_subject,
                            email_body=email_body,
                        )
            else:
                action_url = reverse('courses')
            _notify_admins(
                'Teacher created a new material',
                f'{teacher_user.first_name} {teacher_user.last_name} created "{m.title}".',
                'info',
                reverse('admin_course_detail', args=[m.id]),
                teacher_user,
            )
            created_ids = [m.id]
            material_payload = {
                'id': f"material-{m.id}",
                'code': None,
                'title': m.title,
                'item_type': m.item_type,
                'type': m.type,
                'content': m.content_text,
                'status': m.status,
                'schedule': timezone.localtime(m.scheduled_at, timezone.get_default_timezone()).strftime('%Y-%m-%dT%H:%M') if m.scheduled_at else None,
                'items': len(tokens),
                'created_at': m.created_at.isoformat() if getattr(m, 'created_at', None) else None,
                'assigned_sections': [section.class_code] if section else [],
                'assigned_week': m.assigned_week,
                'assigned_week_display': format_assigned_week_display(m.assigned_week),
            }

        return JsonResponse({
            'success': True,
            'message': 'Reading material(s) created successfully.',
            'material_ids': created_ids,
            'created_count': len(created_ids),
            'material': material_payload,
            'title': title,
            'type': reading_type,
            'status': status,
            'created_at': m.created_at.isoformat() if getattr(m, 'created_at', None) else None,
            'overview': _compute_teacher_overview(teacher_user),
        })

    except json.JSONDecodeError as e:
        logger.error(f"add_reading_material JSON decode error: {e}")
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload.'}, status=400)
    except Exception as e:
        logger.error(f"add_reading_material error: {type(e).__name__}: {str(e)}", exc_info=True)
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': f'Error: {str(e)}'}, status=500)

@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def teacher_update_material(request):
    """API for teachers to update existing reading materials"""
    try:
        data = json.loads(request.body)
        raw_id = data.get('material_id')
        _, material_id = _parse_prefixed_id(raw_id)
        
        user_id = request.session.get('user_id')
        if not material_id:
            return JsonResponse({'success': False, 'error': 'Invalid material ID'}, status=400)
            
        material = Material.objects.filter(
            Q(id=material_id) & (
                Q(section__teacher_id=user_id) |
                Q(assigned_sections__teacher_id=user_id) |
                Q(courses__teacher_id=user_id) |
                Q(assessment__teacher_id=user_id)
            )
        ).distinct().first()

        if not material:
            if Material.objects.filter(id=material_id).exists():
                return JsonResponse({'success': False, 'error': 'Material access denied'}, status=403)
            return JsonResponse({'success': False, 'error': 'Material not found'}, status=404)

        material.title = data.get('title', material.title).strip()
        content = data.get('content', material.content_text).strip()
        material.status = data.get('status', material.status)
        material.type = data.get('usage_type', material.type)

        if 'assigned_week' in data:
            assigned_week, week_error = parse_assigned_week(data.get('assigned_week'))
            if week_error:
                return JsonResponse({'success': False, 'errors': {'assigned_week': week_error}}, status=400)
            material.assigned_week = assigned_week
        
        material.is_active = (material.status in ['published', 'scheduled'])
        # current teacher for any potential Assessment creation
        teacher_user = User.objects.filter(id=user_id).first()

        # Handle schedule update
        if material.status == 'scheduled':
            scheduled_at_str = data.get('scheduled_at')
            if scheduled_at_str:
                try:
                    # Logic to parse browser datetime-local format and make it timezone-aware
                    dt_str = scheduled_at_str + ':00' if scheduled_at_str.count(':') == 1 else scheduled_at_str
                    dt = parse_datetime(dt_str)
                    if dt and not timezone.is_aware(dt):
                        dt = timezone.make_aware(dt)
                    material.scheduled_at = dt
                except Exception:
                    pass
        else:
            material.scheduled_at = None

        if content != material.content_text:
            material.content_text = content
            # Re-detect type and tokens if content changed
            def detect_type(text):
                if len(re.split(r'\n{2,}', text.strip())) > 1: return 'paragraph'
                if re.search(r'[.!?]', text) and len(text.split()) > 3: return 'sentence'
                return 'word'
            
            material.item_type = detect_type(content)
            material.content_json = {'items': content.split('\n') if material.item_type == 'word' else [content]}
            
        # Ensure Assessment linkage reflects the requested usage type.
        # If material should be an assessment (or both), create or update the
        # linked Assessment record so attempts are recorded in the
        # assessments table. If switching to practice, detach the link.
        try:
            if material.type in ('assessment', 'both'):
                if not getattr(material, 'assessment', None):
                    code = 'AS' + uuid.uuid4().hex[:8].upper()
                    while Assessment.objects.filter(code=code).exists():
                        code = 'AS' + uuid.uuid4().hex[:8].upper()
                    assessment = Assessment.objects.create(
                        title=material.title,
                        code=code,
                        assessment_type=material.item_type,
                        content=material.content_text or material.prompt_text or '',
                        status=material.status,
                        scheduled_at=material.scheduled_at if material.status == 'scheduled' else None,
                        teacher=teacher_user,
                        section=material.section,
                        is_active=material.is_active,
                    )
                    material.assessment = assessment
                else:
                    # Keep assessment metadata in sync (best-effort)
                    try:
                        a = material.assessment
                        a.title = material.title
                        a.assessment_type = material.item_type
                        a.content = material.content_text or material.prompt_text or ''
                        a.status = material.status
                        a.scheduled_at = material.scheduled_at if material.status == 'scheduled' else None
                        a.is_active = material.is_active
                        a.save()
                    except Exception:
                        pass
            else:
                # Switching to practice: detach assessment link but do not delete record
                if getattr(material, 'assessment', None):
                    material.assessment = None
        except Exception:
            # Non-fatal; proceed to save material regardless
            logger.exception('Failed to synchronize Assessment linkage for material %s', getattr(material, 'id', None))

        material.save()
        # Return updated overview so clients can sync UI immediately
        try:
            teacher_user = User.objects.filter(id=user_id).first()
            overview = _compute_teacher_overview(teacher_user) if teacher_user else None
        except Exception:
            overview = None
        return JsonResponse({'success': True, 'message': 'Material updated successfully', 'overview': overview})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def teacher_update_practice(request):
    """Allow teachers to update Practice items (title, content, status)."""
    try:
        data = json.loads(request.body)
        raw_id = data.get('practice_id')
        _, practice_id = _parse_prefixed_id(raw_id)

        user_id = request.session.get('user_id')
        # Debug logging: record the incoming practice id and user for troubleshooting
        try:
            logger.info('teacher_update_practice called - user_id=%s raw_id=%s parsed_practice_id=%s payload_keys=%s',
                        user_id, raw_id, practice_id, list(data.keys()))
        except Exception:
            logger.exception('Failed to log teacher_update_practice invocation')
        if not practice_id:
            return JsonResponse({'success': False, 'error': 'Invalid practice ID'}, status=400)

        practice = Practice.objects.filter(
            Q(id=practice_id) & (Q(teacher_id=user_id) | Q(section__teacher_id=user_id))
        ).distinct().first()
        if not practice:
            if Practice.objects.filter(id=practice_id).exists():
                return JsonResponse({'success': False, 'error': 'Practice access denied'}, status=403)
            return JsonResponse({'success': False, 'error': 'Practice not found'}, status=404)

        title = data.get('title')
        content = data.get('content')
        status = data.get('status')

        if title is not None:
            practice.title = title.strip()
        if content is not None:
            practice.content_text = content.strip()
        if status is not None:
            practice.status = status
            practice.is_active = (status in ['published', 'scheduled'])

        practice.save()
        return JsonResponse({'success': True, 'message': 'Practice updated successfully'})
    except Exception as e:
        logger.exception('Error updating practice')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def delete_practice(request):
    """Allow teachers to delete their own Practice items."""
    try:
        data = json.loads(request.body)
        raw_id = data.get('practice_id')
        _, practice_id = _parse_prefixed_id(raw_id)

        user_id = request.session.get('user_id')
        if not practice_id:
            return JsonResponse({'success': False, 'error': 'Practice ID is required'}, status=400)

        practice = Practice.objects.filter(id=practice_id, teacher_id=user_id).first()
        if not practice:
            return JsonResponse({'success': False, 'error': 'Practice not found or access denied'}, status=404)

        practice.delete()
        return JsonResponse({'success': True, 'message': 'Practice deleted successfully'})
    except Exception as e:
        logger.exception('Error deleting practice')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def delete_reading_material(request):
    """API for teachers to permanently delete a reading material"""
    try:
        data = json.loads(request.body)
        raw_id = data.get('material_id')
        _, material_id = _parse_prefixed_id(raw_id)
        
        if not material_id:
            return JsonResponse({'success': False, 'error': 'Material ID is required'}, status=400)
            
        user_id = request.session.get('user_id')
        if not user_id:
            return JsonResponse({'success': False, 'error': 'Session expired. Please log in again.'}, status=401)

        # Find the material. We check both the direct section link and assigned_sections
        material = Material.objects.filter(
            Q(id=material_id) & (
                Q(section__teacher_id=user_id) |
                Q(assigned_sections__teacher_id=user_id) |
                Q(courses__teacher_id=user_id) |
                Q(assessment__teacher_id=user_id)
            )
        ).distinct().first()
        
        if not material:
            return JsonResponse({'success': False, 'error': 'Material not found or access denied'}, status=404)

        material.delete()
        try:
            teacher_user = User.objects.filter(id=user_id).first()
            overview = _compute_teacher_overview(teacher_user) if teacher_user else None
        except Exception:
            overview = None
        return JsonResponse({'success': True, 'message': 'Material deleted successfully', 'overview': overview})
    except Exception as e:
        logger.error(f"Error deleting material: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_protect
@require_http_methods(["POST"])
@login_required(role='student')
def record_assessment_completion(request):
    """Handles notification when student completes reading material."""
    try:
        data = json.loads(request.body)
        assessment_id = data.get('assessment_id')
        material_id = data.get('material_id')
        is_retake = data.get('is_retake', False)
        attempt_number = data.get('attempt_number', 0)
        activity_type = data.get('activity_type', 'assessment')
        student_user = User.objects.get(id=request.session.get('user_id'))

        assessment = None
        teacher_user = None
        title_text = None
        material = None
        practice_obj = None

        a_prefix, a_id = _parse_prefixed_id(assessment_id)
        m_prefix, m_id = _parse_prefixed_id(material_id)

        # Prefer explicit assessment identifier
        if a_id and (a_prefix is None or a_prefix.startswith('assessment')):
            assessment = Assessment.objects.select_related('teacher').filter(id=a_id).first()
            if assessment:
                teacher_user = assessment.teacher
                title_text = assessment.title
        # material_id may refer to an Assessment (prefixed), Material, or Practice record
        if not assessment and m_id and m_prefix and m_prefix.startswith('assessment'):
            assessment = Assessment.objects.select_related('teacher').filter(id=m_id).first()
            if assessment:
                teacher_user = assessment.teacher
                title_text = assessment.title

        if not assessment and m_id and (m_prefix is None or m_prefix.startswith('material')):
            material = Material.objects.select_related('assessment', 'section__teacher').filter(id=m_id).first()
            if material:
                if material.assessment:
                    assessment = material.assessment
                    teacher_user = material.assessment.teacher
                elif material.section:
                    teacher_user = material.section.teacher
                title_text = material.title or material.content_text or material.prompt_text or material.item_type
        # support practice ids (practice-<id>) that map to Practice model
        if not assessment and m_id and m_prefix and m_prefix.startswith('practice'):
            try:
                from .models import Practice as PracticeModel
                practice_obj = PracticeModel.objects.select_related('teacher').filter(id=m_id).first()
                if practice_obj:
                    title_text = practice_obj.title or practice_obj.content_text or practice_obj.prompt_text
                    teacher_user = getattr(practice_obj, 'teacher', None)
            except Exception:
                practice_obj = None

        if not assessment and not material and not practice_obj:
            return JsonResponse({'success': False, 'error': 'No assessment_id or material_id provided.'}, status=400)

        class_code = data.get('class_code')
        is_practice = activity_type == 'practice' or (practice_obj is not None) or (material and material.section is None and material.assessment is None)
        already_completed = False
        if not is_practice:
            already_completed = _student_completed_assessment_before(assessment, material, student_user)

        # Record attempt server-side (authoritative). We mark attempts as completed
        # because this endpoint is called when the student finishes the reading flow.
        try:
            device_info = {
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'remote_addr': request.META.get('REMOTE_ADDR', ''),
            }
            if assessment:
                assessment.record_attempt(student_user, status='completed', completed_at=timezone.now().isoformat(), device_info=device_info)
            elif practice_obj:
                practice_obj.record_attempt(student_user, replace=True, status='completed', completed_at=timezone.now().isoformat(), device_info=device_info)
            elif material and getattr(material, 'assessment', None):
                # Material linked to an Assessment
                material.assessment.record_attempt(student_user, status='completed', completed_at=timezone.now().isoformat(), device_info=device_info)
            # Note: standalone Material objects that are not linked to Assessment do not
            # currently have an attempts schema; they are handled by client-side notifications.
        except Exception as e:
            logger.exception('Failed to persist assessment/practice attempt: %s', e)

        student_name = f"{student_user.first_name} {student_user.last_name}".strip() or student_user.custom_id
        class_name = _resolve_assessment_class_name(assessment=assessment, material=material, class_code=class_code)

        email_subject = None
        if is_retake:
            title = "Student Retook an Assessment"
            display_class = class_name or "a class"
            notif_msg = f'{student_name} retook the assessment "{title_text}" in {display_class}.'
            email_subject = "Student Retook an Assessment"
        elif is_practice:
            title = "Student Completed a Practice Material"
            display_class = class_name or "a class"
            notif_msg = f'{student_name} read "{title_text}" in {display_class}.'
        else:
            title = "Student Completed an Assessment"
            notif_msg = _assessment_completion_message(student_name, title_text, class_name)

        should_notify_assessment = (
            not is_practice
            and (is_retake or not already_completed)
        )

        teacher_recipients = []
        if is_practice:
            if teacher_user:
                teacher_recipients.append(teacher_user)
            else:
                for section in Section.objects.filter(is_active=True).select_related('teacher'):
                    if section.has_student(student_user, active_only=True) and section.teacher:
                        teacher_recipients.append(section.teacher)
        elif should_notify_assessment:
            teacher_recipients = _teachers_for_assessment_completion(
                assessment=assessment,
                material=material,
                student_user=student_user,
            )

        seen_teacher_ids = set()
        for recipient in teacher_recipients:
            if recipient.id in seen_teacher_ids:
                continue
            seen_teacher_ids.add(recipient.id)

            if not is_practice and _assessment_completion_notif_exists(
                recipient, student_user, notif_msg, is_retake=is_retake
            ):
                continue
            
            current_email_body = None
            if is_retake:
                teacher_name = f"{recipient.first_name} {recipient.last_name}"
                display_class = class_name or "a class"
                current_email_body = (
                    f"Hello {teacher_name},\n\n"
                    f"This is to inform you that {student_name} has completed retake attempt {attempt_number} of 3 "
                    f"for \"{title_text}\" in {display_class}.\n\n"
                    "You may review the student's latest submission and performance through your PABASA dashboard.\n\n"
                    "Thank you,\n\n"
                    "The PABASA Team"
                )

            _create_notification(
                recipient,
                title,
                notif_msg,
                "assessment",
                f"/dashboard/teacher/students/detail/?student_id={student_user.custom_id}",
                student_user,
                email_subject=email_subject,
                email_body=current_email_body,
            )

        if should_notify_assessment or is_practice:
            _notify_admins(
                title,
                notif_msg,
                "assessment",
                reverse('admin_students'),
                student_user,
            )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@require_http_methods(["GET"])
@login_required()
def get_notifications(request):
    """API: Fetch latest notifications for the user."""
    user = User.objects.get(id=request.session.get('user_id'))
    notifs = Notification.objects.filter(recipient=user).values(
        'id', 'title', 'message', 'notification_type', 'is_read', 'action_url', 'created_at'
    )
    return JsonResponse({'success': True, 'notifications': list(notifs)})

@require_http_methods(["GET"])
@login_required()
def get_unread_notification_count(request):
    """API: Get unread count for badge."""
    user = User.objects.get(id=request.session.get('user_id'))
    count = Notification.objects.filter(recipient=user, is_read=False).count()
    return JsonResponse({'success': True, 'unread_count': count})

@csrf_protect
@require_http_methods(["POST"])
@login_required()
def mark_notification_read(request):
    """API: Mark a notification as read."""
    try:
        data = json.loads(request.body)
        notif_id = data.get('notification_id')
        user = User.objects.get(id=request.session.get('user_id'))
        Notification.objects.filter(id=notif_id, recipient=user).update(is_read=True)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@require_http_methods(["GET"])
@login_required(role='teacher')
def get_teacher_students_api(request):
    """
    Authority source for all students associated with a teacher.
    Aggregates students from all active sections owned by the teacher.
    """
    try:
        user_id = request.session.get('user_id')
        teacher = User.objects.get(id=user_id)
        
        # Get all active sections for this teacher
        sections = Section.objects.filter(teacher=teacher, is_active=True)
        
        student_map = {}
        for section in sections:
            enrolled = section.get_enrolled_students(active_only=True)
            for entry in enrolled:
                raw_sid = entry.get('student_id')
                if not raw_sid:
                    continue

                try:
                    sid = int(raw_sid)
                except (TypeError, ValueError):
                    logger.warning(
                        "Skipping enrolled student with invalid student_id %r in section %s",
                        raw_sid,
                        section.class_code,
                    )
                    continue

                sid_key = str(sid)
                
                if sid_key not in student_map:
                    student_map[sid_key] = {
                        'id': sid,
                        'name': f"{entry.get('first_name')} {entry.get('last_name')}",
                        'email': entry.get('email', ''),
                        'custom_id': entry.get('custom_id', ''),
                        'classes': [section.class_name],
                        'class_codes': [section.class_code]
                    }
                else:
                    if section.class_name not in student_map[sid_key]['classes']:
                        student_map[sid_key]['classes'].append(section.class_name)
                    if section.class_code not in student_map[sid_key]['class_codes']:
                        student_map[sid_key]['class_codes'].append(section.class_code)
        
        user_ids = [sdata['id'] for sdata in student_map.values()]
        users = User.objects.filter(id__in=user_ids).in_bulk()
        
        results = []
        for sdata in student_map.values():
            user = users.get(sdata['id'])
            if user:
                # Extract metrics from profile tags
                profile = {}
                if isinstance(user.tags, list):
                    for tag in user.tags:
                        if isinstance(tag, dict) and 'student_profile' in tag:
                            profile = tag['student_profile']
                            break
                
                sdata.update({
                    'level': user.reading_level or profile.get('reading_level', 'Developing Readers'),
                    'accuracy': profile.get('accuracy', '0'),
                    'wpm': profile.get('wpm', '0'),
                })
                results.append(sdata)
        return JsonResponse({'success': True, 'students': results})
    except Exception as e:
        logger.error(f"Error in get_teacher_students_api: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# =================================================================================
# PRINCIPAL DASHBOARD VIEWS (UI/UX Layout - Placeholder Data Only)
# =================================================================================

def _parse_user_agent(user_agent):
    """Parse user agent string to extract browser and OS info."""
    if not user_agent:
        return 'Unknown Device'
    ua = user_agent.lower()
    browser = 'Unknown Browser'
    os = 'Unknown OS'
    if 'edg/' in ua:
        browser = 'Edge'
    elif 'chrome/' in ua and 'chromium' not in ua:
        browser = 'Chrome'
    elif 'firefox/' in ua:
        browser = 'Firefox'
    elif 'safari/' in ua and 'chrome' not in ua:
        browser = 'Safari'
    if 'windows' in ua:
        os = 'Windows'
    elif 'macintosh' in ua or 'mac os x' in ua:
        os = 'macOS'
    elif 'linux' in ua:
        os = 'Linux'
    elif 'android' in ua:
        os = 'Android'
    elif 'iphone' in ua or 'ipad' in ua:
        os = 'iOS'
    return f'{browser} on {os}'


def _principal_context(request, page_title):
    """Helper function to generate context for Principal pages"""
    user = User.objects.filter(id=request.session.get('user_id')).first()
    if user:
        first_name = user.first_name
        last_name = user.last_name
        middle_initial = user.middle_initial
        profile_info = _get_profile_dict(user, 'principal_profile_info') or {}
        if not isinstance(profile_info, dict):
            profile_info = {}
        position = profile_info.get('position', 'Head Teacher/Principal II')
    else:
        first_name = request.session.get('first_name', 'Jobelyn')
        last_name = request.session.get('last_name', 'Valdez')
        middle_initial = ''
        position = 'Head Teacher/Principal II'
    return {
        'principal_id': request.session.get('custom_id', 'PRN-SES'),
        'first_name': first_name,
        'last_name': last_name,
        'middle_initial': middle_initial,
        'position': position,
        'page_title': page_title,
    }

def principal_required(view_func):
    """Decorator to check if user is Principal"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not _check_auth(request):
            return redirect('auth')
        # For now, we'll allow admin or principal role to access
        # Update this when principal authentication is fully implemented
        if request.session.get('user_role') not in ['admin', 'principal']:
            return redirect('auth')
        return view_func(request, *args, **kwargs)
    return wrapper

@principal_required
def dashboard_principal(request):
    """Principal Dashboard - Main overview with greeting, statistics, and recent activities"""
    context = _principal_context(request, 'Dashboard')

    # Build the display name dynamically from the user's personal information
    name_parts = [context.get('first_name', '')]
    if context.get('middle_initial'):
        name_parts.append(context['middle_initial'] + '.')
    if context.get('last_name'):
        name_parts.append(context['last_name'])
    greeting_name = ' '.join(name_parts).strip() or 'Principal'

    context.update({
        'greeting_name': greeting_name,
        'greeting_title': context.get('position', 'Head Teacher/Principal II'),
        'school_name': 'Salawag Elementary School',
    })
    return render(request, 'pabasa_app/principal_dashboard.html', context)

@principal_required
def principal_performance(request):
    """Principal Performance Page - Grade performance, completion rates, and trends"""
    context = _principal_context(request, 'Performance')
    # Placeholder data for performance tracking
    context.update({
        'current_month_performance': '82.5%',
        'completion_rate': '78%',
        'ytd_progress': '74%',
    })
    return render(request, 'pabasa_app/principal_performance.html', context)

@principal_required
def principal_assessments(request):
    """Principal Assessments Page - Assessment overview and results"""
    context = _principal_context(request, 'Assessments')
    # Placeholder data for assessments
    context.update({
        'total_assessments': 35,
        'in_progress': 12,
        'completed': 18,
        'pending': 5,
    })
    return render(request, 'pabasa_app/principal_assessments.html', context)

@principal_required
def principal_reports(request):
    """Principal Reports Page - Generate and view reports"""
    context = _principal_context(request, 'Reports')
    # Placeholder data for reports
    context.update({
        'report_types': [
            'School Performance',
            'Grade-Level',
            'Assessment',
        ],
    })
    return render(request, 'pabasa_app/principal_reports.html', context)

@csrf_protect
@require_http_methods(["GET", "POST"])
@principal_required
def principal_settings(request):
    """Principal Settings Page - School information and account settings"""
    user = User.objects.filter(id=request.session.get('user_id')).first()
    if not user:
        request.session.flush()
        return redirect('auth')

    context = _principal_context(request, 'Settings')
    notification_settings = _notification_settings_for_user(user)

    default_school_info = {
        'name': 'Salawag Elementary School',
        'code': 'SES-2024',
        'municipality': 'Imus',
        'province': 'Cavite',
        'district': 'District 4',
        'region': 'CALABARZON',
        'address': 'Salawag, Imus, Cavite',
        'contact': '(046) 555-0123',
        'email': 'salawag.elementary@deped.gov.ph',
    }
    default_academic_settings = {
        'academic_year': '2024-2025',
        'term': '2',
        'school_year_start': '2024-06-03',
        'school_year_end': '2025-04-30',
    }

    school_info = _get_profile_dict(user, 'principal_school_info') or {}
    academic_settings = _get_profile_dict(user, 'principal_academic_settings') or {}
    principal_profile_info = _get_profile_dict(user, 'principal_profile_info') or {}
    if not isinstance(school_info, dict):
        school_info = {}
    if not isinstance(academic_settings, dict):
        academic_settings = {}
    if not isinstance(principal_profile_info, dict):
        principal_profile_info = {}

    if request.method == 'POST':
        action = request.POST.get('settings_action', '').strip()

        if action == 'save_school_info':
            school_info = {
                'name': request.POST.get('school_name', '').strip() or default_school_info['name'],
                'code': request.POST.get('school_code', '').strip() or default_school_info['code'],
                'municipality': request.POST.get('municipality', '').strip() or default_school_info['municipality'],
                'province': request.POST.get('province', '').strip() or default_school_info['province'],
                'district': request.POST.get('district', '').strip() or default_school_info['district'],
                'region': request.POST.get('region', '').strip() or default_school_info['region'],
                'address': request.POST.get('address', '').strip() or default_school_info['address'],
                'contact': request.POST.get('contact', '').strip() or default_school_info['contact'],
                'email': request.POST.get('email', '').strip() or default_school_info['email'],
            }
            _set_profile_dict(user, 'principal_school_info', school_info)
            context['settings_success'] = 'School information updated.'

        elif action == 'save_academic_year':
            academic_settings = {
                'academic_year': request.POST.get('academic_year', '').strip() or default_academic_settings['academic_year'],
                'term': request.POST.get('term', '').strip() or default_academic_settings['term'],
                'school_year_start': request.POST.get('school_year_start', '').strip() or default_academic_settings['school_year_start'],
                'school_year_end': request.POST.get('school_year_end', '').strip() or default_academic_settings['school_year_end'],
            }
            _set_profile_dict(user, 'principal_academic_settings', academic_settings)
            context['settings_success'] = 'Academic year settings updated.'

        elif action == 'change_password':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not current_password or not new_password or not confirm_password:
                context['settings_error'] = 'All password fields are required.'
            elif not check_password(current_password, user.password_hash):
                context['settings_error'] = 'Current password is incorrect.'
            elif new_password != confirm_password:
                context['settings_error'] = 'New passwords do not match.'
            elif len(new_password) < 8:
                context['settings_error'] = 'Password must be at least 8 characters.'
            else:
                user.password_hash = make_password(new_password)
                user.save(update_fields=['password_hash', 'updated_at'])
                context['settings_success'] = 'Password changed successfully.'

        elif action == 'save_personal_info':
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            middle_initial = request.POST.get('middle_initial', '').strip()
            email = request.POST.get('email', '').strip()
            contact_number = request.POST.get('contact_number', '').strip()
            position = request.POST.get('position', '').strip()

            if not first_name or not last_name:
                context['settings_error'] = 'First name and last name are required.'
            else:
                user.first_name = first_name
                user.last_name = last_name
                user.middle_initial = middle_initial if middle_initial else ''
                user.email = email
                user.contact_no = contact_number
                request.session['first_name'] = user.first_name
                request.session['last_name'] = user.last_name
                request.session['middle_initial'] = user.middle_initial
                user.save(update_fields=['first_name', 'last_name', 'middle_initial', 'email', 'contact_no', 'updated_at'])
                profile_info = _get_profile_dict(user, 'principal_profile_info') or {}
                if not isinstance(profile_info, dict):
                    profile_info = {}
                profile_info['position'] = position or 'Head Teacher/Principal II'
                _set_profile_dict(user, 'principal_profile_info', profile_info)
                context['settings_success'] = 'Personal information updated.'

        elif action == 'save_notifications':
            notification_settings = _posted_notification_settings(request)
            _set_profile_dict(user, 'notification_settings', notification_settings)
            context['settings_success'] = 'Notification preferences updated.'

        else:
            context['settings_error'] = 'Unknown settings action.'

    last_login_dt = user.updated_at if isinstance(user.updated_at, datetime) else datetime.fromisoformat(str(user.updated_at)) if user.updated_at else None
    account_created_dt = user.created_at if isinstance(user.created_at, datetime) else datetime.fromisoformat(str(user.created_at)) if user.created_at else None
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    browser_device = _parse_user_agent(user_agent)
    context.update({
        'school_info': {**default_school_info, **school_info},
        'academic_settings': {**default_academic_settings, **academic_settings},
        'principal_profile_info': {
            'position': principal_profile_info.get('position', 'Head Teacher/Principal II'),
        },
        'first_name': user.first_name,
        'last_name': user.last_name,
        'middle_initial': user.middle_initial,
        'email': user.email,
        'contact_number': user.contact_no or '',
        'notification_settings': notification_settings,
        'last_login': last_login_dt.strftime('%B %d, %Y') if last_login_dt else 'N/A',
        'account_created': account_created_dt.strftime('%B %d, %Y') if account_created_dt else 'N/A',
        'browser_device': browser_device,
    })
    return render(request, 'pabasa_app/principal_settings.html', context)
