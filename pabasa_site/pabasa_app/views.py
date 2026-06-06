from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth import authenticate, login
from django.db import IntegrityError
from functools import wraps
import os
from pathlib import Path
import uuid
from .models import User, TeacherProfile, StudentProfile

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
        
        # Create user
        custom_id = generate_custom_id('teacher')
        user = User.objects.create(
            custom_id=custom_id,
            role='teacher',
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            email=data.get('email'),
            sex=data.get('sex'),
            birth_month=int(data.get('birth_month', 0)),
            birth_day=int(data.get('birth_day', 0)),
            birth_year=int(data.get('birth_year', 0)),
            password_hash=make_password(data.get('password')),
            contact_no=data.get('contact_no', '')
        )
        
        # Create teacher profile
        teacher_code = f"TCH-{user.id:04d}"
        TeacherProfile.objects.create(
            user=user,
            teacher_code=teacher_code,
            teacher_role=data.get('teacher_role', ''),
            school=data.get('school', ''),
            department=data.get('department', '')
        )
        
        return JsonResponse({
            'success': True, 
            'message': 'Teacher registered successfully',
            'custom_id': custom_id
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
        
        # Create user
        custom_id = generate_custom_id('student')
        user = User.objects.create(
            custom_id=custom_id,
            role='student',
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            email=data.get('email'),
            sex=data.get('sex'),
            birth_month=int(data.get('birth_month', 0)),
            birth_day=int(data.get('birth_day', 0)),
            birth_year=int(data.get('birth_year', 0)),
            password_hash=make_password(data.get('password')),
            contact_no=data.get('contact_no', '')
        )
        
        # Create student profile
        student_code = f"G2-{user.id:04d}"
        StudentProfile.objects.create(
            user=user,
            student_code=student_code,
            grade_level=data.get('grade_level', ''),
            section=data.get('section', ''),
            reading_level=data.get('reading_level', ''),
            parent_contact_no=data.get('parent_contact_no', '')
        )
        
        return JsonResponse({
            'success': True, 
            'message': 'Student registered successfully',
            'custom_id': custom_id
        })
    
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
        
        # Create session
        request.session['user_id'] = user.id
        request.session['custom_id'] = user.custom_id
        request.session['user_role'] = user.role
        request.session['first_name'] = user.first_name
        request.session['last_name'] = user.last_name
        request.session['email'] = user.email
        
        # Determine redirect URL based on role
        redirect_url = '/dashboard/teacher/' if user.role == 'teacher' else '/dashboard/'
        
        return JsonResponse({
            'success': True,
            'message': 'Login successful',
            'role': user.role,
            'redirect_url': redirect_url,
            'custom_id': user.custom_id
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
    
    user_data = {
        'nav_role': 'student',
        'user_id': request.session.get('custom_id'),
        'first_name': request.session.get('first_name'),
        'last_name': request.session.get('last_name'),
        'email': request.session.get('email')
    }
    return render(request, 'pabasa_app/dashboard.html', user_data)

def dashboard_teacher(request):
    if not _check_auth(request):
        return redirect('auth')
    if request.session.get('user_role') != 'teacher':
        return redirect('auth')
    
    user_data = {
        'nav_role': 'teacher',
        'user_id': request.session.get('custom_id'),
        'first_name': request.session.get('first_name'),
        'last_name': request.session.get('last_name'),
        'email': request.session.get('email')
    }
    return render(request, 'pabasa_app/dashboard_teacher.html', user_data)

def courses(request):
    if not _check_auth(request):
        return redirect('auth')
    return render(request, 'pabasa_app/courses.html', {'nav_role': 'teacher'})

def assessment(request):
    if not _check_auth(request):
        return redirect('auth')
    return render(request, 'pabasa_app/assessment.html', {'nav_role': 'student'})

def reading_word_page(request):
    return render(request, 'pabasa_app/reading_word_page.html')

def reading_sentence_page(request):
    return render(request, 'pabasa_app/reading_sentence_page.html')

def reading_para_page(request):
    return render(request, 'pabasa_app/reading_para_page.html')

def practice_word_page(request):
    return render(request, 'pabasa_app/practice_word_page.html')

def practice_sentence_page(request):
    return render(request, 'pabasa_app/practice_sentence_page.html')

def practice_para_page(request):
    return render(request, 'pabasa_app/practice_para_page.html')

def course_teacher_view(request):
    return render(request, 'pabasa_app/course_tecaher_view.html', {'nav_role': 'teacher'})

def course_student_view(request):
    return render(request, 'pabasa_app/course_student_view.html')

def students(request):
    return render(request, 'pabasa_app/students.html', {'nav_role': 'teacher'})

def student_detail(request):
    return render(request, 'pabasa_app/student_detail.html')

def calendar(request):
    return render(request, 'pabasa_app/calendar.html')

def settings(request):
    nav_role = request.GET.get('role', 'student')
    return render(request, 'pabasa_app/settings.html', {'nav_role': nav_role})

def practice(request):
    return render(request, 'pabasa_app/practice.html', {'nav_role': 'student'})

@csrf_protect
@require_http_methods(["GET", "POST"])
def profile(request):
    nav_role = request.GET.get('role', 'student')
    username = request.user.username if request.user.is_authenticated else 'user'
    
    # Check if user has a profile photo
    profile_photo_url = None
    photos_dir = Path('pabasa_site/pabasa_app/static/pabasa_app/uploads/profiles')
    if photos_dir.exists():
        for file in photos_dir.glob(f'student_photo_{username}.*'):
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
                    photos_dir = Path('pabasa_site/pabasa_app/static/pabasa_app/uploads/profiles')
                    photos_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Save the file with a unique name (e.g., student_photo_maeventapa.jpg)
                    filename = f"student_photo_{username}.{file_ext}"
                    filepath = photos_dir / filename
                    
                    # Delete any previous photos with different extensions
                    for file in photos_dir.glob(f'student_photo_{username}.*'):
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
                    photos_dir = Path('pabasa_site/pabasa_app/static/pabasa_app/uploads/profiles')
                    
                    # Find and delete any profile photo for this user
                    if photos_dir.exists():
                        for file in photos_dir.glob(f'student_photo_{username}.*'):
                            file.unlink()
                    
                    return JsonResponse({'success': True, 'message': 'Photo removed successfully'})
                
                except Exception as e:
                    return JsonResponse({'success': False, 'error': str(e)})
    
    return render(request, 'pabasa_app/profile.html', {'nav_role': nav_role, 'profile_photo_url': profile_photo_url, 'username': username})

def notifications(request):
    nav_role = request.GET.get('role', 'teacher')
    return render(request, 'pabasa_app/notifications.html', {'nav_role': nav_role})
