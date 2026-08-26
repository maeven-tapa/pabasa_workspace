import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
django.setup()

from pabasa_app.models import User, Section, SchoolCalendar, CalendarEvent
from pabasa_app.views import (
    _active_school_calendar,
    _calendar_current_term,
    _calendar_is_in_preassessment_window,
    _calendar_is_in_postassessment_window,
    _official_crla_assessment_phase,
    _official_assessment_availability_for_student,
    _official_crla_material_for_student,
    _assessment_workflow_context,
    assessment,
)

student = User.objects.filter(custom_id='TRACE-STU').first()
if not student:
    teacher = User.objects.create(
        custom_id='TRACE-TEA',
        role='teacher',
        first_name='Trace',
        last_name='Teacher',
        sex='female',
        birth_month=1,
        birth_day=1,
        birth_year=1990,
        email='trace-teacher@example.com',
        password_hash='pbkdf2_sha256$260000$dummy',
    )
    student = User.objects.create(
        custom_id='TRACE-STU',
        role='student',
        first_name='Trace',
        last_name='Student',
        sex='male',
        birth_month=1,
        birth_day=1,
        birth_year=2012,
        email='trace-student@example.com',
        password_hash='pbkdf2_sha256$260000$dummy',
    )
    school = teacher.school_record
    if school is None:
        raise ValueError("Trace setup requires teacher.school_record before creating a Section")
    section = Section.objects.create(
        school=school,
        teacher=teacher,
        class_name='Trace Class',
        class_code='TRACE-100',
        subject='Reading',
        is_active=True,
    )
    section.add_student(student)

calendar = SchoolCalendar.objects.filter(school_year='2026-2027').first()
if not calendar:
    calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=1, is_active=True)
    CalendarEvent.objects.create(school_calendar=calendar, term=1, title='Start', event_type='start_of_classes', start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))
    CalendarEvent.objects.create(school_calendar=calendar, term=1, title='End', event_type='end_of_classes', start_date=date(2027, 5, 31), end_date=date(2027, 5, 31))
    CalendarEvent.objects.create(school_calendar=calendar, term=1, title='Opening', event_type='school_opening', start_date=date(2026, 8, 1), end_date=date(2026, 8, 31))
    CalendarEvent.objects.create(school_calendar=calendar, term=1, title='Closing', event_type='school_closing', start_date=date(2026, 8, 31), end_date=date(2026, 8, 31))
    CalendarEvent.objects.create(school_calendar=calendar, term=1, title='Pre', event_type='pre_assessment', start_date=date(2026, 8, 1), end_date=date(2026, 8, 7))
    CalendarEvent.objects.create(school_calendar=calendar, term=1, title='Post', event_type='post_assessment', start_date=date(2026, 8, 8), end_date=date(2026, 8, 15))

check_date = date(2026, 8, 8)
active = _active_school_calendar(check_date)
current_term = _calendar_current_term(active) if active else None
pre_window = _calendar_is_in_preassessment_window(active, current_term, on_date=check_date) if active and current_term else None
post_window = _calendar_is_in_postassessment_window(active, current_term, on_date=check_date) if active and current_term else None
phase = _official_crla_assessment_phase(student, on_date=check_date)
availability = _official_assessment_availability_for_student(student, request=None)
material = _official_crla_material_for_student(student, availability.get('assessment_type'))
workflow = _assessment_workflow_context(student)

print('calendar_school_year=', active.school_year if active else None)
print('current_term=', current_term)
print('pre_window=', pre_window)
print('post_window=', post_window)
print('phase_resolver=', phase)
print('availability=', availability)
print('material_key=', getattr(material, 'system_assessment_key', None))
print('workflow_active_phase=', workflow.get('active_phase'))
print('workflow_stage=', workflow.get('stage'))
