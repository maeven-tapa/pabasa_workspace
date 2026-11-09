"""Presentation-only renderer for the parent-facing reading progress report.

All academic values come from the existing collector payload. Decorative bars
visualize recorded percentages; they never produce scores or classifications.
"""

from functools import lru_cache
from io import BytesIO
import math
from pathlib import Path
from threading import RLock
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate, CondPageBreak, Flowable, Frame, LongTable,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

from .reading_report_details import summarize_workbook_progress


NAVY = colors.HexColor('#073B5C')
BLUE = colors.HexColor('#007DB6')
SKY = colors.HexColor('#32B7E9')
AMBER = colors.HexColor('#FFBF25')
INK = colors.HexColor('#193B50')
MUTED = colors.HexColor('#607888')
LINE = colors.HexColor('#DCE7EF')
PALE_BLUE = colors.HexColor('#EFF7FC')
PALE_AMBER = colors.HexColor('#FFF7E1')
WHITE = colors.white
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 40
WIDTH = PAGE_WIDTH - 2 * MARGIN
ASSETS = Path(__file__).resolve().parent / 'static' / 'pabasa_app'
_font_lock = RLock()


@lru_cache(maxsize=1)
def _fonts():
    with _font_lock:
        root = ASSETS / 'font' / 'report'
        files = {'PabasaSans': 'Lato-Regular.ttf', 'PabasaSansBold': 'Lato-Bold.ttf',
                 'PabasaDisplay': 'Lato-Black.ttf', 'PabasaSansItalic': 'Lato-Italic.ttf'}
        if not all((root / name).is_file() for name in files.values()):
            return 'Helvetica', 'Helvetica-Bold', 'Helvetica-Bold', 'Helvetica-Oblique'
        for name, filename in files.items():
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(root / filename)))
        pdfmetrics.registerFontFamily('PabasaSans', normal='PabasaSans', bold='PabasaSansBold',
                                      italic='PabasaSansItalic', boldItalic='PabasaSansBold')
        return tuple(files)


def _text(value, fallback='Not yet available'):
    value = fallback if value in (None, '') else value
    return escape(str(value)).replace('\n', '<br/>')


def _percent(value):
    try:
        return f'{value:g}'
    except (TypeError, ValueError):
        return str(value)


def _valid_percent(value):
    return isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 100


class _ProgressBar(Flowable):
    def __init__(self, value, width, color=BLUE):
        super().__init__()
        self.value, self.width, self.height, self.color = value, width, 6, color

    def draw(self):
        self.canv.setFillColor(LINE)
        self.canv.roundRect(0, 2, self.width, 4, 2, fill=1, stroke=0)
        if self.value > 0:
            self.canv.setFillColor(self.color)
            self.canv.roundRect(0, 2, self.width * self.value / 100, 4, 2, fill=1, stroke=0)


WORKBOOK_STATUS = (
    ('completed', 'Completed', BLUE), ('ongoing', 'Ongoing', SKY),
    ('awaiting_review', 'Awaiting review', AMBER),
    ('completion_unrecorded', 'Completion unrecorded', LINE),
)
RECOMMENDATION_LABELS = {
    'P0': 'CRLA unavailable',
    'P1': 'Continue / review', 'P2': 'Guided practice',
    'P3': 'Oral reading', 'P4': 'Regular reading / support',
    'P5': 'Grade level / Practice Mode',
}


class _ActivityCountBar(Flowable):
    """Absolute activity counts on one common scale; never a proficiency score."""
    def __init__(self, period, maximum, width, fonts):
        super().__init__()
        self.period, self.maximum, self.fonts = period, maximum, fonts
        self.width, self.height = width, 15

    def draw(self):
        x = 0
        for key, _label, color in WORKBOOK_STATUS:
            count = self.period[key]
            if not count:
                continue
            width = self.width * count / self.maximum
            self.canv.setFillColor(color)
            self.canv.rect(x, 1, width, 13, fill=1, stroke=0)
            if width >= 18:
                self.canv.setFillColor(WHITE if key == 'completed' else NAVY)
                self.canv.setFont(self.fonts[1], 7)
                self.canv.drawCentredString(x + width / 2, 4, str(count))
            x += width


