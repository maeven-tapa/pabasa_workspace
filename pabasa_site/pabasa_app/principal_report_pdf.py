"""Principal PDF presentation. No queries, cohort selection or academic scoring.

School metrics are laid out from the exact export rows; other report types keep
every supplied column and row. Bars only visualize existing percentage values.
"""
from io import BytesIO
import math
from pathlib import Path
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate, CondPageBreak, Flowable, Frame, LongTable,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

# Share the established parent report's brand tokens and font registration only.
# The parent renderer and its layout are unchanged.
from .reading_report_pdf import (
    AMBER, ASSETS, BLUE, INK, LINE, MUTED, NAVY, PALE_AMBER, PALE_BLUE, SKY,
    WHITE, _fonts,
)

TEAL = colors.HexColor('#087C83')
PALE_TEAL = colors.HexColor('#EAF6F4')


def _text(value):
    return escape('N/A' if value is None else str(value)).replace('\n', '<br/>')


def _percentage(value):
    """Reject missing, non-finite and out-of-range values; never infer a score."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and 0 <= number <= 100 else None


def _value(value, percent=False):
    return 'N/A' if value is None else f'{value}{"%" if percent else ""}'


class _LabelSlot(Flowable):
    """Align metric baselines across cards whose labels wrap differently."""
    def __init__(self, paragraph, height):
        super().__init__()
        self.paragraph, self.height = paragraph, height

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        self.text_height = self.paragraph.wrap(avail_width, avail_height)[1]
        return self.width, self.height

    def draw(self):
        self.paragraph.drawOn(self.canv, 0, self.height - self.text_height)


class _Panel(Flowable):
    """A dynamically sized, indivisible card with wrapped text."""
    def __init__(self, width, content, *, fill=PALE_BLUE, accent=BLUE, minimum=0,
                 percentage=None, padding=15):
        super().__init__()
        self.width, self.content = width, content
        self.fill, self.accent, self.minimum = fill, accent, minimum
        self.percentage, self.padding = _percentage(percentage), padding

    def wrap(self, avail_width, avail_height):
        self.sizes = [item.wrap(self.width - self.padding * 2, 100000) for item in self.content]
        self.height = max(self.minimum, self.padding * 2 + sum(h for _, h in self.sizes)
                          + (14 if self.percentage is not None else 0))
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(self.fill)
        c.roundRect(0, 0, self.width, self.height, 9, fill=1, stroke=0)
        c.setFillColor(self.accent)
        c.roundRect(self.padding, self.height - 5, 27, 3, 1.5, fill=1, stroke=0)
        y = self.height - self.padding
        for item, (_, height) in zip(self.content, self.sizes):
            y -= height
            item.drawOn(c, self.padding, y)
        if self.percentage is not None:
            y = self.padding - 1
            c.setFillColor(LINE)
            c.roundRect(self.padding, y, self.width - self.padding * 2, 5, 2.5, fill=1, stroke=0)
            if self.percentage > 0:
                c.setFillColor(self.accent)
                c.roundRect(self.padding, y, (self.width - self.padding * 2) * self.percentage / 100,
                            5, 2.5, fill=1, stroke=0)


class _NumberedCanvas(Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self.pages)
        regular, bold, *_ = _fonts()
        for state in self.pages:
            self.__dict__.update(state)
            self.saveState()
            width = self._pagesize[0]
            self.setStrokeColor(LINE)
            self.setLineWidth(.6)
            self.line(38, 38, width - 38, 38)
            self.setStrokeColor(AMBER)
            self.setLineWidth(2)
            self.line(38, 38, 70, 38)
            self.setFont(bold, 7.4)
            self.setFillColor(NAVY)
            self.drawString(38, 24, 'PABASA')
            self.setFont(regular, 7.4)
            self.setFillColor(MUTED)
            self.drawString(80, 24, 'CONFIDENTIAL  /  School leadership report')
            self.drawRightString(width - 38, 24, f'Page {self._pageNumber} of {total}')
            self.restoreState()
            super().showPage()
        super().save()


class _Design:
    def __init__(self, snapshot, page, logo_path=None):
        self.snapshot, self.page = snapshot, page
        self.width, self.margin = page[0] - 76, 38
        self.fonts = regular, bold, display, italic = _fonts()
        self.logo_path = Path(logo_path) if logo_path else None
        self.institution = Paragraph(_text(snapshot['school_name']), ParagraphStyle('institution',
            fontName=bold, fontSize=12, leading=16, textColor=WHITE))
        self.institution_height = self.institution.wrap(page[0] - 300, 100000)[1]
        self.hero_extra = max(0, self.institution_height - 48)
        self.styles = {
            'body': ParagraphStyle('principal_body', fontName=regular, fontSize=10,
                leading=14, textColor=INK, allowWidows=0, allowOrphans=0),
            'small': ParagraphStyle('principal_small', fontName=regular, fontSize=8.5,
                leading=12, textColor=MUTED),
            'label': ParagraphStyle('principal_label', fontName=bold, fontSize=9,
                leading=12, textColor=NAVY),
            'eyebrow': ParagraphStyle('principal_eyebrow', fontName=bold, fontSize=8,
                leading=13, textColor=BLUE, charSpace=.8),
            'number': ParagraphStyle('principal_number', fontName=display, fontSize=32,
                leading=39, textColor=NAVY),
            'metric': ParagraphStyle('principal_metric', fontName=display, fontSize=23,
                leading=29, textColor=NAVY),
            'heading': ParagraphStyle('principal_heading', fontName=display, fontSize=17,
                leading=23, textColor=NAVY, keepWithNext=True),
            'cell': ParagraphStyle('principal_cell', fontName=regular, fontSize=9,
                leading=12.5, textColor=INK),
            'table_head': ParagraphStyle('principal_table_head', fontName=bold, fontSize=8.5,
                leading=11.5, textColor=WHITE),
        }

    def p(self, value, style='body'):
        return Paragraph(_text(value), self.styles[style])

    def grid(self, panels, gap=10):
        cells, widths = [], []
        height = max(panel.wrap(panel.width, 100000)[1] for panel in panels)
        for panel in panels:
            panel.minimum = height
            if cells:
                cells.append('')
                widths.append(gap)
            cells.append(panel)
            widths.append(panel.width)
        table = Table([cells], colWidths=widths, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return table

    def cards(self, items, *, size='metric', color=BLUE, fill=PALE_BLUE, minimum=0):
        width = (self.width - 10 * (len(items) - 1)) / len(items)
        panels = []
        labels = [self.p(item[0], 'label') for item in items]
        label_height = max(label.wrap(width - 30, 100000)[1] for label in labels) + 3
        for label, (_, value, note, percent) in zip(labels, items):
            panels.append(_Panel(width, [_LabelSlot(label, label_height), self.p(value, size),
                self.p(note, 'small')], fill=fill, accent=color, minimum=minimum, percentage=percent))
        return self.grid(panels)

    def section(self, story, number, title, note=None):
        story.extend([CondPageBreak(110), self.p(f'{number:02}  /  SCHOOL ANALYTICS', 'eyebrow'),
                      self.p(title, 'heading')])
        if note:
            paragraph = self.p(note, 'small')
            paragraph.keepWithNext = True
            story.append(paragraph)
        story.append(Spacer(1, 9))

    def scope(self):
        s = self.snapshot
        calendar = s['scope_calendar']
        values = [
            ('SCHOOL YEAR', calendar.school_year if calendar else 'Legacy / unassigned year'),
            ('REPORTING PERIOD', f'Term {s["scope_term"]}' if s['scope_term'] else 'All terms'),
            ('ASSESSMENT PERIOD', s.get('scope_phase_label') or s['scope_phase'] or 'All CRLA periods'),
            ('GENERATED', timezone.localtime(s['snapshot_at']).strftime('%B %d, %Y %I:%M %p')),
        ]
        cells = [[self.p(label, 'eyebrow'), self.p(value, 'label')] for label, value in values]
        table = Table([cells[:2], cells[2:]], colWidths=[self.width / 2] * 2, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        return table

    def masthead(self, canvas, doc):
        canvas.saveState()
        w, h = self.page
        if doc.page == 1:
            extra = self.hero_extra
            canvas.setFillColor(NAVY)
            canvas.rect(0, h - 192 - extra, w, 192 + extra, fill=1, stroke=0)
            # Architectural arcs are decoration, not a data visualization.
            canvas.saveState()
            clip = canvas.beginPath()
            clip.rect(0, h - 192 - extra, w, 192 + extra)
            canvas.clipPath(clip, stroke=0, fill=0)
            canvas.setStrokeColor(colors.HexColor('#185270'))
            canvas.setLineWidth(1)
            for radius in (76, 105, 134):
                canvas.circle(w + 10, h - 155, radius, fill=0, stroke=1)
            canvas.restoreState()
            canvas.setFillColor(AMBER)
            canvas.rect(0, h - 196 - extra, w, 4, fill=1, stroke=0)
            canvas.setFillColor(WHITE)
            canvas.roundRect(38, h - 79, 56, 56, 9, fill=1, stroke=0)
            logo = self.logo_path
            if 'salawag' in self.snapshot['school_name'].lower() and not self.snapshot.get('school_logo'):
                logo = ASSETS / 'images' / 'ses_logo.jpg'
            elif not logo or not logo.is_file():
                # Salawag identity is used only for its school, never another principal's school.
                logo = ASSETS / 'images' / 'ses_logo.jpg' if 'salawag' in self.snapshot['school_name'].lower() else None
            if logo and logo.is_file():
                canvas.drawImage(str(logo), 42, h - 75, width=48, height=48,
                                 preserveAspectRatio=True, anchor='c', mask='auto')
            else:
                canvas.setFillColor(BLUE)
                canvas.setFont(self.fonts[2], 19)
                canvas.drawCentredString(66, h - 57, 'P')
            nh = self.institution_height
            self.institution.drawOn(canvas, 107, h - 31 - nh)
            canvas.setFont(self.fonts[0], 8)
            canvas.setFillColor(colors.HexColor('#BFDFED'))
            canvas.drawString(107, h - 44 - nh, 'INSTITUTIONAL READING MONITORING')
            canvas.setFillColor(WHITE)
            canvas.roundRect(w - 138, h - 65, 100, 36, 7, fill=1, stroke=0)
            brand = ASSETS / 'images' / 'pabasa_logo.png'
            if brand.is_file():
                canvas.drawImage(str(brand), w - 131, h - 60, width=86, height=26,
                                 preserveAspectRatio=True, anchor='c', mask='auto')
            else:
                canvas.setFillColor(BLUE)
                canvas.setFont(self.fonts[2], 18)
                canvas.drawString(w - 130, h - 53, 'PABASA')
            canvas.setFillColor(AMBER)
            canvas.setFont(self.fonts[1], 8)
            canvas.drawString(38, h - 105 - extra, 'PRINCIPAL\'S EXECUTIVE REPORT')
            canvas.setFillColor(WHITE)
            canvas.setFont(self.fonts[2], 28)
            canvas.drawString(38, h - 137 - extra, 'School Reading')
            canvas.drawString(38, h - 168 - extra, 'Performance Report')
            canvas.setFont(self.fonts[0], 9)
            canvas.setFillColor(colors.HexColor('#BFDFED'))
            canvas.drawRightString(w - 38, h - 180 - extra, 'PARTICIPATION  /  ASSESSMENT  /  SUPPORT')
        else:
            canvas.setFillColor(NAVY)
            canvas.setFont(self.fonts[2], 15)
            canvas.drawString(38, h - 36, 'PABASA')
            canvas.setFillColor(MUTED)
            canvas.setFont(self.fonts[0], 8.5)
            canvas.drawRightString(w - 38, h - 35, 'SCHOOL READING PERFORMANCE  /  PRINCIPAL REPORT')
            canvas.setStrokeColor(LINE)
            canvas.line(38, h - 49, w - 38, h - 49)
            canvas.setStrokeColor(AMBER)
            canvas.setLineWidth(2.5)
            canvas.line(38, h - 49, 77, h - 49)
        canvas.restoreState()


def _dashboard(d, s, report_label):
    story = [d.scope(), Spacer(1, 13), d.p('EXECUTIVE OVERVIEW', 'eyebrow'),
             d.p(report_label, 'heading'), Spacer(1, 10)]
    story.append(d.cards([
        ('Total Enrolled Students', _value(s['total_students']), 'Grade 2 enrollment cohort', None),
        ('Assigned Teachers', _value(s['total_teachers']), 'Active teachers assigned to the cohort', None),
    ], size='number', minimum=106))
    story.append(Spacer(1, 10))
    story.append(d.cards([
        ('Official CRLA Coverage', _value(s['completion_rate'], True),
         f'{s["official_completed_students"]} learners completed / {s["total_students"]} enrolled', s['completion_rate']),
        ('Latest Official Reading Accuracy', _value(s['average_score'], True),
         f'{s["accuracy_samples"]} recorded accuracy samples; not a coverage measure', s['average_score']),
    ], size='number', color=TEAL, fill=PALE_TEAL, minimum=125))
    story.extend([Spacer(1, 16), d.p('SCHOOL & ASSESSMENT OVERVIEW', 'eyebrow'),
                  d.cards([
                      ('Active Sections', _value(s['total_sections']), 'Within the selected reporting scope', None),
                      ('Assessment tasks represented', _value(s['total_assessments']), 'Tasks represented in existing records', None),
                  ], minimum=86), Spacer(1, 14)])
    story.append(_Panel(d.width, [d.p('HOW TO READ THESE FIGURES', 'eyebrow'),
        d.p(s['metric_definition'], 'small')], fill=PALE_AMBER, accent=AMBER, padding=12))
    return story


def _school_analytics(d, s, rows):
    # Consume the same rows used by CSV/preview. Preserve every label and value.
    metrics = {label: value for label, value in rows}
    used = set()

    def item(label, note='', percent=None):
        used.add(label)
        return label, metrics.get(label, 'N/A'), note, percent

    story = [d.p('DETAILED SCHOOL ANALYTICS', 'eyebrow'),
             d.p(s['school_name'], 'heading'),
             d.p(f'Grade 2  /  {s.get("scope_section_label") or "All sections"}', 'small'), Spacer(1, 10)]
    # School, year and exact raw term/phase values remain in the detailed scope block.
    scope_labels = ['School Name', 'School Year', 'Term', 'Assessment period']
    scope = []
    for label in scope_labels:
        if label in metrics:
            used.add(label)
            if label != 'School Name':
                scope.append(f'{label}: {metrics[label]}')
    story.extend([_Panel(d.width, [d.p('  /  '.join(scope), 'small')], fill=PALE_BLUE, padding=12), Spacer(1, 16)])
    d.section(story, 1, 'CRLA Assessment Performance',
              'Coverage describes participation. Accuracy describes recorded reading results.')
    story.append(d.cards([
        item('Official CRLA learners completed'),
        item('Official CRLA coverage', percent=s['completion_rate']),
        item('Latest official reading accuracy', percent=s['average_score']),
        item('Accuracy samples'),
    ], minimum=110, color=TEAL, fill=PALE_TEAL))
    story.extend([Spacer(1, 7), d.p('Accuracy uses the latest qualifying result per learner. Samples count recorded accuracy values, including zero.', 'small'), Spacer(1, 18)])
    d.section(story, 2, 'ARAL Program Engagement',
              'Recorded participation and review status; these counts are not proficiency scores or sequential stages.')
    story.append(d.cards([
        item('ARAL eligible by official profile'),
        item('ARAL learners with recorded progress'),
        item('Recorded intervention exits'),
        item('Learners pending review'),
    ], minimum=110, color=AMBER, fill=PALE_AMBER))
    story.extend([Spacer(1, 7), d.p('Recorded progress covers eligible learners without a recorded exit; pending review reflects recorded work awaiting review.', 'small'), Spacer(1, 18)])
    d.section(story, 3, 'Learning Activities & Supplementary Engagement',
              'Activity and assignment counts, not learner counts. Completion does not establish skill mastery.')
    story.append(d.cards([
        item('Recorded prescribed completed activities'),
        item('Supplementary assignments'),
        item('Supplementary completed assignments'),
    ], minimum=100, color=TEAL, fill=PALE_TEAL))
    # These values are displayed verbatim in the executive dashboard.
    used.update(['Enrolled Grade 2 students', 'Assigned active Teachers', 'Active Sections',
                 'Assessment tasks represented'])
    # Future export metrics are retained, rather than silently dropped by this layout.
    remaining = [[label, value] for label, value in rows if label not in used]
    if remaining:
        story.append(Spacer(1, 16))
        d.section(story, 4, 'Additional Institutional Metrics')
        story.append(_detail_table(d, ['Metric', 'Value'], remaining))
    return story


def _detail_table(d, headers, rows):
    # A minimum share keeps names readable even beside very long narrative cells.
    weights = [min(50, max(24, len(str(header)))) for header in headers]
    for row in rows[:100]:
        for index, value in enumerate(row):
            weights[index] = max(weights[index], min(60, len(str(value))))
    widths = [d.width * value / sum(weights) for value in weights]
    data = [[d.p(header, 'table_head') for header in headers]]
    data.extend([[d.p(value, 'cell') for value in row] for row in rows])
    if not rows:
        data.append([d.p('No records in the selected scope.', 'cell')] + [''] * (len(headers) - 1))
    table = LongTable(data, colWidths=widths, repeatRows=1, splitByRow=1, splitInRow=1, hAlign='LEFT')
    commands = [
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, PALE_BLUE]),
        ('LINEBELOW', (0, 0), (-1, 0), 2, AMBER),
        ('LINEBELOW', (0, 1), (-1, -1), .35, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
    ]
    if not rows:
        commands.append(('SPAN', (0, 1), (-1, 1)))
    table.setStyle(TableStyle(commands))
    return table


def build_principal_pdf(snapshot, report_type, headers, rows, logo_path=None):
    """Render the supplied snapshot without changing report values or filters."""
    from .principal_exports import REPORT_TYPES

    # The executive page remains portrait; wide detail exports retain landscape.
    page = A4
    detail_page = landscape(A4) if len(headers) > 6 else A4
    d = _Design(snapshot, page, logo_path)
    detail = _Design(snapshot, detail_page, logo_path)
    output = BytesIO()
    document = BaseDocTemplate(output, pagesize=page, leftMargin=38, rightMargin=38,
        topMargin=64, bottomMargin=52, title='PABASA | School Reading Performance Report',
        author='PABASA', subject=f'{REPORT_TYPES[report_type]} | Principal school monitoring')
    first = Frame(38, 52, d.width, page[1] - 260 - d.hero_extra, leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0, id='executive')
    later = Frame(38, 52, detail.width, detail_page[1] - 116, leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0, id='analytics')
    document.addPageTemplates([
        PageTemplate(id='executive', frames=first, onPage=d.masthead,
                     autoNextPageTemplate='analytics', pagesize=page),
        PageTemplate(id='analytics', frames=later, onPage=detail.masthead, pagesize=detail_page),
    ])
    story = _dashboard(d, snapshot, f'{REPORT_TYPES[report_type]} / Grade 2')
    story.append(PageBreak())
    if report_type == 'school':
        story.extend(_school_analytics(detail, snapshot, rows))
    else:
        story.extend([detail.p('DETAILED SCHOOL ANALYTICS', 'eyebrow'),
                      detail.p(f'{REPORT_TYPES[report_type]} Report', 'heading'),
                      detail.p(snapshot['school_name'], 'small'), detail.scope(), Spacer(1, 14),
                      _detail_table(detail, headers, rows)])
    document.build(story, canvasmaker=_NumberedCanvas)
    return output.getvalue()
