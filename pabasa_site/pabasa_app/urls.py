from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('auth/', views.auth, name='auth'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('forgot-password/otp/', views.forgot_password_otp, name='forgot_password_otp'),
    path('signup/', views.signup, name='signup'),
    path('signup/teacher/', views.teacher_signup, name='teacher_signup'),
    path('signup/student/', views.student_signup, name='student_signup'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/courses/', views.courses, name='courses'),
    path('dashboard/assessment/', views.assessment, name='assessment'),
    path('dashboard/assessment/reading_ui/word/', views.reading_word_page, name='reading_word_page'),
    path('dashboard/assessment/reading_ui/sentence/', views.reading_sentence_page, name='reading_sentence_page'),
    path('dashboard/assessment/reading_ui/para/', views.reading_para_page, name='reading_para_page'),
    path('dashboard/courses/teacher-view/', views.course_teacher_view, name='course_teacher_view'),
    path('dashboard/courses/student-view/', views.course_student_view, name='course_student_view'),
    path('dashboard/students/', views.students, name='students'),
    path('dashboard/students/detail/', views.student_detail, name='student_detail'),
    path('dashboard/calendar/', views.calendar, name='calendar'),
    path('dashboard/settings/', views.settings, name='settings'),
    path('dashboard/practice/', views.practice, name='practice'),
    path('dashboard/profile/', views.profile, name='profile'),
    path('dashboard/notifications/', views.notifications, name='notifications'),
    path('what-is-pabasa/', views.pabasa_info, name='pabasa_info'),
    path('about/', views.about, name='about'),
]