def _recommendation_code(text, details):
    # Legacy payloads and stale metadata must not acquire a guessed P-code.
    codes = {item.get('code') for item in details if item.get('text') == text
             and item.get('code') in RECOMMENDATION_LABELS}
    return next(iter(codes)) if len(codes) == 1 else None


class _SectionHeading(Flowable):
    def __init__(self, number, title, fonts, compact=False):
        super().__init__()
        self.number, self.title, self.fonts = number, title, fonts
        self.width, self.height = WIDTH, 20 if compact else 22

    def draw(self):
        canvas = self.canv
        y = self.height - 18
        canvas.setFillColor(AMBER)
        canvas.roundRect(0, y, 21, 17, 5, fill=1, stroke=0)
        canvas.setFillColor(NAVY)
        canvas.setFont(self.fonts[1], 8)
        canvas.drawCentredString(10.5, y + 5, f'{self.number:02}')
        canvas.setFont(self.fonts[1], 10.2)
        canvas.drawString(30, y + 4, self.title)
        end = 37 + pdfmetrics.stringWidth(self.title, self.fonts[1], 10.2)
        if end < WIDTH - 12:
            canvas.setStrokeColor(LINE)
            canvas.setLineWidth(.6)
            canvas.line(end, y + 8, WIDTH, y + 8)


class _MetricCard(Flowable):
    def __init__(self, label, value, width, fonts, percent=None, amber=False, compact=False):
        super().__init__()
        self.width, self.fonts, self.percent = width, fonts, percent
        self.amber, self.compact = amber, compact
        self.label = Paragraph(_text(label), ParagraphStyle('metric_label', fontName=fonts[1],
            fontSize=7.2, leading=9, textColor=MUTED))
        missing = value in (None, '')
        self.value = Paragraph(_text(value), ParagraphStyle('metric_value', fontName=fonts[2],
            fontSize=11 if missing else 22, leading=14 if missing else 26, textColor=NAVY))

    def wrap(self, avail_width, avail_height):
        self.label_height = self.label.wrap(self.width - 22, 10000)[1]
        self.value_height = self.value.wrap(self.width - 22, 10000)[1]
        self.height = max(getattr(self, 'minimum_height', 50),
                          15 + self.label_height + self.value_height + (10 if self.percent is not None else 0))
        return self.width, self.height

    def draw(self):
        self.canv.setFillColor(PALE_AMBER if self.amber else PALE_BLUE)
        self.canv.roundRect(0, 0, self.width, self.height, 8, fill=1, stroke=0)
        top = self.height - 8
        self.label.drawOn(self.canv, 11, top - self.label_height)
        self.value.drawOn(self.canv, 11, top - self.label_height - self.value_height - 3)
        if self.percent is not None:
            _ProgressBar(self.percent, self.width - 22, AMBER if self.amber else BLUE).drawOn(self.canv, 11, 6)


