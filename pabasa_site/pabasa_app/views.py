from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.cache import never_cache
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import EmailMultiAlternatives
from django.core import signing
from django.contrib.auth import authenticate, login
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.text import slugify
from functools import wraps
from urllib.parse import quote
import logging
import json
import os
import shutil
from pathlib import Path
from html import escape
import random
import traceback
import ssl
import time
import uuid
import zipfile
import csv
from io import BytesIO

# Use a platform-aware Tesseract path so OCR works in local and deployed environments.
TESSERACT_STATIC_PATH = (
    os.environ.get('TESSERACT_CMD')
    or os.environ.get('TESSERACT_PATH')
    or (r"C:\Program Files\Tesseract-OCR\tesseract.exe" if os.name == 'nt' else '/usr/bin/tesseract')
)
IMAGE_OCR_EMPTY_MESSAGE = (
    'No readable text could be recovered from that image. '
    'Try a straight, well-lit photo with the words in focus, dark text on a light background, '
    'and minimal extra space around the page.'
)
try:
    import pytesseract
    if os.path.isfile(TESSERACT_STATIC_PATH):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_STATIC_PATH
except Exception:
    pass

from .forms import AdminPracticeMaterialForm, parse_practice_items
from .test_accounts import PRINCIPAL_DEFAULT_CUSTOM_ID, ensure_default_principal_account
from django.db import transaction
import re
import traceback
from .models import User, Section, Assessment, Material, Practice, Note, Notification, Course
from .reading_material_utils import format_assigned_week_display, parse_assigned_week
from .reading_stt import (
    analyze_reading,
    language_code_for,
    phrase_hints_for,
    synthesize_read_aloud_audio,
    transcribe_audio_bytes_with_model,
)

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

def _create_notification(recipient, title, message, notification_type='info', action_url='', created_by=None, email_subject=None, email_body=None, send_email=True, force_in_app=False):
    if not recipient:
        return None

    settings_dict = _notification_settings_for_user(recipient)
    notification = None
    if force_in_app or settings_dict.get('push_enabled') is True:
        notification = Notification.objects.create(
            recipient=recipient,
            created_by=created_by,
            title=title,
            message=message,
            notification_type=notification_type,
            action_url=action_url or '',
        )

    if not send_email:
        return notification

    # REAL-TIME EMAIL DISPATCH: Send email immediately if user preference allows
    try:
        if settings_dict.get('email_notifications') is True and getattr(recipient, 'email', ''):
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

def _notify_admins(title, message, notification_type='info', action_url='', created_by=None, send_email=True):
    for admin_user in _admin_users():
        _create_notification(admin_user, title, message, notification_type, action_url, created_by, send_email=send_email)


def _principal_users():
    return User.objects.filter(role='principal', is_archived=False)


def _notification_recently_sent(recipient, title, message, window_minutes=1440):
    if not recipient:
        return False
    window_start = timezone.now() - timedelta(minutes=window_minutes)
    return Notification.objects.filter(
        recipient=recipient,
        title=title,
        message=message,
        created_at__gte=window_start,
    ).exists()


def _notify_principals(title, message, notification_type='info', action_url='', created_by=None, send_email=False, force_in_app=True):
    sent_count = 0
    for principal_user in _principal_users():
        if _notification_recently_sent(principal_user, title, message, window_minutes=1440):
            continue
        created = _create_notification(
            principal_user,
            title,
            message,
            notification_type,
            action_url or reverse('dashboard_principal'),
            created_by,
            send_email=send_email,
            force_in_app=force_in_app,
        )
        if created is not None:
            sent_count += 1
    return sent_count


def _notify_principal_performance_events(student_user, assessment=None, material=None, class_name=None, score_payload=None):
    if not student_user:
        return []

    section = None
    if assessment and assessment.section:
        section = assessment.section
    elif material and material.section:
        section = material.section
    elif material and hasattr(material, 'assigned_sections'):
        section = material.assigned_sections.filter(is_active=True).first()

    if not section:
        return []

    now = timezone.now()
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)

    def _section_weekly_average(section_obj):
        scores = [
            float(score)
            for score in Assessment.objects.filter(
                section=section_obj,
                is_active=True,
                attempt_status='completed',
                completed_at__gte=week_start,
                completed_at__lt=week_end,
                total_score__isnull=False,
            ).values_list('total_score', flat=True)
            if score is not None
        ]
        if not scores:
            return None
        return round(sum(scores) / len(scores), 1)

    current_week_avg = _section_weekly_average(section)
    score_value = None
    if score_payload:
        score_value = score_payload.get('total_score')
        if score_value is None:
            score_value = score_payload.get('score')
    if score_value is None and assessment:
        score_value = getattr(assessment, 'total_score', None)

    other_sections = []
    for other_section in Section.objects.filter(is_active=True).exclude(id=section.id):
        average = _section_weekly_average(other_section)
        if average is not None:
            other_sections.append(average)
    highest_weekly_avg = max(other_sections) if other_sections else None
    if current_week_avg is not None and (highest_weekly_avg is None or current_week_avg > highest_weekly_avg):
        _notify_principals(
            'Top-performing class of the week',
            f"{section.class_name} achieved the highest reading score this week at {current_week_avg:.1f}%.",
            'success',
            reverse('dashboard_principal'),
            student_user,
            send_email=False,
        )

    previous_week_start = week_start - timedelta(days=7)
    previous_week_end = week_start

    def _school_weekly_average(start_dt, end_dt):
        scores = [
            float(score)
            for score in Assessment.objects.filter(
                is_active=True,
                attempt_status='completed',
                completed_at__gte=start_dt,
                completed_at__lt=end_dt,
                total_score__isnull=False,
            ).values_list('total_score', flat=True)
            if score is not None
        ]
        if not scores:
            return None
        return round(sum(scores) / len(scores), 1)

    current_school_average = _school_weekly_average(week_start, week_end)
    previous_school_average = _school_weekly_average(previous_week_start, previous_week_end)
    if current_school_average is not None and previous_school_average is not None and current_school_average > previous_school_average + 0.5:
        _notify_principals(
            'School reading performance improved',
            f'The school reading performance improved from {previous_school_average:.1f}% to {current_school_average:.1f}% this week.',
            'success',
            reverse('dashboard_principal'),
            student_user,
            send_email=False,
        )

    if current_week_avg is not None and current_week_avg < 70:
        _notify_principals(
            'Reading intervention needed',
            f"{section.class_name} needs reading intervention support after averaging {current_week_avg:.1f}% this week.",
            'warning',
            reverse('dashboard_principal'),
            student_user,
            send_email=False,
        )

    if score_value is not None and score_value >= 90:
        _notify_principals(
            'Outstanding reading outcomes',
            f"{section.class_name} achieved outstanding reading outcomes with a score of {score_value:.1f}%.",
            'success',
            reverse('dashboard_principal'),
            student_user,
            send_email=False,
        )

    return []


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
        if getattr(material, 'teacher', None):
            add_teacher(material.teacher)
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
    if material and hasattr(material, "has_student_completed") and material.has_student_completed(student_user):
        return True
    if assessment and assessment.has_student_completed(student_user):
        return True
    if material and material.assessment and material.assessment.has_student_completed(student_user):
        return True
    return False

CRLA_CLASSIFICATIONS = [
    (95, "Readers at Grade Level"),
    (85, "Transitioning Readers"),
    (75, "Developing Readers"),
    (60, "High Emerging Readers"),
    (0, "Low Emerging Readers"),
]


def _clamp_score(value, default=0):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    return round(max(0, min(100, numeric)), 2)


def _crla_classification(total_score):
    score = _clamp_score(total_score)
    for threshold, label in CRLA_CLASSIFICATIONS:
        if score >= threshold:
            return label
    return CRLA_CLASSIFICATIONS[-1][1]


def _assessment_score_payload(data):
    """Normalize assessment scoring values submitted by the reader."""
    raw = data.get('scores') if isinstance(data.get('scores'), dict) else data
    fluency = _clamp_score(raw.get('fluency_score', raw.get('fluency')))
    accuracy = _clamp_score(raw.get('accuracy', raw.get('accuracy_score')))
    pronunciation = _clamp_score(raw.get('pronunciation_score', raw.get('pronunciation')))
    time_score = _clamp_score(raw.get('time_score', raw.get('time')))
    total = raw.get('total_score')
    if total is None:
        total = round((fluency + accuracy + pronunciation + time_score) / 4, 2)
    else:
        total = _clamp_score(total)
    classification = raw.get('crla_classification') or raw.get('classification') or _crla_classification(total)

    try:
        wpm = round(max(0, float(raw.get('wpm', 0))), 2)
    except (TypeError, ValueError):
        wpm = 0
    try:
        duration_seconds = round(max(0, float(raw.get('duration_seconds', 0))), 2)
    except (TypeError, ValueError):
        duration_seconds = 0
    try:
        word_count = max(0, int(float(raw.get('word_count', 0))))
    except (TypeError, ValueError):
        word_count = 0

    needs_manual_review = bool(raw.get('needs_manual_review', False))
    remarks = raw.get('remarks') or (
        "Speech recognition unavailable; review recording manually."
        if needs_manual_review else
        f"CRLA classification: {classification}."
    )

    return {
        'fluency_score': fluency,
        'accuracy': accuracy,
        'pronunciation_score': pronunciation,
        'time_score': time_score,
        'total_score': total,
        'crla_classification': classification,
        'classification': classification,
        'wpm': wpm,
        'duration_seconds': duration_seconds,
        'word_count': word_count,
        'transcript': str(raw.get('transcript', ''))[:5000],
        'speech_recognition_used': bool(raw.get('speech_recognition_used', False)),
        'needs_manual_review': needs_manual_review,
        'passed': total >= 75,
        'remarks': remarks,
    }


def _practice_score_payload(data):
    """Build a lightweight practice score payload from student reading actions."""
    raw = data.get('scores') if isinstance(data.get('scores'), dict) else data
    correct_responses = int(raw.get('correct_responses', raw.get('correct', 0)) or 0)
    incorrect_responses = int(raw.get('incorrect_responses', raw.get('incorrect', 0)) or 0)
    items_completed = int(raw.get('items_completed') or 0)
    try:
        total_practice_items = max(0, int(raw.get('total_practice_items') or items_completed or 0))
    except (TypeError, ValueError):
        total_practice_items = items_completed
    try:
        total_read_words = max(0, int(raw.get('total_read_words') or 0))
    except (TypeError, ValueError):
        total_read_words = 0
    try:
        total_skipped_words = max(0, int(raw.get('total_skipped_words') or 0))
    except (TypeError, ValueError):
        total_skipped_words = 0
    total_attempts = correct_responses + incorrect_responses
    if total_attempts <= 0 and items_completed > 0:
        total_attempts = items_completed
    if total_attempts <= 0:
        accuracy = 0
    else:
        accuracy = round((correct_responses / total_attempts) * 100, 2)
    score = raw.get('score')
    if score is None:
        score = accuracy
    score = _clamp_score(score)

    reading_time_seconds = raw.get('reading_time_seconds') or raw.get('duration_seconds') or 0
    try:
        reading_time_seconds = max(0, float(reading_time_seconds))
    except (TypeError, ValueError):
        reading_time_seconds = 0

    duration_seconds = reading_time_seconds
    if duration_seconds > 0:
        wpm = round((correct_responses / (duration_seconds / 60.0)), 2) if correct_responses else 0
    else:
        wpm = 0

    attempt_number = raw.get('attempt_number') or 1
    try:
        attempt_number = int(attempt_number)
    except (TypeError, ValueError):
        attempt_number = 1

    return {
        'score': score,
        'accuracy': accuracy,
        'total_score': score,
        'correct_responses': correct_responses,
        'incorrect_responses': incorrect_responses,
        'reading_time_seconds': duration_seconds,
        'duration_seconds': duration_seconds,
        'wpm': wpm,
        'attempt_number': attempt_number,
        'items_completed': items_completed or total_attempts,
        'total_practice_items': total_practice_items,
        'total_read_words': total_read_words,
        'total_skipped_words': total_skipped_words,
        'passed': score >= 75,
        'remarks': _practice_feedback_message(score),
    }


PRACTICE_FEEDBACK_RULES = (
    (90, "🎉 Excellent work! You're all ready for when an assessment comes. Keep up the amazing reading!"),
    (80, "🌟 Great job! You're doing very well. A little more practice and you'll be assessment-ready!"),
    (70, "👏 Good work! You're making great progress. Keep practicing to become an even stronger reader."),
    (60, "📖 Nice effort! You're improving every time you practice. Keep reading and you'll continue to get better."),
    (50, "💪 Keep going! You're learning with every practice session. Read carefully and don't give up!"),
    (0, "💙 Don't worry! Every great reader starts with practice. Keep trying—you'll improve one word at a time!"),
)


def _practice_feedback_message(score):
    normalized_score = max(0, min(100, float(score or 0)))
    for threshold, message in PRACTICE_FEEDBACK_RULES:
        if normalized_score >= threshold:
            return message
    return PRACTICE_FEEDBACK_RULES[-1][1]


def _update_student_reading_profile(student_user, score_payload):
    profile = _get_profile_dict(student_user, 'student_profile')
    if not isinstance(profile, dict):
        profile = {}
    profile.update({
        'reading_level': score_payload['crla_classification'],
        'accuracy': str(round(score_payload['accuracy'])),
        'wpm': str(round(score_payload['wpm'])),
        'fluency_score': score_payload['fluency_score'],
        'pronunciation_score': score_payload['pronunciation_score'],
        'time_score': score_payload['time_score'],
        'total_score': score_payload['total_score'],
        'crla_classification': score_payload['crla_classification'],
        'last_assessment_at': timezone.now().isoformat(),
    })
    student_user.reading_level = score_payload['crla_classification']
    _set_profile_dict(student_user, 'student_profile', profile)
    try:
        student_user.save(update_fields=['reading_level', 'updated_at'])
    except Exception:
        student_user.save()

def _section_active_students(section):
    student_ids = [
        entry.get('student_id')
        for entry in _section_students(section, active_only=True)
        if entry.get('student_id')
    ]
    return User.objects.filter(id__in=student_ids, role='student', is_archived=False)


def _normalized_student_entry_id(entry):
    student_id = entry.get('student_id') if isinstance(entry, dict) else None
    if student_id is None or student_id == '':
        return ''
    return str(student_id).strip()


def _latest_student_reading_report(student_user, sections=None, course=None):
    """Build the latest reading report for a student from assessment attempts/profile data."""
    profile = _get_profile_dict(student_user, 'student_profile')
    if not isinstance(profile, dict):
        profile = {}

    joined_classes = []
    if sections:
        for section in sections:
            if not section:
                continue
            label = getattr(section, 'class_name', '') or getattr(section, 'class_code', '') or ''
            if label:
                joined_classes.append(label)
    if not joined_classes and getattr(course, 'title', ''):
        joined_classes.append(getattr(course, 'title', ''))
    if not isinstance(profile, dict):
        profile = {}

    latest = {}
    latest_dt = None
    if sections is not None:
        assessments = Assessment.objects.filter(section__in=sections, is_active=True, source_assessment__isnull=True)
        for assessment in assessments:
            attempts = assessment.get_attempts()
            for attempt in attempts:
                if not isinstance(attempt, dict) or attempt.get('status') != 'completed':
                    continue
                try:
                    sid = int(attempt.get('student_id'))
                except (TypeError, ValueError):
                    continue
                if sid != student_user.id:
                    continue

                raw_completed_at = attempt.get('completed_at') or attempt.get('updated_at') or attempt.get('started_at') or ''
                completed_dt = _parse_attempt_timestamp(raw_completed_at)
                is_newer = False
                if completed_dt and latest_dt:
                    is_newer = completed_dt > latest_dt
                elif completed_dt and not latest_dt:
                    is_newer = True
                elif not latest and raw_completed_at:
                    is_newer = True
                elif latest and raw_completed_at and str(raw_completed_at) > str(latest.get('completed_at', '')):
                    is_newer = True

                if not latest or is_newer:
                    latest_dt = completed_dt or latest_dt
                    latest = {
                        'completed_at': raw_completed_at,
                        'assessment_title': assessment.title,
                        'assessment_type': assessment.assessment_type,
                        'level': attempt.get('crla_classification') or attempt.get('classification'),
                        'accuracy': attempt.get('accuracy'),
                        'wpm': attempt.get('wpm'),
                        'fluency_score': attempt.get('fluency_score'),
                        'pronunciation_score': attempt.get('pronunciation_score'),
                        'time_score': attempt.get('time_score'),
                        'duration_seconds': attempt.get('duration_seconds'),
                        'total_score': attempt.get('total_score'),
                    }

    report = {
        'student_name': f"{student_user.first_name} {student_user.last_name}".strip() or student_user.custom_id or 'Student',
        'student_id': getattr(student_user, 'custom_id', '') or '',
        'email': getattr(student_user, 'email', '') or '',
        'grade_level': getattr(student_user, 'grade_level', '') or profile.get('grade_level') or profile.get('grade') or '',
        'joined_classes': joined_classes,
        'course_name': getattr(course, 'title', '') or '',
        'course_code': getattr(course, 'code', '') or '',
        'reading_level': latest.get('level') or student_user.reading_level or profile.get('reading_level') or profile.get('crla_classification') or '',
        'accuracy': latest.get('accuracy') if latest.get('accuracy') is not None else profile.get('accuracy'),
        'wpm': latest.get('wpm') if latest.get('wpm') is not None else profile.get('wpm'),
        'fluency_score': latest.get('fluency_score') if latest.get('fluency_score') is not None else profile.get('fluency_score'),
        'pronunciation_score': latest.get('pronunciation_score') if latest.get('pronunciation_score') is not None else profile.get('pronunciation_score'),
        'time_score': latest.get('time_score') if latest.get('time_score') is not None else profile.get('time_score'),
        'duration_seconds': latest.get('duration_seconds') if latest.get('duration_seconds') is not None else profile.get('duration_seconds'),
        'total_score': latest.get('total_score') if latest.get('total_score') is not None else profile.get('total_score'),
        'completed_at': latest.get('completed_at') or profile.get('last_assessment_at') or '',
        'assessment_title': latest.get('assessment_title') or profile.get('last_assessment_title') or '',
        'assessment_type': latest.get('assessment_type') or '',
        'has_completed_assessment': bool(latest),
    }

    accuracy = _as_float(report.get('accuracy'), default=None)
    wpm = _as_float(report.get('wpm'), default=None)
    fluency = _as_float(report.get('fluency_score'), default=None)
    pronunciation = _as_float(report.get('pronunciation_score'), default=None)
    total_score = _as_float(report.get('total_score'), default=None)

    if not report['has_completed_assessment'] and not any(value not in (None, '', '0', 0) for value in [
        report.get('accuracy'), report.get('wpm'), report.get('fluency_score'),
        report.get('pronunciation_score'), report.get('time_score'), report.get('total_score')
    ]):
        recommendation = "No completed assessment is available yet. Schedule or complete a baseline reading assessment to establish the student's current level."
    elif accuracy is not None and accuracy < 80:
        recommendation = "Focus on decoding, word recognition, and short guided rereading practice before increasing passage difficulty."
    elif wpm is not None and wpm < 60:
        recommendation = "Build reading speed through short daily fluency drills and repeated oral reading for 10 minutes."
    elif (fluency is not None and fluency < 80) or (pronunciation is not None and pronunciation < 80):
        recommendation = "Use guided oral rereading, teacher modeling, and pronunciation practice to improve clarity and expression."
    elif total_score is not None and total_score >= 85:
        recommendation = "Commend the student's consistency and continue regular reading practice to sustain progress."
    else:
        recommendation = "Continue steady home reading practice and review teacher-assigned materials to strengthen fluency and confidence."

    report['recommendation'] = recommendation
    report['summary'] = (
        "No completed assessment yet"
        if not report['has_completed_assessment']
        else f"{report.get('reading_level') or 'Reading level pending'} - "
             f"{report.get('accuracy') if report.get('accuracy') not in (None, '') else 'No'}% accuracy, "
             f"{report.get('wpm') if report.get('wpm') not in (None, '') else 'No'} WPM"
    )
    return report


def _format_reading_report_text(report):
    def metric(label, value, suffix=''):
        if value in (None, ''):
            return f"{label}: Not yet available"
        return f"{label}: {value}{suffix}"
    
    def format_duration(seconds):
        """Format seconds into MM:SS or HH:MM:SS format."""
        if seconds is None or seconds == '' or seconds == 0:
            return 'Not yet available'
        try:
            total_seconds = int(round(float(seconds)))
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            secs = total_seconds % 60
            if hours > 0:
                return f'{hours}:{minutes:02d}:{secs:02d}'
            return f'{minutes}:{secs:02d}'
        except (TypeError, ValueError):
            return 'Not yet available'
    
    def format_datetime(dt_str):
        """Format datetime string from ISO format to user-friendly format."""
        if not dt_str:
            return 'Not yet available'
        try:
            parsed_dt = _parse_attempt_timestamp(dt_str)
            if parsed_dt:
                localized_dt = timezone.localtime(parsed_dt, timezone.get_default_timezone())
                return localized_dt.strftime('%B %d, %Y, %I:%M %p')
            return str(dt_str)
        except Exception:
            return str(dt_str)

    lines = [
        "Reading Performance Report",
        f"Student: {report.get('student_name') or 'Student'}",
        f"Grade Level: {report.get('grade_level') or 'Not yet available'}",
        f"Joined Classes: {', '.join(report.get('joined_classes') or ['Not yet available'])}",
        f"Course: {report.get('course_name') or 'Course'} ({report.get('course_code') or 'No code'})",
        f"Reading Level / CRLA Classification: {report.get('reading_level') or 'Not yet available'}",
        metric("Accuracy", report.get('accuracy'), "%"),
        metric("Words Per Minute", report.get('wpm'), " WPM"),
        metric("Fluency Score", report.get('fluency_score'), "%"),
        metric("Pronunciation Score", report.get('pronunciation_score'), "%"),
        metric("Time", format_duration(report.get('duration_seconds'))),
        metric("Time Score", report.get('time_score'), "%"),
        metric("Total Score", report.get('total_score'), "%"),
        f"Latest Completed Assessment: {format_datetime(report.get('completed_at')) if report.get('completed_at') else 'No completed assessment yet'}",
        f"Suggested Home Support: {report.get('recommendation')}",
    ]
    if report.get('assessment_title'):
        lines.insert(12, f"Assessment: {report.get('assessment_title')}")
    return "\n".join(lines)


