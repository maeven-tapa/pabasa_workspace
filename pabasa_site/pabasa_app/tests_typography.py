"""Coverage for the shared font across inherited and standalone UI documents."""
from pathlib import Path
import re
import struct

from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.template.loader import get_template, render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings

from .static_images import OptimizedImageMiddleware


APP = Path(__file__).resolve().parent
TEMPLATES = APP / 'templates'
STATIC = APP / 'static' / 'pabasa_app'
INCLUDE = 'pabasa_app/includes/typography.html'


def ui_sources():
    for root in (TEMPLATES, STATIC):
        for path in root.rglob('*'):
            if path.suffix in {'.html', '.css', '.js'} and 'vendor' not in path.parts and '.min.' not in path.name:
                yield path, path.read_text(encoding='utf-8-sig')


class TypographyTests(SimpleTestCase):
    def test_every_document_entry_point_loads_shared_typography(self):
        documents = []
        for path in TEMPLATES.rglob('*.html'):
            source = path.read_text(encoding='utf-8-sig')
            if re.search(r'<head\b', source, re.I):
                # Check every independent document, including its new include.
                get_template(path.relative_to(TEMPLATES).as_posix())
                documents.append(path)
                self.assertIn(INCLUDE, source, str(path))
                self.assertEqual(source.count(INCLUDE), 1, str(path))
        self.assertGreater(len(documents), 100)

    def test_text_family_overrides_use_the_shared_variable_and_icons_keep_their_font(self):
        allowed = {
            'var(--font-family-primary)', 'inherit', 'bootstrap-icons', '"bootstrap-icons"', "'bootstrap-icons'",
            'var(--font-family-primary), "bootstrap-icons"',
        }
        for path, source in ui_sources():
            if path.name == 'typography.css':
                continue
            for value in re.findall(r'(?<![-\w])font-family\s*:\s*([^;\r\n{}<>]+)', source):
                family = re.sub(r'\s*!important\s*$', '', value).strip()
                self.assertIn(family, allowed, f'{path}: {value}')
        icon_css = (STATIC / 'vendor/bootstrap-icons/bootstrap-icons.css').read_text(encoding="utf-8")
        self.assertIn('bootstrap-icons', icon_css)

    def test_font_shorthands_and_dynamic_styles_do_not_reintroduce_old_text_faces(self):
        legacy = re.compile(r'\b(?:Nunito|Fredoka|Quattrocento|Schoolbell|Coiny|Poppins|Baloo|SpecialElite|Rye|Oxanium|Carnevalee|Super Bubble|ui-monospace)\b', re.I)
        for path, source in ui_sources():
            for value in re.findall(r'(?<![-\w])font\s*:\s*([^;{}\r\n<>]+)', source):
                self.assertIsNone(legacy.search(value), f'{path}: {value}')
            self.assertNotIn('fonts.googleapis.com', source, str(path))
            self.assertNotIn('fonts.gstatic.com', source, str(path))
            for value in re.findall(r"setProperty\(['\"]font-family['\"],\s*['\"]([^'\"]+)", source):
                self.assertEqual(value, 'var(--font-family-primary)', str(path))

    def test_only_regular_andika_is_registered_as_an_application_text_face(self):
        registrations = []
        for path, source in ui_sources():
            for family in re.findall(r'@font-face\s*\{\s*font-family\s*:\s*([^;]+)', source):
                if 'bootstrap-icons' not in family:
                    registrations.append((path.name, family.strip('"\'')))
        self.assertEqual(registrations, [('typography.css', 'Andika')])
        css = (STATIC / 'css/typography.css').read_text(encoding="utf-8")
        self.assertIn('font-weight: 400;', css)
        self.assertIn('font-display: swap;', css)
        self.assertIn('../font/AndBasR.ttf', css)
        self.assertNotRegex(css, r'\*\s*\{[^}]*font-family')
        font = (STATIC / 'font/AndBasR.ttf').read_bytes()
        tables = {
            tag: (offset, length)
            for tag, _checksum, offset, length in struct.iter_unpack('>4sIII', font[12:12 + 16 * struct.unpack_from('>H', font, 4)[0]])
        }
        self.assertEqual(struct.unpack_from('>H', font, tables[b'OS/2'][0] + 4)[0], 400)

    def test_font_css_and_icons_are_served_in_development_and_production_static_modes(self):
        paths = ('css/typography.css', 'font/AndBasR.ttf', 'vendor/bootstrap-icons/fonts/bootstrap-icons.woff2')
        for debug in (True, False):
            with self.subTest(debug=debug), override_settings(DEBUG=debug, WHITENOISE_AUTOREFRESH=debug, WHITENOISE_USE_FINDERS=True):
                middleware = OptimizedImageMiddleware(lambda request: HttpResponse(status=404))
                for asset in paths:
                    name = 'pabasa_app/' + asset
                    expected = Path(finders.find(name)).read_bytes()
                    response = middleware(RequestFactory().get('/static/' + name))
                    self.assertEqual(response.status_code, 200, name)
                    self.assertEqual(b''.join(response.streaming_content), expected)
                    response.close()

    def test_error_pages_and_django_admin_load_the_shared_font(self):
        for page in ('400.html', '403.html', '404.html', '500.html'):
            html = render_to_string(page)
            self.assertIn('/static/pabasa_app/css/typography.css', html)
        self.assertIn(INCLUDE, (TEMPLATES / 'admin/base_site.html').read_text(encoding="utf-8"))

    def test_canvas_chart_and_practice_measurements_use_the_loaded_text_font(self):
        chart = (TEMPLATES / 'pabasa_app/students.html').read_text(encoding="utf-8")
        self.assertIn('Chart.defaults.font.family', chart)
        self.assertIn("getPropertyValue('--font-family-primary')", chart)
        self.assertIn("chartCanvas.chart?.update('none')", chart)
        practice = (STATIC / 'js/practice_reader.js').read_text(encoding="utf-8")
        self.assertIn('document.fonts?.ready.then', practice)
