from django.db import migrations, models


def backfill_attempt_terms(apps, schema_editor):
    Assessment = apps.get_model('pabasa_app', 'Assessment')
    CalendarEvent = apps.get_model('pabasa_app', 'CalendarEvent')
    Material = apps.get_model('pabasa_app', 'Material')

    # Seeded system materials describe a stage, not a term. They are reused in
    # every configured term, so remove the legacy pre=1/mid=2/post=3 mapping.
    Material.objects.filter(is_system_owned=True, is_official_reading=True).update(official_term=None)

    attempts = Assessment.objects.filter(
        student__isnull=False,
        attempt_status='completed',
        completed_at__isnull=False,
    ).filter(
        models.Q(is_system_owned=True)
        | models.Q(material__is_official_reading=True)
        | models.Q(source_assessment__is_system_owned=True)
    )
    for attempt in attempts.iterator():
        completed_date = attempt.completed_at.date()
        phase = str(attempt.system_assessment_phase or '').strip().lower()
        event_types = {
            'pretest': ('pre_assessment',),
            'midtest': ('midline_assessment',),
            'posttest': ('post_assessment',),
        }.get(phase, ('pre_assessment', 'midline_assessment', 'post_assessment'))
        event = CalendarEvent.objects.filter(
            start_date__lte=completed_date,
            end_date__gte=completed_date,
            event_type__in=event_types,
            school_calendar__is_active=True,
        ).order_by('-school_calendar__updated_at', 'term', 'id').first()
        if event:
            Assessment.objects.filter(pk=attempt.pk).update(official_term=event.term)


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0067_backfill_official_crla_terms')]

    operations = [
        migrations.AddField(
            model_name='assessment',
            name='official_term',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_attempt_terms, migrations.RunPython.noop),
    ]