def _build_certificate_pdf(student_name='', issued_on=None, school_name='PABASA', teacher_name=''):
    """Create a polished certificate PDF for performance commendation emails."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, HRFlowable
    except ImportError as exc:
        logger.exception("ReportLab is not installed")
        raise RuntimeError(f"PDF export is unavailable: {exc}")

    buffer = BytesIO()
    page_size = landscape(A4)
    left_margin = 0.8 * inch
    right_margin = 0.8 * inch
    top_margin = 0.8 * inch
    bottom_margin = 0.8 * inch
    available_width = page_size[0] - left_margin - right_margin

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CertificateTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=24,
        leading=28, textColor=colors.HexColor('#1f4e79'), alignment=TA_CENTER, spaceAfter=14,
    )
    subtitle_style = ParagraphStyle(
        'CertificateSubtitle', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=13,
        leading=16, textColor=colors.HexColor('#8B3E2F'), alignment=TA_CENTER, spaceAfter=10,
    )
    body_style = ParagraphStyle(
        'CertificateBody', parent=styles['BodyText'], fontName='Helvetica', fontSize=12,
        leading=16, textColor=colors.HexColor('#111827'), alignment=TA_CENTER, spaceAfter=8,
    )
    name_style = ParagraphStyle(
        'CertificateName', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18,
        leading=20, textColor=colors.HexColor('#111827'), alignment=TA_CENTER, spaceAfter=12,
    )
    signature_style = ParagraphStyle(
        'CertificateSignature', parent=styles['BodyText'], fontName='Helvetica', fontSize=10,
        leading=14, textColor=colors.HexColor('#374151'), alignment=TA_CENTER, spaceAfter=4,
    )

    if issued_on is None:
        issued_on = timezone.localtime(timezone.now(), timezone.get_default_timezone()).strftime('%B %d, %Y')

    elements = []
    elements.append(Paragraph('PABASA', title_style))
    elements.append(Paragraph('Certificate of Achievement', subtitle_style))
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph('This certificate is proudly presented to', body_style))
    elements.append(Spacer(1, 0.08 * inch))
    elements.append(Paragraph(student_name or 'Student Name', name_style))
    elements.append(Spacer(1, 0.12 * inch))
    elements.append(Paragraph(
        'In recognition of your outstanding reading performance and dedication to improving your reading skills through the PABASA Reading Assessment System. Your hard work, perseverance, and commitment to learning are truly commendable. Keep up the excellent work and continue striving for success.',
        body_style,
    ))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(f'Presented this {issued_on}.', body_style))
    elements.append(Spacer(1, 0.35 * inch))
    elements.append(HRFlowable(width=available_width * 0.5, thickness=0.6, color=colors.HexColor('#8B3E2F')))
    elements.append(Spacer(1, 0.04 * inch))
    elements.append(Paragraph(school_name or 'PABASA School', signature_style))
    elements.append(Paragraph('Principal / School Representative', signature_style))
    elements.append(Paragraph(teacher_name or 'Teacher', signature_style))

    doc = SimpleDocTemplate(buffer, pagesize=page_size, leftMargin=left_margin, rightMargin=right_margin, topMargin=top_margin, bottomMargin=bottom_margin)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def _build_reading_report_pdf(report, message='', course=None, teacher=None, recipient_email=''):
    """Create a polished PDF attachment for course update / report emails."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, HRFlowable
    except ImportError as exc:
        logger.exception("ReportLab is not installed")
        raise RuntimeError(f"PDF export is unavailable: {exc}")

    buffer = BytesIO()
    page_size = A4
    left_margin = 0.7 * inch
    right_margin = 0.7 * inch
    top_margin = 0.7 * inch
    bottom_margin = 0.7 * inch
    available_width = page_size[0] - left_margin - right_margin

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=20,
        leading=24, textColor=colors.HexColor('#8B3E2F'), spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        'ReportSubtitle', parent=styles['BodyText'], fontName='Helvetica', fontSize=10,
        leading=13, textColor=colors.HexColor('#4b5563'), spaceAfter=3,
    )
    section_style = ParagraphStyle(
        'SectionTitle', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12,
        leading=14, textColor=colors.HexColor('#8B3E2F'), spaceAfter=6,
    )
    body_style = ParagraphStyle(
        'ReportBody', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.2,
        leading=12, textColor=colors.HexColor('#111827'), spaceAfter=4,
    )
    meta_style = ParagraphStyle(
        'MetaBody', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.2,
        leading=12, textColor=colors.HexColor('#111827'), spaceAfter=3,
    )
    note_style = ParagraphStyle(
        'NoteBody', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.2,
        leading=12, textColor=colors.HexColor('#374151'), spaceAfter=4,
    )

    def _make_row(label, value):
        return [Paragraph(str(label), body_style), Paragraph(str(value or 'Not yet available'), body_style)]

    def _make_metrics_table(values):
        rows = []
        for label, value in values:
            rows.append([Paragraph(str(label), body_style), Paragraph(str(value), body_style)])
        table = Table(rows, colWidths=[2.3 * inch, available_width - 2.3 * inch], repeatRows=0)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e5e7eb')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        return table

    def _format_duration(seconds):
        """Format seconds into MM:SS or HH:MM:SS format."""
        if seconds is None or seconds == '' or seconds == 0:
            return 'Not yet available'
        try:
            total_seconds = int(round(float(seconds)))
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            secs = total_seconds % 60
            if hours > 0:
                return f'{hours}:{minutes:02d}:{secs:02d}'
            return f'{minutes}:{secs:02d}'
        except (TypeError, ValueError):
            return 'Not yet available'

    def _format_datetime(dt_str):
        """Format datetime string from ISO format to user-friendly format."""
        if not dt_str:
            return 'Not yet available'
        try:
            parsed_dt = _parse_attempt_timestamp(dt_str)
            if parsed_dt:
                localized_dt = timezone.localtime(parsed_dt, timezone.get_default_timezone())
                return localized_dt.strftime('%B %d, %Y, %I:%M %p')
            return str(dt_str)
        except Exception:
            return str(dt_str)

    generated_at = timezone.localtime(timezone.now(), timezone.get_default_timezone()).strftime('%B %d, %Y %I:%M %p')
    student_name = report.get('student_name') or 'Student'
    joined_classes = report.get('joined_classes') or []
    if isinstance(joined_classes, str):
        class_text = joined_classes
    else:
        class_text = ', '.join([str(item) for item in joined_classes if item]) or 'Not yet available'

    elements = []
    logo_path = settings.BASE_DIR / 'pabasa_app' / 'static' / 'pabasa_app' / 'images' / 'pabasalogo.png'
    header_parts = []
    if logo_path.exists():
        header_parts.append(Image(str(logo_path), width=0.75 * inch, height=0.75 * inch))
    else:
        header_parts.append(Paragraph('<b>PABASA</b>', title_style))
    header_parts.append(Paragraph('PABASA Reading Report', title_style))
    header_table = Table([[header_parts[0], header_parts[1]]], colWidths=[0.9 * inch, available_width - 0.9 * inch], repeatRows=0)
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.extend([header_table, Spacer(1, 0.08 * inch)])
    elements.append(Paragraph(f'Generated on {generated_at}', subtitle_style))
    elements.append(Paragraph(f'Prepared for {student_name}', subtitle_style))
    elements.append(Spacer(1, 0.08 * inch))
    elements.append(HRFlowable(width=available_width, thickness=0.6, color=colors.HexColor('#8B3E2F')))
    elements.append(Spacer(1, 0.12 * inch))

    profile_rows = [
        ['Student Name', report.get('student_name') or 'Student'],
        ['Student ID', report.get('student_id') or 'Not yet available'],
        ['Grade Level', report.get('grade_level') or 'Not yet available'],
        ['Email', report.get('email') or 'Not yet available'],
        ['Joined Classes', class_text],
        ['Course', f"{report.get('course_name') or 'Course'} ({report.get('course_code') or 'No code'})"],
    ]
    profile_table = Table(profile_rows, colWidths=[1.7 * inch, available_width - 1.7 * inch], repeatRows=0)
    profile_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fcfcfc')),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(Paragraph('Student & Class Details', section_style))
    elements.append(profile_table)
    elements.append(Spacer(1, 0.12 * inch))

    elements.append(Paragraph('Reading Overview', section_style))
    metrics = [
        ('Reading Level / CRLA Classification', report.get('reading_level') or 'Not yet available'),
        ('Accuracy', f"{report.get('accuracy') or 'Not yet available'}%" if report.get('accuracy') not in (None, '') else 'Not yet available'),
        ('Words Per Minute', f"{report.get('wpm') or 'Not yet available'} WPM" if report.get('wpm') not in (None, '') else 'Not yet available'),
        ('Fluency Score', f"{report.get('fluency_score') or 'Not yet available'}%" if report.get('fluency_score') not in (None, '') else 'Not yet available'),
        ('Pronunciation Score', f"{report.get('pronunciation_score') or 'Not yet available'}%" if report.get('pronunciation_score') not in (None, '') else 'Not yet available'),
        ('Time', _format_duration(report.get('duration_seconds'))),
        ('Time Score', f"{report.get('time_score') or 'Not yet available'}%" if report.get('time_score') not in (None, '') else 'Not yet available'),
        ('Total Score', f"{report.get('total_score') or 'Not yet available'}%" if report.get('total_score') not in (None, '') else 'Not yet available'),
    ]
    elements.append(_make_metrics_table(metrics))
    elements.append(Spacer(1, 0.12 * inch))

    elements.append(Paragraph('Assessment Results', section_style))
    formatted_completed_at = _format_datetime(report.get('completed_at')) if report.get('completed_at') else 'No completed assessment yet'
    assessment_text = [
        f"Latest Completed Assessment: {formatted_completed_at}",
        f"Assessment Title: {report.get('assessment_title') or 'Not yet available'}",
        f"Assessment Type: {report.get('assessment_type') or 'Not yet available'}",
        f"Summary: {report.get('summary') or 'No summary available'}",
    ]
    elements.extend([Paragraph(item, note_style) for item in assessment_text])
    elements.append(Spacer(1, 0.12 * inch))

    elements.append(Paragraph('Recommendations & Support', section_style))
    elements.append(Paragraph(report.get('recommendation') or 'Continue regular reading practice and teacher-guided support.', note_style))

    if message:
        elements.append(Spacer(1, 0.08 * inch))
        elements.append(Paragraph('Teacher Comments', section_style))
        elements.append(Paragraph(message, note_style))

    if teacher or recipient_email:
        elements.append(Spacer(1, 0.08 * inch))
        elements.append(Paragraph('Additional Details', section_style))
        extra_lines = []
        if teacher:
            extra_lines.append(f"Teacher: {teacher.first_name} {teacher.last_name}".strip())
        if recipient_email:
            extra_lines.append(f"Recipient Email: {recipient_email}")
        if course:
            extra_lines.append(f"Course: {course.title} ({course.code})")
        elements.extend([Paragraph(item, note_style) for item in extra_lines])

    def _draw_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(colors.HexColor('#6b7280'))
        canvas_obj.drawString(left_margin, 0.38 * inch, 'PABASA Automated Reading Assessment System')
        canvas_obj.drawCentredString(page_size[0] / 2.0, 0.38 * inch, f'Page {canvas_obj.getPageNumber()}')
        canvas_obj.drawRightString(page_size[0] - right_margin, 0.38 * inch, f'Generated {generated_at}')
        canvas_obj.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=page_size, leftMargin=left_margin, rightMargin=right_margin, topMargin=top_margin, bottomMargin=bottom_margin)
    doc.build(elements, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    buffer.seek(0)
    return buffer.getvalue()

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

def _send_pabasa_otp_email(subject, text_message, recipient_email, first_name, otp, eyebrow, heading, intro, action_url=None, action_label="Open PABASA"):
    safe_name = escape(first_name or "PABASA user")
    safe_otp = escape(str(otp))
    safe_eyebrow = escape(eyebrow)
    safe_heading = escape(heading)
    safe_intro = escape(intro)
    safe_action_url = escape(action_url or "")
    safe_action_label = escape(action_label)
    action_html = ""
    if action_url:
        action_html = f"""
                                            <tr>
                                                <td align="center" style="padding: 8px 0 4px;">
                                                    <a href="{safe_action_url}" style="display: inline-block; background: #2EA8E5; color: #ffffff; font-family: Arial, sans-serif; font-size: 14px; font-weight: 800; text-decoration: none; padding: 13px 22px; border-radius: 999px; box-shadow: 0 10px 22px rgba(46, 168, 229, 0.22);">{safe_action_label}</a>
                                                </td>
                                            </tr>
        """

    html_message = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{safe_heading}</title>
</head>
<body style="margin: 0; padding: 0; background: #F0F8FF;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background: #F0F8FF; margin: 0; padding: 32px 12px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width: 620px; background: #ffffff; border-radius: 28px; overflow: hidden; border: 1px solid rgba(16, 70, 110, 0.12); box-shadow: 0 18px 42px rgba(16, 70, 110, 0.12);">
                    <tr>
                        <td style="background: linear-gradient(135deg, #10466E 0%, #2EA8E5 72%, #FFD639 100%); padding: 28px 30px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td>
                                        <div style="display: inline-block; background: rgba(255,255,255,0.16); border: 1px solid rgba(255,255,255,0.28); border-radius: 18px; color: #ffffff; font-family: Arial, sans-serif; font-size: 12px; font-weight: 800; letter-spacing: 0.12em; padding: 8px 12px; text-transform: uppercase;">PABASA</div>
                                        <h1 style="color: #ffffff; font-family: Arial, sans-serif; font-size: 30px; line-height: 1.15; margin: 18px 0 8px;">{safe_heading}</h1>
                                        <p style="color: rgba(255,255,255,0.86); font-family: Arial, sans-serif; font-size: 14px; line-height: 1.55; margin: 0;">{safe_eyebrow}</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 30px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td>
                                        <p style="color: #0F2D45; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.6; margin: 0 0 12px;">Hello {safe_name},</p>
                                        <p style="color: #4A6680; font-family: Arial, sans-serif; font-size: 15px; line-height: 1.65; margin: 0 0 22px;">{safe_intro}</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" style="padding: 8px 0 22px;">
                                        <div style="background: #EAF7FD; border: 1px dashed rgba(46, 168, 229, 0.5); border-radius: 22px; padding: 20px 18px;">
                                            <div style="color: #4A6680; font-family: Arial, sans-serif; font-size: 12px; font-weight: 800; letter-spacing: 0.14em; margin-bottom: 8px; text-transform: uppercase;">Your OTP Code</div>
                                            <div style="color: #10466E; font-family: 'Courier New', monospace; font-size: 36px; font-weight: 800; letter-spacing: 0.24em; line-height: 1;">{safe_otp}</div>
                                        </div>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <div style="background: #FFF8D6; border: 1px solid rgba(245, 184, 0, 0.28); border-radius: 16px; color: #6A5710; font-family: Arial, sans-serif; font-size: 13px; line-height: 1.55; padding: 14px 16px; margin-bottom: 18px;">
                                            This code is valid for 10 minutes. For your safety, do not share it with anyone.
                                        </div>
                                    </td>
                                </tr>
                                {action_html}
                                <tr>
                                    <td style="padding-top: 18px;">
                                        <p style="color: #6B7D8F; font-family: Arial, sans-serif; font-size: 13px; line-height: 1.6; margin: 0;">If you did not request this code, you can safely ignore this email.</p>
                                        <p style="color: #0F2D45; font-family: Arial, sans-serif; font-size: 14px; font-weight: 700; line-height: 1.6; margin: 18px 0 0;">Thank you,<br>The PABASA Team</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    email = EmailMultiAlternatives(subject, text_message, settings.DEFAULT_FROM_EMAIL, [recipient_email])
    email.attach_alternative(html_message, "text/html")
    email.send(fail_silently=False)

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
    _send_pabasa_otp_email(
        subject,
        message,
        email,
        first_name,
        otp,
        "Teacher account verification",
        "Complete your teacher signup",
        "Use the code below to finish creating your PABASA teacher account.",
        auth_url,
        "Go to PABASA"
    )

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
    _send_pabasa_otp_email(
        subject,
        message,
        email,
        first_name,
        otp,
        "Student account verification",
        "Complete your student signup",
        "Use the code below to finish creating your PABASA student account.",
        auth_url,
        "Go to PABASA"
    )

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
    _send_pabasa_otp_email(
        subject,
        message,
        email,
        first_name,
        otp,
        "Password reset verification",
        "Reset your PABASA password",
        "We received a request to reset your PABASA password. Use the code below to continue.",
        otp_url,
        "Verify OTP"
    )


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
        _notify_principals(
            'New teacher account created',
            f'{user.first_name} {user.last_name} created a new teacher account.',
            'success',
            reverse('admin_teacher_detail', args=[user.id]),
            user,
            send_email=False,
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
        custom_id = data.get('custom_id', '').strip().upper()
        password = data.get('password', '')

        if custom_id == PRINCIPAL_DEFAULT_CUSTOM_ID:
            ensure_default_principal_account()
        
        if not custom_id or not password:
            return JsonResponse({'success': False, 'error': 'Custom ID and password are required'}, status=400)
        
        # Find user by custom_id
        try:
            user = User.objects.get(custom_id__iexact=custom_id)
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
    birthday_display = ""
    if user.birth_month and user.birth_day and user.birth_year:
        birthday_display = f"{int(user.birth_month):02d}/{int(user.birth_day):02d}/{user.birth_year}"
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
        'active_teacher_class_count': len(joined_classes),
    }
    # Include teacher-created courses for server-side rendering to avoid
    # a blank page while client-side JS fetches them.
    try:
        teacher_courses = []
        if user and (user.role in ['teacher', 'admin'] or effective_role in ['teacher', 'admin']):
            from .models import Course
            qs = Course.objects.filter(teacher=user, is_active=True)
            for c in qs:
                sections_count = c.sections.count()
                assessments_count = c.assessments.count()
                materials_count = c.materials.count()
                # Approximate student count by summing section student counts
                students_count = 0
                for s in c.sections.all():
                    try:
                        students_count += _section_student_count(s)
                    except Exception:
                        continue
                teacher_courses.append({
                    'id': c.id,
                    'code': c.code,
                    'title': c.title,
                    'description': c.description,
                    'metrics': {
                        'sections': sections_count,
                        'assessments': assessments_count,
                        'materials': materials_count,
                        'students': students_count,
                        'average_progress': _compute_course_average_progress(c),
                    }
                })
    except Exception:
        teacher_courses = []
    context['teacher_courses'] = teacher_courses
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
                has_attempts = Assessment.objects.filter(teacher=tp_user, source_assessment__isnull=True).exists()
                has_activity = has_classes or has_materials or has_joined_students or has_attempts

                # Get latest timestamps
                candidate_dates = []
                if getattr(tp_user, 'updated_at', None):
                    candidate_dates.append(tp_user.updated_at)
                cls_max = Section.objects.filter(teacher=tp_user).aggregate(m=Max('updated_at'))['m']
                if cls_max:
                    candidate_dates.append(cls_max)
                asm_max = Assessment.objects.filter(teacher=tp_user, source_assessment__isnull=True).aggregate(m=Max('updated_at'))['m']
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
        'student_theme_slug': (
            user.equipped_theme
            if user and user.role == 'student' and user.equipped_theme in STUDENT_THEME_CATALOG
            else 'sky'
        ),
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
        'weekly_digest_enabled': False,
        'new_materials': True,
        'reading_reminders': getattr(user, 'role', '') == 'student',
        'progress_updates': True,
    }

def _notification_settings_for_user(user):
    saved_settings = _get_profile_dict(user, 'notification_settings')
    if not isinstance(saved_settings, dict):
        saved_settings = {}
    return {
        **_notification_settings_defaults(user),
        **saved_settings,
    }

def _posted_notification_settings(request):
    return {
        'push_enabled': request.POST.get('push_enabled') == 'on',
        'email_notifications': request.POST.get('email_notifications') == 'on',
        'weekly_digest_enabled': request.POST.get('weekly_digest_enabled') == 'on',
        'new_materials': request.POST.get('new_materials') == 'on',
        'reading_reminders': request.POST.get('reading_reminders') == 'on',
        'progress_updates': request.POST.get('progress_updates') == 'on',
    }

def _json_notification_settings(data, user):
    defaults = _notification_settings_defaults(user)
    return {
        'push_enabled': bool(data.get('push_enabled', defaults['push_enabled'])),
        'email_notifications': bool(data.get('email_notifications', defaults['email_notifications'])),
        'weekly_digest_enabled': bool(data.get('weekly_digest_enabled', defaults['weekly_digest_enabled'])),
        'new_materials': bool(data.get('new_materials', defaults['new_materials'])),
        'reading_reminders': bool(data.get('reading_reminders', defaults['reading_reminders'])),
        'progress_updates': bool(data.get('progress_updates', defaults['progress_updates'])),
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
            'active_assessments': Assessment.objects.filter(is_active=True, source_assessment__isnull=True).count(),
            'published_assessments': Assessment.objects.filter(status='published', is_active=True, source_assessment__isnull=True).count(),
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

PRINCIPAL_DEFAULT_PASSWORD = 'Principal@123'
PRINCIPAL_LOGOS_DIR = settings.BASE_DIR / 'pabasa_app' / 'static' / 'pabasa_app' / 'uploads' / 'school_logos'
PRINCIPAL_LOGOS_STATIC_PREFIX = 'pabasa_app/uploads/school_logos'

def _principal_school_initials(school_name):
    words = re.findall(r"[A-Za-z0-9]+", school_name or "")
    ignored_words = {'of', 'the', 'and', 'at', 'in', 'for'}
    initials = ''.join(word[0].upper() for word in words if word.lower() not in ignored_words)
    return initials or 'SCH'

def _generate_principal_custom_id(school_name):
    initials = _principal_school_initials(school_name)
    prefix = f'PRN-{initials}-'
    existing_ids = User.objects.filter(role='principal', custom_id__startswith=prefix).values_list('custom_id', flat=True)
    highest = 0
    for custom_id in existing_ids:
        match = re.match(rf"^{re.escape(prefix)}(\d+)$", custom_id)
        if match:
            highest = max(highest, int(match.group(1)))
    next_number = highest + 1
    candidate = f'{prefix}{next_number:03d}'
    while User.objects.filter(custom_id=candidate).exists():
        next_number += 1
        candidate = f'{prefix}{next_number:03d}'
    return candidate

def _split_full_name(full_name):
    parts = [part for part in (full_name or '').strip().split() if part]
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0], parts[0]
    return ' '.join(parts[:-1]), parts[-1]

def _save_principal_logo(logo_file, custom_id):
    allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    file_ext = (logo_file.name.rsplit('.', 1)[-1] if '.' in logo_file.name else '').lower()
    if file_ext not in allowed_extensions:
        raise ValueError('School logo must be an image file.')

    PRINCIPAL_LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f'{slugify(custom_id) or uuid.uuid4().hex}.{file_ext}'
    destination = PRINCIPAL_LOGOS_DIR / filename
    with open(destination, 'wb+') as target:
        for chunk in logo_file.chunks():
            target.write(chunk)
    return f'{PRINCIPAL_LOGOS_STATIC_PREFIX}/{filename}'

def _send_principal_credentials_email(request, user, school_name):
    auth_url = request.build_absolute_uri(reverse('auth'))
    subject = 'Your PABASA Principal Account is Ready'
    message = (
        f"Hello {user.first_name} {user.last_name},\n\n"
        "A PABASA Principal account has been created for you.\n\n"
        f"Full Name: {user.first_name} {user.last_name}\n"
        f"School Name: {school_name}\n"
        f"PABASA ID / Username: {user.custom_id}\n"
        f"Default Password: {PRINCIPAL_DEFAULT_PASSWORD}\n\n"
        "Log in using the existing PABASA login page:\n"
        f"{auth_url}\n\n" 
        "After logging in, you will be redirected to the Principal Dashboard.\n\n"
        "Thank you,\nPABASA Team"
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)

@admin_required
def admin_principals(request):
    context = _admin_context(request, 'Principals', [])
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    context.update({
        'form_data': {},
        'created_principal': None,
        'created_principal_id': None,
        'default_password': PRINCIPAL_DEFAULT_PASSWORD,
        'search_query': search_query,
        'status_filter': status_filter,
    })

    principals = User.objects.filter(role='principal')
    if search_query:
        principals = principals.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(custom_id__icontains=search_query)
            | Q(email__icontains=search_query)
        )
    if status_filter == 'active':
        principals = principals.filter(is_archived=False)
    elif status_filter == 'inactive':
        principals = principals.filter(is_archived=True)

    if request.method == 'POST':
        form_data = {
            'full_name': request.POST.get('full_name', '').strip(),
            'school_name': request.POST.get('school_name', '').strip(),
            'school_address': request.POST.get('school_address', '').strip(),
            'email': request.POST.get('email', '').strip().lower(),
            'contact_no': request.POST.get('contact_no', '').strip(),
        }
        context['form_data'] = form_data
        logo_file = request.FILES.get('school_logo')
        errors = []

        for label, value in [
            ('Full name', form_data['full_name']),
            ('School name', form_data['school_name']),
            ('School address', form_data['school_address']),
            ('Email address', form_data['email']),
            ('Contact number', form_data['contact_no']),
        ]:
            if not value:
                errors.append(f'{label} is required.')
        if not logo_file:
            errors.append('School logo is required.')
        if form_data['email'] and User.objects.filter(email__iexact=form_data['email']).exists():
            errors.append('An account with this email address already exists.')

        if errors:
            context['principal_error'] = ' '.join(errors)
            context['principals'] = principals.order_by('last_name', 'first_name')
            return render(request, 'pabasa_app/admin_principals.html', context)

        try:
            with transaction.atomic():
                first_name, last_name = _split_full_name(form_data['full_name'])
                custom_id = _generate_principal_custom_id(form_data['school_name'])
                logo_path = _save_principal_logo(logo_file, custom_id)
                current_year = timezone.now().year
                user = User.objects.create(
                    custom_id=custom_id,
                    role='principal',
                    first_name=first_name,
                    last_name=last_name,
                    middle_initial='',
                    suffix='',
                    sex='N/A',
                    birth_month=1,
                    birth_day=1,
                    birth_year=current_year,
                    email=form_data['email'],
                    contact_no=form_data['contact_no'],
                    password_hash=make_password(PRINCIPAL_DEFAULT_PASSWORD),
                    school=form_data['school_name'],
                    profile_picture=logo_path,
                )
                _set_profile_dict(user, 'principal_school_info', {
                    'name': form_data['school_name'],
                    'address': form_data['school_address'],
                    'contact': form_data['contact_no'],
                    'email': form_data['email'],
                    'logo': logo_path,
                })
                _set_profile_dict(user, 'principal_profile_info', {
                    'position': 'Principal',
                    'full_name': form_data['full_name'],
                })
                _send_principal_credentials_email(request, user, form_data['school_name'])

            context['principal_success'] = 'Principal account created and credentials email sent.'
            context['created_principal'] = user
            context['created_principal_id'] = user.id
            context['created_principal_name'] = _admin_user_full_name(user)
            context['created_school_name'] = form_data['school_name']
            context['form_data'] = {}

            principals = User.objects.filter(role='principal')
            if search_query:
                principals = principals.filter(
                    Q(first_name__icontains=search_query)
                    | Q(last_name__icontains=search_query)
                    | Q(custom_id__icontains=search_query)
                    | Q(email__icontains=search_query)
                )
            if status_filter == 'active':
                principals = principals.filter(is_archived=False)
            elif status_filter == 'inactive':
                principals = principals.filter(is_archived=True)
        except ValueError as exc:
            context['principal_error'] = str(exc)
        except IntegrityError:
            context['principal_error'] = 'A principal account with the generated PABASA ID or email already exists. Please try again.'
        except Exception:
            logger.exception('Failed to create principal account')
            context['principal_error'] = 'The account could not be created or the email could not be sent. Please check the mail settings and try again.'

    context['principals'] = principals.order_by('last_name', 'first_name')
    return render(request, 'pabasa_app/admin_principals.html', context)

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
    if role == 'student':
        return 'admin_students'
    if role == 'principal':
        return 'admin_principals'
    return 'admin_teachers'

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
def admin_principal_detail(request, user_id):
    user = _get_managed_user(user_id, 'principal')
    if not user:
        return redirect('admin_principals')
    context = _admin_user_template_context(request, user, 'Principal Details')
    school_info = _get_profile_dict(user, 'principal_school_info') or {}
    profile_info = _get_profile_dict(user, 'principal_profile_info') or {}
    context.update({
        'school_info': school_info if isinstance(school_info, dict) else {},
        'principal_profile_info': profile_info if isinstance(profile_info, dict) else {},
    })
    return render(request, 'pabasa_app/admin_principal_detail.html', context)

@admin_required
@require_http_methods(["GET", "POST"])
def admin_student_edit(request, user_id):
    return _admin_edit_user(request, user_id, 'student')

@admin_required
@require_http_methods(["GET", "POST"])
def admin_teacher_edit(request, user_id):
    return _admin_edit_user(request, user_id, 'teacher')

@admin_required
@require_http_methods(["GET", "POST"])
def admin_principal_edit(request, user_id):
    user = _get_managed_user(user_id, 'principal')
    if not user:
        return redirect('admin_principals')

    school_info = _get_profile_dict(user, 'principal_school_info') or {}
    profile_info = _get_profile_dict(user, 'principal_profile_info') or {}
    if not isinstance(school_info, dict):
        school_info = {}
    if not isinstance(profile_info, dict):
        profile_info = {}

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        school_name = request.POST.get('school_name', '').strip()
        school_address = request.POST.get('school_address', '').strip()
        contact_no = request.POST.get('contact_no', '').strip()

        context = _admin_user_template_context(request, user, 'Edit Principal')
        context.update({'school_info': school_info, 'principal_profile_info': profile_info})

        if not request.POST.get('first_name', '').strip() or not request.POST.get('last_name', '').strip():
            context['error_message'] = 'First name and last name are required.'
            return render(request, 'pabasa_app/admin_principal_edit.html', context, status=400)
        if not email or not school_name or not school_address or not contact_no:
            context['error_message'] = 'School name, school address, email, and contact number are required.'
            return render(request, 'pabasa_app/admin_principal_edit.html', context, status=400)
        if User.objects.filter(email__iexact=email).exclude(id=user.id).exists():
            context['error_message'] = 'Email is already used by another account.'
            return render(request, 'pabasa_app/admin_principal_edit.html', context, status=400)

        try:
            logo_file = request.FILES.get('school_logo')
            logo_path = school_info.get('logo') or user.profile_picture or ''
            if logo_file:
                logo_path = _save_principal_logo(logo_file, user.custom_id)

            user.first_name = request.POST.get('first_name', '').strip()
            user.middle_initial = request.POST.get('middle_initial', '').strip()[:1]
            user.last_name = request.POST.get('last_name', '').strip()
            user.suffix = request.POST.get('suffix', '').strip()
            user.email = email
            user.contact_no = contact_no
            user.school = school_name
            user.profile_picture = logo_path
            user.save(update_fields=['first_name', 'middle_initial', 'last_name', 'suffix', 'email', 'contact_no', 'school', 'profile_picture', 'updated_at'])

            school_info.update({
                'name': school_name,
                'address': school_address,
                'contact': contact_no,
                'email': email,
                'logo': logo_path,
            })
            profile_info.update({
                'position': request.POST.get('position', '').strip() or 'Principal',
                'full_name': _admin_user_full_name(user),
            })
            _set_profile_dict(user, 'principal_school_info', school_info)
            _set_profile_dict(user, 'principal_profile_info', profile_info)
            return redirect('admin_principal_detail', user_id=user.id)
        except ValueError as exc:
            context['error_message'] = str(exc)
            return render(request, 'pabasa_app/admin_principal_edit.html', context, status=400)

    context = _admin_user_template_context(request, user, 'Edit Principal')
    context.update({'school_info': school_info, 'principal_profile_info': profile_info})
    return render(request, 'pabasa_app/admin_principal_edit.html', context)

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

@admin_required
@require_http_methods(["POST"])
def admin_principal_deactivate(request, user_id):
    user = _get_managed_user(user_id, 'principal')
    if not user:
        return redirect('admin_principals')

    action = request.POST.get('action', 'deactivate').strip().lower()
    if action == 'reactivate' and user.is_archived:
        user.is_archived = False
        user.archived_at = None
        user.save(update_fields=['is_archived', 'archived_at', 'updated_at'])
    elif action == 'deactivate' and not user.is_archived:
        user.is_archived = True
        user.archived_at = timezone.now()
        user.save(update_fields=['is_archived', 'archived_at', 'updated_at'])

    return redirect('admin_principal_detail', user_id=user.id)

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
        'Language',
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
    # Practice library content is stored in the Material table.
    return Material.objects.filter(
        section__isnull=True,
        difficulty_level__in=_practice_difficulty_values(),
        type='practice',
    )

def _get_admin_practice_material(practice_id):
    return _admin_practice_queryset().filter(id=practice_id).first()

def _admin_practice_status(material):
    return 'Archived' if not material.is_active else material.get_status_display()

def _practice_material_items(material):
    if not material:
        return []
    return parse_practice_items(material.content_text, material.item_type)

def _practice_config_label(value, choices):
    if not value:
        return ''
    choice_map = dict(choices)
    if value in choice_map:
        return choice_map[value]
    return str(value).replace('_', ' ').title()


def _practice_progression_mode_title(mode):
    titles = {
        'free': 'Free Mode',
        'color': 'Color Mode',
        'hunt': 'Hunt Mode',
    }
    return titles.get((mode or '').strip().lower(), 'Practice Mode')


def _practice_progression_level_keys():
    return [f'level_{index}' for index in range(1, 6)]


def _practice_progression_difficulty_keys():
    return ['easy', 'medium', 'hard']


def _material_level_completion(material, student_user):
    if not material or not student_user:
        return None
    content_json = getattr(material, 'content_json', None) or {}
    if not isinstance(content_json, dict):
        return None
    completions = content_json.get('student_completions') or {}
    if not isinstance(completions, dict):
        return None
    completion = completions.get(str(student_user.id)) or {}
    return completion if isinstance(completion, dict) else None


def _apply_progression_unlock_override(progression, unlock_target):
    normalized_target = (unlock_target or '').strip().lower().replace('-', '_')
    if not normalized_target:
        return progression

    parts = normalized_target.split('_')
    if len(parts) < 2:
        return progression

    difficulty = parts[0]
    level = '_'.join(parts[1:])
    ordered_levels = []
    for section in progression.get('sections', []):
        for level_payload in section.get('levels', []):
            ordered_levels.append((section, level_payload))

    target_index = None
    for index, (section, level_payload) in enumerate(ordered_levels):
        if section.get('difficulty') == difficulty and level_payload.get('level') == level:
            target_index = index
            break

    if target_index is None:
        return progression

    progression['ui_unlock_target'] = normalized_target
    progression['ui_unlock_indices'] = [index for index in range(target_index + 1)]
    return progression


def _practice_game_progression(mode, student_user=None):
    normalized_mode = (mode or '').strip().lower()
    if normalized_mode not in {'free', 'color', 'hunt'}:
        normalized_mode = 'free'

    level_keys = _practice_progression_level_keys()
    difficulty_keys = _practice_progression_difficulty_keys()
    materials_by_slot = {}

    for material in Material.objects.filter(
        type='practice',
        is_active=True,
        status='published',
        content_json__mode=normalized_mode,
    ).order_by('created_at', 'id'):
        content_json = getattr(material, 'content_json', None) or {}
        if not isinstance(content_json, dict):
            continue
        slot_mode = str(content_json.get('mode') or '').strip().lower()
        slot_difficulty = str(content_json.get('difficulty') or getattr(material, 'difficulty_level', '') or '').strip().lower()
        slot_level = str(content_json.get('level') or '').strip().lower()
        if slot_mode != normalized_mode:
            continue
        if slot_difficulty not in difficulty_keys or slot_level not in level_keys:
            continue
        materials_by_slot[(slot_difficulty, slot_level)] = material

    section_payloads = []
    total_completed = 0
    total_stars = 0
    next_challenge = None

    for difficulty in difficulty_keys:
        level_payloads = []
        difficulty_unlocked = difficulty == 'easy'
        is_free_mode = normalized_mode == 'free'
        previous_difficulty = None
        previous_levels = []
        if difficulty == 'medium':
            previous_difficulty = 'easy'
        elif difficulty == 'hard':
            previous_difficulty = 'medium'

        if is_free_mode and previous_difficulty:
            previous_slots = [
                {
                    'difficulty': previous_difficulty,
                    'level': level_key,
                    'material': materials_by_slot.get((previous_difficulty, level_key)),
                    'completion': _material_level_completion(materials_by_slot.get((previous_difficulty, level_key)), student_user),
                }
                for level_key in level_keys
            ]
            previous_levels = previous_slots
            difficulty_unlocked = all(
                slot['completion'] and slot['completion'].get('status') == 'completed' and slot['material'] is not None
                for slot in previous_levels
            )

        for level_key in level_keys:
            material = materials_by_slot.get((difficulty, level_key))
            completion = _material_level_completion(material, student_user)
            is_completed = bool(completion and completion.get('status') == 'completed')
            material_exists = material is not None
            previous_level_key = level_keys[level_keys.index(level_key) - 1] if level_key != level_keys[0] else None
            previous_completed = True
            if previous_level_key:
                previous_material = materials_by_slot.get((difficulty, previous_level_key))
                previous_completion = _material_level_completion(previous_material, student_user)
                previous_completed = bool(previous_completion and previous_completion.get('status') == 'completed')

            unlocked = False
            if is_free_mode:
                if difficulty == 'easy' and level_key == 'level_1':
                    unlocked = True
                elif material_exists and difficulty_unlocked and previous_completed:
                    unlocked = True
                elif difficulty != 'easy' and difficulty_unlocked and level_key == 'level_1' and material_exists:
                    unlocked = True
            else:
                unlocked = material_exists

            if not material_exists:
                state = 'content_unavailable'
                button_label = 'Content unavailable'
            elif is_completed:
                state = 'completed'
                button_label = 'Replay'
            elif unlocked:
                state = 'unlocked'
                button_label = 'Play Level'
            else:
                state = 'locked'
                button_label = 'Locked'

            stars_earned = 0
            if completion and isinstance(completion, dict):
                stars_earned = int(completion.get('stars_earned') or 0)
            total_stars += stars_earned if is_completed else 0
            if is_completed:
                total_completed += 1

            level_payloads.append({
                'difficulty': difficulty,
                'difficulty_label': _practice_config_label(difficulty, AdminPracticeMaterialForm.DIFFICULTY_CHOICES),
                'level': level_key,
                'level_label': _practice_config_label(level_key, AdminPracticeMaterialForm.LEVEL_CHOICES),
                'title': material.title if material else 'Coming soon',
                'material_exists': material_exists,
                'state': state,
                'unlocked': unlocked and material_exists,
                'completed': is_completed,
                'stars_earned': stars_earned,
                'button_label': button_label,
                'play_url': reverse('practice_word_page') if material and (material.item_type or 'word') == 'word' else reverse('practice_sentence_page') if material and (material.item_type or 'word') == 'sentence' else reverse('practice_para_page') if material else '#',
                'material_id': f"practice-{material.id}" if material else None,
                'completion': completion,
                'locked_reason': 'Complete Level 1 to unlock this level.' if level_key != 'level_1' and state == 'locked' else 'Complete all previous difficulty levels to unlock this section.' if state == 'locked' and difficulty != 'easy' else '',
            })

        section_payloads.append({
            'difficulty': difficulty,
            'difficulty_label': _practice_config_label(difficulty, AdminPracticeMaterialForm.DIFFICULTY_CHOICES),
            'unlocked': True if not is_free_mode else (difficulty == 'easy' or difficulty_unlocked),
            'levels': level_payloads,
            'locked_reason': 'Complete all previous difficulty levels to unlock this section.' if is_free_mode and difficulty != 'easy' and not difficulty_unlocked else '',
        })

        if next_challenge is None:
            candidate = next((level for level in level_payloads if level['state'] == 'unlocked' or level['state'] == 'content_unavailable' or level['state'] == 'completed'), None)
            if candidate:
                next_challenge = candidate

    total_levels = len(level_keys) * len(difficulty_keys)
    return {
        'mode': normalized_mode,
        'mode_title': _practice_progression_mode_title(normalized_mode),
        'sections': section_payloads,
        'summary': {
            'completed_levels': total_completed,
            'total_levels': total_levels,
            'progress_percent': round((total_completed / total_levels) * 100) if total_levels else 0,
            'stars_earned': total_stars,
            'current_difficulty': next_challenge['difficulty_label'] if next_challenge else 'Easy',
            'current_level': next_challenge['level_label'] if next_challenge else 'Level 1',
            'next_label': f"{next_challenge['difficulty_label']} {next_challenge['level_label']}" if next_challenge else 'Easy Level 1',
        },
    }


