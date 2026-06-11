import os
import sys
import django

# Add the project directory to the Python path
sys.path.insert(0, r'c:\Users\Amiel\OneDrive\Documents\GitHub\pabasa_workspace\pabasa_site')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
django.setup()

from pabasa_app.models import Section, User, Assessment

print("=== All Sections (Classes) ===")
sections = Section.objects.all()
for section in sections:
    print(f"Code: {section.class_code}, Name: {section.class_name}, Teacher: {section.teacher.custom_id if section.teacher else 'N/A'}")

print("\n=== All Teachers ===")
teachers = User.objects.filter(role='teacher')
for teacher in teachers:
    print(f"ID: {teacher.custom_id}, Name: {teacher.first_name} {teacher.last_name}, Email: {teacher.email}")
    sections = Section.objects.filter(teacher=teacher)
    print(f"  Sections: {sections.count()}")

print("\n=== All Users ===")
users = User.objects.all()
for user in users:
    print(f"Username: {user.custom_id}, Email: {user.email}, Role: {user.role}")
