"""Principal report rows and paginated PDFs from the same monitoring snapshot."""
from html import escape
from io import BytesIO

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
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, LongTable, TableStyle, Image, KeepTogether

    wide = len(headers) > 6
    page = landscape(A4) if wide else A4
    margin = 40
    width = page[0] - 2 * margin
    output = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='PrincipalCell', fontName='Helvetica', fontSize=8, leading=11, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='PrincipalHead', parent=styles['PrincipalCell'], textColor=colors.white, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='PrincipalTitle', parent=styles['Heading1'], textColor=colors.HexColor('#8B3E2F'), fontSize=20, leading=24))

    def paragraph(value, style='PrincipalCell'):
        return Paragraph(escape(str(value)).replace('\n', '<br/>'), styles[style])

    label = REPORT_TYPES[report_type]
    generated = timezone.localtime(snapshot['snapshot_at']).strftime('%B %d, %Y %I:%M %p')
    elements = []
    title = paragraph('PABASA Principal Report', 'PrincipalTitle')
    if logo_path and logo_path.exists():
        elements.append(Table([[Image(str(logo_path), width=42, height=42), title]], colWidths=[54, width - 54]))
    else:
        elements.append(title)
    elements.extend([paragraph(snapshot['school_name']), paragraph(f'Report Type: {label}'), paragraph(f'Date Generated: {generated}'), Spacer(1, 10)])
    calendar = snapshot['scope_calendar']
    elements.append(paragraph(f"Grade 2 | School Year: {calendar.school_year if calendar else 'Legacy / unassigned'} | Term: {snapshot['scope_term'] or 'All'} | Period: {snapshot['scope_phase'] or 'All'}"))
    elements.append(paragraph(snapshot['metric_definition']))
    elements.append(Spacer(1, 10))
    cards = [
        ('Enrolled students', str(snapshot['total_students'])), ('Assigned Teachers', str(snapshot['total_teachers'])),
        ('Official CRLA coverage', display(snapshot['completion_rate'], '%')), ('Latest official reading accuracy', display(snapshot['average_score'], '%')),
    ]
    card_table = Table([[paragraph(title), paragraph(value)] for title, value in cards], colWidths=[width * .65, width * .35])
    card_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FCFF')),
                                   ('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#d7e5ef')),
                                   ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
    elements.extend([KeepTogether([paragraph('Summary Overview', 'Heading2'), card_table]), Spacer(1, 12)])
    elements.append(paragraph('Detailed Report', 'Heading2'))
    data = [[paragraph(header, 'PrincipalHead') for header in headers]]
    data.extend([[paragraph(value) for value in row] for row in rows])
    if not rows:
        data.append([paragraph('No records in the selected scope.')] + [paragraph('') for _ in headers[1:]])
    weights = [min(50, max(12, len(str(header)))) for header in headers]
    # Sampling affects column widths only; all rows are exported without truncation.
    for row in rows[:100]:
        for index, value in enumerate(row):
            weights[index] = max(weights[index], min(60, len(str(value))))
    total = sum(weights)
    widths = [width * weight / total for weight in weights]
    table = LongTable(data, colWidths=widths, repeatRows=1, splitByRow=1, splitInRow=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8B3E2F')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f8f8')]),
        ('GRID', (0, 0), (-1, -1), .35, colors.HexColor('#d1d5db')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    if not rows:
        table.setStyle(TableStyle([('SPAN', (0, 1), (-1, 1))]))
    elements.append(table)

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.HexColor('#4b5563'))
        canvas.drawString(margin, 22, 'PABASA - Confidential School Report')
        canvas.drawRightString(page[0] - margin, 22, f'Page {document.page}')
        canvas.restoreState()

    SimpleDocTemplate(output, pagesize=page, leftMargin=margin, rightMargin=margin,
                      topMargin=36, bottomMargin=40).build(elements, onFirstPage=footer, onLaterPages=footer)
    content = output.getvalue()
    response = HttpResponse(content, content_type='application/pdf')
    stamp = timezone.localtime(snapshot['snapshot_at']).strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="principal_{report_type}_report_{stamp}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