class _ReportCanvas(Canvas):
    """Add final page totals without querying or changing any report values."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._report_pages = []

    def showPage(self):
        self._report_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._report_pages)
        for state in self._report_pages:
            self.__dict__.update(state)
            self.saveState()
            self.setStrokeColor(LINE)
            self.setLineWidth(.5)
            self.line(MARGIN, 34, PAGE_WIDTH - MARGIN, 34)
            self.setFont(_fonts()[0], 7)
            self.setFillColor(MUTED)
            self.drawString(MARGIN, 22, 'PABASA  /  Reading development, together')
            self.drawRightString(PAGE_WIDTH - MARGIN, 22, f'Page {self._pageNumber} of {total}')
            self.restoreState()
            super().showPage()
        super().save()


class _ReportDesign:
    def __init__(self, compact=False):
        self.fonts = _fonts()
        self.compact = compact
        regular, bold, display, italic = self.fonts
        self.body = ParagraphStyle('report_body', fontName=regular, fontSize=8.7,
            leading=12, textColor=INK, spaceAfter=4, allowWidows=0, allowOrphans=0)
        self.small = ParagraphStyle('report_small', parent=self.body, fontSize=7.6, leading=10, spaceAfter=2)
        self.muted = ParagraphStyle('report_muted', parent=self.small, textColor=MUTED)
        self.table_body = ParagraphStyle('report_table_body', parent=self.body, fontSize=8.1, leading=10.7, spaceAfter=0)
        self.table_head = ParagraphStyle('report_table_head', parent=self.small, fontName=bold,
            textColor=WHITE, fontSize=7.4, leading=9.5, spaceAfter=0)
        self.label = ParagraphStyle('report_label', parent=self.small, fontName=bold, fontSize=7,
            leading=9, textColor=BLUE, spaceAfter=3)
        self.name = ParagraphStyle('report_name', parent=self.body, fontName=display, fontSize=16,
            leading=20, textColor=NAVY, spaceAfter=0)
        self.profile = ParagraphStyle('report_profile', parent=self.body, fontName=display,
            fontSize=16, leading=20, textColor=NAVY, spaceAfter=2)
        self.note = ParagraphStyle('report_note', parent=self.body, fontName=italic, leading=13)
        self.number = ParagraphStyle('report_number', parent=self.body, fontName=display,
            fontSize=10, textColor=BLUE, leading=13, alignment=1, spaceAfter=0)

    def p(self, value, style=None, fallback='Not yet available'):
        return Paragraph(_text(value, fallback), style or self.body)

    def section(self, story, number, title, minimum=None):
        # Reserve only a useful first fragment, not a whole table: large tables
        # should use the remaining page instead of leaving a large blank area.
        story.extend([Spacer(1, 2), CondPageBreak(minimum or (52 if self.compact else 62)),
                      _SectionHeading(number, title, self.fonts, self.compact)])

    def surface(self, rows, widths=None, fill=PALE_BLUE, padding=10, accent=None, spans=()):
        table = LongTable(rows, colWidths=widths or [WIDTH], splitByRow=1, splitInRow=1,
                          hAlign='LEFT', cornerRadii=[8, 8, 8, 8])
        commands = [('BACKGROUND', (0, 0), (-1, -1), fill),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), padding),
                    ('RIGHTPADDING', (0, 0), (-1, -1), padding),
                    ('TOPPADDING', (0, 0), (-1, -1), padding),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), padding)]
        if accent:
            commands.append(('LINEBEFORE', (0, 0), (0, -1), 3, accent))
        commands.extend(('SPAN', start, end) for start, end in spans)
        table.setStyle(TableStyle(commands))
        return table

    def notice(self, value, amber=False):
        return self.surface([[self.p(value, self.small)]], fill=PALE_AMBER if amber else PALE_BLUE,
                            padding=2 if self.compact else 7, accent=AMBER if amber else SKY)

    def ledger(self, headers, rows, fractions):
        table = LongTable([[self.p(label, self.table_head) for label in headers], *rows],
            colWidths=[WIDTH * fraction for fraction in fractions], repeatRows=1,
            splitByRow=1, splitInRow=1, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, PALE_BLUE]),
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, AMBER),
            ('LINEBELOW', (0, 1), (-1, -1), .4, LINE),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        return table

    def metric_grid(self, values):
        gap = 9
        cell_width = (WIDTH - gap * (len(values) - 1)) / len(values)
        cells, widths = [], []
        for index, (label, value, percent, amber) in enumerate(values):
            if index:
                cells.append('')
                widths.append(gap)
            cells.append(_MetricCard(label, value, cell_width, self.fonts, percent, amber, self.compact))
            widths.append(cell_width)
        cards = [cell for cell in cells if isinstance(cell, _MetricCard)]
        height = max(card.wrap(cell_width, 10000)[1] for card in cards)
        for card in cards:
            card.minimum_height = height
        table = Table([cells], colWidths=widths, hAlign='LEFT')
        table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0)]))
        return table

    def masthead(self, canvas, doc):
        canvas.saveState()
        height = 118 if self.compact else 148
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_HEIGHT - height, PAGE_WIDTH, height, fill=1, stroke=0)
        canvas.setFillColor(AMBER)
        canvas.rect(0, PAGE_HEIGHT - height, PAGE_WIDTH, 4, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.roundRect(MARGIN, PAGE_HEIGHT - 54, 102, 34, 7, fill=1, stroke=0)
        logo = ASSETS / 'images' / 'pabasa_logo.png'
        if logo.is_file():
            canvas.drawImage(str(logo), MARGIN + 7, PAGE_HEIGHT - 50, width=88, height=29,
                             preserveAspectRatio=True, anchor='c', mask='auto')
        else:
            canvas.setFont(self.fonts[2], 19)
            canvas.setFillColor(BLUE)
            canvas.drawString(MARGIN + 10, PAGE_HEIGHT - 44, 'PABASA')
        canvas.setFont(self.fonts[1], 7.2)
        canvas.setFillColor(AMBER)
        canvas.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 39, 'FOR PARENTS & GUARDIANS')
        canvas.setFillColor(WHITE)
        canvas.setFont(self.fonts[2], 22 if self.compact else 26)
        canvas.drawString(MARGIN, PAGE_HEIGHT - (81 if self.compact else 87), 'STUDENT READING')
        canvas.drawString(MARGIN, PAGE_HEIGHT - (107 if self.compact else 117), 'PROGRESS REPORT')
        if not self.compact:
            canvas.setFont(self.fonts[0], 8.5)
            canvas.setFillColor(colors.HexColor('#C1E5F5'))
            canvas.drawString(MARGIN, PAGE_HEIGHT - 135, 'Assessment, guided practice & reading development')
        # A vector open book gives the document its own visual identity.
        x, y = PAGE_WIDTH - 105, PAGE_HEIGHT - (89 if self.compact else 105)
        canvas.setStrokeColor(colors.HexColor('#236487'))
        canvas.setLineWidth(.7)
        canvas.circle(x + 25, y + 8, 43 if not self.compact else 30, stroke=1, fill=0)
        for direction in (-1, 1):
            path = canvas.beginPath()
            path.moveTo(x, y - 17)
            path.lineTo(x + direction * 31, y - 8)
            path.lineTo(x + direction * 31, y + 26)
            path.lineTo(x, y + 17)
            path.close()
            canvas.setFillColor(AMBER if direction == 1 else SKY)
            canvas.drawPath(path, fill=1, stroke=0)
        canvas.setStrokeColor(NAVY)
        canvas.setLineWidth(1)
        canvas.line(x, y - 17, x, y + 17)
        canvas.restoreState()

    def running_header(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BLUE)
        canvas.setFont(self.fonts[2], 15)
        canvas.drawString(MARGIN, PAGE_HEIGHT - 39, 'PABASA')
        canvas.setFillColor(MUTED)
        canvas.setFont(self.fonts[0], 8)
        canvas.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 38, 'Student reading progress  /  Family report')
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(.7)
        canvas.line(MARGIN, PAGE_HEIGHT - 51, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 51)
        canvas.setStrokeColor(AMBER)
        canvas.setLineWidth(2.5)
        canvas.line(MARGIN, PAGE_HEIGHT - 51, MARGIN + 41, PAGE_HEIGHT - 51)
        canvas.restoreState()


def build_reading_progress_pdf(report, message='', teacher=None, *, date_formatter):
    """Render the supplied report without database access or academic calculations."""
    crla, history, workbook = report.get('crla') or {}, report.get('crla_history') or {}, report.get('workbook') or {}
    activities, workbook_rows = report.get('aral_activities') or [], workbook.get('rows') or []
    compact = not (activities or workbook_rows or len(history.get('rows') or []) > 1)
    design = _ReportDesign(compact)
    story = []
    date_value = date_formatter

    design.section(story, 1, 'STUDENT INFORMATION')
    def information(label, value, prominent=False):
        return [design.p(label, design.label), design.p(value, design.name if prominent else design.body)]

    teacher_name = report.get('teacher_name') or (f'{teacher.first_name} {teacher.last_name}'.strip() if teacher else '')
    grade_section = ' / '.join(filter(None, [str(report.get('grade_level') or ''), str(report.get('section') or '')]))
    story.append(design.surface([
        [information('Student', report.get('student_name'), True), '', information('Student ID', report.get('student_id'))],
        [information('Grade / Section', grade_section), information('Teacher', teacher_name),
         information('Reporting Period', report.get('school_year') or report.get('course_name'))],
    ], [WIDTH / 3] * 3, padding=5 if compact else 8, spans=(((0, 0), (1, 0)),)))

    design.section(story, 2, 'CRLA INITIAL ASSESSMENT')
    if crla.get('available'):
        story.append(design.surface([[
            [design.p('Reading Profile / Classification', design.label), design.p(crla.get('reading_profile'), design.profile)],
            [design.p('Assessment Period: ' + str(crla.get('assessment_period') or crla.get('assessment_phase') or 'Not yet available'), design.small),
             design.p('Assessment Date: ' + date_value(crla.get('completed_at')), design.small)],
        ]], [WIDTH * .58, WIDTH * .42], padding=5 if compact else 8))
        story.append(Spacer(1, 4 if compact else 8))
        metrics = [
            ('Score', crla.get('total_score'), None, False),
            ('Accuracy', f"{crla['accuracy']}%" if crla.get('accuracy') is not None else None,
             crla['accuracy'] if _valid_percent(crla.get('accuracy')) else None, False),
            ('Words Per Minute', crla.get('wpm'), None, True),
        ]
        if compact:
            story.append(design.surface([[
                Paragraph(f'<b>{_text(label)}</b>: {_text(value)}', design.small)
                for label, value, _percent_value, _amber in metrics
            ]], [WIDTH / 3] * 3, padding=4))
        else:
            story.append(design.metric_grid(metrics))
        details = ', '.join(f'{key.replace("_", " ").title()}: {value}' for key, value in (crla.get('part2_results') or {}).items())
        if compact:
            story.extend([Spacer(1, 3), Paragraph(f'<b>Task / Part 2</b>: {_text(details)}', design.small)])
        else:
            story.extend([Spacer(1, 7), design.surface([[[design.p('Task / Part 2', design.label), design.p(details)]]],
                         fill=WHITE, padding=7, accent=SKY)])
        if crla.get('finalized_without_submission'):
            story.append(design.notice('No student submission was recorded. The class was finalized with a zero-score result.', amber=True))
    else:
        story.append(design.notice(crla.get('message')))

    design.section(story, 3, 'CRLA PROGRESS HISTORY', minimum=100 if history.get('rows') else None)
    if history.get('rows'):
        story.append(design.p('School year: ' + str(history.get('school_year') or 'Not yet available'), design.small))
        rows = [[design.p(item.get('period'), design.label), design.p(date_value(item.get('completed_at')), design.table_body),
                 design.p(item.get('classification'), design.table_body),
                 design.p(f"{item['accuracy']}%" if item.get('accuracy') is not None else 'Not recorded', design.table_body),
                 design.p(item.get('wpm') if item.get('wpm') is not None else 'Not recorded', design.table_body),
                 design.p(item.get('comprehension'), design.table_body)] for item in history['rows']]
        story.append(design.ledger(['Period', 'Date', 'Reading classification', 'Accuracy', 'WPM', 'Comprehension'],
                                  rows, [.10, .16, .24, .12, .10, .28]))
    if history.get('message') or not history.get('rows'):
        story.append(design.notice(history.get('message') or 'No verified official CRLA results are available for this reporting period.'))

    design.section(story, 4, 'SUPPLEMENTARY ARAL ACTIVITIES', minimum=112 if activities else None)
    story.append(design.p("Supplementary ARAL Activities provide targeted reading support through additional learning exercises designed to address students' specific reading needs, reinforce essential skills, and improve reading proficiency.", design.small))
    if activities:
        rows = []
        for activity in activities:
            facts = []
            if activity.get('score') is not None: facts.append(f"Score: {activity['score']}")
            if activity.get('accuracy') is not None: facts.append(f"Accuracy: {activity['accuracy']}%")
            if activity.get('wpm') is not None: facts.append(f"WPM: {activity['wpm']}")
            if activity.get('correct_items') is not None and activity.get('total_items') is not None:
                facts.append(f"Items: {activity['correct_items']}/{activity['total_items']}")
            if activity.get('automated_speech_analysis'): facts.append('Automated speech-analysis data')
            rows.append([design.p(activity.get('activity_name'), design.table_body),
                design.p(', '.join(str(v) for v in activity.get('assigned_weeks', [])), design.table_body),
                design.p(date_value(activity.get('completed_at')), design.table_body),
                design.p('; '.join(facts), design.table_body)])
        story.append(design.ledger(['Activity', 'Week', 'Completion Date', 'Recorded Performance'], rows, [.25, .10, .18, .47]))
    else:
        story.append(design.notice('No completed ARAL activities are available for this reporting period.'))

    design.section(story, 5, 'ARAL WORKBOOK PERFORMANCE')
    story.append(Paragraph('<b>Reporting Period</b> &nbsp; | &nbsp; School year: '
                           + _text(workbook.get('school_year')), design.small))
    if workbook_rows:
        periods = list(dict.fromkeys(item['period'] for item in workbook_rows))
        story.append(design.p(f"Covered records: {len(workbook_rows)} workbook activity records. " + '; '.join(periods), design.small))
        if workbook.get('unverified_count'):
            story.append(design.notice('Records labeled unverified have no confirmed school year or term and are shown separately from verified periods.', amber=True))
        story.extend([Spacer(1, 4), CondPageBreak(84), design.p('Completion Overview', design.label), design.metric_grid([
            ('Completed', workbook.get('completed_count', 0), None, False),
            ('Ongoing', workbook.get('ongoing_count', 0), None, False),
            ('Submitted or without recorded completion', workbook.get('other_count', 0), None, True),
        ]), Spacer(1, 6), design.p('Item percentages show completion only. Practice results may include retries; teacher scores cover reviewed items only.', design.muted),
        Spacer(1, 4), CondPageBreak(70), design.p('Activity Performance', design.label)])
        rows = []
        for item in workbook_rows:
            labels = [f"{label} {item[key]}" for label, key in (
                ('Session', 'session'), ('Lesson', 'lesson'), ('Gawain', 'gawain'),
            ) if item.get(key) not in (None, '')]
            identity = [design.p(' / '.join(labels), design.muted), design.p(item.get('title', 'Workbook activity'), design.table_body)]
            completion = [design.p(item.get('completion_status', 'Not recorded'), design.table_body)]
            item_text = item.get('items', 'Not recorded')
            if item.get('completion_percent') is not None:
                item_text += f" ({_percent(item['completion_percent'])}% of items)"
            completion.append(design.p(item_text, design.muted))
            if item.get('completion_percent') is not None:
                if _valid_percent(item['completion_percent']):
                    completion.append(_ProgressBar(item['completion_percent'], WIDTH * .23 - 14))
            performance = [design.p('; '.join(item.get('results') or ['No scored result recorded']), design.table_body),
                           Spacer(1, 3), design.p(item.get('review_status', 'No teacher evaluation recorded'), design.muted)]
            period_text = str(item.get('period') or 'Not yet available').replace(' / ', '\n')
            long_record = (len(str(item.get('title') or '')) > 300
                           or len('; '.join(item.get('results') or [])) > 650
                           or len(str(item.get('review_status') or '')) > 250
                           or len(str(item.get('completion_status') or '')) > 250)
            if long_record:
                if rows:
                    story.append(design.ledger(['Workbook activity', 'Saved period', 'Completion', 'Results / teacher review'],
                                              rows, [.30, .16, .23, .31]))
                    rows = []
                # A long narrative should use the page width, not spill down
                # many pages of one narrow column with three empty columns.
                details = [design.p('Workbook activity', design.label), *identity, Spacer(1, 5),
                           design.p('Saved period', design.label), design.p(period_text, design.table_body),
                           Spacer(1, 5), design.p('Completion', design.label), *completion,
                           Spacer(1, 5), design.p('Results / teacher review', design.label), *performance]
                story.extend([design.surface([[details]], padding=10, accent=SKY), Spacer(1, 6)])
            else:
                rows.append([identity, design.p(period_text, design.table_body), completion, performance])
        if rows:
            story.append(design.ledger(['Workbook activity', 'Saved period', 'Completion', 'Results / teacher review'], rows, [.30, .16, .23, .31]))
    else:
        story.append(design.notice('No workbook progress or recording submissions are available for this reporting period.'))

    design.section(story, 6, 'READING SKILLS PRACTICED THROUGH SUPPLEMENTARY ACTIVITIES', minimum=95)
    description = 'These reading skills were practiced through supplementary activities selected by the teacher to provide additional support in areas where the learner may need further improvement.'
    story.append(Paragraph(_text(description) + " <b>Practice does not confirm mastery</b> or measure the learner's overall reading proficiency.", design.small))
    competencies = [item for item in report.get('competencies') or [] if item.get('activities')]
    skills = []
    skill_names = []
    for competency in competencies:
        names = ', '.join(item.get('activity_name', '') for item in competency.get('activities', [])) or 'No completed activities recorded'
        skill_names.append(names)
        inline = (f'<font color="#007DB6"><b>{_text(competency.get("name"))}</b></font>:'
                  f' &nbsp; {_text(names)}')
        skills.append(Paragraph(inline, design.small))
    if any(len(names) > 400 for names in skill_names):
        story.append(design.ledger(['Reading skill', 'Activities practiced'],
            [[design.p(competency.get('name'), design.label), design.p(names, design.table_body)]
             for competency, names in zip(competencies, skill_names)], [.25, .75]))
    elif skills:
        columns = 2 if len(skills) in (2, 4) else min(3, len(skills))
        card_width = (WIDTH - 8 * (columns - 1)) / columns
        for index in range(0, len(skills), columns):
            group = skills[index:index + columns]
            cells, widths = [], []
            for column in range(columns):
                if column:
                    cells.append('')
                    widths.append(8)
                cells.append(group[column] if column < len(group) else '')
                widths.append(card_width)
            grid = LongTable([cells], colWidths=widths, splitInRow=1, hAlign='LEFT')
            grid.setStyle(TableStyle([
                *[('BACKGROUND', (i * 2, 0), (i * 2, 0), PALE_BLUE) for i in range(len(group))],
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.extend([grid, Spacer(1, 4)])
    else:
        story.append(design.notice('No completed supplementary activities are recorded yet.'))

    progress = summarize_workbook_progress(workbook)
    recent = report.get('recent_progress') or []
    design.section(story, 7, 'READING PROGRESS', minimum=122 if progress['periods'] else 90)
    story.append(design.p('Prescribed ARAL Workbook', design.label))
    if progress['periods']:
        maximum = max(sum(period[key] for key, _label, _color in WORKBOOK_STATUS)
                      for period in progress['periods'])
        story.append(design.p(f"{progress['school_year']} | Activity counts by verified term | Scale: 0 to {maximum}", design.small))
        rows = []
        label_colors = {'awaiting_review': '#8A5B00', 'completion_unrecorded': MUTED.hexval()}
        for period in progress['periods']:
            counts = ' &nbsp; | &nbsp; '.join(
                f'<font color="{label_colors.get(key, color.hexval())}">{label}: {period[key]}</font>'
                for key, label, color in WORKBOOK_STATUS)
            details = [_ActivityCountBar(period, maximum, WIDTH - 95, design.fonts),
                       Paragraph(counts, design.muted)]
            recordings = [f"{period[key]} {label}" for key, label in (
                ('recordings_reviewed', 'reviewed'), ('recordings_pending', 'awaiting review'),
                ('recordings_retry', 'retry requested')) if period[key]]
            if recordings:
                details.append(design.p('Recordings: ' + ' / '.join(recordings), design.muted))
            rows.append([design.p(f"Term {period['term']}", design.label), details])
        chart = design.surface(rows, [75, WIDTH - 75], padding=5)
        chart.splitInRow = 0  # Keep each bar, its counts and review status together.
        story.append(chart)
        story.append(design.p('Saved records only, not all assigned work. Completion is not correctness or mastery. Results and teacher reviews: Section 05.', design.muted))
    else:
        story.append(design.notice('No workbook records with a verified school year and term are available to chart.'))
    if progress['excluded_count']:
        story.append(design.p(f"{progress['excluded_count']} workbook record(s) outside a verified report period are shown in Section 05 and excluded from this chart.", design.muted))

    # The original recent records remain visible, including records that cannot
    # be verified as supplementary. Never relabel a CRLA/workbook result as one.
    supplementary = [item for item in recent if item.get('supplementary_skill_activity') is True]
    other_recent = [item for item in recent if item.get('supplementary_skill_activity') is not True]
    for label, records in [('Supplementary activities', supplementary),
                           ('Other recent recorded results', other_recent)]:
        if not records:
            continue
        story.extend([Spacer(1, 4), CondPageBreak(90), design.p(label, design.label)])
        rows = []
        for item in records:
            identity = [design.p(item.get('activity_name'), design.table_body),
                        design.p('Completed: ' + date_value(item.get('completed_at')), design.muted)]
            accuracy = item.get('accuracy')
            performance = [design.p(f'{accuracy}% accuracy' if accuracy is not None else 'Not recorded', design.table_body)]
            if _valid_percent(accuracy):
                performance.append(_ProgressBar(accuracy, WIDTH * .25 - 14))
            facts = []
            if item.get('miscues') is not None: facts.append(f"miscues {item['miscues']}")
            if item.get('automated_speech_analysis'): facts.append('automated speech-analysis information')
            rows.append([identity, performance,
                         design.p(item.get('wpm'), design.small, 'Not recorded'),
                         design.p('; '.join(facts), design.muted, 'Not recorded')])
        story.append(design.ledger(['Activity / completion date', 'Accuracy (0-100%)', 'WPM', 'Recorded context'],
                                  rows, [.33, .25, .13, .29]))
    if recent:
        story.append(design.p('Each accuracy bar is a separate activity result, not overall proficiency or a matched progress comparison.', design.muted))
    else:
        story.append(design.notice('No recent persisted reading results are available.'))

    design.section(story, 8, "TEACHER'S NOTE", minimum=62 if compact else 80)
    story.append(design.surface([[design.p(message, design.note, 'No teacher note was added.')]],
                                fill=PALE_AMBER, padding=6 if compact else 9, accent=AMBER))
    design.section(story, 9, 'NEXT STEPS', minimum=80 if compact else 90)
    story.append(design.p('Parent recommendations', design.label))
    story.append(Paragraph(' &nbsp;|&nbsp; '.join(
        f'<b>{code}</b> {_text(label)}' for code, label in RECOMMENDATION_LABELS.items()), design.muted))
    details = report.get('recommendation_details') or []
    for index, recommendation in enumerate(report.get('recommendations') or [], 1):
        code = _recommendation_code(recommendation, details)
        story.append(design.surface([[design.p(code or f'{index:02}', design.number), design.p(recommendation)]],
                                    [32, WIDTH - 32], fill=WHITE, padding=3, accent=AMBER))
        story.append(Spacer(1, 2))

    buffer = BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                          bottomMargin=47, topMargin=68,
                          title='Student Reading Progress Report', author='PABASA',
                          subject='Reading assessment and guided practice progress')
    first_top = PAGE_HEIGHT - (133 if compact else 165)
    doc.addPageTemplates([
        PageTemplate(id='First', frames=[Frame(MARGIN, 47, WIDTH, first_top - 47,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)],
            onPage=design.masthead, autoNextPageTemplate='Continuation'),
        PageTemplate(id='Continuation', frames=[Frame(MARGIN, 47, WIDTH, PAGE_HEIGHT - 115,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=design.running_header),
    ])
    doc.build(story, canvasmaker=_ReportCanvas)
    return buffer.getvalue()
