import json
from pabasa_site.settings import BASE_DIR
from django import setup
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
setup()
from pabasa_app.models import Course, User

u = User.objects.filter(role='teacher').first()
print('teacher', getattr(u, 'id', None), getattr(u, 'first_name', None), getattr(u, 'last_name', None))
courses = Course.objects.select_related('teacher').prefetch_related('materials__assessment', 'materials__section', 'materials__assigned_sections__teacher')
print('courses', courses.count())
for c in courses:
    shared = 0
    total = 0
    shared_materials = []
    for m in c.materials.all():
        total += 1
        owner_id = None
        owner_name = None
        if getattr(m, 'assessment', None) and getattr(m.assessment, 'teacher_id', None):
            owner_id = m.assessment.teacher_id
            owner_name = f'{m.assessment.teacher.first_name} {m.assessment.teacher.last_name}'
        elif getattr(m, 'section', None) and getattr(m.section, 'teacher_id', None):
            owner_id = m.section.teacher_id
            owner_name = f'{m.section.teacher.first_name} {m.section.teacher.last_name}'
        else:
            sec = m.assigned_sections.filter(is_active=True).select_related('teacher').first()
            if sec and getattr(sec, 'teacher_id', None):
                owner_id = sec.teacher_id
                owner_name = f'{sec.teacher.first_name} {sec.teacher.last_name}'
        if owner_id and owner_id != c.teacher_id:
            shared += 1
            shared_materials.append((m.id, m.title, owner_id, owner_name))
    if shared > 0:
        print('course', c.id, c.code, 'teacher', c.teacher_id, 'materials', total, 'shared', shared)
        for sid, title, oid, oname in shared_materials:
            print('  shared', sid, title, 'owner', oid, oname)
