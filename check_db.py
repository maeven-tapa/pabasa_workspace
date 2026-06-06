import os
import sys
import django

# Add the project directory to the Python path
sys.path.insert(0, r'C:\Users\iamdo\Documents\GitHub\pabasa_workspace\pabasa_site')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
django.setup()

from pabasa_app.models import ReadingClass, TeacherProfile, User

print("=== All Reading Classes ===")
classes = ReadingClass.objects.all()
for cls in classes:
    print(f"Code: {cls.class_code}, Name: {cls.class_name}, Teacher: {cls.teacher}")

print("\n=== All Teachers ===")
teachers = TeacherProfile.objects.all()
for teacher in teachers:
    print(f"Code: {teacher.teacher_code}, User: {teacher.user.username if teacher.user else 'N/A'}")
    classes = ReadingClass.objects.filter(teacher=teacher)
    print(f"  Classes: {classes.count()}")

print("\n=== All Users ===")
users = User.objects.all()
for user in users:
    print(f"Username: {user.custom_id}, Email: {user.email}, Role: {user.role}")
