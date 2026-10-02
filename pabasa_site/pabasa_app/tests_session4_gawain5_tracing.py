from django.test import SimpleTestCase

from .handwriting_validation import is_recognizable_session4_pair, segment_session4_trace_groups


def stroke(points):
    return [{'x': x, 'y': y} for x, y in points]


class Session4Gawain5TracingValidationTests(SimpleTestCase):
    def test_valid_bb_pair_with_separate_strokes(self):
        value = [
            stroke([(0.15, 0.2), (0.15, 0.8), (0.28, 0.2), (0.28, 0.45)]),
            stroke([(0.15, 0.5), (0.28, 0.75)]),
            stroke([(0.52, 0.3), (0.52, 0.8), (0.66, 0.55)]),
        ]
        self.assertTrue(is_recognizable_session4_pair(value, 'Bb'))

    def test_valid_bb_pair_can_be_one_continuous_path(self):
        value = [stroke([
            (0.15, 0.8), (0.15, 0.2), (0.28, 0.2), (0.28, 0.45),
            (0.15, 0.5), (0.28, 0.75), (0.52, 0.3), (0.52, 0.8),
            (0.66, 0.55),
        ])]
        self.assertTrue(is_recognizable_session4_pair(value, 'Bb'))

    def test_incomplete_or_malformed_trace_fails(self):
        self.assertFalse(is_recognizable_session4_pair([stroke([(0.2, 0.2), (0.2, 0.8)])], 'Bb'))
        self.assertFalse(is_recognizable_session4_pair([{'x': 0.1}], 'Bb'))

    def test_twelve_strokes_segment_into_three_bb_groups(self):
        payload = []
        for base in (0.14, 0.39, 0.60):
            for offset in (0.0, 0.025, 0.055, 0.10):
                payload.append(stroke([(base + offset, 0.2), (base + offset, 0.8)]))
        groups = segment_session4_trace_groups(payload, 3)
        self.assertEqual([len(group) for group in groups], [4, 4, 4])
        self.assertTrue(all(is_recognizable_session4_pair(group, 'Bb') for group in groups))

    def test_segmenter_accepts_the_endpoint_normalized_tuple_payload(self):
        payload = []
        for base in (0.14, 0.39, 0.60):
            for offset in (0.0, 0.025, 0.055, 0.10):
                payload.append([(base + offset, 0.2), (base + offset, 0.8)])
        groups = segment_session4_trace_groups(payload, 3)
        self.assertEqual([len(group) for group in groups], [4, 4, 4])

    def test_invalid_group_rejects_the_submission(self):
        payload = []
        for base in (0.14, 0.39, 0.60):
            for offset in (0.0, 0.025, 0.055, 0.08):
                payload.append(stroke([(base + offset, 0.2), (base + offset, 0.8)]))
        payload[4:8] = [stroke([(0.38 + offset, 0.400), (0.38 + offset, 0.401)]) for offset in (0.0, 0.005, 0.010, 0.015)]
        groups = segment_session4_trace_groups(payload, 3)
        self.assertFalse(all(is_recognizable_session4_pair(group, 'Bb') for group in groups))