def _practice_row_summary(material):
    content_json = getattr(material, 'content_json', None) or {}
    selected_difficulty = getattr(material, 'difficulty_level', '') or content_json.get('difficulty', '')
    item_type = 'sentence' if selected_difficulty == 'hard' else 'word'
    items = parse_practice_items(material.content_text, item_type)
    item_count = len(items)
    summary_text = f"{item_count} {item_type}{'s' if item_count != 1 else ''}"
    status_label = 'Archived' if not material.is_active else (material.get_status_display() or material.status)
    status_badge_class = 'text-bg-secondary' if not material.is_active else ('text-bg-success' if material.status == 'published' else 'text-bg-warning')
    return {
        'material': material,
        'mode_label': _practice_config_label(content_json.get('mode', ''), AdminPracticeMaterialForm.MODE_CHOICES),
        'difficulty_label': _practice_config_label(selected_difficulty, AdminPracticeMaterialForm.DIFFICULTY_CHOICES),
        'level_label': _practice_config_label(content_json.get('level', ''), AdminPracticeMaterialForm.LEVEL_CHOICES),
        'language_label': content_json.get('language', ''),
        'item_count': item_count,
        'item_summary': summary_text,
        'items': items,
        'is_hard': selected_difficulty == 'hard',
        'status_label': status_label,
        'status_badge_class': status_badge_class,
    }


def _practice_matches_search(material, search_query):
    search_query = (search_query or '').strip().lower()
    if not search_query:
        return True
    row = _practice_row_summary(material)
    haystack = ' '.join([
        row['mode_label'].lower(),
        row['difficulty_label'].lower(),
        row['level_label'].lower(),
        row['language_label'].lower(),
        ' '.join(row['items']).lower(),
        (material.content_text or '').lower(),
    ])
    return search_query in haystack


def _sort_practice_rows(rows, sort_value):
    sort_value = (sort_value or '-created_at').strip()
    reverse = sort_value.startswith('-')
    field = sort_value.lstrip('-')
    if field == 'mode':
        return sorted(rows, key=lambda row: (row['mode_label'] or '').lower(), reverse=reverse)
    if field == 'difficulty':
        return sorted(rows, key=lambda row: (row['difficulty_label'] or '').lower(), reverse=reverse)
    if field == 'level':
        return sorted(rows, key=lambda row: (row['level_label'] or '').lower(), reverse=reverse)
    if field == 'updated_at':
        return sorted(rows, key=lambda row: row['material'].updated_at, reverse=reverse)
    return sorted(rows, key=lambda row: row['material'].created_at, reverse=reverse)


def _admin_practice_context(request, page_title):
    search_query = request.GET.get('q', '').strip()
    mode_filter = request.GET.get('mode', 'all').strip().lower()
    status_filter = request.GET.get('status', 'all').strip().lower()
    difficulty_filter = request.GET.get('difficulty', 'all').strip().lower()
    level_filter = request.GET.get('level', 'all').strip().lower()
    sort_value = request.GET.get('sort', '-created_at').strip()

    practice_items = _admin_practice_queryset()

    if mode_filter in {value for value, _label in AdminPracticeMaterialForm.MODE_CHOICES}:
        practice_items = practice_items.filter(content_json__mode=mode_filter)

    if status_filter == 'active':
        practice_items = practice_items.filter(is_active=True)
    elif status_filter == 'archived':
        practice_items = practice_items.filter(is_active=False)
    elif status_filter in {value for value, _label in AdminPracticeMaterialForm.STATUS_CHOICES}:
        practice_items = practice_items.filter(status=status_filter, is_active=True)

    if difficulty_filter in _practice_difficulty_values():
        practice_items = practice_items.filter(difficulty_level=difficulty_filter)

    if level_filter in {value for value, _label in AdminPracticeMaterialForm.LEVEL_CHOICES}:
        practice_items = practice_items.filter(content_json__level=level_filter)

    if search_query:
        practice_items = [item for item in practice_items if _practice_matches_search(item, search_query)]
    else:
        practice_items = list(practice_items)

    practice_rows = [_practice_row_summary(item) for item in practice_items]
    practice_rows = _sort_practice_rows(practice_rows, sort_value)

    context = _admin_context(request, page_title, [
        'Mode',
        'Difficulty',
        'Level',
        'Language',
        'Items',
        'Status',
        'Date Created',
        'Last Updated',
        'Actions',
    ])
    context.update({
        'practice_items': practice_rows,
        'search_query': search_query,
        'mode_filter': mode_filter,
        'status_filter': status_filter,
        'difficulty_filter': difficulty_filter,
        'level_filter': level_filter,
        'sort': sort_value,
        'mode_options': [('all', 'All Modes')] + AdminPracticeMaterialForm.MODE_CHOICES,
        'status_options': [('all', 'All Statuses'), ('active', 'Active')] + AdminPracticeMaterialForm.STATUS_CHOICES + [('archived', 'Archived')],
        'difficulty_options': [('all', 'All Difficulties')] + AdminPracticeMaterialForm.DIFFICULTY_CHOICES,
        'level_options': [('all', 'All Levels')] + AdminPracticeMaterialForm.LEVEL_CHOICES,
        'sort_options': [
            ('-created_at', 'Newest Created'),
            ('created_at', 'Oldest Created'),
            ('-updated_at', 'Recently Updated'),
            ('updated_at', 'Oldest Updated'),
            ('mode', 'Mode A-Z'),
            ('-mode', 'Mode Z-A'),
            ('difficulty', 'Difficulty A-Z'),
            ('-difficulty', 'Difficulty Z-A'),
            ('level', 'Level A-Z'),
            ('-level', 'Level Z-A'),
        ],
    })
    return context

def _admin_practice_template_context(request, material=None, page_title='Practice'):
    initial = {}
    if material:
        content_json = getattr(material, 'content_json', None) or {}
        initial = {
            'mode': content_json.get('mode', ''),
            'difficulty_level': material.difficulty_level,
            'level': content_json.get('level', ''),
            'status': material.status if getattr(material, 'status', None) in dict(AdminPracticeMaterialForm.STATUS_CHOICES) else 'draft',
            'language': content_json.get('language', ''),
            'content_text': material.content_text,
        }

    form = AdminPracticeMaterialForm(initial=initial, material=material)
    occupied_levels_map = {}
    for mode, _mode_label in AdminPracticeMaterialForm.MODE_CHOICES:
        occupied_levels_map[mode] = {}
        for difficulty, _difficulty_label in AdminPracticeMaterialForm.DIFFICULTY_CHOICES:
            occupied_levels_map[mode][difficulty] = form.get_occupied_levels(mode, difficulty)

    context = _admin_context(request, page_title, [])
    context.update({
        'form': form,
        'practice': material,
        'practice_status': _admin_practice_status(material) if material else '',
        'practice_item_count': len(_practice_material_items(material)),
        'occupied_levels_map': occupied_levels_map,
    })
    return context

def _save_admin_practice_material(form, material=None, request=None):
    """Save admin practice material directly to Material table (canonical storage)."""
    cleaned = form.cleaned_data
    material_obj = material if material and isinstance(material, Material) else Material()
    material_obj.title = f"{cleaned['mode'].title()} {cleaned['difficulty_level'].title()} {cleaned['level'].replace('_', ' ').title()}"
    material_obj.item_type = 'sentence' if cleaned['difficulty_level'] == 'hard' else 'word'
    material_obj.prompt_text = ''
    material_obj.content_text = cleaned.get('content_text', '')
    material_obj.content_json = {
        'mode': cleaned['mode'],
        'difficulty': cleaned['difficulty_level'],
        'level': cleaned['level'],
        'language': cleaned.get('language', ''),
    }
    material_obj.type = 'practice'
    material_obj.status = cleaned['status']
    material_obj.difficulty_level = cleaned['difficulty_level']
    material_obj.section = None
    material_obj.source_type = 'personal'
    material_obj.is_active = material_obj.status in ['published', 'scheduled']
    material_obj.save()
    return material_obj

@admin_required
@require_http_methods(["GET", "POST"])
def admin_practice_create(request):
    if request.method == 'POST':
        form = AdminPracticeMaterialForm(request.POST, material=None)
        if form.is_valid():
            material = _save_admin_practice_material(form, None, request)
            return redirect('admin_practice_detail', practice_id=material.id)
        context = _admin_context(request, 'Add Practice Content', [])
        context.update({'form': form, 'practice': None})
        return render(request, 'pabasa_app/admin_practice_create.html', context, status=400)

    return render(request, 'pabasa_app/admin_practice_create.html',
                  _admin_practice_template_context(request, None, 'Add Practice Content'))

@admin_required
def admin_practice_detail(request, practice_id):
    """View details of a practice material (practice_id refers to Material ID)."""
    material = _get_admin_practice_material(practice_id)
    if not material:
        return redirect('admin_practice_assessment')
    return render(request, 'pabasa_app/admin_practice_detail.html',
                  _admin_practice_template_context(request, material, 'Practice Details'))

@admin_required
@require_http_methods(["GET", "POST"])
def admin_practice_edit(request, practice_id):
    """Edit a practice material (practice_id refers to Material ID)."""
    material = _get_admin_practice_material(practice_id)
    if not material:
        return redirect('admin_practice_assessment')

    if request.method == 'POST':
        form = AdminPracticeMaterialForm(request.POST, material=material)
        if form.is_valid():
            updated_material = _save_admin_practice_material(form, material, request)
            return redirect('admin_practice_detail', practice_id=updated_material.id)
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
@require_http_methods(["POST"])
def admin_practice_delete(request, practice_id):
    material = _get_admin_practice_material(practice_id)
    if not material:
        return redirect('admin_practice_assessment')

    material.delete()
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

@xframe_options_sameorigin
def reading_word_page(request):
    return render(request, 'pabasa_app/reading_word_page.html', _dashboard_context(request))

@xframe_options_sameorigin
def reading_sentence_page(request):
    return render(request, 'pabasa_app/reading_sentence_page.html', _dashboard_context(request))

@xframe_options_sameorigin
def reading_para_page(request):
    return render(request, 'pabasa_app/reading_para_page.html', _dashboard_context(request))


@csrf_protect
@require_http_methods(["POST"])
def reading_transcribe_api(request):
    if not _check_auth(request):
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)

    audio = request.FILES.get('audio')
    target_text = (request.POST.get('target_text') or '').strip()
    if not audio:
        return JsonResponse({'success': False, 'error': 'Audio is required.'}, status=400)
    if not target_text:
        return JsonResponse({'success': False, 'error': 'Reading text is required.'}, status=400)

    try:
        current_syllable_index = int(request.POST.get('current_syllable_index') or 0)
    except (TypeError, ValueError):
        current_syllable_index = 0

    mode = (request.POST.get('mode') or '').strip().lower()
    language = (request.POST.get('language') or '').strip()
    language_code = language_code_for(language, mode)
    phrase_hints = phrase_hints_for(language, mode)
    api_key = getattr(settings, 'GOOGLE_STT_API_KEY', '').strip()
    project_id = getattr(settings, 'GOOGLE_CLOUD_PROJECT_ID', '').strip()
    location = getattr(settings, 'GOOGLE_STT_LOCATION', 'global').strip()
    stt_model = getattr(settings, 'GOOGLE_STT_MODEL', 'chirp_3').strip()
    credentials_file = str(getattr(settings, 'GOOGLE_STT_CREDENTIALS_FILE', '') or '')

    if not api_key and stt_model != 'chirp_3':
        return JsonResponse({'success': False, 'error': 'Google Speech is not configured.'}, status=503)

    try:
        transcript, model_used, fallback_reason = transcribe_audio_bytes_with_model(
            audio.read(),
            api_key,
            language_code=language_code,
            phrase_hints=phrase_hints,
            model=stt_model,
            project_id=project_id,
            location=location,
            mime_type=getattr(audio, 'content_type', '') or 'audio/webm',
            credentials_file=credentials_file,
        )
        analysis = analyze_reading(target_text, current_syllable_index, transcript)
        analysis.update({
            'success': True,
            'language_code': language_code,
            'stt_model': model_used,
            'stt_fallback_reason': fallback_reason,
        })
        return JsonResponse(analysis)
    except Exception as exc:
        logger.exception('Reading transcription failed')
        return JsonResponse({'success': False, 'error': str(exc)}, status=502)


@csrf_protect
@require_http_methods(["POST"])
def reading_read_aloud_api(request):
    if not _check_auth(request):
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)

    target_text = (request.POST.get('target_text') or '').strip()
    mode = (request.POST.get('mode') or '').strip().lower()
    language = (request.POST.get('language') or '').strip()
    language_code = language_code_for(language, mode)
    api_key = getattr(settings, 'GOOGLE_STT_API_KEY', '').strip()

    if not target_text:
        return JsonResponse({'success': False, 'error': 'Reading text is required.'}, status=400)
    if not api_key:
        return JsonResponse({'success': False, 'error': 'Google Text-to-Speech is not configured.'}, status=503)

    try:
        audio_content = synthesize_read_aloud_audio(target_text, api_key, language_code)
        return JsonResponse({
            'success': True,
            'audio_content': audio_content,
            'mime_type': 'audio/mpeg',
            'language_code': language_code,
        })
    except Exception as exc:
        logger.exception('Read aloud synthesis failed')
        return JsonResponse({'success': False, 'error': str(exc)}, status=502)


def _student_practice_queryset():
    return Material.objects.filter(
        section__isnull=True,
        type='practice',
        is_active=True,
        status='published',
        difficulty_level__in=_practice_difficulty_values(),
    ).order_by('created_at', 'id')

def _material_practice_completion(material, student_user):
    if not material or not student_user:
        return {}
    content_json = getattr(material, 'content_json', None) or {}
    if not isinstance(content_json, dict):
        return {}
    completions = content_json.get('student_completions') or {}
    if not isinstance(completions, dict):
        return {}
    completion = completions.get(str(student_user.id)) or {}
    return completion if isinstance(completion, dict) else {}

def _record_material_practice_completion(material, student_user, attempt_payload):
    content_json = dict(getattr(material, 'content_json', None) or {})
    completions = dict(content_json.get('student_completions') or {})
    existing_completion = completions.get(str(student_user.id)) or {}
    try:
        incoming_stars = max(0, int(attempt_payload.get('stars_earned', 0) or 0))
    except (TypeError, ValueError):
        incoming_stars = 0
    try:
        existing_stars = max(0, int(existing_completion.get('stars_earned', 0) or 0))
    except (TypeError, ValueError):
        existing_stars = 0
    game_mode = str(content_json.get('mode') or attempt_payload.get('game_mode') or '').strip().lower()
    saved_stars = max(existing_stars, incoming_stars) if game_mode == 'color' else incoming_stars
    completion = {
        'student_id': student_user.id,
        'status': 'completed',
        'completed_at': attempt_payload.get('completed_at') or timezone.now().isoformat(),
        'stars_earned': saved_stars,
        'items_completed': attempt_payload.get('items_completed', 0),
        'total_practice_items': attempt_payload.get('total_practice_items', 0),
        'total_read_words': attempt_payload.get('total_read_words', 0),
        'total_skipped_words': attempt_payload.get('total_skipped_words', 0),
        'correct_responses': attempt_payload.get('correct_responses', 0),
        'incorrect_responses': attempt_payload.get('incorrect_responses', 0),
        'reading_time_seconds': attempt_payload.get('reading_time_seconds', 0),
        'score': attempt_payload.get('score', 0),
        'accuracy': attempt_payload.get('accuracy', 0),
        'wpm': attempt_payload.get('wpm', 0),
        'attempt_number': attempt_payload.get('attempt_number', 1),
        'device_info': attempt_payload.get('device_info', {}),
    }
    completions[str(student_user.id)] = completion
    content_json['student_completions'] = completions
    material.content_json = content_json
    material.save(update_fields=['content_json', 'updated_at'])
    return completion

def _serialize_student_practice_material(material, student_user=None):
    completion = _material_practice_completion(material, student_user)
    is_done = completion.get('status') in {'completed', 'done'}
    content_json = dict(getattr(material, 'content_json', None) or {})
    selected_difficulty = getattr(material, 'difficulty_level', '') or content_json.get('difficulty', '')
    selected_level = content_json.get('level', '')
    return {
        'id': f"practice-{material.id}",
        'raw_id': material.id,
        'title': material.title,
        'difficulty': selected_difficulty,
        'difficulty_label': _practice_config_label(selected_difficulty, AdminPracticeMaterialForm.DIFFICULTY_CHOICES),
        'level': selected_level,
        'level_label': _practice_config_label(selected_level, AdminPracticeMaterialForm.LEVEL_CHOICES),
        'game_mode': str(content_json.get('mode') or '').strip().lower(),
        'type': material.item_type,
        'status': 'Done' if is_done else material.status,
        'raw_status': material.status,
        'is_done': is_done,
        'completed_at': completion.get('completed_at', ''),
        'stars_earned': max(0, int(completion.get('stars_earned') or 0)),
        'prompt': material.prompt_text,
        'content': material.content_text,
        'items': _practice_material_items(material),
        'created_at': material.created_at.isoformat() if material.created_at else '',
    }

def _student_practice_context(request, mode=None):
    context = _dashboard_context(request, 'student')
    student_user = User.objects.filter(id=request.session.get('user_id')).first()
    materials = [_serialize_student_practice_material(material, student_user) for material in _student_practice_queryset()]
    context.update({
        'practice_materials': materials,
        'practice_difficulties': AdminPracticeMaterialForm.DIFFICULTY_CHOICES,
        'selected_practice_mode': mode or '',
        'selected_practice_difficulty': request.GET.get('difficulty', '').strip().lower(),
    })
    return context


def _build_live_assessment_action_url(material, session_id, start_at, countdown_seconds=10):
    if not material:
        return ''

    item_type = (material.item_type or '').strip().lower()
    if item_type == 'sentence':
        mode = 'sentence'
    elif item_type == 'paragraph':
        mode = 'para'
    else:
        mode = 'word'

    title = (material.title or material.prompt_text or 'Assessment').strip() or 'Assessment'
    code = (material.code or '').strip() or 'LIVE'
    content = (material.content_text or material.prompt_text or '').strip()
    content_json = material.content_json or {}
    if isinstance(content_json, dict):
        content = content or (content_json.get('content_text') or '').strip()
    language = (content_json.get('language') if isinstance(content_json, dict) else '') or 'English'
    params = {
        'id': str(material.id),
        'test': title,
        'code': code,
        'live': '1',
        'live_session_id': session_id,
        'start_at': start_at,
        'countdown': str(countdown_seconds),
        'content': content,
        'item_type': item_type or 'word',
        'language': language,
    }
    query = '&'.join(f'{key}={quote(str(value), safe="")}' for key, value in params.items())
    return f'/dashboard/assessment/reading_ui/{mode}/?{query}'


def _build_assist_assessment_url(material, student_user, course, teacher_user, section=None):
    if not material or not student_user or not teacher_user:
        return ''

    item_type = (material.item_type or '').strip().lower()
    mode = 'sentence' if item_type == 'sentence' else 'para' if item_type == 'paragraph' else 'word'
    content_json = material.content_json or {}
    content = (material.content_text or material.prompt_text or '').strip()
    if isinstance(content_json, dict):
        content = content or (content_json.get('content_text') or '').strip()
    language = (content_json.get('language') if isinstance(content_json, dict) else '') or 'English'
    token = signing.dumps({
        'student_id': student_user.id,
        'teacher_id': teacher_user.id,
        'course_id': course.id if course else None,
        'material_id': material.id,
    }, salt='pabasa-assist-assessment')
    params = {
        'id': str(material.id),
        'test': (material.title or material.prompt_text or 'Assessment').strip() or 'Assessment',
        'code': section.class_code if section else (material.code or (course.code if course else 'ASSIST')),
        'content': content,
        'item_type': item_type or 'word',
        'language': language,
        'assist': '1',
        'assist_token': token,
    }
    query = '&'.join(f'{key}={quote(str(value), safe="")}' for key, value in params.items())
    return f'/dashboard/assessment/reading_ui/{mode}/?{query}'


def _resolve_assist_token(token, max_age=60 * 60 * 4):
    if not token:
        return None
    try:
        payload = signing.loads(token, salt='pabasa-assist-assessment', max_age=max_age)
    except signing.BadSignature:
        return None
    student_user = User.objects.filter(id=payload.get('student_id'), role='student', is_archived=False).first()
    teacher_user = User.objects.filter(id=payload.get('teacher_id'), role__in=['teacher', 'admin']).first()
    material = Material.objects.filter(id=payload.get('material_id')).first()
    course = Course.objects.filter(id=payload.get('course_id')).first() if payload.get('course_id') else None
    if not student_user or not teacher_user or not material:
        return None
    if course and teacher_user.role != 'admin' and course.teacher_id != teacher_user.id:
        return None
    sections = course.sections.filter(is_active=True) if course else Section.objects.filter(is_active=True, teacher=teacher_user)
    allowed = any(section.has_student(student_user, active_only=True) for section in sections)
    if not allowed:
        return None
    return {
        'student': student_user,
        'teacher': teacher_user,
        'material': material,
        'course': course,
    }


@csrf_protect
@require_http_methods(["GET"])
def get_assist_students(request):
    if not _check_auth(request):
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
    if request.session.get('user_role') not in ['teacher', 'admin']:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    teacher_user = User.objects.filter(id=request.session.get('user_id')).first()
    course = Course.objects.filter(id=request.GET.get('course_id')).first()
    material = Material.objects.filter(id=request.GET.get('material_id')).first()
    if not teacher_user or not course or not material:
        return JsonResponse({'success': False, 'error': 'Course or material not found'}, status=404)
    if teacher_user.role != 'admin' and course.teacher_id != teacher_user.id:
        return JsonResponse({'success': False, 'error': 'Course access denied'}, status=403)
    if not course.materials.filter(id=material.id).exists():
        return JsonResponse({'success': False, 'error': 'Material is not assigned to this course'}, status=403)

    students = []
    seen = set()
    for section in course.sections.filter(is_active=True).order_by('class_name'):
        for entry in section.get_enrolled_students(active_only=True):
            student_id = entry.get('student_id')
            if not student_id or student_id in seen:
                continue
            student_user = User.objects.filter(id=student_id, role='student', is_archived=False).first()
            if not student_user:
                continue
            seen.add(student_id)
            students.append({
                'id': student_user.id,
                'custom_id': student_user.custom_id,
                'name': f"{student_user.first_name} {student_user.last_name}".strip() or student_user.custom_id,
                'email': student_user.email,
                'section': section.class_name,
                'section_code': section.class_code,
            })
    return JsonResponse({'success': True, 'students': students})


@csrf_protect
@require_http_methods(["POST"])
def start_assist_assessment(request):
    if not _check_auth(request):
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
    if request.session.get('user_role') not in ['teacher', 'admin']:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        data = {}

    teacher_user = User.objects.filter(id=request.session.get('user_id')).first()
    course = Course.objects.filter(id=data.get('course_id')).first()
    material = Material.objects.filter(id=data.get('material_id')).first()
    student_user = User.objects.filter(id=data.get('student_id'), role='student', is_archived=False).first()
    if not teacher_user or not course or not material or not student_user:
        return JsonResponse({'success': False, 'error': 'Unable to start assisted assessment'}, status=404)
    if teacher_user.role != 'admin' and course.teacher_id != teacher_user.id:
        return JsonResponse({'success': False, 'error': 'Course access denied'}, status=403)
    if not course.materials.filter(id=material.id).exists():
        return JsonResponse({'success': False, 'error': 'Material is not assigned to this course'}, status=403)

    section = None
    for candidate in course.sections.filter(is_active=True):
        if candidate.has_student(student_user, active_only=True):
            section = candidate
            break
    if section is None:
        return JsonResponse({'success': False, 'error': 'Student is not enrolled in this course'}, status=403)

    _create_notification(
        teacher_user,
        'Assist assessment started',
        f'{teacher_user.first_name} {teacher_user.last_name} started assisted assessment "{material.title}" for {student_user.first_name} {student_user.last_name}.',
        'assessment',
        '',
        teacher_user,
        send_email=False,
        force_in_app=True,
    )
    return JsonResponse({
        'success': True,
        'launch_url': _build_assist_assessment_url(material, student_user, course, teacher_user, section),
    })


@require_http_methods(["GET"])
def live_assessment_server_time(request):
    return JsonResponse({
        'success': True,
        'server_time': timezone.now().isoformat(),
    })


@csrf_protect
@require_http_methods(["POST"])
def start_live_assessment(request):
    if not _check_auth(request):
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)

    if request.session.get('user_role') not in ['teacher', 'admin']:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        data = {}

    course_id = data.get('course_id')
    material_id = data.get('material_id')
    teacher_user = User.objects.filter(id=request.session.get('user_id')).first()
    if not teacher_user:
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)

    course = None
    if course_id:
        course = Course.objects.filter(id=course_id).first()
        if course and teacher_user.role != 'admin' and course.teacher_id != teacher_user.id:
            return JsonResponse({'success': False, 'error': 'Course access denied'}, status=403)

    material = None
    if material_id:
        material = Material.objects.filter(id=material_id).first()
        if material and teacher_user.role != 'admin' and material.teacher_id != teacher_user.id:
            is_course_linked = bool(
                course and (
                    course.sections.filter(id=material.section_id).exists()
                    or material.assigned_sections.filter(id__in=course.sections.values_list('id', flat=True)).exists()
                    or material.courses.filter(id=course.id).exists()
                )
            )
            if not is_course_linked:
                return JsonResponse({'success': False, 'error': 'Material access denied'}, status=403)

    if not material:
        return JsonResponse({'success': False, 'error': 'Material not found'}, status=404)

    sections = []
    if course:
        sections = list(course.sections.filter(is_active=True))
        if not sections and material.section and material.section.is_active:
            sections = [material.section]
    elif material.section and material.section.is_active:
        sections = [material.section]

    if not sections:
        return JsonResponse({'success': False, 'error': 'No class sections available for this material'}, status=400)

    student_ids = []
    seen_student_ids = set()
    for section in sections:
        for entry in section.get_enrolled_students(active_only=True):
            student_id = entry.get('student_id')
            if not student_id or str(student_id) in seen_student_ids:
                continue
            student_user = User.objects.filter(id=student_id, role='student', is_archived=False).first()
            if student_user:
                seen_student_ids.add(str(student_id))
                student_ids.append(student_user.id)

    if not student_ids:
        return JsonResponse({'success': False, 'error': 'No active students found for this course'}, status=400)

    session_id = uuid.uuid4().hex
    start_at = timezone.now().isoformat()
    countdown_seconds = 10
    action_url = _build_live_assessment_action_url(material, session_id, start_at, countdown_seconds)
    title = 'Live Assessment Starting'
    message = (
        f"Your teacher has started a live assessment for {material.title or 'this reading'}. "
        "You'll be redirected automatically and begin together in a moment."
    )

    for student_id in student_ids:
        student_user = User.objects.filter(id=student_id).first()
        if not student_user:
            continue
        _create_notification(
            student_user,
            title,
            message,
            'assessment',
            action_url,
            teacher_user,
            send_email=False,
            force_in_app=True,
        )

    return JsonResponse({
        'success': True,
        'session': {
            'id': session_id,
            'start_at': start_at,
            'student_count': len(student_ids),
            'action_url': action_url,
        },
    })


@never_cache
@login_required(role='student')
def practice_word_page(request):
    return render(request, 'pabasa_app/practice_word_page.html', _student_practice_context(request, 'word'))

@never_cache
@login_required(role='student')
def practice_sentence_page(request):
    return render(request, 'pabasa_app/practice_sentence_page.html', _student_practice_context(request, 'sentence'))

@never_cache
@login_required(role='student')
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

def _practice_tutorial_flag_key(mode):
    mode_key = (mode or '').strip().lower()
    mapping = {
        'free': 'free_mode_tutorial_seen',
        'color': 'color_mode_tutorial_seen',
        'hunt': 'hunt_mode_tutorial_seen',
    }
    return mapping.get(mode_key)


def _get_user_preference_dict(user):
    pref = getattr(user, 'preference', None) or {}
    return pref if isinstance(pref, dict) else {}


def _has_seen_practice_tutorial(request, user, flag_key):
    if not flag_key:
        return True
    preferences = _get_user_preference_dict(user)
    return bool(preferences.get(flag_key) or request.session.get(flag_key))


def _mark_practice_tutorial_seen(request, user, flag_key):
    if not flag_key:
        return
    request.session[flag_key] = True
    request.session.modified = True
    if not user:
        return
    preferences = dict(_get_user_preference_dict(user))
    if preferences.get(flag_key) is True:
        return
    preferences[flag_key] = True
    user.preference = preferences
    user.save(update_fields=['preference', 'updated_at'])


def _practice_tutorial_content(mode):
    mode_key = (mode or '').strip().lower()
    mapping = {
        'free': [
            'Welcome to Free Mode! Read the word aloud.',
            'Swipe up to read. Swipe down to skip.',
            'Finish all the words and have fun reading!',
        ],
        'color': [
            'Welcome to Color Mode! The picture is empty.',
            'Read a word correctly. A new part appears!',
            'Keep reading until the whole picture is complete!',
        ],
        'hunt': [
            'Welcome to Hunt Mode! Get ready for a challenge.',
            'Read words correctly to score points.',
            'Beat the timer and aim for the highest score!',
        ],
    }
    return mapping.get(mode_key, mapping['free'])


@never_cache
@login_required(role='student')
def practice(request):
    student_user = User.objects.filter(id=request.session.get('user_id')).first()
    context = _student_practice_context(request)
    context['game_progression_summary'] = {
        mode: _practice_game_progression(mode, student_user)['summary']
        for mode in ['free', 'color', 'hunt']
    }
    return render(request, 'pabasa_app/practice.html', context)


