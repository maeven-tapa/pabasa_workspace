from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth import authenticate, login
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.db import IntegrityError
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
from .models import User, Section, Enrollment, Assessment, Material, Note, Notification

# Compatibility aliases: some code still expects TeacherProfile/StudentProfile names
TeacherProfile = User
StudentProfile = User

# Utilities for profile-like data now stored on `User.tags` (JSONField)
def _get_profile_dict(user, key):
    if not user:
        return {}
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
    user.save()
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.db.models import Max, Count


logger = logging.getLogger(__name__)

PROFILE_PHOTOS_DIR = settings.BASE_DIR / 'pabasa_app' / 'static' / 'pabasa_app' / 'uploads' / 'profiles'

# Authentication decorator
def login_required(role=None):
    """Decorator to check if user is authenticated and optionally check role"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if 'user_id' not in request.session:
                return redirect('auth')
            if role and request.session.get('user_role') != role:
                return redirect('auth')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

# Authentication functions
def generate_custom_id(role):
    """Generate unique custom ID based on role"""
    if role == 'teacher':
        prefix = 'TCH'
    else:  # student
        prefix = 'G2'
    
    # Get the count of existing users with this role
    count = User.objects.filter(role=role).count() + 1
    return f"{prefix}-{count:04d}"

def generate_otp(length=6):
    return ''.join(random.choice('0123456789') for _ in range(length))

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

def _store_pending_teacher_signup(request, data):
    otp = generate_otp()
    request.session['pending_teacher_signup'] = {
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
    }
    request.session['pending_teacher_signup_otp'] = otp
    request.session['pending_teacher_signup_otp_created'] = time.time()
    request.session.modified = True
    return otp

# REPLACE
def _store_pending_student_signup(request, data):
    otp = generate_otp()
    request.session['pending_student_signup'] = {
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
        'parent_contact_no': data.get('parent_contact_no', ''),
    }
    request.session['pending_student_signup_otp'] = otp
    request.session['pending_student_signup_otp_created'] = time.time()
    request.session.modified = True
    return otp

def _clear_pending_teacher_signup(request):
    request.session.pop('pending_teacher_signup', None)
    request.session.pop('pending_teacher_signup_otp', None)
    request.session.pop('pending_teacher_signup_otp_created', None)
    request.session.modified = True

def _clear_pending_student_signup(request):
    request.session.pop('pending_student_signup', None)
    request.session.pop('pending_student_signup_otp', None)
    request.session.pop('pending_student_signup_otp_created', None)
    request.session.modified = True

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
    otp = generate_otp()
    request.session['pending_password_reset'] = {
        'email': email,
    }
    request.session['pending_password_reset_otp'] = otp
    request.session['pending_password_reset_otp_created'] = time.time()
    request.session.modified = True
    return otp


def _clear_pending_password_reset(request):
    request.session.pop('pending_password_reset', None)
    request.session.pop('pending_password_reset_otp', None)
    request.session.pop('pending_password_reset_otp_created', None)
    request.session.pop('password_reset_verified', None)
    request.session.pop('password_reset_email', None)
    request.session.modified = True


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
            contact_no=pending['contact_no']
        )

        # store teacher profile data inside User.tags for compatibility
        _set_profile_dict(user, 'teacher_profile', {
            'teacher_code': custom_id,
            'teacher_role': pending.get('teacher_role', ''),
            'school': pending.get('school', ''),
            'department': pending.get('department', ''),
            'is_active': True,
        })

        teacher_code = custom_id

        send_teacher_confirmation_email(request, user, custom_id)
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
            contact_no=pending.get('contact_no', '')
        )

        # store student profile data inside User.tags for compatibility
        _set_profile_dict(user, 'student_profile', {
            'student_code': custom_id,
            'grade_level': pending.get('grade_level', ''),
            'section': pending.get('section', ''),
            'reading_level': pending.get('reading_level', ''),
            'parent_contact_no': pending.get('parent_contact_no', ''),
            'is_active': True,
        })

        send_student_confirmation_email(request, user)
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

        # Verify account activity status using profile dict stored on User.tags
        if user.role == 'teacher':
            tp = _get_profile_dict(user, 'teacher_profile')
            if tp.get('is_active') is False:
                return JsonResponse({'success': False, 'error': 'This account is deactivated'}, status=403)
        elif user.role == 'student':
            sp = _get_profile_dict(user, 'student_profile')
            if sp.get('is_active') is False:
                return JsonResponse({'success': False, 'error': 'This account is deactivated'}, status=403)

        # Create session
        request.session['user_id'] = user.id
        request.session['custom_id'] = user.custom_id
        request.session['user_role'] = user.role
        request.session['first_name'] = user.first_name
        request.session['last_name'] = user.last_name
        request.session['email'] = user.email
        
        redirect_url = '/dashboard/teacher/' if user.role == 'teacher' else '/dashboard/'
        
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
    first_name = request.session.get('first_name', '')
    last_name = request.session.get('last_name', '')
    user = User.objects.filter(id=request.session.get('user_id')).first()
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
            tp_dict = _get_profile_dict(user, 'teacher_profile')
            teacher_role = tp_dict.get('teacher_role', '')

        username = f"{user.first_name}_{user.last_name}".lower().replace(" ", "_")
        if PROFILE_PHOTOS_DIR.exists():
            for file in PROFILE_PHOTOS_DIR.glob(f'profile_photo_{username}.*'):
                profile_photo_url = f'/static/pabasa_app/uploads/profiles/{file.name}'
                break

    joined_classes = []
    if user and user.role == 'student':
        student_user = user
        sp_dict = _get_profile_dict(student_user, 'student_profile')
        enrollments = Enrollment.objects.filter(student=student_user, is_active=True)
        for enrollment in enrollments:
            cls = enrollment.section
            student_count = Enrollment.objects.filter(section=cls, is_active=True).count()
            joined_classes.append({
                    'code': cls.class_code,
                    'name': cls.class_name,
                    'student_count': student_count,
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
                # Check for classes, materials, enrollments
                has_classes = Section.objects.filter(teacher=tp_user, is_active=True).exists()
                has_materials = Assessment.objects.filter(teacher=tp_user, is_active=True).exists()
                has_enrollments = Enrollment.objects.filter(section__teacher=tp_user, is_active=True).exists()
                has_attempts = Assessment.objects.filter(teacher=tp_user).exists()
                has_activity = has_classes or has_materials or has_enrollments or has_attempts

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
                enr_max = Enrollment.objects.filter(section__teacher=tp_user).aggregate(m=Max('joined_at'))['m']
                if enr_max:
                    candidate_dates.append(enr_max)

                if candidate_dates:
                    last_activity = max(candidate_dates)

            else:
                # For students, use student user updated or enrollment timestamps
                sp_user = user
                if sp_user:
                    has_activity = True
                    candidate_dates = [d for d in [getattr(sp_user, 'updated_at', None), getattr(sp_user, 'created_at', None)] if d]
                    enr_max = Enrollment.objects.filter(student=sp_user, is_active=True).aggregate(m=Max('joined_at'))['m']
                    if enr_max:
                        candidate_dates.append(enr_max)
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

def courses(request):
    if not _check_auth(request):
        return redirect('auth')
    return render(request, 'pabasa_app/courses.html', _dashboard_context(request, 'teacher'))

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

def practice_word_page(request):
    return render(request, 'pabasa_app/practice_word_page.html', _dashboard_context(request))

def practice_sentence_page(request):
    return render(request, 'pabasa_app/practice_sentence_page.html', _dashboard_context(request))

def practice_para_page(request):
    return render(request, 'pabasa_app/practice_para_page.html', _dashboard_context(request))

# REPLACE the entire course_teacher_view function:
def course_teacher_view(request):
    if not _check_auth(request):
        return redirect('auth')
    if request.session.get('user_role') != 'teacher':
        return redirect('auth')
    return render(request, 'pabasa_app/course_tecaher_view.html', _dashboard_context(request, 'teacher'))

def course_student_view(request):
    return render(request, 'pabasa_app/course_student_view.html', _dashboard_context(request))

def students(request):
    return render(request, 'pabasa_app/students.html', _dashboard_context(request, 'teacher'))

def student_detail(request):
    return render(request, 'pabasa_app/student_detail.html')

def calendar(request):
    return render(request, 'pabasa_app/calendar.html', _dashboard_context(request))

def settings_view(request):
    nav_role = request.GET.get('role', 'student')
    return render(request, 'pabasa_app/settings.html', _dashboard_context(request, nav_role))

def practice(request):
    return render(request, 'pabasa_app/practice.html', _dashboard_context(request, 'student'))

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
    teacher_profile = None
    student_profile = None

    if user.role == "teacher":
        teacher_profile = TeacherProfile.objects.filter(user=user).first()
        if teacher_profile:
            pabasa_id = teacher_profile.teacher_code
            role_display = f"Teacher - {teacher_profile.teacher_role}" if teacher_profile.teacher_role else "Teacher"
    else:
        student_profile = StudentProfile.objects.filter(user=user).first()
        if student_profile:
            pabasa_id = student_profile.student_code
            role_display = f"Student - {student_profile.grade_level}" if student_profile.grade_level else "Student"

    initials = "".join(part[:1] for part in full_name.split()[:2]).upper() or "PA"
    
    # Check if user has a profile photo
    profile_photo_url = None
    photos_dir = PROFILE_PHOTOS_DIR
    if photos_dir.exists():
        for file in photos_dir.glob(f'profile_photo_{username}.*'):
            profile_photo_url = f'/static/pabasa_app/uploads/profiles/{file.name}'
            break
    
    if request.method == 'POST':
        # Handle AJAX requests for photo upload/removal
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Handle photo upload
            if 'profile_photo' in request.FILES:
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
                    return JsonResponse({'success': True, 'message': 'Photo uploaded successfully', 'photo_url': photo_url})
                
                except Exception as e:
                    return JsonResponse({'success': False, 'error': str(e)})
            
            # Handle photo removal
            elif request.POST.get('remove_photo') == 'true':
                try:
                    photos_dir = PROFILE_PHOTOS_DIR
                    
                    # Find and delete any profile photo for this user
                    if photos_dir.exists():
                        for file in photos_dir.glob(f'profile_photo_{username}.*'):
                            file.unlink()
                    
                    return JsonResponse({'success': True, 'message': 'Photo removed successfully'})
                
                except Exception as e:
                    return JsonResponse({'success': False, 'error': str(e)})

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
                return JsonResponse({'success': True, 'message': 'Password changed successfully'})

            elif request.POST.get('deactivate_account') == 'true':
                if user.role == "teacher":
                    TeacherProfile.objects.filter(user=user).update(is_active=False)
                else:
                    StudentProfile.objects.filter(user=user).update(is_active=False)
                request.session.flush()
                return JsonResponse({'success': True, 'redirect_url': reverse('auth')})

            elif request.POST.get('delete_account') == 'true':
                try:
                    if photos_dir.exists():
                        for file in photos_dir.glob(f'profile_photo_{username}.*'):
                            file.unlink()
                    user.delete()
                    request.session.flush()
                    return JsonResponse({'success': True, 'redirect_url': reverse('home')})
                except Exception as e:
                    return JsonResponse({'success': False, 'error': str(e)})
    
    return render(request, 'pabasa_app/profile.html', {
        'nav_role': nav_role,
        'profile_photo_url': profile_photo_url,
        'username': username,
        'full_name': full_name,
        'first_name': user.first_name,
        'middle_name': user.middle_initial,
        'last_name': user.last_name,
        'suffix': user.suffix,
        'email': user.email,
        'pabasa_id': pabasa_id,
        'role_display': role_display,
        'initials': initials,
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
    Allows a student to join a class by creating a ClassEnrollment record.
    Expects a JSON payload with 'class_code'.
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

        section = Section.objects.filter(class_code=class_code, is_active=True).first()

        if not section:
            return JsonResponse({'success': False, 'error': 'Invalid class code.'}, status=404)

        if Enrollment.objects.filter(student=student_user, section=section, is_active=True).exists():
            return JsonResponse({'success': False, 'error': 'You have already joined this class.'}, status=409)

        Enrollment.objects.create(student=student_user, section=section, is_active=True)

        return JsonResponse({'success': True, 'message': f'Successfully joined class {class_code}'})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload'}, status=400)
    except Exception as e:
        logger.error(f"Error joining class: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'An unexpected error occurred'}, status=500)


@csrf_protect
@require_http_methods(["POST"])
@login_required(role='student')
def unenroll_class(request):
    """Student unenroll endpoint: deactivates the ClassEnrollment and notifies the teacher."""
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

        enrollment = Enrollment.objects.filter(student=student_user, section=section, is_active=True).first()
        if not enrollment:
            return JsonResponse({'success': False, 'error': 'Enrollment not found'}, status=404)

        with transaction.atomic():
            enrollment.is_active = False
            enrollment.save()

            # Create an in-app notification for the teacher
            teacher_user = section.teacher
            title = 'Student unenrolled'
            message = f"{student_user.first_name} {student_user.last_name} has unenrolled from your class {section.class_name}."
            Notification.objects.create(
                recipient=teacher_user,
                created_by=student_user,
                title=title,
                message=message,
                notification_type='info'
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
        grade_level = data.get('grade_level', '').strip()
        section = data.get('section', '').strip()

        if not grade_level:
            return JsonResponse({'success': False, 'error': 'Grade level is required'}, status=400)

        if not section:
            return JsonResponse({'success': False, 'error': 'Section is required'}, status=400)

        if not class_name:
            return JsonResponse({'success': False, 'error': 'Class name is required'}, status=400)

        # Retrieve the teacher user for the logged-in user
        user_id = request.session.get('user_id')
        teacher_user = User.objects.filter(id=user_id).first()
        if not teacher_user or teacher_user.role != 'teacher':
            return JsonResponse({'success': False, 'error': 'Teacher not found'}, status=404)

        unique_code = generate_unique_class_code()

        new_class = Section.objects.create(
            teacher=teacher_user,
            class_code=unique_code,
            class_name=class_name,
            grade_level=grade_level,
            section=section,
            header=header,
            description=description,
            subject=data.get('subject', '').strip(),
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

@require_http_methods(["GET"])
@login_required(role='teacher')
def get_teacher_classes(request):

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
        student_count = Enrollment.objects.filter(
            section=cls, is_active=True
        ).count()
        class_list.append({
            'code': cls.class_code,
            'name': cls.class_name,
            'subject': cls.subject,
            'grade_level': cls.grade_level,
            'section': cls.section,
            'description': cls.description,
            'header': cls.header,
            'students': str(student_count),
            'teacher_email': request.session.get('email', ''),
        })

    return JsonResponse({'success': True, 'classes': class_list})


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
        total_students = Enrollment.objects.filter(section__teacher=teacher_user, is_active=True).count()
        materials_posted = Assessment.objects.filter(teacher=teacher_user, is_active=True).count()
        reports_generated = Note.objects.filter(teacher=teacher_user).count()

        return JsonResponse({
            'success': True,
            'classes_count': classes_count,
            'total_students': total_students,
            'materials_posted': materials_posted,
            'reports_generated': reports_generated,
        })
    except Exception as e:
        logger.error('Error computing teacher overview: %s', e, exc_info=True)
        return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)

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
        affected_enrollments = list(Enrollment.objects.filter(section=section, is_active=True).select_related('student'))
        affected_students = [en.student for en in affected_enrollments]

        with transaction.atomic():
            section.is_active = False
            section.save()

            # Deactivate enrollments
            Enrollment.objects.filter(section=section, is_active=True).update(is_active=False)

            # Deactivate assessments tied to this section
            Assessment.objects.filter(section=section, is_active=True).update(is_active=False)

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
                        notification_type='warning'
                    )

                    # Best-effort email to student
                    try:
                        subject = f"Class removed: {section.class_name}"
                        send_mail(subject, message, getattr(settings, 'DEFAULT_FROM_EMAIL', None), [student_user.email], fail_silently=True)
                    except Exception:
                        logger.exception('Failed to send class-deleted email to student %s', student_user.email)
                except Exception:
                    logger.exception('Failed to notify a student for class deletion')

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
def add_reading_material(request):
    """
    Creates a new reading material (Assessment) linked to a class.
    Expects JSON: { title, reading_type, content, status, class_code, scheduled_at? }
    """
    try:
        data = json.loads(request.body)
        title        = data.get('title', '').strip()
        reading_type = data.get('reading_type', '').strip()   # word | sentence | paragraph
        content      = data.get('content', '').strip()
        status       = data.get('status', '').strip()          # published | draft | scheduled
        class_code   = data.get('class_code', '').strip()
        scheduled_at = data.get('scheduled_at', '').strip()

        # ── server-side validation ──────────────────────────────────────────
        errors = {}
        if not title:
            errors['title'] = 'Material title is required.'
        if reading_type not in ('word', 'sentence', 'paragraph'):
            errors['reading_type'] = 'Reading type is required.'
        if not content:
            errors['content'] = 'Material content is required.'
        if status not in ('published', 'draft', 'scheduled'):
            errors['status'] = 'Status is required.'
        if status == 'scheduled' and not scheduled_at:
            errors['scheduled_at'] = 'Scheduled date & time is required.'

        if errors:
            return JsonResponse({'success': False, 'errors': errors}, status=400)

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

        # ── generate unique assessment code ─────────────────────────────────
        import uuid as _uuid
        assessment_code = f"MAT-{reading_type[:3].upper()}-{_uuid.uuid4().hex[:6].upper()}"
        while Assessment.objects.filter(code=assessment_code).exists():
            assessment_code = f"MAT-{reading_type[:3].upper()}-{_uuid.uuid4().hex[:6].upper()}"

        assessment = Assessment.objects.create(
            title=title,
            code=assessment_code,
            assessment_type=reading_type,
            teacher=teacher_user,
            section=section,
            is_active=(status == 'published'),
        )

        return JsonResponse({
            'success': True,
            'message': 'Reading material created successfully.',
            'code': assessment_code,
            'title': title,
            'status': status,
            'scheduled_at': scheduled_at if status == 'scheduled' else None,
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload.'}, status=400)
    except Exception as e:
        logger.error(f"add_reading_material error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Internal server error.'}, status=500)

@csrf_protect
@require_http_methods(["POST"])
@login_required(role='student')
def record_assessment_completion(request):
    """Handles notification when student completes reading material."""
    try:
        data = json.loads(request.body)
        assessment_id = data.get('assessment_id')
        student_user = User.objects.get(id=request.session.get('user_id'))
        assessment = Assessment.objects.select_related('teacher').get(id=assessment_id)
        teacher_user = assessment.teacher

        notif_msg = f"{student_user.first_name} {student_user.last_name} completed {assessment.title}"
        Notification.objects.create(
            recipient=teacher_user,
            created_by=student_user,
            title="Reading Material Completed",
            message=notif_msg,
            notification_type="assessment",
            action_url=f"/dashboard/teacher/students/detail/?student_id={student_user.custom_id}"
        )
        send_mail(
            "Reading Material Completed", notif_msg,
            settings.DEFAULT_FROM_EMAIL, [teacher_user.email],
            fail_silently=True
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