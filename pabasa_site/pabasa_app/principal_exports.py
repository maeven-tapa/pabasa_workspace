"""Principal report rows and paginated PDFs from the same monitoring snapshot."""
from django.http import HttpResponse
from django.utils import timezone


REPORT_TYPES = {'school': 'School Performance', 'grade': 'Grade-Level', 'assessment': 'Assessment',
                'classifications': 'CRLA Classifications', 'sections': 'Section Implementation', 'intervention': 'Intervention Follow-up'}


def display(value, suffix=''):
    return 'N/A' if value is None else f'{value}{suffix}'


def report_rows(snapshot, report_type='school', grade_filter='Grade 2'):
    if report_type == 'grade':
        rows = snapshot['grade_rows'] if grade_filter in ('', 'Grade 2') else []
        return ['Grade', 'Enrolled', 'Official CRLA completed', 'Result missing', 'Coverage %', 'Reading accuracy %', 'Samples'], [
            [row['grade'], row['total_students'], row['completed'], row['total_students'] - row['completed'],
             display(row['completion_pct']), display(row['reading_score']), row['reading_samples']] for row in rows]
    if report_type == 'assessment':
        return ['Assessment', 'Type', 'Status', 'Completed / Expected', 'Completion %', 'Average raw points', 'Record category'], [
            [r['title'], r['assessment_type'], r['status'], f"{r['completed_students']} / {r['expected_students']}",
             display(r['completion_rate']), display(r['avg_score']), r['category']] for r in snapshot['assessment_rows']]
    if report_type == 'classifications':
        return ['Official reading profile', 'Learners', '% of enrolled cohort'], [
            [row['label'], row['count'], row['percentage']] for row in snapshot['classification_rows']
        ] + [['No finalized official result', snapshot['missing_official_students'],
              round(100 - snapshot['completion_rate'], 1) if snapshot['total_students'] else 0]]
    if report_type == 'sections':
        return ['Section', 'Teacher', 'Enrolled', 'Official completed', 'Coverage %', 'ARAL eligible', 'Review / Follow-up'], [
            [r['name'], r['teacher'], r['total_students'], r['completed'], r['completion_pct'], r.get('eligible', 0),
             f"{r.get('pending_review', 0)} / {r.get('follow_up', 0)}"] for r in snapshot['section_rows']]
    if report_type == 'intervention':
        return ['Learner', 'Section', 'Teacher', 'Follow-up reason'], [
            [r['name'], r['section'], r['teacher'], r['reason']] for r in snapshot.get('follow_up_rows', [])]
    return ['Metric', 'Value'], [
        ['School Name', snapshot['school_name']],
        ['School Year', snapshot['scope_calendar'].school_year if snapshot['scope_calendar'] else 'Legacy / unassigned year'],
        ['Term', snapshot['scope_term'] or 'All'], ['Assessment period', snapshot['scope_phase'] or 'All'],
        ['Enrolled Grade 2 students', snapshot['total_students']], ['Assigned active Teachers', snapshot['total_teachers']],
        ['Active Sections', snapshot['total_sections']], ['Assessment tasks represented', snapshot['total_assessments']],
        ['Official CRLA learners completed', snapshot['official_completed_students']],
        ['Official CRLA coverage', display(snapshot['completion_rate'], '%')],
        ['Latest official reading accuracy', display(snapshot['average_score'], '%')], ['Accuracy samples', snapshot['accuracy_samples']],
        ['ARAL eligible by official profile', snapshot.get('aral_eligible_students', 0)],
        ['ARAL learners with recorded progress', snapshot.get('aral_progress_students', 0)],
        ['Recorded intervention exits', snapshot.get('aral_recorded_exits', 0)],
        ['Learners pending review', snapshot.get('pending_review_students', 0)],
        ['Recorded prescribed completed activities', snapshot.get('prescribed_counts', {}).get('completed', 0)],
        ['Supplementary assignments', snapshot.get('supplementary_counts', {}).get('assigned', 0)],
        ['Supplementary completed assignments', snapshot.get('supplementary_counts', {}).get('completed', 0)],
    ]


def pdf_response(snapshot, report_type, headers, rows, logo_path=None):
    from .principal_report_pdf import build_principal_pdf

    content = build_principal_pdf(snapshot, report_type, headers, rows, logo_path)
    response = HttpResponse(content, content_type='application/pdf')
    stamp = timezone.localtime(snapshot['snapshot_at']).strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="principal_{report_type}_report_{stamp}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