STUDENT_THEME_CATALOG = {
    'sky': {'name': 'Sky Island', 'cost': 0, 'icon': 'cloud-sun', 'note': 'Starter theme'},
    'forest': {'name': 'Forest', 'cost': 75, 'icon': 'tree', 'note': 'Leafy reading trails'},
    'treasure': {'name': 'Treasure Island', 'cost': 120, 'icon': 'gem', 'note': 'Golden map accents'},
    'ocean': {'name': 'Ocean Voyage', 'cost': 160, 'icon': 'water', 'note': 'Calm sea details'},
    'space': {'name': 'Space Reading', 'cost': 220, 'icon': 'rocket-takeoff', 'note': 'Cosmic reading glow'},
    'zoo': {'name': 'Zoo', 'cost': 280, 'icon': 'binoculars', 'note': 'Wildlife-inspired accents'},
    'library': {'name': 'Magic Library', 'cost': 350, 'icon': 'stars', 'note': 'Enchanted book details'},
}


def _student_theme_lifetime_stars(student_user):
    if not student_user:
        return 0
    return sum(
        max(0, int(_practice_game_progression(mode, student_user)['summary'].get('stars_earned') or 0))
        for mode in ['free', 'color', 'hunt']
    )


def _sync_student_theme_wallet(student_user):
    lifetime_stars = _student_theme_lifetime_stars(student_user)
    credited = max(0, int(student_user.theme_stars_credited or 0))
    available = max(0, int(student_user.available_stars or 0))
    if lifetime_stars > credited:
        available += lifetime_stars - credited
        credited = lifetime_stars

    unlocked = student_user.unlocked_themes if isinstance(student_user.unlocked_themes, list) else []
    unlocked = list(dict.fromkeys(['sky', *[slug for slug in unlocked if slug in STUDENT_THEME_CATALOG]]))
    equipped = student_user.equipped_theme if student_user.equipped_theme in unlocked else 'sky'
    changed = (
        available != student_user.available_stars
        or credited != student_user.theme_stars_credited
        or unlocked != student_user.unlocked_themes
        or equipped != student_user.equipped_theme
    )
    student_user.available_stars = available
    student_user.theme_stars_credited = credited
    student_user.unlocked_themes = unlocked
    student_user.equipped_theme = equipped
    if changed:
        student_user.save(update_fields=[
            'available_stars', 'theme_stars_credited', 'unlocked_themes', 'equipped_theme', 'updated_at'
        ])
    return lifetime_stars


@never_cache
@login_required(role='student')
def theme_shop(request):
    with transaction.atomic():
        student_user = User.objects.select_for_update().get(id=request.session.get('user_id'))
        lifetime_stars = _sync_student_theme_wallet(student_user)

    context = _student_practice_context(request)
    unlocked = set(student_user.unlocked_themes or ['sky'])
    themes = []
    for slug, theme in STUDENT_THEME_CATALOG.items():
        owned = slug in unlocked
        equipped = student_user.equipped_theme == slug
        themes.append({
            'slug': slug,
            **theme,
            'owned': owned,
            'equipped': equipped,
            'can_afford': student_user.available_stars >= theme['cost'],
            'status': 'equipped' if equipped else 'unlocked' if owned else 'locked',
        })
    context.update({
        'stars_earned': lifetime_stars,
        'available_stars': student_user.available_stars,
        'shop_themes': themes,
    })
    return render(request, 'pabasa_app/theme_shop.html', context)


@csrf_protect
@require_http_methods(["POST"])
@login_required(role='student')
def student_theme_action(request):
    try:
        payload = json.loads(request.body or '{}')
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)
    slug = str(payload.get('theme') or '').strip().lower()
    action = str(payload.get('action') or '').strip().lower()
    theme = STUDENT_THEME_CATALOG.get(slug)
    if not theme or action not in {'unlock', 'equip'}:
        return JsonResponse({'success': False, 'error': 'Invalid theme action.'}, status=400)

    with transaction.atomic():
        student_user = User.objects.select_for_update().get(id=request.session.get('user_id'), role='student')
        lifetime_stars = _sync_student_theme_wallet(student_user)
        unlocked = list(student_user.unlocked_themes or ['sky'])

        if action == 'unlock' and slug not in unlocked:
            if student_user.available_stars < theme['cost']:
                return JsonResponse({
                    'success': False,
                    'error': 'Not enough stars.',
                    'available_stars': student_user.available_stars,
                }, status=400)
            student_user.available_stars -= theme['cost']
            unlocked.append(slug)
            student_user.unlocked_themes = list(dict.fromkeys(unlocked))
            student_user.save(update_fields=['available_stars', 'unlocked_themes', 'updated_at'])
        elif action == 'equip':
            if slug not in unlocked:
                return JsonResponse({'success': False, 'error': 'Unlock this theme first.'}, status=403)
            student_user.equipped_theme = slug
            student_user.save(update_fields=['equipped_theme', 'updated_at'])

    return JsonResponse({
        'success': True,
        'theme': slug,
        'owned': slug in student_user.unlocked_themes,
        'equipped_theme': student_user.equipped_theme,
        'available_stars': student_user.available_stars,
        'total_stars_earned': lifetime_stars,
    })


@never_cache
@login_required(role='student')
@require_http_methods(["POST"])
def practice_mark_tutorial_seen(request, mode):
    normalized_mode = (mode or '').strip().lower()
    flag_key = _practice_tutorial_flag_key(normalized_mode)
    student_user = User.objects.filter(id=request.session.get('user_id'), role='student').first()
    _mark_practice_tutorial_seen(request, student_user, flag_key)
    return redirect('practice_game_progression', mode=normalized_mode)


