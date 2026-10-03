"""Real school-year, term and finalized CRLA fixtures for prescribed tests."""

from datetime import datetime, time, timedelta
from uuid import uuid4

from django.utils import timezone

from .models import Assessment, CalendarEvent, Enrollment, Material, SchoolCalendar, Section, User


PHASES = {1: ('pretest', 'bosy_crla_pretest'), 2: ('midtest', 'midline_crla_midtest'), 3: ('posttest', 'eosy_crla_posttest')}


def prescribed_term_fixture(student, *, teacher=None, section=None, term=1, calendar=None,
                            today=None, classification='Developing Reader', completed=True,
                            start=None, end=None):
    today = today or timezone.localdate()
    school = student.school_record
    token = uuid4().hex[:10]
    if calendar is None:
        start_year = today.year if today.month >= 6 else today.year - 1
        school_year = f'{start_year}-{start_year + 1}'
        calendar = SchoolCalendar.objects.create(school_year=school_year, current_term=term, is_active=True)
    if teacher is None:
        teacher = User.objects.create(
            custom_id=f'PFT-{token}', role='teacher', first_name='Fixture', last_name='Teacher',
            sex='female', birth_month=1, birth_day=1, birth_year=1990,
            email=f'pft-{token}@example.test', password_hash='x', school_record=school,
        )
    if section is None:
        section = Section.objects.create(
            school=school, school_calendar=calendar, teacher=teacher, class_code=f'PFS-{token}',
            class_name='Prescribed Fixture', subject='Filipino', grade_level='Grade 2',
            section=f'Fixture-{token}',
        )
    elif section.school_calendar_id != calendar.id:
        section.school_calendar = calendar
        section.save(update_fields=['school_calendar'])
    enrollment = Enrollment.objects.filter(student=student, section=section).first()
    if not enrollment:
        enrollment = Enrollment.objects.create(student=student, section=section, school=school, school_calendar=calendar)
    elif enrollment.school_calendar_id != calendar.id:
        enrollment.school_calendar = calendar
        enrollment.save(update_fields=['school_calendar', 'updated_at'])
    student.school_calendar = calendar
    student.save(update_fields=['school_calendar', 'updated_at'])
    CalendarEvent.objects.create(
        school_calendar=calendar, term=term, title='Opening Block', event_type='school_opening',
        start_date=start or today - timedelta(days=7), end_date=start or today - timedelta(days=7),
    )
    CalendarEvent.objects.create(
        school_calendar=calendar, term=term, title='Closing Block', event_type='school_closing',
        start_date=end or today + timedelta(days=7), end_date=end or today + timedelta(days=7),
    )
    result = None
    if completed:
        phase, key = PHASES[term]
        material = Material.objects.filter(system_assessment_key=key).first()
        if material is None:
            material = Material.objects.create(
                teacher=teacher, title=f'Official CRLA {token}', code=f'PFC-M-{token}',
                type='assessment', item_type='word', status='published', assessment_kind='crla',
                is_official_reading=True, is_system_owned=True,
                system_assessment_key=key, system_assessment_phase=phase, official_term=term,
            )
        result = Assessment.objects.create(
            teacher=teacher, student=student, enrollment=enrollment, material=material,
            title=f'Official CRLA result {token}', code=f'PFC-R-{token}', assessment_type='word',
            attempt_status='completed',
            completed_at=timezone.make_aware(datetime.combine(today, time(12, 0))),
            system_assessment_key=key, system_assessment_phase=phase, official_term=term,
            crla_classification=classification,
        )
    return calendar, section, enrollment, result
