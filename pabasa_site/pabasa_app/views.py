from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
import os
from pathlib import Path

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
    return render(request, 'pabasa_app/dashboard.html', {'nav_role': 'student'})

def dashboard_teacher(request):
    return render(request, 'pabasa_app/dashboard_teacher.html', {'nav_role': 'teacher'})

def courses(request):
    return render(request, 'pabasa_app/courses.html', {'nav_role': 'teacher'})

def assessment(request):
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
