from django.test import SimpleTestCase

from .views import _lesson29_has_two_letter_regions, _lesson29_trace_is_recognizable


def stroke(points):
    return [{'x': x, 'y': y} for x, y in points]


class Lesson29TraceGroupingTests(SimpleTestCase):
    def test_two_side_by_side_letters_unlock_submission(self):
        traces = [
            stroke([(0.20, 0.2), (0.35, 0.8)]),
            stroke([(0.65, 0.2), (0.80, 0.8)]),
        ]

        self.assertTrue(_lesson29_has_two_letter_regions(traces))

    def test_missing_letter_does_not_unlock_submission(self):
        traces = [
            stroke([(0.20, 0.2), (0.35, 0.8)]),
            stroke([(0.30, 0.2), (0.45, 0.8)]),
        ]

        self.assertFalse(_lesson29_has_two_letter_regions(traces))

    def test_pp_accepts_a_simplified_but_structured_pair(self):
        traces = [
            stroke([(0.20, 0.20), (0.20, 0.65)]),
            stroke([(0.20, 0.22), (0.35, 0.22), (0.35, 0.42), (0.20, 0.42)]),
            stroke([(0.65, 0.30), (0.65, 0.80)]),
            stroke([(0.65, 0.35), (0.78, 0.35), (0.78, 0.52), (0.65, 0.52)]),
        ]

        self.assertTrue(_lesson29_trace_is_recognizable(traces, 'Pp'))

    def test_pp_rejects_unrelated_marks(self):
        traces = [
            stroke([(0.15, 0.20), (0.35, 0.70)]),
            stroke([(0.65, 0.20), (0.85, 0.70)]),
        ]

        self.assertFalse(_lesson29_trace_is_recognizable(traces, 'Pp'))

    def test_hh_accepts_a_simplified_but_structured_pair(self):
        traces = [
            stroke([(0.15, 0.20), (0.15, 0.72)]),
            stroke([(0.34, 0.20), (0.34, 0.72)]),
            stroke([(0.15, 0.46), (0.34, 0.46)]),
            stroke([(0.66, 0.20), (0.66, 0.78)]),
            stroke([(0.66, 0.48), (0.76, 0.40), (0.84, 0.48), (0.84, 0.62)]),
        ]

        self.assertTrue(_lesson29_trace_is_recognizable(traces, 'Hh'))

    def test_hh_accepts_an_h_with_a_steep_arch_finish(self):
        traces = [
            stroke([(0.15, 0.20), (0.15, 0.72)]),
            stroke([(0.34, 0.20), (0.34, 0.72)]),
            stroke([(0.15, 0.46), (0.34, 0.46)]),
            stroke([(0.66, 0.20), (0.66, 0.78)]),
            stroke([(0.66, 0.48), (0.70, 0.56), (0.73, 0.70)]),
        ]

        self.assertTrue(_lesson29_trace_is_recognizable(traces, 'Hh'))

    def test_hh_rejects_unrelated_marks(self):
        traces = [
            stroke([(0.15, 0.20), (0.35, 0.72)]),
            stroke([(0.34, 0.20), (0.15, 0.72)]),
            stroke([(0.66, 0.20), (0.84, 0.72)]),
        ]

        self.assertFalse(_lesson29_trace_is_recognizable(traces, 'Hh'))

    def test_hh_rejects_two_uppercase_h_letters(self):
        traces = [
            stroke([(0.15, 0.20), (0.15, 0.72)]),
            stroke([(0.34, 0.20), (0.34, 0.72)]),
            stroke([(0.15, 0.46), (0.34, 0.46)]),
            stroke([(0.66, 0.20), (0.66, 0.72)]),
            stroke([(0.84, 0.20), (0.84, 0.72)]),
            stroke([(0.66, 0.46), (0.84, 0.46)]),
        ]

        self.assertFalse(_lesson29_trace_is_recognizable(traces, 'Hh'))