@never_cache
@login_required(role='student')
def practice_game_progression(request, mode):
    student_user = User.objects.filter(id=request.session.get('user_id')).first()
    normalized_mode = (mode or '').strip().lower()
    if normalized_mode not in {'free', 'color', 'hunt'}:
        return redirect('practice')

    context = _student_practice_context(request)
    progression = _practice_game_progression(normalized_mode, student_user)
    progression = _apply_progression_unlock_override(progression, request.GET.get('unlock', ''))
    flag_key = _practice_tutorial_flag_key(normalized_mode)
    show_tutorial = not _has_seen_practice_tutorial(request, student_user, flag_key)
    if show_tutorial:
        # The automatic guide is a one-time introduction. Count the first page
        # display itself so closing with X cannot make it auto-open again.
        _mark_practice_tutorial_seen(request, student_user, flag_key)
    context.update({
        'selected_game_mode': normalized_mode,
        'game_mode_title': progression['mode_title'],
        'game_progression': progression,
        'game_progression_summary': progression['summary'],
        'tutorial_mode': normalized_mode,
        'tutorial_title': progression['mode_title'],
        'tutorial_cards': _practice_tutorial_content(normalized_mode),
        'show_tutorial': show_tutorial,
    })
    return render(request, 'pabasa_app/practice_progression.html', context)

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
    birthday_display = ""
    if user.birth_month and user.birth_day and user.birth_year:
        birthday_display = f"{int(user.birth_month):02d}/{int(user.birth_day):02d}/{user.birth_year}"

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

        # Handle notification preference changes from the profile page.
        elif request.POST.get('save_notification_settings') == 'true':
            try:
                data = {}
                if request.content_type == 'application/json':
                    data = json.loads(request.body or '{}')
                else:
                    data = {
                        'push_enabled': request.POST.get('push_enabled') == 'true',
                        'email_notifications': request.POST.get('email_notifications') == 'true',
                        'weekly_digest_enabled': request.POST.get('weekly_digest_enabled') == 'true',
                        'new_materials': request.POST.get('new_materials') == 'true',
                        'reading_reminders': request.POST.get('reading_reminders') == 'true',
                        'progress_updates': request.POST.get('progress_updates') == 'true',
                    }
                notification_settings = _json_notification_settings(data, user)
                _set_profile_dict(user, 'notification_settings', notification_settings)
                return JsonResponse({
                    'success': True,
                    'message': 'Notification preferences saved.',
                    'notification_settings': notification_settings,
                })
            except Exception as e:
                logger.error(f"Error saving notification preferences for {user.custom_id}: {str(e)}")
                return JsonResponse({'success': False, 'error': str(e)})

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
        'gender': user.sex or '',
        'birthday_display': birthday_display,
        'grade_level': user.grade_level or '',
        'contact_number': user.contact_no or '',
        'notification_settings': _notification_settings_for_user(user),
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
@login_required(role='teacher')
def send_course_update(request):
    """Send a course progress update to selected enrolled students and store sent updates as notes."""
    try:
        data = json.loads(request.body or '{}')
        course_id = data.get('course_id')
        student_ids = data.get('student_ids') or []
        update_type = str(data.get('update_type') or 'general').strip()[:50]
        message_template = str(data.get('message') or '').strip()

        if not course_id:
            return JsonResponse({'success': False, 'error': 'Course is required'}, status=400)
        if not isinstance(student_ids, list) or not student_ids:
            return JsonResponse({'success': False, 'error': 'Select at least one recipient'}, status=400)
        if not message_template:
            return JsonResponse({'success': False, 'error': 'Teacher comments are required'}, status=400)

        teacher_user = User.objects.filter(id=request.session.get('user_id'), role='teacher').first()
        if not teacher_user:
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        course = Course.objects.filter(id=course_id, teacher=teacher_user, is_active=True).prefetch_related('sections').first()
        if not course:
            return JsonResponse({'success': False, 'error': 'Course not found'}, status=404)

        selected_student_ids = []
        for raw_id in student_ids:
            try:
                selected_student_ids.append(int(raw_id))
            except (TypeError, ValueError):
                continue

        if not selected_student_ids:
            return JsonResponse({'success': False, 'error': 'No valid student recipients selected'}, status=400)

        course_sections = list(course.sections.filter(is_active=True))
        students = User.objects.filter(id__in=selected_student_ids, role='student')
        students_by_id = {student.id: student for student in students}
        ordered_students = [students_by_id[sid] for sid in selected_student_ids if sid in students_by_id]

        sender = getattr(settings, 'DEFAULT_FROM_EMAIL', 'pabasa.tupc@gmail.com')
        sent = []
        skipped = []

        for student in ordered_students:
            if not any(section.has_student(student, active_only=True) for section in course_sections):
                skipped.append({'student_id': student.id, 'reason': 'not_enrolled'})
                continue
            if not student.email:
                skipped.append({'student_id': student.id, 'reason': 'missing_email'})
                continue

            student_name = f"{student.first_name} {student.last_name}".strip() or student.custom_id or 'Student'
            personalized_message = message_template.replace('{name}', student_name)
            report = _latest_student_reading_report(student, sections=course_sections, course=course)
            scheduled_at_input = str(data.get('scheduled_at') or data.get('scheduledAt') or data.get('scheduled_at_input') or '').strip()
            reading_material_input = str(data.get('reading_material') or '').strip()
            report_text = _format_reading_report_text(report)
            normalized_update_type = update_type.lower()

            attachment_name = None
            attachment_bytes = None
            attachment_mime = 'application/pdf'
            report_attachment_included = False

            if normalized_update_type == 'followup':
                subject = "Student Reading Progress Report – PABASA"
                report_attachment_included = True
                attachment_name = f"{student_name.replace(' ', '_')}_reading_report.pdf"
                email_body = (
                    "Dear Parent/Guardian,\n\n"
                    "We hope you are doing well.\n\n"
                    "Attached is the latest Reading Progress Report for your child from the PABASA Reading Assessment System. "
                    "The report contains an overview of your child's recent reading performance, including assessment results, progress, and other relevant information.\n\n"
                    "We encourage you to review the attached report and continue supporting your child's reading development at home.\n\n"
                    "If you have any questions or would like to discuss your child's progress, please feel free to contact the school.\n\n"
                    "Thank you for your continued support and partnership in your child's learning.\n\n"
                    "Sincerely,\n\n"
                    "PABASA Team"
                )
                include_attachment = True
            elif normalized_update_type == 'commendation':
                subject = "Performance Commendation – PABASA"
                certificate_date = timezone.localtime(timezone.now(), timezone.get_default_timezone()).strftime('%B %d, %Y')
                certificate_pdf = _build_certificate_pdf(
                    student_name=student_name,
                    issued_on=certificate_date,
                    school_name='PABASA',
                    teacher_name=f"{teacher_user.first_name} {teacher_user.last_name}".strip() or 'Teacher',
                )
                email_body = (
                    f"Dear {student_name},\n\n"
                    "Congratulations on your continued effort and success in reading! "
                    "We are very proud of the progress you have made and the dedication you have shown.\n\n"
                    f"{personalized_message}\n\n"
                    "A certificate is attached for your recognition. "
                    "This Certificate of Achievement celebrates your outstanding reading performance and dedication to learning. "
                    "Please keep it as a reminder of your outstanding reading achievement.\n\n"
                    "Sincerely,\n\n"
                    "PABASA Team"
                )
                include_attachment = True
                attachment_name = f"{student_name.replace(' ', '_')}_certificate_of_achievement.pdf"
                attachment_bytes = certificate_pdf
                attachment_mime = 'application/pdf'
            elif normalized_update_type == 'assessment':
                subject = "Scheduled Assessment Notice – PABASA"
                assessment_title = str(data.get('assessment_title') or 'Reading Assessment').strip() or 'Reading Assessment'
                scheduled_at = str(scheduled_at_input or 'TBD').strip() or 'TBD'
                reading_material = reading_material_input or str(data.get('reading_material') or 'Not specified').strip() or 'Not specified'

                try:
                    from datetime import datetime
                    parsed_dt = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                    if parsed_dt.tzinfo is None:
                        parsed_dt = parsed_dt.replace(tzinfo=timezone.get_current_timezone())
                    scheduled_at_display = timezone.localtime(parsed_dt, timezone.get_default_timezone()).strftime('%B %d, %Y at %I:%M %p')
                except Exception:
                    scheduled_at_display = scheduled_at

                email_body = (
                    f"Dear {student_name},\n\n"
                    f"This is a reminder that your scheduled reading assessment, {assessment_title}, is coming up.\n\n"
                    f"Scheduled Date and Time: {scheduled_at_display}\n"
                    f"Reading Material: {reading_material}\n\n"
                    f"{personalized_message}\n\n"
                    "Please prepare ahead of time and be ready to do your best.\n\n"
                    "Sincerely,\n\n"
                    "PABASA Team"
                )
                include_attachment = False
            else:
                subject = "Student Reading Progress Report – PABASA"
                email_body = (
                    "Dear Parent/Guardian,\n\n"
                    "We hope you are doing well.\n\n"
                    "Attached is the latest Reading Progress Report for your child from the PABASA Reading Assessment System. "
                    "The report contains an overview of your child's recent reading performance, including assessment results, progress, and other relevant information.\n\n"
                    "We encourage you to review the attached report and continue supporting your child's reading development at home.\n\n"
                    "If you have any questions or would like to discuss your child's progress, please feel free to contact the school.\n\n"
                    "Thank you for your continued support and partnership in your child's learning.\n\n"
                    "Sincerely,\n\n"
                    "PABASA Team"
                )
                include_attachment = True
            note_text = (
                f"Course: {course.title} ({course.code})\n"
                f"Update Type: {update_type}\n"
                f"Recipient Email: {student.email}\n\n"
                f"Teacher Comments:\n"
                f"{personalized_message}\n\n"
                f"{report_text}"
            )

            email_message = EmailMultiAlternatives(
                subject,
                email_body,
                sender,
                [student.email],
            )
            if include_attachment:
                try:
                    if normalized_update_type == 'commendation':
                        email_message.attach(attachment_name, attachment_bytes, attachment_mime)
                    else:
                        pdf_bytes = _build_reading_report_pdf(
                            report,
                            message=personalized_message,
                            course=course,
                            teacher=teacher_user,
                            recipient_email=student.email,
                        )
                        email_message.attach(attachment_name, pdf_bytes, 'application/pdf')
                except Exception:
                    logger.exception('Failed to build PDF attachment for course update')
            email_message.send(fail_silently=False)
            Note.objects.create(
                teacher=teacher_user,
                student=student,
                note_text=note_text,
                note_type=f"course_update:{update_type}"[:50],
            )
            sent.append({
                'student_id': student.id,
                'email': student.email,
                'name': student_name,
                'report_summary': report.get('summary'),
                'report_included': report_attachment_included,
            })

        if not sent:
            return JsonResponse({
                'success': False,
                'error': 'No selected recipients could be emailed',
                'skipped': skipped,
            }, status=400)

        return JsonResponse({
            'success': True,
            'sent_count': len(sent),
            'sent': sent,
            'skipped': skipped,
            'report_included': any(item.get('report_included', False) for item in sent),
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload'}, status=400)
    except Exception as e:
        logger.exception('Failed to send course update')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


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
        _notify_principals(
            'New class created',
            f"{teacher_user.first_name} {teacher_user.last_name} created a new class: {new_class.class_name}.",
            'info',
            reverse('dashboard_principal'),
            teacher_user,
            send_email=False,
        )

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
def _derive_attempt_completion_percentage(attempt):
    if not isinstance(attempt, dict):
        return 0.0

    for key in ['completion_percentage', 'progress_percentage', 'progress_percent', 'completionPercent', 'progressPercent']:
        value = attempt.get(key)
        if value in (None, ''):
            continue
        try:
            percentage = float(value)
        except (TypeError, ValueError):
            continue
        if 0 <= percentage <= 100:
            return percentage

    items_completed = attempt.get('items_completed')
    total_items = attempt.get('total_practice_items') or attempt.get('total_items') or attempt.get('total_material_items')
    if items_completed is not None and total_items not in (None, ''):
        try:
            return max(0.0, min(100.0, (float(items_completed) / float(total_items)) * 100.0))
        except (TypeError, ValueError):
            pass

    status = str(attempt.get('status') or '').lower()
    if status == 'completed':
        return 100.0
    return 0.0


def _compute_course_average_progress(course):
    try:
        enrolled_students = []
        for section in course.sections.filter(is_active=True):
            for entry in section.get_enrolled_students(active_only=True):
                student_id = _normalized_student_entry_id(entry)
                if student_id:
                    enrolled_students.append(student_id)
        if not enrolled_students:
            return 0.0

        material_ids = []
        for material in course.materials.filter(is_active=True):
            if str(getattr(material, 'status', '') or '').strip().lower() == 'archived':
                continue
            material_ids.append(material.id)

        if not material_ids:
            return 0.0

        progress_values = []
        for student_id in enrolled_students:
            try:
                student_user = User.objects.filter(id=int(student_id), role='student').first()
            except Exception:
                student_user = None
            if not student_user:
                continue

            completion_total = 0.0
            completion_count = 0
            for material_id in material_ids:
                material = Material.objects.filter(id=material_id).first()
                if not material:
                    continue
                try:
                    if getattr(material, 'assessment_id', None) is not None:
                        assessment = material.assessment
                        if assessment is None:
                            continue
                        latest_attempt = assessment.get_attempts(student_user)
                        if latest_attempt:
                            completion_total += _derive_attempt_completion_percentage(latest_attempt[-1])
                            completion_count += 1
                    else:
                        latest_result = Assessment.objects.filter(
                            material=material,
                            student=student_user,
                            is_active=True,
                            source_assessment__isnull=True,
                        ).order_by('-created_at').first()
                        if latest_result:
                            completion_total += _derive_attempt_completion_percentage({
                                'status': getattr(latest_result, 'attempt_status', ''),
                                'items_completed': getattr(latest_result, 'items_completed', None),
                                'total_practice_items': getattr(latest_result, 'total_practice_items', None),
                            })
                            completion_count += 1
                except Exception:
                    continue

            if completion_count:
                progress_values.append(completion_total / completion_count)

        if not progress_values:
            return 0.0
        return round(sum(progress_values) / len(progress_values), 2)
    except Exception:
        return 0.0


@require_http_methods(["GET"])
@login_required()
def get_teacher_courses_api(request):
    try:
        session_user = User.objects.filter(id=request.session.get('user_id')).first()
        shared = str(request.GET.get('shared', '') or '').strip().lower() in ['1', 'true', 'yes', 'on']

        teacher_user = None
        if session_user and session_user.role == 'teacher':
            teacher_user = session_user
        elif session_user and session_user.role == 'admin':
            # Admins must provide a teacher identifier (id or custom_id) via query params for normal teacher filtering.
            tid = request.GET.get('teacher_id') or request.GET.get('teacher_custom_id') or request.GET.get('teacher')
            if not tid and not shared:
                return JsonResponse({'success': False, 'error': 'Missing teacher_id parameter for admin'}, status=400)
            if tid:
                try:
                    teacher_user = User.objects.filter(Q(id=int(tid)) | Q(custom_id__iexact=str(tid)), role='teacher').first()
                except Exception:
                    teacher_user = User.objects.filter(custom_id__iexact=str(tid), role='teacher').first()
                if not teacher_user:
                    return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)
        else:
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        # Prefetch related objects to avoid N+1 queries
        if shared:
            # Shared mode feeds the Others library. Include all active courses,
            # including the current teacher's own shared resources.
            courses_qs = Course.objects.filter(is_active=True)
        else:
            # Personal mode: return only current teacher's courses
            if not teacher_user:
                return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)
            courses_qs = Course.objects.filter(teacher=teacher_user, is_active=True)

        courses_qs = courses_qs.select_related('teacher').prefetch_related(
            'sections', 'materials', 'assessments', 'assessments__materials'
        ).order_by('-created_at')

        course_list = []
        for c in courses_qs:
            course_sections = list(c.sections.filter(is_active=True))
            secs = [{'id': s.id, 'code': s.class_code, 'name': s.class_name} for s in course_sections]
            course_teacher_name = ''
            if getattr(c, 'teacher', None):
                course_teacher_name = f"{c.teacher.first_name} {c.teacher.last_name}".strip()

            # Serialize assessments with helpful metadata used by the frontend
            assessments_list = []
            course_assessments_qs = Assessment.objects.filter(
                source_assessment__isnull=True
            ).filter(
                Q(courses=c, teacher=teacher_user) |
                Q(section__in=course_sections, teacher=teacher_user)
            ).prefetch_related('materials', 'teacher').distinct()
            for a in course_assessments_qs:
                # Skip inactive or archived assessments so they don't appear in the UI
                if not getattr(a, 'is_active', True):
                    continue
                if str(getattr(a, 'status', '') or '').strip().lower() == 'archived':
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
                    attempts = a.get_attempts()
                    accs = [att.get('accuracy') for att in attempts if isinstance(att.get('accuracy'), (int, float))]
                    if accs:
                        avg = round(sum(accs) / len(accs))
                except Exception:
                    avg = None

                assessment_teacher_name = course_teacher_name
                if getattr(a, 'teacher', None):
                    assessment_teacher_name = f"{a.teacher.first_name} {a.teacher.last_name}".strip() or assessment_teacher_name

                assessments_list.append({
                    'id': a.id,
                    'raw_id': a.id,
                    'action_id': f"assessment-{a.id}",
                    'code': a.code,
                    'title': a.title,
                    'teacher_name': assessment_teacher_name,
                    'author': assessment_teacher_name,
                    'assessment_type': a.assessment_type,
                    'level': a.get_assessment_type_display() if hasattr(a, 'get_assessment_type_display') else (a.assessment_type or ''),
                    'items': items,
                    'items_count': items,
                    'minutes': minutes,
                    'average': f"{avg}%" if avg is not None else None,
                    'attempt_count': len(attempts) if isinstance(attempts, list) else 0,
                    'has_attempts': bool(attempts) if isinstance(attempts, list) else False,
                    'dueDate': a.scheduled_at.isoformat() if getattr(a, 'scheduled_at', None) else None,
                    'status': 'archived' if not a.is_active else a.status,
                    'is_active': a.is_active,
                    'created_at': a.created_at.isoformat() if getattr(a, 'created_at', None) else None,
                })

            # Serialize materials with normalized metadata
            materials_list = []
            for m in c.materials.all():
                # Skip inactive or archived materials so they don't appear in the UI
                if not getattr(m, 'is_active', True):
                    continue
                if str(getattr(m, 'status', '') or '').strip().lower() == 'archived':
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

                material_teacher_name = course_teacher_name
                material_owner_teacher_id = None
                if getattr(m, 'assessment', None) and getattr(m.assessment, 'teacher', None):
                    material_owner_teacher_id = m.assessment.teacher_id
                    material_teacher_name = f"{m.assessment.teacher.first_name} {m.assessment.teacher.last_name}".strip() or material_teacher_name
                elif getattr(m, 'section', None) and getattr(m.section, 'teacher', None):
                    material_owner_teacher_id = m.section.teacher_id
                    material_teacher_name = f"{m.section.teacher.first_name} {m.section.teacher.last_name}".strip() or material_teacher_name
                else:
                    try:
                        first_section = m.assigned_sections.filter(is_active=True).select_related('teacher').first()
                        if first_section and getattr(first_section, 'teacher_id', None):
                            material_owner_teacher_id = first_section.teacher_id
                            material_teacher_name = f"{first_section.teacher.first_name} {first_section.teacher.last_name}".strip() or material_teacher_name
                    except Exception:
                        material_owner_teacher_id = None

                if material_owner_teacher_id is None and getattr(m, 'teacher_id', None):
                    material_owner_teacher_id = m.teacher_id
                    if getattr(m, 'teacher', None):
                        material_teacher_name = f"{m.teacher.first_name} {m.teacher.last_name}".strip() or material_teacher_name

                source_type = str(getattr(m, 'source_type', 'personal') or 'personal').strip().lower()
                is_shared_material = source_type == 'shared'

                content_json = getattr(m, 'content_json', None) or {}
                language_value = ''
                if isinstance(content_json, dict):
                    language_value = str(content_json.get('language') or '').strip()
                if not language_value:
                    language_value = str(getattr(m, 'language', '') or '').strip()
                if not language_value:
                    language_value = 'English'

                materials_list.append({
                    'id': m.id,
                    'raw_id': m.id,
                    'action_id': f"material-{m.id}",
                    'record_kind': 'material',
                    'assessment_id': m.assessment_id,
                    'code': m.assessment.code if m.assessment else None,
                    'title': m.title,
                    'teacher_name': material_teacher_name,
                    'author': material_teacher_name,
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
                    'source_type': getattr(m, 'source_type', 'personal') or 'personal',
                    'material_source': getattr(m, 'source_type', 'personal') or 'personal',
                    'is_shared_material': is_shared_material,
                    'shared_owner_teacher_name': material_teacher_name if is_shared_material else None,
                    'language': language_value,
                    'content_json': content_json,
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
                    practice_teacher_name = course_teacher_name
                    if getattr(p, 'teacher', None):
                        practice_teacher_name = f"{p.teacher.first_name} {p.teacher.last_name}".strip() or practice_teacher_name
                    items_cnt = len(_practice_material_items(p)) if callable(_practice_material_items) else None
                    practices_list.append({
                        'id': f"practice-{p.id}",
                        'raw_id': p.id,
                        'action_id': f"practice-{p.id}",
                        'record_kind': 'practice',
                        'title': p.title,
                        'teacher_name': practice_teacher_name,
                        'author': practice_teacher_name,
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

            unique_student_ids = set()
            for section in course_sections:
                for entry in section.get_enrolled_students(active_only=True):
                    student_id = _normalized_student_entry_id(entry)
                    if student_id:
                        unique_student_ids.add(student_id)

            average_progress = _compute_course_average_progress(c)

            metrics = {
                'sections': len(course_sections),
                'assessments': len(assessments_list),
                'materials': len(materials_list) + len(practices_list),
                'students': len(unique_student_ids),
                'average_progress': average_progress,
            }

            course_list.append({
                'id': c.id,
                'code': c.code,
                'title': c.title,
                'description': c.description,
                'sections': secs,
                'assessments': assessments_list,
                'materials': materials_list,
                'practices': practices_list,
                'metrics': metrics,
            })

        return JsonResponse({'success': True, 'courses': course_list})
    except Exception as e:
        logger.exception('Unhandled error in get_teacher_courses_api')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
@login_required(role='teacher')
def get_teacher_assessments_api(request):
    try:
        teacher_user = User.objects.filter(id=request.session.get('user_id')).first()
        if not teacher_user:
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        course_id = request.GET.get('course_id')
        assessments_qs = Assessment.objects.filter(
            teacher=teacher_user,
            source_assessment__isnull=True,
            is_active=True
        )

        if course_id is not None:
            course = Course.objects.filter(id=course_id, teacher=teacher_user, is_active=True).first()
            if course:
                # When viewing a specific course, only include assessments
                # that are explicitly linked to that course (via the
                # Course.assessments M2M), assessments attached to the
                # course's sections, or assessments produced by materials
                # that belong to the course or its assigned sections.
                # Do NOT include all teacher-owned assessments across other courses.
                assessments_qs = Assessment.objects.filter(
                    source_assessment__isnull=True,
                    is_active=True
                ).filter(
                    Q(courses=course, teacher=teacher_user) |
                    Q(section__in=course.sections.all(), teacher=teacher_user) |
                    Q(material__courses=course, teacher=teacher_user) |
                    Q(material__assigned_sections__in=course.sections.all(), teacher=teacher_user)
                ).distinct()

        # Always exclude records explicitly marked as archived (status field)
        assessments_qs = assessments_qs.exclude(status__iexact='archived').prefetch_related('materials').order_by('-created_at').distinct()

        def _average(values):
            # Compute averages when there is at least one numeric value.
            nums = [v for v in values if isinstance(v, (int, float))]
            if not nums:
                return None
            return round(sum(nums) / len(nums), 1)

        assessment_list = []
        for a in assessments_qs:
            attempts = a.get_attempts()
            assessment_list.append({
                'id': a.id,
                'raw_id': a.id,
                'code': a.code,
                'title': a.title,
                'assessment_type': a.assessment_type,
                'status': a.status,
                'is_active': a.is_active,
                'attempt_count': len(attempts),
                'avg_accuracy': _average([att.get('accuracy') for att in attempts]),
                'avg_wpm': _average([att.get('wpm') for att in attempts]),
                'avg_fluency': _average([att.get('fluency_score') for att in attempts]),
                'avg_pronunciation': _average([att.get('pronunciation_score') for att in attempts]),
                'avg_time_score': _average([att.get('time_score') for att in attempts]),
                'created_at': a.created_at.isoformat() if getattr(a, 'created_at', None) else None,
                'updated_at': a.updated_at.isoformat() if getattr(a, 'updated_at', None) else None,
            })

        # Also include Materials that are marked as assessment-type (materials table)
        try:
            from .models import Material
            if course_id is not None and course:
                # Only include teacher-owned assessment materials attached to this course.
                materials_qs = course.materials.filter(
                    teacher=teacher_user,
                    type__in=['assessment', 'both'],
                    is_active=True,
                )
            else:
                materials_qs = Material.objects.filter(
                    teacher=teacher_user,
                    type__in=['assessment', 'both'],
                    is_active=True,
                )

            materials_qs = materials_qs.exclude(status__iexact='archived')

            existing_assessment_ids = set(assessments_qs.values_list('id', flat=True))
            # Also track materials that are already represented by parent assessments
            # to avoid adding a separate "material-<id>" row that duplicates
            # the parent assessment row in the UI.
            existing_material_ids = set(assessments_qs.filter(material_id__isnull=False).values_list('material_id', flat=True))

            for m in materials_qs:
                # If the material is linked to a parent assessment that's
                # already in `assessments_qs`, skip it. Also skip materials
                # whose id is already present as a material on one of the
                # parent assessment rows we will display.
                if (m.assessment_id and m.assessment_id in existing_assessment_ids) or (m.id in existing_material_ids):
                    continue

                # collect attempt rows linked to this material
                # Only include materials that either:
                # 1. Have no assessment_id, OR
                # 2. Have an assessment_id that's a valid parent assessment
                # If a material has an assessment_id not in existing_assessment_ids,
                # it means the assessment was filtered out (archived, wrong course, etc.)
                if m.assessment_id and m.assessment_id not in existing_assessment_ids:
                    # Skip materials with invalid assessment references
                    continue
                    
                attempts_qs = Assessment.objects.filter(material=m).order_by('created_at')
                
                # Only include materials that have attempt rows
                # (materials with no assessment_id and no attempts shouldn't be displayed)
                if not attempts_qs.exists():
                    continue
                    
                accs = [a.accuracy for a in attempts_qs if a.accuracy is not None]
                wpms = [a.wpm for a in attempts_qs if a.wpm is not None]
                fls = [a.fluency_score for a in attempts_qs if a.fluency_score is not None]
                prs = [a.pronunciation_score for a in attempts_qs if a.pronunciation_score is not None]
                tms = [a.time_score for a in attempts_qs if a.time_score is not None]

                def avg_list(nums):
                    if not nums:
                        return None
                    return round(sum(nums) / len(nums), 1)

                assessment_list.append({
                    'id': f"material-{m.id}",
                    'raw_id': m.id,
                    'code': m.code,
                    'title': m.title,
                    'assessment_type': m.item_type,
                    'status': m.status,
                    'is_active': m.is_active,
                    'attempt_count': attempts_qs.count(),
                    'avg_accuracy': avg_list(accs),
                    'avg_wpm': avg_list(wpms),
                    'avg_fluency': avg_list(fls),
                    'avg_pronunciation': avg_list(prs),
                    'avg_time_score': avg_list(tms),
                    'created_at': m.created_at.isoformat() if getattr(m, 'created_at', None) else None,
                    'updated_at': m.updated_at.isoformat() if getattr(m, 'updated_at', None) else None,
                })
        except Exception:
            logger.exception('Failed to include material-based assessments in teacher assessments API')

        return JsonResponse({'success': True, 'assessments': assessment_list})
    except Exception as e:
        logger.exception('Unhandled error in get_teacher_assessments_api')
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

        attempts = assessment.get_attempts()
        student_ids = {
            att.get('student_id')
            for att in attempts
            if isinstance(att, dict) and att.get('student_id')
        }
        students_by_id = {
            student.id: student
            for student in User.objects.filter(id__in=student_ids)
        }
        def _attempt_value(attempt, *keys, default=None):
            for key in keys:
                value = attempt.get(key)
                if value is not None and value != '':
                    return value
            return default

        enriched_attempts = []
        for att in attempts:
            if not isinstance(att, dict):
                continue
            student = students_by_id.get(att.get('student_id'))
            student_name = ''
            if student:
                student_name = f"{student.first_name} {student.last_name}".strip() or student.custom_id or student.email or f"Student {student.id}"
            enriched_attempt = dict(att)
            enriched_attempt.update({
                'student_name': student_name or f"Student {att.get('student_id')}",
                'student_email': getattr(student, 'email', '') if student else '',
                'wpm': _attempt_value(att, 'wpm', 'words_per_minute', 'reading_wpm'),
                'fluency_score': _attempt_value(att, 'fluency_score', 'fluency'),
                'accuracy': _attempt_value(att, 'accuracy', 'accuracy_score', 'reading_accuracy'),
                'pronunciation_score': _attempt_value(att, 'pronunciation_score', 'pronunciation'),
                'time_score': _attempt_value(att, 'time_score', 'time'),
                'total_score': _attempt_value(att, 'total_score', 'score'),
                'crla_classification': _attempt_value(att, 'crla_classification', 'classification'),
            })
            enriched_attempts.append(enriched_attempt)

        def _attempt_timestamp(attempt):
            ts = attempt.get('completed_at') or attempt.get('started_at') or attempt.get('updated_at')
            if not isinstance(ts, str):
                return None
            parsed = parse_datetime(ts)
            if parsed is None:
                return None
            if parsed.tzinfo is None:
                try:
                    return timezone.make_aware(parsed)
                except Exception:
                    return parsed
            return parsed

        enriched_attempts.sort(key=lambda att: _attempt_timestamp(att) or datetime(1970, 1, 1, tzinfo=timezone.utc))

        # Compute per-metric averages when there is at least one numeric attempt
        def _average_list(values):
            nums = [v for v in values if isinstance(v, (int, float))]
            if not nums:
                return None
            try:
                return round(sum(nums) / len(nums), 1)
            except Exception:
                return None

        payload = {
            'id': assessment.id,
            'code': assessment.code,
            'title': assessment.title,
            'type': assessment.assessment_type,
            'level': assessment.get_assessment_type_display() if hasattr(assessment, 'get_assessment_type_display') else assessment.assessment_type,
            'items': sum((m.get('items') or 0) for m in mats),
            'minutes': 0,
            'average': None,
            'avg_accuracy': _average_list([att.get('accuracy') for att in attempts]),
            'avg_wpm': _average_list([att.get('wpm') for att in attempts]),
            'avg_fluency': _average_list([att.get('fluency_score') for att in attempts]),
            'avg_pronunciation': _average_list([att.get('pronunciation_score') for att in attempts]),
            'avg_time_score': _average_list([att.get('time_score') for att in attempts]),
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


@require_http_methods(["GET"])
@login_required(role='teacher')
def get_teacher_material_attempts_api(request):
    """Return attempts for a material (used when material-based assessments exist)."""
    try:
        teacher_user = User.objects.filter(id=request.session.get('user_id')).first()
        if not teacher_user:
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        material_id = request.GET.get('material_id')
        if not material_id:
            return JsonResponse({'success': False, 'error': 'material_id is required'}, status=400)

        _, material_id = _parse_prefixed_id(material_id)
        if not material_id:
            return JsonResponse({'success': False, 'error': 'Invalid material id'}, status=400)

        material = Material.objects.filter(id=material_id).first()
        if not material:
            return JsonResponse({'success': False, 'error': 'Material not found'}, status=404)

        # Authorization: allow if teacher owns the material or owns the section
        if material.teacher_id is not None and material.teacher_id != teacher_user.id and not any(s.teacher_id == teacher_user.id for s in material.assigned_sections.all()):
            # allow teacher if material belongs to their sections or they are the material owner
            pass

        attempts_qs = Assessment.objects.filter(material=material).order_by('created_at')

        students_by_id = {s.id: s for s in User.objects.filter(id__in=[a.student_id for a in attempts_qs if a.student_id])}

        enriched = []
        for a in attempts_qs:
            att = a._serialize_attempt()
            student = students_by_id.get(a.student_id)
            student_name = ''
            if student:
                student_name = f"{student.first_name} {student.last_name}".strip() or student.custom_id or student.email or f"Student {student.id}"
            att.update({
                'student_name': student_name,
                'student_email': getattr(student, 'email', '') if student else '',
                'wpm': a.wpm,
                'fluency_score': a.fluency_score,
                'accuracy': a.accuracy,
                'pronunciation_score': a.pronunciation_score,
                'time_score': a.time_score,
                'total_score': a.total_score,
                'crla_classification': a.crla_classification,
            })
            enriched.append(att)

        payload = {
            'id': f"material-{material.id}",
            'code': material.code,
            'title': material.title,
            'materials': [],
            'attempts': enriched,
        }
        return JsonResponse({'success': True, 'assessment': payload})
    except Exception as e:
        logger.exception('Error in get_teacher_material_attempts_api')
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

        assessment = Assessment.objects.filter(id=aid, source_assessment__isnull=True).first()
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

        assessment = Assessment.objects.filter(id=aid, source_assessment__isnull=True).first()
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
        _notify_principals(
            'New course created',
            f"{teacher_user.first_name} {teacher_user.last_name} created a new course: {course.title}.",
            'info',
            reverse('dashboard_principal'),
            teacher_user,
            send_email=False,
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


@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def delete_course(request):
    try:
        data = json.loads(request.body or '{}')
        course_id = data.get('course_id')

        if not course_id:
            return JsonResponse({'success': False, 'error': 'Course ID is required'}, status=400)

        _, parsed_course_id = _parse_prefixed_id(course_id)
        if parsed_course_id:
            course_id = parsed_course_id

        teacher_user = User.objects.filter(id=request.session.get('user_id')).first()
        if not teacher_user or teacher_user.role != 'teacher':
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        course = Course.objects.filter(id=course_id, teacher=teacher_user, is_active=True).first()
        if not course:
            return JsonResponse({'success': False, 'error': 'Course not found or not owned by you'}, status=404)

        with transaction.atomic():
            related_materials = list(course.materials.all())
            related_assessments = list(course.assessments.all())

            course.sections.clear()
            course.materials.clear()
            course.assessments.clear()

            for material in related_materials:
                try:
                    material.is_active = False
                    material.status = 'archived'
                    material.save(update_fields=['is_active', 'status', 'updated_at'])
                except Exception:
                    logger.exception('Failed to archive material %s during course delete', material.id)

            for assessment in related_assessments:
                try:
                    assessment.is_active = False
                    assessment.status = 'archived'
                    assessment.save(update_fields=['is_active', 'status', 'updated_at'])
                except Exception:
                    logger.exception('Failed to archive assessment %s during course delete', assessment.id)

            try:
                Note.objects.filter(assessment__in=related_assessments).delete()
            except Exception:
                pass

            course.is_active = False
            course.save(update_fields=['is_active', 'updated_at'])
            course.delete()

        return JsonResponse({'success': True, 'message': 'Course deleted successfully'})
    except Exception as e:
        logger.exception('Error deleting course')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def _compute_teacher_overview(teacher_user):
    """Helper: compute the same overview payload returned by get_teacher_overview."""
    try:
        classes_count = Section.objects.filter(teacher=teacher_user, is_active=True).count()
        active_sections = Section.objects.filter(teacher=teacher_user, is_active=True)
        unique_student_ids = set()
        for section in active_sections:
            for entry in section.get_enrolled_students(active_only=True):
                student_id = _normalized_student_entry_id(entry)
                if student_id:
                    unique_student_ids.add(student_id)
        total_students = len(unique_student_ids)

        materials_posted = Material.objects.filter(
            Q(teacher=teacher_user) | Q(section__teacher=teacher_user) | Q(assigned_sections__teacher=teacher_user),
            is_active=True,
        ).distinct().count()

        assessments_posted = Material.objects.filter(
            Q(teacher=teacher_user) | Q(section__teacher=teacher_user) | Q(assigned_sections__teacher=teacher_user),
            type__in=["assessment", "both"],
            is_active=True,
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

        # Basic ownership check: allow shared library materials, unassigned
        # materials, or materials owned through one of the teacher's sections.
        if material.source_type != 'shared' and material.section and material.section.teacher_id != teacher_user.id:
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

        source_type = getattr(material, 'source_type', 'personal') or 'personal'
        return JsonResponse({
            'success': True,
            'material': {
                'id': material.id,
                'title': material.title,
                'item_type': getattr(material, 'item_type', ''),
                'source_type': source_type,
                'material_source': source_type,
                'is_shared_material': source_type == 'shared',
            }
        })
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
            section_materials = Material.objects.filter(
                Q(section=cls) | Q(assigned_sections=cls) | Q(courses__sections=cls),
                is_active=True,
            ).distinct()
            represented_asm_ids = section_materials.exclude(assessment=None).values_list('assessment_id', flat=True)
            assessment_material_count = section_materials.filter(Q(type='assessment') | Q(type='both')).count()
            assessment_material_count += Assessment.objects.filter(section=cls, is_active=True, source_assessment__isnull=True).exclude(id__in=represented_asm_ids).count()

            practice_material_count = section_materials.filter(Q(type='practice') | Q(type='both')).count()
            practice_material_count += Practice.objects.filter(
                Q(section=cls) |
                Q(teacher=teacher_user) |
                Q(section__isnull=True, teacher=teacher_user) |
                Q(section__isnull=True, teacher__role='admin'),
                is_active=True,
            ).count()
            practice_material_count += Material.objects.filter(
                section__isnull=True,
                type='practice',
                is_active=True,
            ).count()
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
                'assessment_material_count': assessment_material_count,
                'practice_material_count': practice_material_count,
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
                student_id = _normalized_student_entry_id(entry)
                if student_id:
                    unique_student_ids.add(student_id)
        total_students = len(unique_student_ids)

        # Separate materials vs assessments counts so they are not conflated
        assessments_posted = Assessment.objects.filter(
            Q(teacher=teacher_user) | Q(section__teacher=teacher_user),
            is_active=True,
            source_assessment__isnull=True
        ).exclude(status__iexact='archived').distinct().count()

        # Materials that are standalone (not representing an Assessment)
        materials_posted = Material.objects.filter(
            Q(section__teacher=teacher_user) | Q(assigned_sections__teacher=teacher_user),
            is_active=True,
            assessment__isnull=True,
        ).exclude(status__iexact='archived').distinct().count()

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
        # Some assessment attempts are stored as Assessment rows tied to a Material via material_id,
        # so exclude those here as well to prevent a material from appearing twice.
        represented_asm_ids = materials_qs.exclude(assessment=None).values_list('assessment_id', flat=True)
        represented_material_ids = materials_qs.values_list('id', flat=True)
        assessments_qs = Assessment.objects.filter(
            section=section,
            source_assessment__isnull=True
        ).exclude(
            Q(id__in=represented_asm_ids) | Q(material_id__in=represented_material_ids)
        )
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
        materials_qs = materials_qs.filter(is_active=True).exclude(status__iexact='archived')
        assessments_qs = assessments_qs.filter(is_active=True).exclude(status__iexact='archived')
        practices_qs = practices_qs.filter(is_active=True).exclude(status__iexact='archived')

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

                # Compute completion state for materials linked to an Assessment.
                # Attempt count is retained for compatibility, but completion UI must
                # rely on completed attempts only.
                attempt_count = 0
                completed_attempt_count = 0
                student_has_completed = False
                latest_attempt_summary = {}
                latest_time_score = None
                if m.assessment:
                    if is_requesting_student and request_user:
                        attempt_count = m.assessment.get_student_attempt_count(request_user)
                        completed_attempt_count = len([
                            attempt for attempt in m.assessment.get_attempts(request_user)
                            if attempt.get('status') == 'completed'
                        ])
                        student_has_completed = completed_attempt_count > 0
                        latest_attempt_summary = m.assessment.get_latest_attempt_summary(request_user)
                        if latest_attempt_summary.get('time_score') is not None:
                            latest_time_score = _clamp_score(latest_attempt_summary.get('time_score'))
                    elif teacher_user and teacher_user.role == 'teacher':
                        # Teachers see 0 completions for themselves on the hub
                        attempt_count = 0
                    else:
                        attempt_count = 0

                content_json = getattr(m, 'content_json', None) or {}
                language_value = ''
                if isinstance(content_json, dict):
                    language_value = str(content_json.get('language') or '').strip()
                if not language_value:
                    language_value = str(getattr(m, 'language', '') or '').strip()

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
                    'source_type': m.source_type,
                    'content': content_value,
                    'content_text': content_value,
                    'status': 'archived' if not m.is_active else (m.status or 'published'),
                    'schedule': timezone.localtime(m.scheduled_at, timezone.get_default_timezone()).strftime('%Y-%m-%dT%H:%M') if getattr(m, 'scheduled_at', None) else None,
                    'items': items_count,
                    'created_at': m.created_at.isoformat() if getattr(m, 'created_at', None) else None,
                    'attempt_count': attempt_count,
                    'completed_attempt_count': completed_attempt_count,
                    'student_has_completed': student_has_completed,
                    'latest_time_score': latest_time_score,
                    'latest_attempt_summary': latest_attempt_summary,
                    'assigned_sections': [s.class_code for s in m.assigned_sections.all()] if hasattr(m, 'assigned_sections') else [],
                    'assigned_week': m.assigned_week,
                    'assigned_week_display': format_assigned_week_display(m.assigned_week),
                    'language': language_value,
                    'content_json': content_json,
                }
            elif kind == 'assessment':
                a = obj
                content_value = a.content or ''
                title_value = a.title or (content_value[:150] + '...' if len(content_value) > 150 else content_value)
                items_count = 1
                # Compute completion state for this assessment. Attempt count is
                # retained for compatibility, but completion UI must rely on
                # completed attempts only.
                completed_attempt_count = 0
                student_has_completed = False
                latest_attempt_summary = {}
                latest_time_score = None
                if is_requesting_student and request_user:
                    attempt_count = a.get_student_attempt_count(request_user)
                    completed_attempt_count = len([
                        attempt for attempt in a.get_attempts(request_user)
                        if attempt.get('status') == 'completed'
                    ])
                    student_has_completed = completed_attempt_count > 0
                    latest_attempt_summary = a.get_latest_attempt_summary(request_user)
                    if latest_attempt_summary.get('time_score') is not None:
                        latest_time_score = _clamp_score(latest_attempt_summary.get('time_score'))
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
                    'completed_attempt_count': completed_attempt_count,
                    'student_has_completed': student_has_completed,
                    'latest_time_score': latest_time_score,
                    'latest_attempt_summary': latest_attempt_summary,
                    'assigned_sections': [a.section.class_code] if a.section else [],
                    'assigned_week': None,
                    'assigned_week_display': format_assigned_week_display(None),
                    'language': '',
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
                    'language': '',
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
            Assessment.objects.filter(section=section, is_active=True, source_assessment__isnull=True).update(is_active=False)
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

def _parse_selected_pages(raw_value, page_count):
    if page_count <= 1:
        return [1]

    if not raw_value:
        return list(range(1, page_count + 1))

    if isinstance(raw_value, (list, tuple)):
        raw_values = raw_value
    else:
        raw_values = [segment.strip() for segment in str(raw_value).split(',') if str(raw_value).strip()]

    selected = []
    for item in raw_values:
        if not item:
            continue
        if '-' in item:
            start_text, end_text = item.split('-', 1)
            try:
                start = int(start_text.strip())
                end = int(end_text.strip())
            except ValueError:
                continue
            if start > end:
                start, end = end, start
            selected.extend(range(start, end + 1))
        else:
            try:
                selected.append(int(item))
            except ValueError:
                continue

    normalized = sorted({page for page in selected if 1 <= page <= page_count})
    return normalized or list(range(1, page_count + 1))


def _extract_text_from_pdf(upload, selected_pages=None):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError('PDF extraction needs the pypdf package installed.') from exc

    upload.seek(0)
    reader = PdfReader(upload)
    page_count = len(reader.pages)
    selected = _parse_selected_pages(selected_pages, page_count)
    page_texts = []
    for page_number in selected:
        page = reader.pages[page_number - 1]
        page_text = (page.extract_text() or '').strip()
        if page_text:
            page_texts.append(page_text)

    return {
        'text': '\n\n'.join(page_texts),
        'page_count': page_count,
        'selected_pages': selected,
    }


def _build_image_upload_debug_info(upload, source='upload'):
    if upload is None:
        return {'source': source, 'size': 0, 'sha256': None, 'content_type': None, 'name': None}

    try:
        size = getattr(upload, 'size', None)
    except Exception:
        size = None

    name = None
    content_type = None
    try:
        name = getattr(upload, 'name', None)
    except Exception:
        name = None
    try:
        content_type = getattr(upload, 'content_type', None)
    except Exception:
        content_type = None

    data = b''
    try:
        if hasattr(upload, 'read'):
            upload.seek(0)
            data = upload.read()
            upload.seek(0)
    except Exception:
        data = b''

    import hashlib
    sha256 = hashlib.sha256(data).hexdigest() if data is not None else None
    return {
        'source': source,
        'name': name,
        'size': size if size is not None else len(data),
        'sha256': sha256,
        'content_type': content_type,
    }


def _resolve_tesseract_executable(pytesseract_module):
    candidates = []

    explicit = os.environ.get('TESSERACT_CMD') or os.environ.get('TESSERACT_PATH')
    if explicit:
        candidate = os.path.expandvars(os.path.expanduser(explicit))
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    if pytesseract_module and hasattr(pytesseract_module, 'pytesseract'):
        for attr in ('tesseract_cmd', 'tesseract_executable'):
            value = getattr(getattr(pytesseract_module, 'pytesseract', None), attr, None)
            if value and value not in candidates:
                candidates.append(value)

    path_entries = []
    try:
        raw_path = os.environ.get('PATH') or ''
        if raw_path:
            path_entries.extend([item for item in raw_path.split(os.pathsep) if item])
    except Exception:
        path_entries = []

    for entry in path_entries:
        expanded = os.path.expandvars(os.path.expanduser(entry))
        if not expanded:
            continue
        if os.path.isfile(expanded):
            basename = os.path.basename(expanded).lower()
            if basename in {'tesseract', 'tesseract.exe', 'tesseract-ocr', 'tesseract-ocr.exe'} and expanded not in candidates:
                candidates.append(expanded)
            continue
        for candidate_name in ('tesseract', 'tesseract.exe', 'tesseract-ocr', 'tesseract-ocr.exe'):
            candidate_path = os.path.join(expanded, candidate_name)
            if candidate_path and candidate_path not in candidates:
                candidates.append(candidate_path)

    if os.path.isfile(TESSERACT_STATIC_PATH):
        candidates.append(TESSERACT_STATIC_PATH)

    try:
        resolved = shutil.which('tesseract')
        if resolved:
            candidates.append(resolved)
    except Exception:
        pass

    try:
        resolved_ocr = shutil.which('tesseract-ocr')
        if resolved_ocr:
            candidates.append(resolved_ocr)
    except Exception:
        pass

    try:
        resolved_exe = shutil.which('tesseract.exe')
        if resolved_exe:
            candidates.append(resolved_exe)
    except Exception:
        pass

    try:
        resolved_ocr_exe = shutil.which('tesseract-ocr.exe')
        if resolved_ocr_exe:
            candidates.append(resolved_ocr_exe)
    except Exception:
        pass

    for candidate in [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        os.path.expandvars(r'%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe'),
        os.path.expandvars(r'%ProgramFiles%\Tesseract-OCR\tesseract.exe'),
        os.path.expandvars(r'%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe'),
        '/usr/bin/tesseract',
        '/usr/bin/tesseract-ocr',
        '/usr/local/bin/tesseract',
        '/usr/local/bin/tesseract-ocr',
    ]:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        normalized = os.path.normcase(os.path.normpath(str(candidate)))
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.path.isfile(candidate):
            return candidate

    return None


def _collect_tesseract_debug_info():
    debug_info = {}
    explicit = os.environ.get('TESSERACT_CMD') or os.environ.get('TESSERACT_PATH') or ''
    debug_info['explicit_env'] = explicit

    raw_path = os.environ.get('PATH') or ''
    path_entries = [entry for entry in raw_path.split(os.pathsep) if entry]
    debug_info['path_entries'] = path_entries

    checked_paths = []
    existing_paths = []
    candidate_names = ('tesseract', 'tesseract.exe', 'tesseract-ocr', 'tesseract-ocr.exe')
    for entry in path_entries:
        expanded = os.path.expandvars(os.path.expanduser(entry))
        if not expanded:
            continue
        if os.path.isfile(expanded):
            basename = os.path.basename(expanded).lower()
            if basename in candidate_names:
                normalized = os.path.normcase(os.path.normpath(expanded))
                checked_paths.append(normalized)
                if os.path.isfile(expanded):
                    existing_paths.append(normalized)
            continue
        for candidate_name in candidate_names:
            candidate_path = os.path.join(expanded, candidate_name)
            normalized = os.path.normcase(os.path.normpath(candidate_path))
            checked_paths.append(normalized)
            if os.path.isfile(candidate_path):
                existing_paths.append(normalized)

    if os.path.isfile(TESSERACT_STATIC_PATH):
        normalized = os.path.normcase(os.path.normpath(TESSERACT_STATIC_PATH))
        checked_paths.append(normalized)
        existing_paths.append(normalized)

    debug_info['checked_paths'] = checked_paths
    debug_info['existing_paths'] = existing_paths
    debug_info['which'] = {
        'tesseract': shutil.which('tesseract'),
        'tesseract-ocr': shutil.which('tesseract-ocr'),
        'tesseract.exe': shutil.which('tesseract.exe'),
        'tesseract-ocr.exe': shutil.which('tesseract-ocr.exe'),
    }

    try:
        import pytesseract as _pyt
        debug_info['pytesseract_tesseract_cmd'] = getattr(_pyt.pytesseract, 'tesseract_cmd', None)
    except Exception as exc:
        debug_info['pytesseract_import_error'] = str(exc)

    debug_info['resolved_tesseract'] = _resolve_tesseract_executable(globals().get('pytesseract'))
    debug_info['tesseract_available'] = bool(debug_info['resolved_tesseract'])
    return debug_info


@csrf_protect
@require_http_methods(['GET'])
@login_required(role='teacher')
def tesseract_debug(request):
    return JsonResponse({'success': True, 'tesseract_debug': _collect_tesseract_debug_info()})


# Log Tesseract resolution once during server startup or first module import.
try:
    _startup_tesseract_path = _resolve_tesseract_executable(globals().get('pytesseract'))
    if _startup_tesseract_path:
        logger.info('Tesseract startup resolved: %s', _startup_tesseract_path)
        try:
            import pytesseract as _pyt
            _pyt.pytesseract.tesseract_cmd = _startup_tesseract_path
        except Exception:
            pass
    else:
        logger.warning('Tesseract startup resolution failed; PATH=%s', os.environ.get('PATH', ''))
except Exception as exc:
    logger.exception('Failed to resolve Tesseract at startup: %s', exc)


def _looks_like_ocr_text(text):
    if not text:
        return False
    cleaned = re.sub(r'\s+', ' ', str(text).strip())
    if not cleaned:
        return False
    if len(cleaned) < 3:
        return False
    letters = sum(1 for ch in cleaned if ch.isalpha())
    digits = sum(1 for ch in cleaned if ch.isdigit())
    return (letters >= 2) or (digits >= 2 and letters >= 1)


def _coerce_image_ocr_result(result):
    if isinstance(result, dict):
        return {
            'text': str(result.get('text') or ''),
            'layout': list(result.get('layout') or []),
            'debug': result.get('debug') if isinstance(result.get('debug'), dict) else {},
        }
    if isinstance(result, str):
        return {'text': result, 'layout': [], 'debug': {}}
    return {'text': '', 'layout': [], 'debug': {}}


def _infer_material_type_from_ocr_layout(layout):
    if not layout:
        return 'word'

    normalized = []
    for entry in layout:
        if not isinstance(entry, dict):
            continue
        text = re.sub(r'\s+', ' ', str(entry.get('text') or '').strip())
        if not text:
            continue
        normalized.append(entry)

    if not normalized:
        return 'word'

    paragraph_ids = {
        (entry.get('block_num'), entry.get('par_num'))
        for entry in normalized
        if entry.get('par_num') is not None
    }
    if len(paragraph_ids) > 1:
        return 'paragraph'

    line_ids = {
        (entry.get('block_num'), entry.get('par_num'), entry.get('line_num'))
        for entry in normalized
        if entry.get('line_num') is not None
    }
    if len(line_ids) > 1:
        return 'sentence'

    return 'word'


def _build_material_items_from_ocr_layout(layout, reading_type=''):
    if not layout:
        return []

    normalized = []
    for entry in layout:
        if not isinstance(entry, dict):
            continue
        text = re.sub(r'\s+', ' ', str(entry.get('text') or '').strip())
        if not text:
            continue
        normalized.append({
            'text': text,
            'left': int(entry.get('left') or 0),
            'top': int(entry.get('top') or 0),
            'width': int(entry.get('width') or 0),
            'height': int(entry.get('height') or 0),
            'conf': int(entry.get('conf') or 0),
            'block_num': int(entry.get('block_num') or 0),
            'par_num': int(entry.get('par_num') or 0),
            'line_num': int(entry.get('line_num') or 0),
            'word_num': int(entry.get('word_num') or 0),
        })

    if not normalized:
        return []

    normalized.sort(key=lambda item: (
        item.get('block_num', 0),
        item.get('par_num', 0),
        item.get('line_num', 0),
        item.get('word_num', 0),
        item.get('top', 0),
        item.get('left', 0),
    ))

    reading_type = (reading_type or '').strip().lower() or _infer_material_type_from_ocr_layout(normalized)
    if reading_type == 'word':
        return [item['text'] for item in normalized]

    if reading_type == 'sentence':
        grouped = []
        current_group = None
        current_words = []
        for item in normalized:
            group_key = (item.get('block_num', 0), item.get('par_num', 0), item.get('line_num', 0))
            if current_group is None or group_key != current_group:
                if current_group is not None:
                    grouped.append(' '.join(current_words))
                current_group = group_key
                current_words = [item['text']]
            else:
                current_words.append(item['text'])
        if current_group is not None:
            grouped.append(' '.join(current_words))
        return grouped

    if reading_type == 'paragraph':
        grouped = []
        current_group = None
        current_words = []
        for item in normalized:
            group_key = (item.get('block_num', 0), item.get('par_num', 0))
            if current_group is None or group_key != current_group:
                if current_group is not None:
                    grouped.append(' '.join(current_words))
                current_group = group_key
                current_words = [item['text']]
            else:
                current_words.append(item['text'])
        if current_group is not None:
            grouped.append(' '.join(current_words))
        return grouped

    return [item['text'] for item in normalized]


def _trim_ocr_border(image):
    try:
        from PIL import ImageChops, ImageOps
    except ImportError:
        return image
    try:
        grayscale = ImageOps.grayscale(image)
        contrasted = ImageOps.autocontrast(grayscale)
        inverted = ImageChops.invert(contrasted)
        bbox = inverted.point(lambda p: 255 if p > 22 else 0).getbbox()
        if not bbox:
            return image
        width, height = image.size
        left, top, right, bottom = bbox
        pad_x = max(8, int(width * 0.025))
        pad_y = max(8, int(height * 0.025))
        left = max(0, left - pad_x)
        top = max(0, top - pad_y)
        right = min(width, right + pad_x)
        bottom = min(height, bottom + pad_y)
        if right - left < width * 0.25 or bottom - top < height * 0.15:
            return image
        return image.crop((left, top, right, bottom))
    except Exception:
        return image


def _resize_ocr_image(image, target_max_dimension=2200):
    try:
        from PIL import Image
    except ImportError:
        return image
    try:
        width, height = image.size
        max_dim = max(width, height)
        min_dim = min(width, height)
        scale = 1.0
        if max_dim > target_max_dimension:
            scale = target_max_dimension / max_dim
        elif min_dim < 900:
            scale = min(2.0, 900 / max(1, min_dim))
        if abs(scale - 1.0) < 0.05:
            return image
        return image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            resample=getattr(Image, 'Resampling', Image).LANCZOS,
        )
    except Exception:
        return image


def _estimate_ocr_rotation(image):
    try:
        from PIL import ImageOps
    except Exception:
        return 0

    try:
        sample = ImageOps.autocontrast(ImageOps.grayscale(image))
        sample = _resize_ocr_image(sample, 700)
        scores = []
        for angle in [-3, -2, -1, 0, 1, 2, 3]:
            rotated = sample.rotate(angle, expand=False, fillcolor=255)
            rows = []
            for y in range(rotated.height):
                dark_pixels = 0
                for x in range(0, rotated.width, 3):
                    if rotated.getpixel((x, y)) < 160:
                        dark_pixels += 1
                rows.append(dark_pixels)
            if len(rows) < 3:
                scores.append((0, angle))
                continue
            row_variance = sum(abs(rows[index] - rows[index - 1]) for index in range(1, len(rows)))
            scores.append((row_variance, angle))
        best_score, best_angle = max(scores, key=lambda pair: pair[0])
        if best_score <= 0 or abs(best_angle) < 1:
            return 0
        return best_angle
    except Exception:
        return 0


def _build_ocr_image_candidates(image):
    try:
        from PIL import ImageEnhance, ImageFilter, ImageOps
    except ImportError:
        return [{'label': 'original', 'image': image}]

    candidates = []
    seen = set()

    def add_candidate(label, img):
        if img is None:
            return
        try:
            if img.mode not in {'RGB', 'L', '1'}:
                img = img.convert('RGB')
            signature = (label, img.mode, img.size)
            if signature in seen:
                return
            seen.add(signature)
            candidates.append({'label': label, 'image': img})
        except Exception:
            return

    original_resized = _resize_ocr_image(image)
    try:
        add_candidate('original-resized-grayscale', ImageOps.autocontrast(ImageOps.grayscale(original_resized)))
    except Exception:
        add_candidate('original-resized', original_resized)

    prepared = _resize_ocr_image(_trim_ocr_border(image))
    rotation = _estimate_ocr_rotation(prepared)
    if rotation:
        try:
            prepared = prepared.rotate(rotation, expand=False, fillcolor='white')
        except Exception:
            pass

    try:
        grayscale = ImageOps.grayscale(prepared)
    except Exception:
        grayscale = prepared.convert('L') if hasattr(prepared, 'convert') else prepared

    autocontrast = ImageOps.autocontrast(grayscale)
    add_candidate('prepared-grayscale', autocontrast)

    try:
        add_candidate(
            'contrast-sharpened',
            ImageOps.autocontrast(
                autocontrast.filter(ImageFilter.UnsharpMask(radius=1.2, percent=180, threshold=3))
            )
        )
    except Exception:
        pass

    try:
        denoised = autocontrast.filter(ImageFilter.MedianFilter(size=3))
        add_candidate('denoised-contrast', ImageOps.autocontrast(denoised))
    except Exception:
        pass

    try:
        contrast_boosted = ImageEnhance.Contrast(prepared.convert('RGB')).enhance(1.8)
        add_candidate('phone-photo-contrast', ImageOps.autocontrast(ImageOps.grayscale(contrast_boosted)))
    except Exception:
        pass

    for threshold in [150, 180]:
        try:
            threshold_image = autocontrast.point(lambda p, t=threshold: 255 if p > t else 0, mode='1')
            add_candidate(f'threshold-{threshold}', threshold_image)
        except Exception:
            continue

    return candidates[:7] or [{'label': 'original', 'image': image}]


def _extract_text_from_image(upload, debug_dir=None, debug_label=''):
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError
    except ImportError as exc:
        raise RuntimeError('Image OCR requires Pillow to be installed.') from exc

    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError('Image OCR requires pytesseract to be installed.') from exc

    try:
        from pytesseract import Output as TesseractOutput
    except Exception:
        TesseractOutput = None

    tesseract_path = _resolve_tesseract_executable(pytesseract)
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    else:
        logger.warning('OCR could not resolve a Tesseract executable. Checked env vars and common install paths.')

    upload.seek(0)
    try:
        with Image.open(BytesIO(upload.read())) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in {'RGB', 'L'}:
                image = image.convert('RGB')

            candidates = _build_ocr_image_candidates(image)
            best_text = ''
            best_layout = []
            best_confidence = -1
            best_candidate = None
            best_candidate_label = ''
            best_config = ''
            attempt_count = 0
            last_ocr_error = None

            for candidate_entry in candidates:
                candidate = candidate_entry.get('image') if isinstance(candidate_entry, dict) else candidate_entry
                candidate_label = candidate_entry.get('label', 'candidate') if isinstance(candidate_entry, dict) else 'candidate'
                for config in ['--oem 3 --psm 6', '--oem 3 --psm 4', '--oem 3 --psm 11']:
                    attempt_count += 1
                    try:
                        if TesseractOutput is None:
                            data = pytesseract.image_to_data(candidate, config=config)
                        else:
                            data = pytesseract.image_to_data(candidate, config=config, output_type=TesseractOutput.DICT)
                    except Exception as exc:
                        last_ocr_error = repr(exc)
                        logger.warning('OCR attempt failed for candidate %s config %s: %s', candidate_label, config, repr(exc))
                        try:
                            if TesseractOutput is None:
                                data = pytesseract.image_to_data(candidate)
                            else:
                                data = pytesseract.image_to_data(candidate, output_type=TesseractOutput.DICT)
                        except Exception as fallback_exc:
                            logger.warning('OCR fallback failed for candidate %s: %s', candidate_label, repr(fallback_exc))
                            data = None

                    layout = []
                    confidence_total = 0
                    confidence_count = 0
                    if data and isinstance(data, dict):
                        texts = data.get('text') or []
                        lefts = data.get('left') or []
                        tops = data.get('top') or []
                        widths = data.get('width') or []
                        heights = data.get('height') or []
                        confs = data.get('conf') or []
                        blocks = data.get('block_num') or []
                        paragraphs = data.get('par_num') or []
                        lines = data.get('line_num') or []
                        words = data.get('word_num') or []

                        for index, text_value in enumerate(texts):
                            cleaned_word = re.sub(r'\s+', ' ', str(text_value or '').strip())
                            if not cleaned_word:
                                continue
                            confidence = 0
                            if index < len(confs):
                                try:
                                    confidence = int(float(confs[index]))
                                except Exception:
                                    confidence = 0
                            if confidence > 0:
                                confidence_total += confidence
                                confidence_count += 1
                            layout.append({
                                'text': cleaned_word,
                                'left': int(lefts[index]) if index < len(lefts) else 0,
                                'top': int(tops[index]) if index < len(tops) else 0,
                                'width': int(widths[index]) if index < len(widths) else 0,
                                'height': int(heights[index]) if index < len(heights) else 0,
                                'conf': confidence,
                                'block_num': int(blocks[index]) if index < len(blocks) else 0,
                                'par_num': int(paragraphs[index]) if index < len(paragraphs) else 0,
                                'line_num': int(lines[index]) if index < len(lines) else 0,
                                'word_num': int(words[index]) if index < len(words) else 0,
                            })
                    elif data:
                        for row in str(data).splitlines()[1:]:
                            columns = row.split('\t')
                            if len(columns) < 12:
                                continue
                            cleaned_word = re.sub(r'\s+', ' ', columns[11].strip())
                            if not cleaned_word:
                                continue
                            try:
                                confidence = int(float(columns[10]))
                            except Exception:
                                confidence = 0
                            if confidence > 0:
                                confidence_total += confidence
                                confidence_count += 1
                            layout.append({
                                'text': cleaned_word,
                                'left': int(columns[6]) if columns[6].isdigit() else 0,
                                'top': int(columns[7]) if columns[7].isdigit() else 0,
                                'width': int(columns[8]) if columns[8].isdigit() else 0,
                                'height': int(columns[9]) if columns[9].isdigit() else 0,
                                'conf': confidence,
                                'block_num': int(columns[2]) if columns[2].isdigit() else 0,
                                'par_num': int(columns[3]) if columns[3].isdigit() else 0,
                                'line_num': int(columns[4]) if columns[4].isdigit() else 0,
                                'word_num': int(columns[5]) if columns[5].isdigit() else 0,
                            })

                    cleaned = re.sub(r'\s+', ' ', ' '.join(item['text'] for item in layout)).strip()
                    if not cleaned:
                        continue

                    average_confidence = confidence_total / confidence_count if confidence_count else 0
                    if len(layout) > len(best_layout) or (len(layout) == len(best_layout) and (average_confidence > best_confidence or (average_confidence == best_confidence and len(cleaned) > len(best_text)))):
                        best_text = cleaned
                        best_layout = layout
                        best_confidence = average_confidence
                        best_candidate = candidate
                        best_candidate_label = candidate_label
                        best_config = config
                    if len(best_layout) >= 4 and best_confidence >= 75:
                        break
                if len(best_layout) >= 4 and best_confidence >= 75:
                    break

            if not best_text:
                fallback_errors = []
                for config in ['--oem 3 --psm 6', '--oem 3 --psm 4', '--oem 3 --psm 11']:
                    try:
                        fallback_data = pytesseract.image_to_data(image, config=config)
                    except Exception as exc:
                        fallback_errors.append(repr(exc))
                        continue

                    fallback_layout = []
                    if isinstance(fallback_data, dict):
                        texts = fallback_data.get('text') or []
                        lefts = fallback_data.get('left') or []
                        tops = fallback_data.get('top') or []
                        widths = fallback_data.get('width') or []
                        heights = fallback_data.get('height') or []
                        confs = fallback_data.get('conf') or []
                        blocks = fallback_data.get('block_num') or []
                        paragraphs = fallback_data.get('par_num') or []
                        lines = fallback_data.get('line_num') or []
                        words = fallback_data.get('word_num') or []
                        for index, text_value in enumerate(texts):
                            cleaned_word = re.sub(r'\s+', ' ', str(text_value or '').strip())
                            if not cleaned_word:
                                continue
                            confidence = 0
                            if index < len(confs):
                                try:
                                    confidence = int(float(confs[index]))
                                except Exception:
                                    confidence = 0
                            fallback_layout.append({
                                'text': cleaned_word,
                                'left': int(lefts[index]) if index < len(lefts) else 0,
                                'top': int(tops[index]) if index < len(tops) else 0,
                                'width': int(widths[index]) if index < len(widths) else 0,
                                'height': int(heights[index]) if index < len(heights) else 0,
                                'conf': confidence,
                                'block_num': int(blocks[index]) if index < len(blocks) else 0,
                                'par_num': int(paragraphs[index]) if index < len(paragraphs) else 0,
                                'line_num': int(lines[index]) if index < len(lines) else 0,
                                'word_num': int(words[index]) if index < len(words) else 0,
                            })
                    elif fallback_data:
                        fallback_layout = [
                            {'text': re.sub(r'\s+', ' ', str(row).strip()), 'left': 0, 'top': 0, 'width': 0, 'height': 0, 'conf': 0, 'block_num': 0, 'par_num': 0, 'line_num': 0, 'word_num': 0}
                            for row in str(fallback_data).splitlines()[1:] if re.sub(r'\s+', ' ', str(row).strip())
                        ]

                    cleaned = re.sub(r'\s+', ' ', ' '.join(item['text'] for item in fallback_layout)).strip()
                    if cleaned:
                        best_text = cleaned
                        best_layout = fallback_layout
                        best_confidence = 0
                        best_candidate = image
                        best_candidate_label = 'original-image'
                        best_config = config
                        break

                if best_text:
                    debug_info = {
                        'candidate_count': len(candidates),
                        'attempt_count': attempt_count,
                        'best_candidate': best_candidate_label,
                        'best_config': best_config,
                        'best_confidence': round(best_confidence, 1) if best_confidence >= 0 else 0,
                        'word_count': len(best_layout),
                        'original_size': f'{image.size[0]}x{image.size[1]}',
                        'tesseract_path': tesseract_path,
                        'tesseract_available': bool(tesseract_path),
                        'fallback_used': True,
                        'fallback_errors': fallback_errors,
                    }
                else:
                    debug_info = {
                        'candidate_count': len(candidates),
                        'attempt_count': attempt_count,
                        'best_candidate': best_candidate_label,
                        'best_config': best_config,
                        'best_confidence': round(best_confidence, 1) if best_confidence >= 0 else 0,
                        'word_count': len(best_layout),
                        'original_size': f'{image.size[0]}x{image.size[1]}',
                        'tesseract_path': tesseract_path,
                        'tesseract_available': bool(tesseract_path),
                        'fallback_used': False,
                        'fallback_errors': fallback_errors,
                        'tesseract_error': last_ocr_error or 'Tesseract produced no text from the uploaded image.',
                    }
            else:
                debug_info = {
                    'candidate_count': len(candidates),
                    'attempt_count': attempt_count,
                    'best_candidate': best_candidate_label,
                    'best_config': best_config,
                    'best_confidence': round(best_confidence, 1) if best_confidence >= 0 else 0,
                    'word_count': len(best_layout),
                    'original_size': f'{image.size[0]}x{image.size[1]}',
                    'tesseract_path': tesseract_path,
                    'tesseract_available': bool(tesseract_path),
                    'fallback_used': False,
                    'tesseract_error': last_ocr_error or '',
                }

            if debug_dir:
                try:
                    debug_dir = Path(debug_dir)
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    safe_label = re.sub(r'[^A-Za-z0-9_.-]+', '_', debug_label or 'ocr').strip('_') or 'ocr'
                    candidate_debug_paths = []
                    if best_candidate is not None:
                        processed_path = debug_dir / f'{safe_label}_processed.png'
                        best_candidate.save(processed_path)
                        debug_info['processed_image'] = str(processed_path)
                    else:
                        for index, candidate_entry in enumerate(candidates[:4], start=1):
                            candidate = candidate_entry.get('image') if isinstance(candidate_entry, dict) else candidate_entry
                            candidate_label = candidate_entry.get('label', f'candidate-{index}') if isinstance(candidate_entry, dict) else f'candidate-{index}'
                            candidate_label = re.sub(r'[^A-Za-z0-9_.-]+', '_', candidate_label).strip('_') or f'candidate-{index}'
                            candidate_path = debug_dir / f'{safe_label}_{index}_{candidate_label}.png'
                            candidate.save(candidate_path)
                            candidate_debug_paths.append(str(candidate_path))
                        if candidate_debug_paths:
                            debug_info['candidate_images'] = candidate_debug_paths
                    metadata_path = debug_dir / f'{safe_label}_metadata.json'
                    metadata_path.write_text(json.dumps(debug_info, indent=2), encoding='utf-8')
                    debug_info['metadata'] = str(metadata_path)
                except Exception:
                    logger.exception('Failed to save OCR processed debug artifacts')

            return {'text': best_text, 'layout': best_layout, 'debug': debug_info}
    except UnidentifiedImageError:
        return {'text': '', 'layout': [], 'debug': {'error': 'unidentified-image'}}
    except Exception:
        logger.exception('Image OCR failed for uploaded material')
        return {'text': '', 'layout': [], 'debug': {'error': 'ocr-failed'}}


def _fallback_material_items_from_text(text):
    if not text:
        return []

    raw_text = str(text).strip()
    if not raw_text:
        return []

    cleaned = re.sub(r'\s+', ' ', raw_text)
    if not cleaned:
        return []

    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', raw_text) if p.strip()]
    if len(paragraphs) > 1:
        return [re.sub(r'\s+', ' ', p).strip() for p in paragraphs[:80] if re.sub(r'\s+', ' ', p).strip()]

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if len(lines) > 1:
        grouped = []
        current = []
        for line in lines:
            if len(current) and len(line.split()) <= 3 and len(current[-1].split()) <= 3:
                current.append(line)
            else:
                if current:
                    grouped.append(' '.join(current))
                current = [line]
        if current:
            grouped.append(' '.join(current))
        if len(grouped) > 1:
            return grouped[:80]
        return [re.sub(r'\s+', ' ', ' '.join(lines)).strip()]

    sentence_items = [segment.strip() for segment in re.split(r'(?<=[.!?])\s+', raw_text) if segment.strip()]
    if len(sentence_items) > 1:
        return sentence_items[:80]

    words = re.findall(r"\b[\w']+\b", cleaned, flags=re.UNICODE)
    if words:
        return words[:80]

    return [cleaned]


def _build_extracted_material_items(text, requested_reading_type=''):
    detected_type = _detect_material_type(text, requested_reading_type)
    items = _split_material_content(text, detected_type, requested_reading_type)
    if not items:
        return detected_type, []
    if detected_type == 'word':
        cleaned_items = []
        seen = set()
        for item in items:
            normalized = re.sub(r'\s+', ' ', str(item).strip())
            key = normalized.lower()
            if not normalized or key in seen:
                continue
            seen.add(key)
            cleaned_items.append(normalized[:220] + ('...' if len(normalized) > 220 else ''))
        return detected_type, cleaned_items
    cleaned_items = []
    seen = set()
    for item in items:
        normalized = re.sub(r'\s+', ' ', str(item).strip())
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        if len(normalized) > 220:
            normalized = normalized[:217].strip() + '...'
        cleaned_items.append(normalized)
    return detected_type, cleaned_items


def _build_extracted_material_items_from_ocr_layout(layout, requested_reading_type=''):
    detected_type = _infer_material_type_from_ocr_layout(layout)
    if requested_reading_type in {'word', 'sentence', 'paragraph'}:
        detected_type = requested_reading_type

    items = _build_material_items_from_ocr_layout(layout, detected_type)
    if not items:
        return detected_type, []

    cleaned_items = []
    seen = set()
    for item in items:
        normalized = re.sub(r'\s+', ' ', str(item).strip())
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        if len(normalized) > 220:
            normalized = normalized[:217].strip() + '...'
        cleaned_items.append(normalized)
    return detected_type, cleaned_items


@csrf_protect
@require_http_methods(["POST"])
@login_required(role='teacher')
def extract_reading_material_file(request):
    """Extract text snippets from an uploaded file for the Add Material modal."""
    upload = request.FILES.get('file')
    if not upload:
        return JsonResponse({'success': False, 'error': 'Please choose a PDF, DOCX, JPEG, PNG, or text file.'}, status=400)

    filename = upload.name or ''
    ext = Path(filename).suffix.lower()
    if ext not in {'.txt', '.docx', '.pdf', '.jpg', '.jpeg', '.png'}:
        return JsonResponse({'success': False, 'error': 'Only PDF, DOCX, JPG, PNG, and text files are supported.'}, status=400)

    if upload.size and upload.size > 8 * 1024 * 1024:
        return JsonResponse({'success': False, 'error': 'File is too large. Please upload a file under 8 MB.'}, status=400)

    selection_mode = (request.POST.get('selection_mode') or 'all').strip().lower()
    selected_pages = request.POST.get('selected_pages') or request.POST.getlist('selected_pages')

    upload_debug = _build_image_upload_debug_info(upload, source='received')
    logger.debug('Image upload debug received: %s', json.dumps(upload_debug, default=str))

    try:
        extracted_text = ''
        page_count = 1
        selected_pages_list = [1]
        extraction_warnings = []
        ocr_layout = []
        ocr_debug = {}
        empty_ocr_result = False
        
        if ext == '.txt':
            raw = upload.read()
            extracted_text = raw.decode('utf-8', errors='replace')
        elif ext == '.docx':
            try:
                with zipfile.ZipFile(upload) as docx_zip:
                    xml = docx_zip.read('word/document.xml').decode('utf-8', errors='ignore')
                extracted_text = re.sub(r'</w:p[^>]*>', '\n', xml)
                extracted_text = re.sub(r'<[^>]+>', '', extracted_text)
                extracted_text = (
                    extracted_text.replace('&amp;', '&')
                        .replace('&lt;', '<')
                        .replace('&gt;', '>')
                        .replace('&quot;', '"')
                        .replace('&apos;', "'")
                )
            except (KeyError, zipfile.BadZipFile):
                return JsonResponse({'success': False, 'error': 'That DOCX file could not be read. Please ensure it is a valid Word document.'}, status=400)
        elif ext in {'.jpg', '.jpeg', '.png'}:
            ocr_layout = []
            ts = int(time.time())
            safe_name = ''.join(c for c in (filename or 'upload') if c.isalnum() or c in (' ', '.', '_', '-')).strip()
            safe_name = safe_name or 'upload'
            debug_dir = None
            debug_label = ''
            if settings.DEBUG:
                debug_dir = Path(settings.BASE_DIR) / 'debug_ocr'
                debug_label = f"{ts}_{Path(safe_name).stem}"
            try:
                ocr_result = _extract_text_from_image(upload, debug_dir=debug_dir, debug_label=debug_label)
                ocr_data = _coerce_image_ocr_result(ocr_result)
                extracted_text = ocr_data.get('text') or ''
                ocr_layout = list(ocr_data.get('layout') or [])
                ocr_debug = ocr_data.get('debug') or {}
                empty_ocr_result = isinstance(ocr_result, str) and not ocr_result.strip()

                ocr_debug['upload_received'] = upload_debug
                ocr_debug['upload_after_ocr'] = _build_image_upload_debug_info(upload, source='after-ocr')
                logger.debug('OCR extraction debug: %s', json.dumps(ocr_debug, default=str))
                logger.debug('OCR extraction summary: filename=%s extracted_chars=%d layout_words=%d', filename, len(extracted_text), len(ocr_layout))

                if not extracted_text:
                    logger.info('Image extraction produced no text for %s', filename)
                else:
                    logger.info('Image extraction succeeded for %s with %d characters', filename, len(extracted_text))
            except Exception as e:
                logger.warning('Image extraction failed: %s', e)
                extraction_warnings.append(f'Image OCR encountered an issue: {str(e)}')
            # Save uploaded image and any extracted text for offline debugging
            try:
                # ensure upload pointer is at start
                try:
                    upload.seek(0)
                except Exception:
                    pass

                debug_dir = debug_dir or (Path(settings.BASE_DIR) / 'debug_ocr')
                debug_dir.mkdir(parents=True, exist_ok=True)
                debug_image_name = f"{ts}_{safe_name}"
                debug_image_path = debug_dir / debug_image_name
                # write binary contents
                with open(debug_image_path, 'wb') as _f:
                    _f.write(upload.read())
                logger.debug('Saved uploaded image for OCR debugging: %s', str(debug_image_path))
                ocr_debug['original_image'] = str(debug_image_path)

                # write extracted text (if any)
                if extracted_text:
                    debug_text_path = debug_dir / f"{ts}_{Path(safe_name).stem}.txt"
                    try:
                        with open(debug_text_path, 'w', encoding='utf-8') as _tf:
                            _tf.write(extracted_text)
                        logger.debug('Saved OCR extracted text to: %s', str(debug_text_path))
                        ocr_debug['text_file'] = str(debug_text_path)
                    except Exception:
                        logger.exception('Failed to save OCR extracted text')

                # reset stream for any further processing
                try:
                    upload.seek(0)
                except Exception:
                    pass
            except Exception:
                logger.exception('Failed to write debug OCR artifacts')
        else:
            try:
                extracted = _extract_text_from_pdf(upload, selected_pages if selection_mode == 'selected' else None)
                extracted_text = extracted['text']
                page_count = extracted['page_count']
                selected_pages_list = extracted['selected_pages']
            except Exception as e:
                logger.warning('PDF extraction failed: %s', e)
                extraction_warnings.append(f'PDF extraction encountered an issue: {str(e)}')

        # Normalize and clean extracted text while preserving paragraph structure.
        try:
            normalized_text = extracted_text.replace('\r\n', '\n').replace('\r', '\n')
            normalized_text = re.sub(r'[ \t]+', ' ', normalized_text)
            normalized_text = re.sub(r'\n{3,}', '\n\n', normalized_text)
            text = normalized_text.strip()
        except Exception:
            text = ''

        # Diagnostic logging: record what was extracted and current pytesseract command
        try:
            import pytesseract as _pyt
            tcmd = getattr(_pyt.pytesseract, 'tesseract_cmd', None)
        except Exception:
            tcmd = None
        logger.debug('Material extraction: filename=%s ext=%s upload_size=%s tesseract_cmd=%s warnings=%s text_len=%d', filename, ext, getattr(upload, 'size', None), tcmd, extraction_warnings, len(text) if text else 0)
        
        try:
            if ocr_layout:
                detected_type, items = _build_extracted_material_items_from_ocr_layout(ocr_layout, '')
            else:
                detected_type, items = _build_extracted_material_items(text, '')
        except Exception as build_exc:
            logger.exception('Material item building failed: %s', build_exc)
            extraction_warnings.append('The extracted text could not be processed into reading items. Please try a different file or a clearer image.')
            detected_type = _detect_material_type(text, '')
            items = []

        if not items and text:
            fallback_items = _fallback_material_items_from_text(text)
            if fallback_items:
                items = fallback_items
                if not extraction_warnings:
                    extraction_warnings.append('The extracted text could not be converted into reading items. Please try a different file or a clearer image.')
            elif not empty_ocr_result:
                if not extraction_warnings:
                    extraction_warnings.append(IMAGE_OCR_EMPTY_MESSAGE)

        warning_msg = '. '.join(extraction_warnings) if extraction_warnings else ''
        if not items:
            if text:
                logger.warning('Extraction produced text but no items: %s...', text[:100])
                logger.debug('Extraction produced text (long sample): %s', text[:2000])
                if not warning_msg:
                    warning_msg = 'The extracted text could not be converted into reading items. Please try a different file or a clearer image.'
                    extraction_warnings.append(warning_msg)
            else:
                if not warning_msg and not empty_ocr_result:
                    warning_msg = IMAGE_OCR_EMPTY_MESSAGE
                    extraction_warnings.append(warning_msg)
                if ocr_debug:
                    tesseract_error = ocr_debug.get('tesseract_error') or ocr_debug.get('error')
                    if tesseract_error:
                        detail_warning = f"{IMAGE_OCR_EMPTY_MESSAGE} OCR detail: {tesseract_error}"
                        if detail_warning not in extraction_warnings:
                            extraction_warnings.append(detail_warning)
                        if not warning_msg or warning_msg == IMAGE_OCR_EMPTY_MESSAGE:
                            warning_msg = detail_warning
                return JsonResponse({
                    'success': True,
                    'items': [],
                    'extracted_items': [],
                    'extractedItems': [],
                    'text': text[:12000],
                    'filename': filename,
                    'reading_type': detected_type,
                    'page_count': page_count,
                    'selected_pages': selected_pages_list,
                    'selection_mode': selection_mode,
                    'warnings': extraction_warnings,
                    'warning_message': warning_msg,
                    'ocr_debug': ocr_debug if settings.DEBUG else {},
                })
            if extraction_warnings:
                return JsonResponse({
                    'success': True,
                    'items': [],
                    'extracted_items': [],
                    'extractedItems': [],
                    'text': '',
                    'filename': filename,
                    'reading_type': detected_type,
                    'page_count': page_count,
                    'selected_pages': selected_pages_list,
                    'selection_mode': selection_mode,
                    'warnings': extraction_warnings,
                    'warning_message': warning_msg,
                    'ocr_debug': ocr_debug if settings.DEBUG else {},
                })
            return JsonResponse({
                'success': True,
                'items': [],
                'extracted_items': [],
                'extractedItems': [],
                'text': '',
                'filename': filename,
                'reading_type': detected_type,
                'page_count': page_count,
                'selected_pages': selected_pages_list,
                'selection_mode': selection_mode,
                'warnings': [],
                'warning_message': '',
                'ocr_debug': ocr_debug if settings.DEBUG else {},
            })

        return JsonResponse({
            'success': True,
            'items': items,
            'extracted_items': items,
            'extractedItems': items,
            'text': text[:12000],
            'filename': filename,
            'reading_type': detected_type,
            'page_count': page_count,
            'selected_pages': selected_pages_list,
            'selection_mode': selection_mode,
            'warnings': extraction_warnings,
            'ocr_debug': ocr_debug if settings.DEBUG else {},
        })
    except zipfile.BadZipFile:
        return JsonResponse({'success': False, 'error': 'That DOCX file could not be read.'}, status=400)
    except Exception as e:
        logger.error('Material file extraction failed: %s', e, exc_info=True)
        warning_msg = '. '.join(extraction_warnings) if extraction_warnings else 'Could not extract text from that file. Please try a different file or a clearer image.'
        if not extraction_warnings:
            extraction_warnings.append(warning_msg)
        return JsonResponse({
            'success': True,
            'items': [],
            'extracted_items': [],
            'extractedItems': [],
            'text': '',
            'filename': filename,
            'reading_type': 'word',
            'page_count': page_count,
            'selected_pages': selected_pages_list,
            'selection_mode': selection_mode,
            'warnings': extraction_warnings,
            'warning_message': warning_msg,
            'ocr_debug': ocr_debug if settings.DEBUG else {},
        })


def _detect_material_type(text, requested_reading_type=''):
    normalized_type = (requested_reading_type or '').strip().lower()
    if normalized_type in {'word', 'sentence', 'paragraph'}:
        return normalized_type

    if not text:
        return 'word'

    stripped = text.strip()
    if not stripped:
        return 'word'

    blocks = [block.strip() for block in re.split(r'\n\s*\n', stripped) if block.strip()]
    if len(blocks) > 1:
        return 'paragraph'

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(lines) > 1:
        if any(re.search(r'[.!?]', line) for line in lines):
            return 'sentence'
        return 'word'

    if re.search(r'[.!?]', stripped):
        sentence_candidates = [s.strip() for s in re.split(r'(?<=[.!?])\s+', stripped) if s.strip()]
        if len(sentence_candidates) > 1 or len(stripped.split()) > 3:
            return 'sentence'

    return 'word'


def _split_material_content(text, rtype, requested_reading_type=''):
    if not text:
        return []
    
    # Clean and normalize text
    cleaned = re.sub(r'\s+', ' ', text.strip())
    if not cleaned:
        return []
    
    if rtype == 'word':
        # Preserve short phrases extracted from PDFs/images as a single item.
        words = re.findall(r"\b[\w']+\b", text, flags=re.UNICODE)
        if words and len(words) <= 2 and '\n' not in text and not re.search(r'[.!?;,:-]', text):
            return [cleaned]
        if words:
            return words
        # Fallback: try splitting on whitespace/punctuation for non-Latin scripts
        fallback = re.split(r'[\s\-,;.!?()[\]{}]+', cleaned)
        fallback = [w.strip() for w in fallback if w.strip()]
        if fallback:
            return fallback
        # Last resort: return the whole text as one word
        return [cleaned] if cleaned else []
    
    if rtype == 'sentence':
        line_items = [line.strip() for line in text.splitlines() if line.strip()]
        if len(line_items) > 1 and '\n\n' not in text:
            return line_items
        # Try splitting on sentence-ending punctuation
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        if sentences:
            return sentences
        # Fallback: return lines if available
        if line_items:
            return line_items
        # Last resort: return the whole text as one sentence
        return [cleaned] if cleaned else []
    
    if rtype == 'paragraph':
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
        if paragraphs:
            return paragraphs
        # Fallback: try splitting on newlines
        line_items = [line.strip() for line in text.splitlines() if line.strip()]
        if len(line_items) > 1:
            return line_items
        # Last resort: return the whole text as one paragraph
        return [cleaned] if cleaned else []
    
    return [cleaned] if cleaned else []


def _shared_material_fingerprint(title, content, item_type, language=''):
    def normalize(value):
        return re.sub(r'\s+', ' ', (value or '').strip()).lower()

    return (
        normalize(title),
        normalize(content),
        normalize(item_type),
        normalize(language),
    )


def _build_updated_shared_material_title(title):
    cleaned = (title or '').strip()
    if not cleaned:
        return '[UPDATED] Shared Material'
    if cleaned.startswith('[UPDATED]'):
        return cleaned
    return f"[UPDATED] {cleaned}"


def _shared_material_import_is_unchanged(source_material, title, content, reading_type, status, language, scheduled_at, assigned_week):
    if not source_material:
        return False

    source_language = ''
    if isinstance(getattr(source_material, 'content_json', None), dict):
        source_language = str(source_material.content_json.get('language') or '').strip() or 'English'

    source_scheduled_at = getattr(source_material, 'scheduled_at', None)
    normalized_source_scheduled = None
    if source_scheduled_at:
        try:
            normalized_source_scheduled = source_scheduled_at.isoformat()
        except Exception:
            normalized_source_scheduled = str(source_scheduled_at)

    normalized_scheduled = None
    if scheduled_at:
        try:
            normalized_scheduled = scheduled_at.isoformat()
        except Exception:
            normalized_scheduled = str(scheduled_at)

    return (
        str(title or '').strip() == str(getattr(source_material, 'title', '') or '').strip()
        and str(content or '').strip() == str(getattr(source_material, 'content_text', '') or '').strip()
        and str(reading_type or '').strip().lower() == str(getattr(source_material, 'item_type', '') or '').strip().lower()
        and str(status or '').strip().lower() == str(getattr(source_material, 'status', '') or '').strip().lower()
        and str(language or '').strip() == source_language
        and str(assigned_week or '') == str(getattr(source_material, 'assigned_week', '') or '')
        and normalized_scheduled == normalized_source_scheduled
    )


def _find_existing_shared_material(title, content, item_type, language='', source_material_id=None):
    qs = Material.objects.filter(source_type='shared', is_active=True)
    if source_material_id:
        _, parsed_id = _parse_prefixed_id(source_material_id)
        if parsed_id:
            material = qs.filter(id=parsed_id).first()
            if material:
                return material

    target = _shared_material_fingerprint(title, content, item_type, language)
    for material in qs.filter(title__iexact=(title or '').strip(), item_type=item_type).order_by('created_at', 'id'):
        material_language = ''
        if isinstance(material.content_json, dict):
            material_language = material.content_json.get('language') or ''
        if _shared_material_fingerprint(material.title, material.content_text, material.item_type, material_language) == target:
            return material
    return None


def _material_response_payload(material, tokens=None, section=None, is_shared_material=None, shared_owner_teacher_name=None):
    item_count = len(tokens) if tokens is not None else 1
    if tokens is None and isinstance(material.content_json, dict) and isinstance(material.content_json.get('items'), list):
        item_count = len(material.content_json.get('items'))

    source_type = str(getattr(material, 'source_type', 'personal') or 'personal').strip().lower()
    resolved_shared = bool(is_shared_material) if is_shared_material is not None else (source_type == 'shared')

    content_json = getattr(material, 'content_json', None) or {}
    language_value = ''
    if isinstance(content_json, dict):
        language_value = str(content_json.get('language') or '').strip()
    if not language_value:
        language_value = str(getattr(material, 'language', '') or '').strip()
    if not language_value:
        language_value = 'English'

    return {
        'id': f"material-{material.id}",
        'raw_id': material.id,
        'code': material.code,
        'title': material.title,
        'item_type': material.item_type,
        'type': material.type,
        'source_type': source_type,
        'material_source': source_type,
        'is_shared_material': resolved_shared,
        'shared_owner_teacher_name': shared_owner_teacher_name if resolved_shared else None,
        'content': material.content_text,
        'status': material.status,
        'language': language_value,
        'schedule': timezone.localtime(material.scheduled_at, timezone.get_default_timezone()).strftime('%Y-%m-%dT%H:%M') if material.scheduled_at else None,
        'items': item_count,
        'created_at': material.created_at.isoformat() if getattr(material, 'created_at', None) else None,
        'assigned_sections': [section.class_code] if section else [s.class_code for s in material.assigned_sections.all()],
        'assigned_week': material.assigned_week,
        'assigned_week_display': format_assigned_week_display(material.assigned_week),
    }


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
        requested_reading_type = (data.get('reading_type') or '').strip().lower()
        status       = (data.get('status') or 'published').strip()          # published | draft | scheduled
        requested_usage_type = (data.get('usage_type') or 'assessment').strip()        # practice | assessment | both
        requested_source_type = (data.get('source_type') or data.get('origin') or 'shared').strip().lower()
        source_type = requested_source_type if requested_source_type in ('personal', 'shared') else 'shared'
        class_code   = (data.get('class_code') or '').strip()
        language     = Material.normalize_language_value(data.get('language'))
        scheduled_at_str = (data.get('scheduled_at') or '').strip()
        assigned_week_raw = data.get('assigned_week')
        assigned_week, week_error = parse_assigned_week(assigned_week_raw)
        source_material_id = data.get('source_material_id')

        if source_type not in ('personal', 'shared'):
            source_type = 'shared'

        # Teachers may only create assessment materials from this endpoint.
        usage_type = 'assessment'

        logger.debug(f"add_reading_material received: title={title}, status={status}, class_code={class_code}, source_type={source_type}")

        # ── server-side validation ──────────────────────────────────────────
        errors = {}
        if not title:
            errors['title'] = 'Material title is required.'
        if not content:
            errors['content'] = 'Material content is required.'
        if status not in ('published', 'draft', 'scheduled'):
            errors['status'] = 'Status is required.'
        if source_type and source_type not in ('personal', 'shared'):
            errors['source_type'] = 'Invalid source type.'
        if status == 'scheduled' and not scheduled_at_str:
            errors['scheduled_at'] = 'Scheduled date & time is required.'
        if week_error:
            errors['assigned_week'] = week_error

        if errors:
            logger.warning(f"add_reading_material validation failed: {errors}")
            return JsonResponse({'success': False, 'errors': errors}, status=400)

        reading_type = _detect_material_type(content, requested_reading_type)
        tokens = _split_material_content(content, reading_type, requested_reading_type)

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
            existing_shared = None
            source_material = None
            needs_duplicate = False
            if source_type == 'shared':
                if source_material_id:
                    _, parsed_id = _parse_prefixed_id(source_material_id)
                    if parsed_id:
                        source_material = Material.objects.filter(id=parsed_id, source_type='shared', is_active=True).first()

                if source_material:
                    needs_duplicate = not _shared_material_import_is_unchanged(
                        source_material,
                        title,
                        content,
                        reading_type,
                        status,
                        language,
                        scheduled_at,
                        assigned_week,
                    )
                    if not needs_duplicate:
                        existing_shared = source_material
                else:
                    existing_shared = _find_existing_shared_material(
                        title,
                        content,
                        reading_type,
                        language,
                        source_material_id=source_material_id,
                    )
            if existing_shared:
                existing_owner_id = existing_shared.teacher_id or getattr(getattr(existing_shared, 'section', None), 'teacher_id', None)
                existing_is_from_other_teacher = bool(existing_owner_id and teacher_user and existing_owner_id != teacher_user.id)
                existing_owner_name = ''
                if existing_is_from_other_teacher and getattr(existing_shared, 'teacher', None):
                    existing_owner_name = f"{existing_shared.teacher.first_name} {existing_shared.teacher.last_name}".strip()
                material_payload = _material_response_payload(
                    existing_shared,
                    is_shared_material=existing_is_from_other_teacher,
                    shared_owner_teacher_name=existing_owner_name or None,
                )
                return JsonResponse({
                    'success': True,
                    'message': 'Shared reading material already exists.',
                    'material_ids': [existing_shared.id],
                    'material_id': existing_shared.id,
                    'created_count': 0,
                    'reused': True,
                    'material': material_payload,
                    'title': existing_shared.title,
                    'type': existing_shared.item_type,
                    'status': existing_shared.status,
                    'created_at': existing_shared.created_at.isoformat() if getattr(existing_shared, 'created_at', None) else None,
                    'overview': _compute_teacher_overview(teacher_user),
                })

            # If this material is intended to be an assessment (or both), do not
            # create an Assessment record until a student completes an attempt.
            # This keeps the Assessments table empty for new materials until
            # results exist.
            assessment_obj = None

            material_title = title
            if source_type == 'shared' and needs_duplicate:
                material_title = _build_updated_shared_material_title(title)

            m = Material.objects.create(
                assessment=None,
                section=section,
                teacher=teacher_user,
                item_type=reading_type,
                title=material_title,
                prompt_text=(tokens[0] if tokens else material_title) or material_title,
                content_text=content,
                content_json={'items': tokens, 'language': language},
                type=usage_type,
                source_type=source_type,
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
            if source_type == 'shared' and getattr(m, 'source_type', '') == 'shared':
                _notify_principals(
                    'New shared reading material added',
                    f'A new reading material from the Others shared library, "{m.title}", has been used by {teacher_user.first_name} {teacher_user.last_name}.',
                    'info',
                    reverse('dashboard_principal'),
                    teacher_user,
                    send_email=False,
                )
            _notify_admins(
                'Teacher created a new material',
                f'{teacher_user.first_name} {teacher_user.last_name} created "{m.title}".',
                'info',
                reverse('admin_course_detail', args=[m.id]),
                teacher_user,
            )
            created_ids = [m.id]
            material_payload = _material_response_payload(m, tokens=tokens, section=section)

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
                Q(teacher_id=user_id) |
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
        requested_reading_type = (data.get('reading_type') or '').strip().lower()
        language = Material.normalize_language_value(data.get('language'))
        material.status = data.get('status', material.status)
        material.type = 'assessment'

        source_type = (data.get('source_type') or material.source_type).strip().lower()
        if source_type in ('personal', 'shared'):
            material.source_type = source_type

        if 'assigned_week' in data:
            assigned_week, week_error = parse_assigned_week(data.get('assigned_week'))
            if week_error:
                return JsonResponse({'success': False, 'errors': {'assigned_week': week_error}}, status=400)
            material.assigned_week = assigned_week
        
        material.is_active = (material.status in ['published', 'scheduled'])
        # current teacher for any potential Assessment creation
        teacher_user = User.objects.filter(id=user_id).first()
        if material.teacher_id is None and teacher_user:
            material.teacher = teacher_user

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

        if content != material.content_text or requested_reading_type in {'word', 'sentence', 'paragraph'}:
            material.content_text = content
            material.item_type = _detect_material_type(content, requested_reading_type)
            content_json = dict(material.content_json or {})
            content_json['items'] = _split_material_content(content, material.item_type, requested_reading_type)
            content_json['language'] = language
            material.content_json = content_json
        else:
            content_json = dict(material.content_json or {})
            content_json['language'] = language
            material.content_json = content_json
            
        # Ensure Assessment linkage reflects the requested usage type.
        # If material should be an assessment (or both), create or update the
        # linked Assessment record so attempts are recorded in the
        # assessments table. If switching to practice, detach the link.
        try:
            if material.type in ('assessment', 'both'):
                if getattr(material, 'assessment', None):
                    # Keep assessment metadata in sync only when the record already exists.
                    try:
                        a = material.assessment
                        a.title = material.title
                        a.assessment_type = material.item_type
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
@admin_required
def teacher_update_practice(request):
    """Allow admins to update Practice items (title, content, status)."""
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
            if practice.material:
                practice.material.content_text = practice.content_text
                practice.material.save(update_fields=['content_text', 'updated_at'])
        if status is not None:
            practice.status = status
            practice.is_active = (status in ['published', 'scheduled'])
            if practice.material:
                practice.material.status = practice.status
                practice.material.is_active = practice.is_active
                practice.material.save(update_fields=['status', 'is_active', 'updated_at'])

        practice.save()
        return JsonResponse({'success': True, 'message': 'Practice updated successfully'})
    except Exception as e:
        logger.exception('Error updating practice')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_protect
@require_http_methods(["POST"])
@admin_required
def delete_practice(request):
    """Allow admins to delete Practice items."""
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
                Q(teacher_id=user_id) |
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
@login_required()
def record_assessment_completion(request):
    """Handles notification when student completes reading material."""
    try:
        data = json.loads(request.body)
        assessment_id = data.get('assessment_id')
        material_id = data.get('material_id')
        is_retake = data.get('is_retake', False)
        attempt_number = data.get('attempt_number', 0)
        activity_type = data.get('activity_type', 'assessment')
        assist_context = _resolve_assist_token(data.get('assist_token'))
        if assist_context:
            student_user = assist_context['student']
            assist_teacher_user = assist_context['teacher']
            material_id = str(assist_context['material'].id)
            assessment_id = None
        else:
            if request.session.get('user_role') != 'student':
                return JsonResponse({'success': False, 'error': 'Forbidden: insufficient role'}, status=403)
            student_user = User.objects.get(id=request.session.get('user_id'))
            assist_teacher_user = None

        assessment = None
        teacher_user = None
        title_text = None
        material = None
        practice_obj = None

        a_prefix, a_id = _parse_prefixed_id(assessment_id)
        m_prefix, m_id = _parse_prefixed_id(material_id)

        # Prefer explicit assessment identifier
        if a_id and (a_prefix is None or a_prefix.startswith('assessment')):
            assessment = Assessment.objects.select_related('teacher').filter(id=a_id, source_assessment__isnull=True).first()
            if assessment:
                teacher_user = assessment.teacher
                title_text = assessment.title
        # material_id may refer to an Assessment (prefixed), Material, or Practice record
        if not assessment and m_id and m_prefix and m_prefix.startswith('assessment'):
            assessment = Assessment.objects.select_related('teacher').filter(id=m_id, source_assessment__isnull=True).first()
            if assessment:
                teacher_user = assessment.teacher
                title_text = assessment.title

        if not assessment and m_id and (m_prefix is None or m_prefix.startswith('material')):
            material = Material.objects.select_related('assessment', 'section__teacher').filter(id=m_id).first()
            if material:
                if material.assessment:
                    assessment = material.assessment
                    if assessment and assessment.source_assessment_id is not None:
                        assessment = assessment.source_assessment or assessment._group_assessment()
                    teacher_user = assessment.teacher if assessment else None
                elif material.section:
                    teacher_user = material.section.teacher
                title_text = material.title or material.content_text or material.prompt_text or material.item_type

        # Fallback: numeric material id may actually be an assessment id when no Material record exists.
        if not assessment and not material and m_id is not None:
            possible_assessment = Assessment.objects.select_related('teacher').filter(id=m_id, source_assessment__isnull=True).first()
            if possible_assessment:
                assessment = possible_assessment
                teacher_user = assessment.teacher
                title_text = assessment.title

        # Student practice hub sends practice-<material_id> for admin library materials.
        if not assessment and not material and m_id and m_prefix and m_prefix.startswith('practice') and activity_type == 'practice':
            material = Material.objects.filter(id=m_id, type='practice').first()
            if material:
                title_text = material.title or material.content_text or material.prompt_text or material.item_type
                try:
                    practice_obj = material.practice_result
                except Practice.DoesNotExist:
                    practice_obj = None

        # support practice ids (practice-<id>) that map to Practice model
        if not assessment and m_id and m_prefix and m_prefix.startswith('practice'):
            try:
                from .models import Practice as PracticeModel
                practice_obj = practice_obj or PracticeModel.objects.select_related('teacher').filter(id=m_id).first()
                if practice_obj:
                    title_text = practice_obj.title or practice_obj.content_text or practice_obj.prompt_text
                    teacher_user = getattr(practice_obj, 'teacher', None)
            except Exception:
                practice_obj = None

        if not assessment and not material and not practice_obj:
            return JsonResponse({'success': False, 'error': 'No assessment_id or material_id provided.'}, status=400)

        class_code = data.get('class_code')
        is_practice = (
            activity_type == 'practice'
            or practice_obj is not None
            or (material and material.type == 'practice')
        )
        already_completed = False
        if not is_practice:
            already_completed = _student_completed_assessment_before(assessment, material, student_user)
        score_payload = _practice_score_payload(data) if is_practice else _assessment_score_payload(data)

        # Record attempt server-side (authoritative). We mark attempts as completed
        # because this endpoint is called when the student finishes the reading flow.
        try:
            device_info = {
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'remote_addr': request.META.get('REMOTE_ADDR', ''),
            }
            attempt_payload = {
                'status': 'completed',
                'completed_at': timezone.now().isoformat(),
                'device_info': device_info,
                'game_mode': str(data.get('game_mode') or '').strip().lower(),
                'stars_earned': data.get('stars_earned', 0),
                'items_completed': data.get('items_completed', 0),
                **score_payload,
            }
            if is_practice:
                material_content = dict(getattr(material, 'content_json', None) or {}) if material else {}
                material_game_mode = str(material_content.get('mode') or attempt_payload.get('game_mode') or '').strip().lower()
                if material and material_game_mode == 'color':
                    existing_completion = _material_practice_completion(material, student_user)
                    try:
                        existing_stars = max(0, int(existing_completion.get('stars_earned', 0) or 0))
                    except (TypeError, ValueError):
                        existing_stars = 0
                    try:
                        incoming_stars = max(0, int(attempt_payload.get('stars_earned', 0) or 0))
                    except (TypeError, ValueError):
                        incoming_stars = 0
                    attempt_payload['stars_earned'] = max(existing_stars, incoming_stars)
                if practice_obj:
                    practice_obj.record_attempt(student_user, replace=True, **attempt_payload)
                if material and material.type == 'practice':
                    _record_material_practice_completion(material, student_user, attempt_payload)
            elif material and material.type in ('assessment', 'both'):
                if teacher_user is None:
                    if getattr(material, 'teacher', None):
                        teacher_user = material.teacher
                    elif material.section and getattr(material.section, 'teacher', None):
                        teacher_user = material.section.teacher
                    else:
                        first_section = material.assigned_sections.filter(is_active=True).select_related('teacher').first()
                        if first_section and getattr(first_section, 'teacher', None):
                            teacher_user = first_section.teacher
                if material.teacher_id is None and teacher_user is not None:
                    material.teacher = teacher_user
                    material.save(update_fields=['teacher', 'updated_at'])
                material.record_assessment_result(student_user, **attempt_payload)
            elif assessment:
                assessment.record_attempt(student_user, **attempt_payload)
            # Note: standalone Material objects that are not linked to Assessment do not
            # currently have an attempts schema; they are handled by client-side notifications.
            if not is_practice:
                _update_student_reading_profile(student_user, score_payload)
        except Exception as e:
            logger.exception('Failed to persist assessment/practice attempt: %s', e)

        student_name = f"{student_user.first_name} {student_user.last_name}".strip() or student_user.custom_id
        class_name = _resolve_assessment_class_name(assessment=assessment, material=material, class_code=class_code)

        if not is_practice and should_notify_assessment:
            _notify_principal_performance_events(
                student_user,
                assessment=assessment,
                material=material,
                class_name=class_name,
                score_payload=score_payload,
            )

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

        if is_practice:
            _notify_admins(
                title,
                notif_msg,
                "assessment",
                reverse('admin_students'),
                student_user,
                send_email=False,
            )
        else:
            teacher_recipients = []
            if should_notify_assessment:
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

                if _assessment_completion_notif_exists(
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

            if should_notify_assessment:
                _notify_admins(
                    title,
                    notif_msg,
                    "assessment",
                    reverse('admin_students'),
                    student_user,
                    send_email=False,
                )
        if assist_teacher_user and not is_practice:
            _create_notification(
                assist_teacher_user,
                'Assist assessment completed',
                f'Assisted assessment "{title_text}" was completed for {student_name}.',
                'assessment',
                f"/dashboard/teacher/students/detail/?student_id={student_user.custom_id}",
                assist_teacher_user,
                send_email=False,
                force_in_app=True,
            )
        response_payload = {'success': True}
        if is_practice and material:
            response_payload.update({
                'material_id': f"practice-{material.id}" if material.type == 'practice' else f"material-{material.id}",
                'status': 'Done',
                'is_done': True,
                'score': score_payload.get('score', 0),
                'accuracy': score_payload.get('accuracy', 0),
                'correct_responses': score_payload.get('correct_responses', 0),
                'incorrect_responses': score_payload.get('incorrect_responses', 0),
                'wpm': score_payload.get('wpm', 0),
                'reading_time_seconds': score_payload.get('reading_time_seconds', 0),
                'redirect_url': f"/dashboard/practice/results/?id=practice-{material.id}",
            })
        return JsonResponse(response_payload)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required(role='student')
def practice_results(request):
    return redirect('practice')

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

@csrf_protect
@require_http_methods(["POST"])
@login_required()
def clear_notifications(request):
    """API: Clear all notifications for the current user."""
    try:
        user = User.objects.get(id=request.session.get('user_id'))
        deleted_count, _ = Notification.objects.filter(recipient=user).delete()
        return JsonResponse({'success': True, 'deleted_count': deleted_count})
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

        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        seven_days_ago = now - timedelta(days=7)

        def _normalize_dashboard_level(value):
            text = str(value or '').strip().lower().replace('_', ' ').replace('-', ' ')
            if not text:
                return None
            if 'pending' in text:
                return 'Pending'
            if 'low' in text and 'emerging' in text:
                return 'Low Emerging Readers'
            if 'high' in text and 'emerging' in text:
                return 'High Emerging Readers'
            if 'develop' in text:
                return 'Developing Readers'
            if 'transition' in text:
                return 'Transitioning Readers'
            if 'grade' in text or text in {'g', 'gr'}:
                return 'Readers at Grade Level'
            return None
        
        # Get all active sections for this teacher
        sections = Section.objects.filter(teacher=teacher, is_active=True)
        
        student_map = {}
        level_counts = {
            'Low Emerging Readers': 0,
            'High Emerging Readers': 0,
            'Developing Readers': 0,
            'Transitioning Readers': 0,
            'Readers at Grade Level': 0,
        }
        attempt_history = {}
        latest_scores = {}
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
        latest_scores = {}
        teacher_sections = Section.objects.filter(
            class_code__in=[
                code
                for sdata in student_map.values()
                for code in sdata.get('class_codes', [])
            ],
            is_active=True,
        )
        for assessment in Assessment.objects.filter(section__in=teacher_sections, is_active=True, source_assessment__isnull=True):
            attempts = assessment.get_attempts()
            for attempt in attempts:
                if not isinstance(attempt, dict) or attempt.get('status') != 'completed':
                    continue
                student_id = attempt.get('student_id')
                if not student_id:
                    continue
                completed_dt = _parse_attempt_timestamp(
                    attempt.get('completed_at') or attempt.get('updated_at') or attempt.get('started_at')
                )
                if not completed_dt:
                    completed_dt = now

                score_value = _as_float(attempt.get('total_score'), default=None)
                if score_value is None:
                    score_value = _as_float(attempt.get('accuracy'), default=None)
                if score_value is None:
                    score_value = _as_float(attempt.get('wpm'), default=None)

                derived_level = None
                if attempt.get('crla_classification') or attempt.get('classification'):
                    derived_level = attempt.get('crla_classification') or attempt.get('classification')
                elif score_value is not None:
                    derived_level = _crla_classification(score_value)

                sid_key = str(student_id)
                attempt_history.setdefault(sid_key, []).append({
                    'completed_at': completed_dt,
                    'score': score_value,
                })

                current = latest_scores.get(sid_key)
                if current and current.get('completed_at_dt') and current['completed_at_dt'] >= completed_dt:
                    continue
                latest_scores[sid_key] = {
                    'completed_at_dt': completed_dt,
                    'completed_at': completed_dt.isoformat(),
                    'assessment_title': assessment.title,
                    'assessment_type': assessment.assessment_type,
                    'level': derived_level,
                    'accuracy': attempt.get('accuracy'),
                    'wpm': attempt.get('wpm'),
                    'fluency_score': attempt.get('fluency_score'),
                    'pronunciation_score': attempt.get('pronunciation_score'),
                    'time_score': attempt.get('time_score'),
                    'duration_seconds': attempt.get('duration_seconds'),
                    'total_score': attempt.get('total_score'),
                }
        
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
                
                latest = latest_scores.get(str(user.id), {})
                history = sorted(attempt_history.get(str(user.id), []), key=lambda item: item['completed_at'])
                recent_history = [item for item in history if item.get('completed_at') and item['completed_at'] >= thirty_days_ago and item.get('score') is not None]
                if len(recent_history) >= 2:
                    first_score = recent_history[0]['score']
                    last_score = recent_history[-1]['score']
                    if first_score not in (None, 0):
                        improvement = ((last_score - first_score) / first_score) * 100
                    else:
                        improvement = last_score - (first_score or 0)
                else:
                    improvement = 0

                last_active = history[-1]['completed_at'] if history else None
                has_score_data = any(
                    value not in (None, '', '0', 0)
                    for value in [
                        latest.get('accuracy'),
                        latest.get('wpm'),
                        latest.get('fluency_score'),
                        latest.get('pronunciation_score'),
                        latest.get('time_score'),
                        latest.get('duration_seconds'),
                        latest.get('total_score'),
                        profile.get('accuracy'),
                        profile.get('wpm'),
                        profile.get('fluency_score'),
                        profile.get('pronunciation_score'),
                        profile.get('time_score'),
                        profile.get('total_score'),
                    ]
                )
                display_level = latest.get('level') or profile.get('reading_level') or (user.reading_level if has_score_data else None)
                normalized_level = _normalize_dashboard_level(display_level)
                if normalized_level is None and not has_score_data:
                    normalized_level = 'Pending'
                sdata.update({
                    'level': normalized_level or 'Pending',
                    'accuracy': latest.get('accuracy') if latest.get('accuracy') is not None else profile.get('accuracy', '0'),
                    'wpm': latest.get('wpm') if latest.get('wpm') is not None else profile.get('wpm', '0'),
                    'fluency_score': latest.get('fluency_score', profile.get('fluency_score')),
                    'pronunciation_score': latest.get('pronunciation_score', profile.get('pronunciation_score')),
                    'time_score': latest.get('time_score', profile.get('time_score')),
                    'duration_seconds': latest.get('duration_seconds'),
                    'total_score': latest.get('total_score', profile.get('total_score')),
                    'completed_at': latest.get('completed_at') or profile.get('last_assessment_at'),
                    'assessment_title': latest.get('assessment_title', profile.get('last_assessment_title')),
                    'assessment_type': latest.get('assessment_type'),
                    'has_completed_assessment': bool(latest),
                    'latest_score': latest.get('total_score') if latest.get('total_score') is not None else latest.get('accuracy') if latest.get('accuracy') is not None else latest.get('wpm'),
                    'last_active_at': last_active.isoformat() if last_active else None,
                    'improvement_30d': round(improvement, 1),
                })
                if normalized_level and normalized_level in level_counts:
                    level_counts[normalized_level] += 1
                results.append(sdata)

        active_this_week = len({
            sid for sid, attempts in attempt_history.items()
            if any(item.get('completed_at') and item['completed_at'] >= seven_days_ago for item in attempts)
        })

        top_performer_name = '—'
        top_performer_score = None
        improvement_values = []

        for student in results:
            sid_key = str(student['id'])
            latest = latest_scores.get(sid_key, {})
            score_value = latest.get('total_score')
            if score_value is None:
                score_value = latest.get('accuracy')
            if score_value is None:
                score_value = latest.get('wpm')

            try:
                score_value = float(score_value) if score_value is not None else None
            except (TypeError, ValueError):
                score_value = None

            if score_value is not None and (top_performer_score is None or score_value > top_performer_score):
                top_performer_score = score_value
                top_performer_name = student['name']

            improvement_value = student.get('improvement_30d')
            if improvement_value is not None:
                improvement_values.append(float(improvement_value))

        avg_improvement = round(sum(improvement_values) / len(improvement_values), 1) if improvement_values else 0
        needs_support_count = level_counts['Low Emerging Readers'] + level_counts['High Emerging Readers']
        grade_level_ready_count = level_counts['Readers at Grade Level']

        dashboard_metrics = {
            'total_students': len(results),
            'needs_support_count': needs_support_count,
            'grade_level_ready_count': grade_level_ready_count,
            'avg_improvement_30d': avg_improvement,
            'active_this_week_count': active_this_week,
            'top_performer_name': top_performer_name,
            'top_performer_score': top_performer_score,
            'level_counts': level_counts,
            'average_score': round(sum((float(s.get('latest_score')) for s in results if s.get('latest_score') not in (None, '')), 0) / max(1, len([s for s in results if s.get('latest_score') not in (None, '')])), 1) if any(s.get('latest_score') not in (None, '') for s in results) else 0,
        }

        return JsonResponse({'success': True, 'students': results, 'level_counts': level_counts, 'dashboard_metrics': dashboard_metrics, 'total_students': len(results)})
    except Exception as e:
        logger.error(f"Error in get_teacher_students_api: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# =================================================================================
# PRINCIPAL DASHBOARD VIEWS
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


def _grade_sort_key(value):
    text = str(value or '').strip()
    match = re.search(r'(\d+)', text)
    return int(match.group(1)) if match else 999


def _normalize_grade(value):
    text = str(value or '').strip()
    if not text:
        return 'Unspecified'
    match = re.search(r'(\d+)', text)
    if match:
        return f"Grade {int(match.group(1))}"
    return text.title()


def _pct(numerator, denominator):
    if not denominator:
        return 0
    try:
        return round((float(numerator) / float(denominator)) * 100)
    except Exception:
        return 0


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_attempt_timestamp(value):
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if parsed:
        return parsed
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _principal_analytics(user):
    students_qs = User.objects.filter(role='student', is_archived=False)
    teachers_qs = User.objects.filter(role='teacher', is_archived=False)
    sections = Section.objects.filter(is_active=True).select_related('teacher')
    assessments = Assessment.objects.filter(is_active=True, source_assessment__isnull=True).select_related('section', 'teacher')

    school_info = _get_profile_dict(user, 'principal_school_info') if user else {}
    school_name = (
        (school_info.get('name') if isinstance(school_info, dict) else None)
        or getattr(user, 'school', None)
        or 'Salawag Elementary School'
    )

    student_grade_map = {}
    grade_students = {}
    for student in students_qs:
        grade_label = _normalize_grade(student.grade_level)
        student_grade_map[student.id] = grade_label
        grade_students.setdefault(grade_label, 0)
        grade_students[grade_label] += 1

    grade_keys = sorted(grade_students.keys(), key=_grade_sort_key)
    grade_data = {
        grade: {
            'grade': grade,
            'total_students': grade_students.get(grade, 0),
            'completed_student_ids': set(),
            'in_progress_student_ids': set(),
            'reading_sum': 0.0,
            'reading_count': 0,
            'speech_sum': 0.0,
            'speech_count': 0,
            'total_sum': 0.0,
            'total_count': 0,
            'current_month_scores': [],
            'previous_month_scores': [],
        }
        for grade in grade_keys
    }

    now = timezone.now()
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_month_end = current_month_start - timedelta(seconds=1)
    previous_month_start = previous_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    assessment_rows = []
    assessment_attempt_rows = []
    status_counts = {'completed': 0, 'in_progress': 0, 'pending': 0}
    type_stats = {}
    latest_activity = []

    def _clean_numeric_scores(values):
        cleaned = []
        for value in values or []:
            numeric = _as_float(value, default=None)
            if numeric is None:
                continue
            # Skip NaN values while keeping valid numeric scores.
            if numeric != numeric:
                continue
            cleaned.append(numeric)
        return cleaned

    for assessment in assessments:
        attempts = assessment.get_attempts()
        participants = set()
        completed_students = set()
        completed_scores = []
        last_completed_at = None

        for attempt in attempts:
            sid = attempt.get('student_id')
            if sid:
                try:
                    participants.add(int(sid))
                except (TypeError, ValueError):
                    continue

            status = str(attempt.get('status') or '').lower()
            if status == 'completed' and sid:
                try:
                    sid_int = int(sid)
                except (TypeError, ValueError):
                    continue
                completed_students.add(sid_int)
                score_val = _as_float(attempt.get('total_score'), default=None)
                if score_val is not None:
                    completed_scores.append(score_val)

                grade_label = student_grade_map.get(sid_int)
                if grade_label and grade_label in grade_data:
                    g = grade_data[grade_label]
                    g['completed_student_ids'].add(sid_int)
                    g['in_progress_student_ids'].discard(sid_int)

                    accuracy = _as_float(attempt.get('accuracy'), default=None)
                    pronunciation = _as_float(attempt.get('pronunciation_score'), default=None)
                    total_score = _as_float(attempt.get('total_score'), default=None)
                    if accuracy is not None:
                        g['reading_sum'] += accuracy
                        g['reading_count'] += 1
                    if pronunciation is not None:
                        g['speech_sum'] += pronunciation
                        g['speech_count'] += 1
                    if total_score is not None:
                        g['total_sum'] += total_score
                        g['total_count'] += 1

                    completed_at = _parse_attempt_timestamp(attempt.get('completed_at') or attempt.get('updated_at') or attempt.get('started_at'))
                    if completed_at:
                        if completed_at >= current_month_start and total_score is not None:
                            g['current_month_scores'].append(total_score)
                        elif previous_month_start <= completed_at <= previous_month_end and total_score is not None:
                            g['previous_month_scores'].append(total_score)
                        if not last_completed_at or completed_at > last_completed_at:
                            last_completed_at = completed_at
            elif sid:
                try:
                    sid_int = int(sid)
                except (TypeError, ValueError):
                    continue
                grade_label = student_grade_map.get(sid_int)
                if grade_label and grade_label in grade_data and sid_int not in grade_data[grade_label]['completed_student_ids']:
                    grade_data[grade_label]['in_progress_student_ids'].add(sid_int)

        expected_students = assessment.section.get_student_count() if assessment.section else len(participants)
        completion_rate = _pct(len(completed_students), expected_students if expected_students else len(participants))

        status_raw = str(assessment.status or '').lower()
        if status_raw == 'draft' or (status_raw == 'scheduled' and assessment.scheduled_at and assessment.scheduled_at > now):
            status_key = 'pending'
        elif completion_rate >= 100 and expected_students:
            status_key = 'completed'
        elif participants or completed_students:
            status_key = 'in_progress'
        else:
            status_key = 'pending'
        status_counts[status_key] += 1

        status_label_map = {
            'completed': ('Completed', 'success'),
            'in_progress': ('In Progress', 'warning'),
            'pending': ('Pending', 'info'),
        }
        status_label, badge = status_label_map[status_key]

        avg_score = round(sum(completed_scores) / len(completed_scores), 1) if completed_scores else 0
        type_key = assessment.assessment_type or 'other'
        type_bucket = type_stats.setdefault(type_key, {'total': 0, 'completed': 0, 'score_sum': 0.0, 'score_count': 0})
        type_bucket['total'] += 1
        if status_key == 'completed':
            type_bucket['completed'] += 1
        if completed_scores:
            type_bucket['score_sum'] += sum(completed_scores)
            type_bucket['score_count'] += len(completed_scores)

        assessment_rows.append({
            'id': assessment.id,
            'title': assessment.title,
            'assessment_type': assessment.get_assessment_type_display(),
            'grade_label': _normalize_grade(getattr(assessment.section, 'class_name', '') or getattr(assessment.section, 'header', '')),
            'status': status_label,
            'status_badge': badge,
            'participants': len(participants),
            'expected_students': expected_students,
            'completed_students': len(completed_students),
            'completion_rate': completion_rate,
            'avg_score': avg_score,
            'code': assessment.code,
            'teacher_name': f"{assessment.teacher.first_name} {assessment.teacher.last_name}".strip(),
            'updated_at': assessment.updated_at,
        })

        attempts_for_students = assessment.get_attempts()
        if attempts_for_students:
            student_ids = {
                int(attempt.get('student_id'))
                for attempt in attempts_for_students
                if attempt and attempt.get('student_id')
            }
            students_map = {
                student.id: student
                for student in User.objects.filter(id__in=student_ids)
            }
            attempt_counts = {}
            for idx, attempt in enumerate(attempts_for_students, start=1):
                if not isinstance(attempt, dict):
                    continue
                sid = attempt.get('student_id')
                try:
                    sid_int = int(sid)
                except (TypeError, ValueError):
                    sid_int = None
                attempt_counts[sid_int] = attempt_counts.get(sid_int, 0) + 1
                student = students_map.get(sid_int)
                student_name = ''
                if student:
                    student_name = f"{student.first_name} {student.last_name}".strip() or student.custom_id or student.email or f"Student {student.id}"
                else:
                    student_name = f"Student {sid_int or sid}"

                attempt_key = f"{assessment.id}-{sid_int or 'unknown'}-{attempt_counts[sid_int]}"
                completed_at = attempt.get('completed_at') or attempt.get('started_at') or attempt.get('updated_at')
                assessment_attempt_rows.append({
                    'attempt_key': attempt_key,
                    'assessment_id': assessment.id,
                    'assessment_code': assessment.code,
                    'assessment_title': assessment.title,
                    'assessment_type': assessment.get_assessment_type_display(),
                    'student_id': sid_int,
                    'student_name': student_name,
                    'attempt_number': attempt_counts[sid_int],
                    'status': str(attempt.get('status') or '').title(),
                    'total_score': _as_float(attempt.get('total_score'), default=None),
                    'accuracy': _as_float(attempt.get('accuracy'), default=None),
                    'pronunciation_score': _as_float(attempt.get('pronunciation_score'), default=None),
                    'wpm': _as_float(attempt.get('wpm'), default=None),
                    'completed_at': completed_at,
                    'updated_at': _parse_attempt_timestamp(completed_at) if completed_at else assessment.updated_at,
                })

        if last_completed_at:
            latest_activity.append({
                'title': 'Assessment Completed',
                'message': f"{assessment.title} recorded completion updates.",
                'created_at': last_completed_at,
                'variant': 'success',
            })

    assessment_rows.sort(key=lambda row: row['updated_at'], reverse=True)

    grade_rows = []
    for grade in sorted(grade_data.keys(), key=_grade_sort_key):
        data = grade_data[grade]
        total_students = data['total_students']
        completed_count = len(data['completed_student_ids'])
        in_progress_count = len(data['in_progress_student_ids'])
        not_started = max(total_students - completed_count - in_progress_count, 0)
        reading_avg = round(data['reading_sum'] / data['reading_count'], 1) if data['reading_count'] else 0
        speech_avg = round(data['speech_sum'] / data['speech_count'], 1) if data['speech_count'] else 0
        average = round((reading_avg + speech_avg) / 2, 1) if (reading_avg or speech_avg) else 0
        completion_pct = _pct(completed_count, total_students)

        current_month_scores = _clean_numeric_scores(data.get('current_month_scores'))
        previous_month_scores = _clean_numeric_scores(data.get('previous_month_scores'))
        current_avg = (sum(current_month_scores) / len(current_month_scores)) if current_month_scores else None
        previous_avg = (sum(previous_month_scores) / len(previous_month_scores)) if previous_month_scores else None
        improvement = round(current_avg - previous_avg, 1) if current_avg is not None and previous_avg is not None else 0

        grade_rows.append({
            'grade': grade,
            'total_students': total_students,
            'completed': completed_count,
            'in_progress': in_progress_count,
            'not_started': not_started,
            'completion_pct': completion_pct,
            'reading_score': reading_avg,
            'speech_score': speech_avg,
            'average_score': average,
            'improvement': improvement,
        })

    grade_rows.sort(key=lambda row: _grade_sort_key(row['grade']))
    top_grades = sorted(grade_rows, key=lambda row: row['average_score'], reverse=True)[:3]
    intervention_grades = [row for row in grade_rows if row['average_score'] and row['average_score'] < 75]

    total_assessments = len(assessment_rows)
    total_students = students_qs.count()
    total_teachers = teachers_qs.count()
    completed_assessments = status_counts['completed']
    completion_rate = _pct(completed_assessments, total_assessments)

    all_scores = _clean_numeric_scores([row.get('avg_score') for row in assessment_rows])
    all_scores = [score for score in all_scores if score > 0]
    average_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0

    notifications_feed = []
    if user:
        for notif in Notification.objects.filter(recipient=user).order_by('-created_at')[:8]:
            notifications_feed.append({
                'title': notif.title,
                'message': notif.message,
                'created_at': notif.created_at,
                'variant': notif.notification_type,
                'is_read': notif.is_read,
            })

    recent_activity = sorted((notifications_feed + latest_activity), key=lambda item: item['created_at'], reverse=True)[:8]

    report_rows = [
        {
            'report_name': f"Assessment Summary - {row['title']}",
            'report_type': 'Assessment',
            'generated_date': row['updated_at'],
            'generated_by': row['teacher_name'],
            'completion_rate': row['completion_rate'],
            'avg_score': row['avg_score'],
        }
        for row in assessment_rows[:10]
    ]

    type_cards = []
    for type_key, bucket in type_stats.items():
        avg = round(bucket['score_sum'] / bucket['score_count'], 1) if bucket['score_count'] else 0
        type_cards.append({
            'label': type_key.title(),
            'total': bucket['total'],
            'completed': bucket['completed'],
            'avg_score': avg,
        })
    type_cards.sort(key=lambda item: item['label'])

    return {
        'school_name': school_name,
        'school_logo': school_info.get('logo') if isinstance(school_info, dict) else '',
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_sections': sections.count(),
        'total_assessments': total_assessments,
        'completed_assessments': completed_assessments,
        'in_progress_assessments': status_counts['in_progress'],
        'pending_assessments': status_counts['pending'],
        'completion_rate': completion_rate,
        'average_score': average_score,
        'grade_rows': grade_rows,
        'top_grades': top_grades,
        'intervention_grades': intervention_grades,
        'assessment_rows': assessment_rows,
        'assessment_attempt_rows': assessment_attempt_rows,
        'assessment_type_cards': type_cards,
        'recent_activity': recent_activity,
        'report_rows': report_rows,
    }


def _principal_report_preview_rows(analytics, report_type='school', grade_filter=''):
    normalized_report_type = (report_type or 'school').strip().lower()

    if normalized_report_type == 'grade':
        rows = analytics.get('grade_rows', [])
        if grade_filter:
            rows = [row for row in rows if row.get('grade') == grade_filter]
        headers = ['Grade', 'Students', 'Completed', 'In Progress', 'Not Started', 'Completion %', 'Average Score']
        values = [
            [
                row.get('grade'),
                row.get('total_students'),
                row.get('completed'),
                row.get('in_progress'),
                row.get('not_started'),
                f"{row.get('completion_pct', 0)}%",
                f"{row.get('average_score', 0)}%",
            ]
            for row in rows
        ]
        return headers, values

    if normalized_report_type == 'assessment':
        rows = analytics.get('assessment_rows', [])
        headers = ['Assessment', 'Type', 'Status', 'Participants', 'Completion %', 'Average Score']
        values = [
            [
                row.get('title'),
                row.get('assessment_type'),
                row.get('status'),
                row.get('participants'),
                f"{row.get('completion_rate', 0)}%",
                f"{row.get('avg_score', 0)}%",
            ]
            for row in rows
        ]
        return headers, values

    grade_rows = analytics.get('grade_rows', []) or []
    top_grade = ''
    struggling_grade = ''
    if grade_rows:
        sorted_grades = sorted(grade_rows, key=lambda row: row.get('average_score', 0), reverse=True)
        top_grade = next((row.get('grade') for row in sorted_grades if row.get('grade')), '')
        struggling_grade = next((row.get('grade') for row in grade_rows if row.get('average_score') and row.get('average_score') < 75), '')

    headers = ['Metric', 'Value']
    values = [
        ['School Name', analytics.get('school_name')],
        ['Total Students', analytics.get('total_students')],
        ['Total Teachers', analytics.get('total_teachers')],
        ['Active Sections', analytics.get('total_sections')],
        ['Total Assessments', analytics.get('total_assessments')],
        ['Completed Assessments', analytics.get('completed_assessments')],
        ['In Progress Assessments', analytics.get('in_progress_assessments')],
        ['Pending Assessments', analytics.get('pending_assessments')],
        ['Overall Completion Rate', f"{analytics.get('completion_rate', 0)}%"],
        ['Average Reading Score', f"{analytics.get('average_score', 0)}%"],
        ['Top Performing Grade', top_grade or 'N/A'],
        ['Struggling Grade', struggling_grade or 'N/A'],
    ]
    return headers, values


def _principal_report_csv_response(report_type, headers, rows):
    filename = f"principal_{report_type}_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response


def _principal_report_logo_path(analytics):
    logo_value = (analytics or {}).get('school_logo') or ''
    if logo_value.startswith('pabasa_app/'):
        candidate = settings.BASE_DIR / 'pabasa_app' / 'static' / logo_value
        if candidate.exists():
            return candidate
    return settings.BASE_DIR / 'pabasa_app' / 'static' / 'pabasa_app' / 'images' / 'pabasalogo.png'


def _principal_report_pdf_response(request, analytics, report_type, grade_filter, headers, rows):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas
        from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        logger.exception("ReportLab is not installed")
        return HttpResponse(f"PDF export is unavailable: {exc}", status=500)

    def _estimate_column_widths(headers, rows, available_width):
        if not headers:
            return []
        sample_rows = [list(headers)] + [list(row) for row in rows]
        column_texts = []
        for idx in range(len(headers)):
            values = [str(item[idx]) if len(item) > idx else '' for item in sample_rows]
            max_len = max(len(value) for value in values) if values else 0
            column_texts.append(max_len)

        min_width = 0.9 * inch
        max_width = 2.2 * inch
        widths = []
        for length in column_texts:
            estimated = max(min_width, min(max_width, length * 4.5))
            widths.append(estimated)

        total_width = sum(widths)
        if total_width > available_width:
            scale = available_width / total_width
            widths = [max(min_width, width * scale) for width in widths]
            total_width = sum(widths)
            if total_width > available_width:
                widths[-1] = max(min_width, widths[-1] - (total_width - available_width))

        return widths

    def _format_percentage(value):
        try:
            return f"{float(value):.1f}%"
        except (TypeError, ValueError):
            return str(value or '0%')

    def _format_count(value):
        try:
            return f"{int(float(value))}"
        except (TypeError, ValueError):
            return str(value or '0')

    def _status_style(status):
        normalized = str(status or '').strip().lower()
        if normalized in {'completed', 'done', 'finished'}:
            return '#2e7d32', '#e8f5e9', 'Completed'
        if normalized in {'in progress', 'in-progress', 'ongoing'}:
            return '#f9a825', '#fff8e1', 'In Progress'
        return '#c62828', '#ffebee', 'Pending'

    def _build_card(title, value, subtitle, accent, icon):
        card = Table(
            [[
                Paragraph(f"<font color='{accent}' size='13'><b>{icon}</b></font>", card_icon_style),
            ], [
                Paragraph(f"<font size='16' color='{accent}'><b>{value}</b></font>", card_value_style),
            ], [
                Paragraph(f"<b>{title}</b>", card_title_style),
            ], [
                Paragraph(subtitle, card_subtitle_style),
            ]],
            colWidths=[card_width],
            repeatRows=0,
        )
        card.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fcfcfc')),
            ('LINEABOVE', (0, 0), (-1, 0), 0.8, colors.HexColor(accent)),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#ececec')),
        ]))
        return card

    buffer = BytesIO()
    left_margin = 0.8 * inch
    right_margin = 0.8 * inch
    top_margin = 0.8 * inch
    bottom_margin = 0.8 * inch
    page_size = A4
    available_width = page_size[0] - left_margin - right_margin
    card_width = (available_width - 0.2 * inch) / 2.0

    preview_headers = [str(header) for header in headers]
    preview_rows = [[str(value) for value in row] for row in rows]
    column_widths = _estimate_column_widths(preview_headers, preview_rows, available_width)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#8B3E2F'),
        spaceAfter=4,
        fontName='Helvetica-Bold',
    )
    subtitle_style = ParagraphStyle(
        'ReportSubtitle',
        parent=styles['BodyText'],
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#4b5563'),
        spaceAfter=4,
    )
    section_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=13,
        leading=15,
        textColor=colors.HexColor('#8B3E2F'),
        spaceAfter=6,
        fontName='Helvetica-Bold',
    )
    table_font_size = 8.6 if len(preview_headers) >= 5 else 9.0
    body_style = ParagraphStyle(
        'ReportBody',
        parent=styles['BodyText'],
        fontSize=table_font_size,
        leading=table_font_size + 1.2,
        textColor=colors.HexColor('#111827'),
        allowWidows=1,
        allowOrphans=1,
    )
    card_title_style = ParagraphStyle(
        'CardTitle',
        parent=styles['BodyText'],
        fontSize=9.5,
        leading=11,
        textColor=colors.HexColor('#374151'),
        spaceAfter=1,
        fontName='Helvetica-Bold',
    )
    card_value_style = ParagraphStyle(
        'CardValue',
        parent=styles['BodyText'],
        fontSize=15,
        leading=16,
        textColor=colors.HexColor('#111827'),
        spaceAfter=2,
        fontName='Helvetica-Bold',
    )
    card_icon_style = ParagraphStyle(
        'CardIcon',
        parent=styles['BodyText'],
        fontSize=12,
        leading=13,
        textColor=colors.HexColor('#8B3E2F'),
        spaceAfter=2,
    )
    card_subtitle_style = ParagraphStyle(
        'CardSubtitle',
        parent=styles['BodyText'],
        fontSize=8.4,
        leading=10,
        textColor=colors.HexColor('#6b7280'),
        spaceAfter=2,
    )
    meta_style = ParagraphStyle(
        'Meta',
        parent=styles['BodyText'],
        fontSize=8.6,
        leading=10,
        textColor=colors.HexColor('#6b7280'),
        spaceAfter=2,
    )

    report_label = {
        'school': 'School Performance',
        'grade': 'Grade-Level',
        'assessment': 'Assessment',
    }.get(report_type, 'School Performance')

    local_now = timezone.localtime(timezone.now(), timezone.get_default_timezone())
    generated_at = local_now.strftime('%B %d, %Y %I:%M %p')
    report_title = 'PABASA Principal Report'
    school_name = analytics.get('school_name') or 'Salawag Elementary School'

    elements = []
    logo_path = _principal_report_logo_path(analytics)
    header_table = Table(
        [[
            Image(str(logo_path), width=0.7 * inch, height=0.7 * inch) if logo_path.exists() else Paragraph('<b>PABASA</b>', styles['Heading3']),
            Paragraph(f"<b>{report_title}</b>", title_style),
        ], [
            '',
            Paragraph(school_name, subtitle_style),
        ], [
            '',
            Paragraph(f"Report Type: {report_label}", subtitle_style),
        ], [
            '',
            Paragraph(f"Date Generated: {generated_at}", subtitle_style),
        ]],
        colWidths=[0.95 * inch, available_width - 0.95 * inch],
        repeatRows=0,
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.extend([header_table, Spacer(1, 0.12 * inch), HRFlowable(width=available_width, thickness=0.5, color=colors.HexColor('#8B3E2F')), Spacer(1, 0.16 * inch)])

    if grade_filter:
        elements.append(Paragraph(f'Grade Level: {grade_filter}', subtitle_style))
        elements.append(Spacer(1, 0.06 * inch))

    elements.append(Paragraph('Summary Overview', section_style))
    elements.append(Spacer(1, 0.06 * inch))

    if report_type == 'grade':
        grade_rows = analytics.get('grade_rows', []) or []
        filtered_grade_rows = [row for row in grade_rows if row.get('grade') == grade_filter] if grade_filter else grade_rows
        selected_grade_label = grade_filter or 'All Grades'
        total_students = sum(int(row.get('total_students', 0) or 0) for row in filtered_grade_rows)
        completed = sum(int(row.get('completed', 0) or 0) for row in filtered_grade_rows)
        in_progress = sum(int(row.get('in_progress', 0) or 0) for row in filtered_grade_rows)
        not_started = sum(int(row.get('not_started', 0) or 0) for row in filtered_grade_rows)
        completion_rate = _pct(completed, total_students) if total_students else 0
        avg_score = round(sum(float(row.get('average_score', 0) or 0) for row in filtered_grade_rows) / len(filtered_grade_rows), 1) if filtered_grade_rows else 0
        summary_cards = [
            _build_card('Focused Grade', selected_grade_label, 'Selected performance scope', '#8B3E2F', '◉'),
            _build_card('Students', _format_count(total_students), 'Students in scope', '#4CAF50', '◌'),
            _build_card('Completed', _format_count(completed), 'Finished work', '#4A90E2', '◍'),
            _build_card('In Progress', _format_count(in_progress), 'Still active', '#FFC107', '↺'),
            _build_card('Not Started', _format_count(not_started), 'Pending participation', '#E53935', '•'),
            _build_card('Completion Rate', _format_percentage(completion_rate), 'Grade-level progress', '#8B3E2F', '%'),
            _build_card('Average Score', _format_percentage(avg_score), 'Reading mastery', '#4CAF50', '★'),
        ]
    elif report_type == 'assessment':
        assessment_rows = analytics.get('assessment_rows', []) or []
        completed_count = sum(1 for row in assessment_rows if str(row.get('status') or '').lower() == 'completed')
        in_progress_count = sum(1 for row in assessment_rows if str(row.get('status') or '').lower() == 'in progress')
        pending_count = sum(1 for row in assessment_rows if str(row.get('status') or '').lower() == 'pending')
        avg_score = round(sum(float(row.get('avg_score', 0) or 0) for row in assessment_rows) / len(assessment_rows), 1) if assessment_rows else 0
        summary_cards = [
            _build_card('Assessments', _format_count(len(assessment_rows)), 'Available assessment tasks', '#8B3E2F', '◉'),
            _build_card('Completed', _format_count(completed_count), 'Tasks finished', '#4CAF50', '◌'),
            _build_card('In Progress', _format_count(in_progress_count), 'Currently active', '#4A90E2', '◍'),
            _build_card('Pending', _format_count(pending_count), 'Awaiting action', '#E53935', '•'),
            _build_card('Completion Rate', _format_percentage(analytics.get('completion_rate', 0)), 'School-wide completion', '#8B3E2F', '%'),
            _build_card('Average Score', _format_percentage(avg_score), 'Assessment mastery', '#4CAF50', '★'),
        ]
    else:
        summary_cards = [
            _build_card('Total Students', _format_count(analytics.get('total_students', 0)), 'Enrollment overview', '#8B3E2F', '◉'),
            _build_card('Total Teachers', _format_count(analytics.get('total_teachers', 0)), 'Active school staff', '#4CAF50', '◌'),
            _build_card('Total Assessments', _format_count(analytics.get('total_assessments', 0)), 'Assigned reading tasks', '#4A90E2', '◍'),
            _build_card('Completed', _format_count(analytics.get('completed_assessments', 0)), 'Finished assessments', '#2e7d32', '✓'),
            _build_card('In Progress', _format_count(analytics.get('in_progress_assessments', 0)), 'Currently active', '#FFC107', '↺'),
            _build_card('Pending', _format_count(analytics.get('pending_assessments', 0)), 'Awaiting action', '#E53935', '•'),
            _build_card('Completion Rate', _format_percentage(analytics.get('completion_rate', 0)), 'Overall progress', '#8B3E2F', '%'),
            _build_card('Average Score', _format_percentage(analytics.get('average_score', 0)), 'Reading mastery', '#4CAF50', '★'),
        ]
    summary_rows = [summary_cards[i:i + 2] for i in range(0, len(summary_cards), 2)]
    summary_grid = Table(summary_rows, colWidths=[card_width, card_width], repeatRows=0)
    summary_grid.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('SPACING', (0, 0), (-1, -1), 4),
    ]))
    elements.extend([summary_grid, Spacer(1, 0.12 * inch)])

    if report_type == 'grade':
        progress_label = 'Grade-Level Snapshot'
        progress_detail = f"Selected Focus: {grade_filter or 'All Grades'}   Completion Rate: {_format_percentage(analytics.get('completion_rate', 0))}"
    elif report_type == 'assessment':
        progress_label = 'Assessment Snapshot'
        progress_detail = f"Completed: {_format_count(analytics.get('completed_assessments', 0))}   In Progress: {_format_count(analytics.get('in_progress_assessments', 0))}   Pending: {_format_count(analytics.get('pending_assessments', 0))}"
    else:
        progress_label = 'School Snapshot'
        progress_detail = f"Overall Completion: {_format_percentage(analytics.get('completion_rate', 0))}   Average Score: {_format_percentage(analytics.get('average_score', 0))}"

    progress_summary = Table([
        [Paragraph(progress_label, card_title_style)],
        [Paragraph(progress_detail, meta_style)],
    ], colWidths=[available_width], repeatRows=0)
    progress_summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f8f8')),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.extend([progress_summary, Spacer(1, 0.12 * inch)])

    elements.append(Paragraph('Detailed Report', section_style))
    elements.append(Spacer(1, 0.06 * inch))

    table_rows = [[Paragraph(str(value), body_style) for value in headers]]
    for row in rows:
        styled_row = []
        for idx, value in enumerate(row):
            cell_text = str(value)
            if headers and str(headers[idx]).strip().lower() == 'status':
                status_color, _, status_label = _status_style(value)
                cell_text = f"<font color='{status_color}'><b>{status_label}</b></font>"
            styled_row.append(Paragraph(cell_text, body_style))
        table_rows.append(styled_row)

    data_table = Table(table_rows, repeatRows=1, splitByRow=0, colWidths=column_widths)
    data_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8B3E2F')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#d1d5db')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#fcfcfc'), colors.HexColor('#f8f8f8')]),
        ('FONTSIZE', (0, 0), (-1, -1), table_font_size),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
    ]))
    elements.append(data_table)

    def _draw_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(colors.HexColor('#6b7280'))
        canvas_obj.drawString(left_margin, 0.38 * inch, 'PABASA Automated Reading Assessment System')
        canvas_obj.drawCentredString(page_size[0] / 2.0, 0.38 * inch, f'Page {canvas_obj.getPageNumber()}')
        canvas_obj.drawRightString(page_size[0] - right_margin, 0.38 * inch, f'Confidential School Report • Generated {generated_at}')
        canvas_obj.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
    )
    doc.build(elements, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    buffer.seek(0)

    filename = f"principal_{report_type}_report_{local_now.strftime('%Y%m%d_%H%M%S')}.pdf"
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


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
    user = User.objects.filter(id=request.session.get('user_id')).first()
    analytics = _principal_analytics(user)

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
        **analytics,
    })
    return render(request, 'pabasa_app/principal_dashboard.html', context)

