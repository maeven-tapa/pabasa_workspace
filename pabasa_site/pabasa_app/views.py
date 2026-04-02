from django.shortcuts import render

def home(request):
    return render(request, 'pabasa_app/home.html')

def auth(request):
    return render(request, 'pabasa_app/auth.html')

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

def logout(request):
    return render(request, 'pabasa_app/logout.html')
