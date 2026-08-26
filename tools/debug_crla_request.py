import os
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')

import django
django.setup()

from django.test import Client
from pabasa_app.models import User, Section, SchoolCalendar, CalendarEvent, Material
from pabasa_app.views import (
    _official_crla_assessment_phase,
    _official_crla_material_keys_for_student,
)


def ensure_calendar():
    calendar = SchoolCalendar.objects.filter(school_year='2026-2027').first()
    if not calendar:
        calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=1, is_active=True)
    events = {
        'start_of_classes': (date(2026, 6, 1), date(2026, 6, 1)),
        'end_of_classes': (date(2027, 5, 31), date(2027, 5, 31)),
        'school_opening': (date(2026, 8, 1), date(2026, 8, 31)),
        'school_closing': (date(2026, 8, 31), date(2026, 8, 31)),
        'pre_assessment': (date(2026, 8, 1), date(2026, 8, 7)),
        'post_assessment': (date(2026, 8, 8), date(2026, 8, 15)),
    }
    for event_type, (start, end) in events.items():
        CalendarEvent.objects.update_or_create(
            school_calendar=calendar,
            term=1,
            event_type=event_type,
            defaults={
                'title': event_type,
                'start_date': start,
                'end_date': end,
            },
        )
    return calendar


def ensure_student_and_section():
    student = User.objects.filter(custom_id='DEBUG-STUDENT').first()
    if not student:
        student = User.objects.create(
            custom_id='DEBUG-STUDENT',
            role='student',
            first_name='Debug',
            last_name='Student',
            sex='female',
            birth_month=1,
            birth_day=1,
            birth_year=2012,
            email='debug.student@example.com',
            password_hash='pbkdf2_sha256$260000$dummy',
            preference={'reading_assessment_state': {'reader_classification': 'Low Emerging Readers', 'aral_eligible': True}},
        )
    teacher = User.objects.filter(custom_id='DEBUG-TEACHER').first()
    if not teacher:
        teacher = User.objects.create(
            custom_id='DEBUG-TEACHER',
            role='teacher',
            first_name='Debug',
            last_name='Teacher',
            sex='female',
            birth_month=1,
            birth_day=1,
            birth_year=1990,
            email='debug.teacher@example.com',
            password_hash='pbkdf2_sha256$260000$dummy',
        )
    section = Section.objects.filter(class_code='DEBUG-CLASS').first()
    if not section:
        school = teacher.school_record
        if school is None:
            raise ValueError("Debug setup requires teacher.school_record before creating a Section")
        section = Section.objects.create(
            school=school,
            teacher=teacher,
            class_name='Debug Class',
            class_code='DEBUG-CLASS',
            subject='Reading',
            is_active=True,
        )
    section.add_student(student)
    return student, section


def ensure_eosy_material():
    material = Material.objects.filter(system_assessment_key='eosy_crla_posttest').first()
    if not material:
        material = Material.objects.create(
            title='End of School Year (EoSY) CRLA Post-Test',
            item_type='paragraph',
            content_text='debug',
            content_json={'assessment_key': 'eosy_crla_posttest', 'language': 'Filipino', 'items': []},
            assessment_kind='crla',
            assessment_set='crla',
            type='assessment',
            status='published',
            student_access=True,
            section=None,
            teacher=None,
            is_active=True,
            is_official_reading=True,
            is_system_owned=True,
            system_assessment_key='eosy_crla_posttest',
            system_assessment_period='eosy',
            system_assessment_phase='posttest',
        )
    return material


def main():
    ensure_calendar()
    student, section = ensure_student_and_section()
    material = ensure_eosy_material()

    client = Client()
    session = client.session
    session['user_id'] = student.id
    session['user_role'] = 'student'
    session.save()

    check_date = date(2026, 8, 8)
    phase = _official_crla_assessment_phase(student, on_date=check_date)
    official_keys = _official_crla_material_keys_for_student(student, on_date=check_date)
    print('request_user:', student.id, student.role, student.custom_id)
    print('is_requesting_student:', student.role == 'student')
    print('phase:', phase)
    print('official_keys:', official_keys)

    qs = Material.objects.filter(
        is_active=True,
        is_official_reading=True,
        is_system_owned=True,
        system_assessment_key__in=official_keys,
    ).exclude(status__iexact='archived')
    print('official_materials_qs count:', qs.count())
    for row in qs.values('id', 'title', 'system_assessment_key', 'is_active', 'is_official_reading', 'is_system_owned', 'status'):
        print(row)

    response = client.get('/api/class/materials/', {'class_code': section.class_code})
    print('response status:', response.status_code)
    try:
        print('response json:', response.json())
    except Exception as exc:
        print('response text:', response.content)
        raise


if __name__ == '__main__':
    main()