@principal_required
def principal_performance(request):
    """Principal Performance Page - Grade performance, completion rates, and trends"""
    context = _principal_context(request, 'Performance')
    user = User.objects.filter(id=request.session.get('user_id')).first()
    analytics = _principal_analytics(user)
    grade_rows = analytics.get('grade_rows', [])
    current_month_performance = round(sum([row['average_score'] for row in grade_rows if row['average_score']]) / max(len([row for row in grade_rows if row['average_score']]), 1), 1) if grade_rows else 0
    context.update({
        **analytics,
        'current_month_performance': current_month_performance,
        'ytd_progress': analytics.get('completion_rate', 0),
    })
    return render(request, 'pabasa_app/principal_performance.html', context)

@principal_required
def principal_assessments(request):
    """Principal Assessments Page - Assessment overview and results"""
    context = _principal_context(request, 'Assessments')
    user = User.objects.filter(id=request.session.get('user_id')).first()
    analytics = _principal_analytics(user)
    context.update({
        **analytics,
        'in_progress': analytics.get('in_progress_assessments', 0),
        'completed': analytics.get('completed_assessments', 0),
        'pending': analytics.get('pending_assessments', 0),
    })
    return render(request, 'pabasa_app/principal_assessments.html', context)

@principal_required
def principal_reports(request):
    """Principal Reports Page - Generate and view reports"""
    context = _principal_context(request, 'Reports')
    user = User.objects.filter(id=request.session.get('user_id')).first()
    analytics = _principal_analytics(user)

    report_type_labels = {
        'school': 'School Performance',
        'grade': 'Grade-Level',
        'assessment': 'Assessment',
    }

    selected_report_type = (request.GET.get('report_type') or 'school').strip().lower()
    selected_grade = (request.GET.get('grade_level') or '').strip()
    if selected_report_type != 'grade':
        selected_grade = ''
    export_type = (request.GET.get('export') or '').strip().lower()
    headers, rows = _principal_report_preview_rows(analytics, selected_report_type, selected_grade)
    selected_report_label = f"{report_type_labels.get(selected_report_type, 'School Performance')} Report"
    selected_report_summary = 'School-wide participation, completion rate, and performance trends across the campus.'

    if selected_report_type == 'grade':
        if selected_grade:
            selected_report_label = f'{report_type_labels.get(selected_report_type, "School Performance")} Report - {selected_grade}'
            selected_report_summary = f'Grade-level performance data focused on {selected_grade}.'
        else:
            selected_report_summary = 'Grade-level comparison across all available grade levels.'
    elif selected_report_type == 'assessment':
        selected_report_summary = 'Assessment-specific results, completion status, and student performance by task.'

    if export_type == 'csv' or export_type == 'excel':
        return _principal_report_csv_response(selected_report_type, headers, rows)

    if export_type == 'pdf':
        return _principal_report_pdf_response(request, analytics, selected_report_type, selected_grade, headers, rows)

    context.update({
        **analytics,
        'report_types': [
            {'value': 'school', 'label': 'School Performance'},
            {'value': 'grade', 'label': 'Grade-Level'},
            {'value': 'assessment', 'label': 'Assessment'},
        ],
        'selected_report_type': selected_report_type,
        'selected_grade': selected_grade,
        'selected_report_label': selected_report_label,
        'report_preview_summary': selected_report_summary,
        'report_preview_count': len(rows),
        'report_preview_headers': headers,
        'report_preview_rows': rows,
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
        'name': getattr(user, 'school', '') or '',
        'code': '',
        'municipality': '',
        'province': '',
        'district': '',
        'region': '',
        'address': '',
        'contact': getattr(user, 'contact_no', '') or '',
        'email': getattr(user, 'email', '') or '',
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
                'name': request.POST.get('school_name', '').strip(),
                'code': request.POST.get('school_code', '').strip(),
                'municipality': request.POST.get('municipality', '').strip(),
                'province': request.POST.get('province', '').strip(),
                'district': request.POST.get('district', '').strip(),
                'region': request.POST.get('region', '').strip(),
                'address': request.POST.get('address', '').strip(),
                'contact': request.POST.get('contact', '').strip(),
                'email': request.POST.get('email', '').strip(),
                'logo': school_info.get('logo', ''),
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
