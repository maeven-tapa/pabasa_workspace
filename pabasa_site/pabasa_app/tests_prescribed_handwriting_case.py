from pathlib import Path

import json
from math import cos, sin

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import School, User
from .prescribed_test_fixtures import prescribed_term_fixture

from .handwriting_validation import is_recognizable_single_e
from .views import _lesson7_gawain2c_row_is_recognizable


def strokes(*paths):
    return [[{'x': x, 'y': y} for x, y in path] for path in paths]


CAPITAL_I = strokes(
    [(.3, .2), (.3, .7)], [(.22, .2), (.38, .2)], [(.22, .7), (.38, .7)],
)
LOWERCASE_I = strokes(
    [(.3, .38), (.3, .7)], [(.3, .28), (.305, .285)],
)
CAPITAL_E = strokes(
    [(.3, .2), (.3, .7)], [(.3, .2), (.6, .2)],
    [(.3, .45), (.55, .45)], [(.3, .7), (.6, .7)],
)
LOWERCASE_E = strokes(
    [(.4, .45), (.6, .45), (.63, .38), (.56, .3), (.45, .28),
     (.35, .34), (.3, .45), (.32, .56), (.43, .65), (.59, .63)],
)


def pointer_line(start, end, count=25):
    return [{'x': start[0] + (end[0] - start[0]) * i / (count - 1) + .0015 * sin(i * 2.3),
             'y': start[1] + (end[1] - start[1]) * i / (count - 1) + .0015 * cos(i * 1.7)}
            for i in range(count)]


CONTINUOUS_E = [sum((pointer_line(start, end) for start, end in zip(
    [(.64, .2), (.32, .2), (.32, .43), (.56, .43), (.32, .43), (.32, .72)],
    [(.32, .2), (.32, .43), (.56, .43), (.32, .43), (.32, .72), (.64, .72)],
)), [])]
CURVED_E = [[
    *pointer_line((.4, .46), (.6, .46)),
    *({'x': .46 + .18 * cos(-.15 - 5 * i / 79),
       'y': .46 + .18 * sin(-.15 - 5 * i / 79)} for i in range(80)),
]]


def sampled(drawing):
    """Model the short segments emitted by a pointermove stream."""
    return [[point for first, second in zip(path, path[1:])
             for point in ({'x': first['x'] + (second['x'] - first['x']) * step / 5,
                            'y': first['y'] + (second['y'] - first['y']) * step / 5}
                           for step in range(5))] + [path[-1]] for path in drawing]


def wide_canvas(drawing):
    """Map a normal letter to the wide, short writing row used in the page."""
    return [[{'x': .26 + (point['x'] - .3) * .16, 'y': point['y']}
             for point in path] for path in drawing]


class PrescribedHandwritingCaseTests(SimpleTestCase):
    def test_lesson7_rows_accept_only_the_requested_case(self):
        self.assertTrue(_lesson7_gawain2c_row_is_recognizable(CAPITAL_I, 0))
        self.assertFalse(_lesson7_gawain2c_row_is_recognizable(CAPITAL_I, 1))
        self.assertTrue(_lesson7_gawain2c_row_is_recognizable(LOWERCASE_I, 1))
        self.assertFalse(_lesson7_gawain2c_row_is_recognizable(LOWERCASE_I[:1], 1))

    def test_lesson8_rows_accept_only_the_requested_case(self):
        self.assertTrue(is_recognizable_single_e(CAPITAL_E, uppercase=True))
        self.assertFalse(is_recognizable_single_e(CAPITAL_E, uppercase=False))
        self.assertTrue(is_recognizable_single_e(LOWERCASE_E, uppercase=False))
        self.assertFalse(is_recognizable_single_e(LOWERCASE_E, uppercase=True))
        self.assertTrue(is_recognizable_single_e(sampled(CAPITAL_E), uppercase=True))
        self.assertTrue(is_recognizable_single_e(sampled(LOWERCASE_E), uppercase=False))
        self.assertTrue(is_recognizable_single_e(CONTINUOUS_E, uppercase=True))
        self.assertFalse(is_recognizable_single_e(CONTINUOUS_E, uppercase=False))
        self.assertTrue(is_recognizable_single_e(sampled(CONTINUOUS_E), uppercase=True))
        self.assertTrue(is_recognizable_single_e(CURVED_E, uppercase=False))
        self.assertFalse(is_recognizable_single_e(CURVED_E, uppercase=True))
        self.assertTrue(is_recognizable_single_e(wide_canvas(CONTINUOUS_E), uppercase=True))
        self.assertFalse(is_recognizable_single_e(wide_canvas(CURVED_E), uppercase=True))
        self.assertTrue(is_recognizable_single_e(wide_canvas(CURVED_E), uppercase=False))

    def test_lesson7_completion_does_not_play_magaling(self):
        template = (Path(__file__).parent / 'templates/pabasa_app/lesson_7_gawain_2c_page.html').read_text(encoding='utf-8')
        self.assertNotIn('Magaling!', template)


class PrescribedHandwritingProgressTests(TestCase):
    def setUp(self):
        school = School.objects.create(name='Handwriting Case School', code='HW-CASE')
        self.student = User.objects.create(
            custom_id='HW-CASE-STUDENT', role='student', first_name='Case', last_name='Learner',
            sex='female', birth_month=1, birth_day=1, birth_year=2018,
            email='handwriting-case@example.test', password_hash='x', school_record=school,
        )
        prescribed_term_fixture(self.student)
        session = self.client.session
        session.update({'user_id': self.student.pk, 'user_role': 'student', 'email': self.student.email})
        session.save()

    def send(self, key, row, drawing):
        url = reverse('prescribed_activity_progress', kwargs={'activity_key': key})
        payload = {'row_index': row, 'current_index': row + 1, 'strokes': drawing}
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')

    def test_lesson7_lowercase_row_rejects_capital(self):
        key = 'lesson7-gawain2c'
        self.assertEqual(self.send(key, 0, CAPITAL_I).status_code, 200)
        self.assertEqual(self.send(key, 1, CAPITAL_I).status_code, 400)
        self.assertEqual(self.send(key, 1, LOWERCASE_I).status_code, 200)

    def test_lesson8_case_is_enforced_by_progress_endpoint(self):
        key = 'lesson8-gawain1'
        complete = reverse('prescribed_activity_complete', kwargs={'activity_key': key})
        self.assertEqual(self.send(key, 0, LOWERCASE_E).status_code, 400)
        self.assertEqual(self.client.post(complete, data='{}', content_type='application/json').status_code, 400)
        self.assertEqual(self.send(key, 0, CAPITAL_E).status_code, 200)
        self.assertEqual(self.send(key, 1, CAPITAL_E).status_code, 400)
        self.assertEqual(self.send(key, 1, LOWERCASE_E).status_code, 200)
        self.assertEqual(self.client.post(complete, data='{}', content_type='application/json').status_code, 200)

    def test_lesson8_accepts_touch_sampled_continuous_capital(self):
        self.assertEqual(self.send('lesson8-gawain1', 0, wide_canvas(CONTINUOUS_E)).status_code, 200)
