from django.shortcuts import render

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
    return render(request, 'pabasa_app/dashboard.html')

def courses(request):
    return render(request, 'pabasa_app/courses.html')

def course_teacher_view(request):
    return render(request, 'pabasa_app/course_tecaher_view.html')

def students(request):
    return render(request, 'pabasa_app/students.html')

def calendar(request):
    return render(request, 'pabasa_app/calendar.html')

def settings(request):
    return render(request, 'pabasa_app/settings.html')

def practice(request):
    return render(request, 'pabasa_app/practice.html')

def profile(request):
    return render(request, 'pabasa_app/profile.html')

def notifications(request):
    return render(request, 'pabasa_app/notifications.html')
