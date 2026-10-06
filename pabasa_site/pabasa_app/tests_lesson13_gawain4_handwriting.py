from django.test import SimpleTestCase

from .handwriting_validation import is_recognizable_lesson13_pair, segment_lesson13_trace_groups


def stroke(points):
    return [{'x': x, 'y': y} for x, y in points]


class Lesson13Gawain4HandwritingTests(SimpleTestCase):
    def test_three_uppercase_l_groups_use_two_strokes_each(self):
        value = []
        for base in (0.15, 0.40, 0.65):
            value.extend([
                stroke([(base, 0.16), (base, 0.45), (base, 0.82)]),
                stroke([(base, 0.82), (base + 0.20, 0.82)]),
            ])
        groups = segment_lesson13_trace_groups(value, 'L', 3)
        self.assertEqual([len(group) for group in groups], [2, 2, 2])
        self.assertTrue(all(is_recognizable_lesson13_pair(group, 'L') for group in groups))

    def test_uppercase_l_allows_small_gap_and_wobble(self):
        value = [stroke([(0.30, 0.17), (0.302, 0.46), (0.304, 0.80)]), stroke([(0.31, 0.79), (0.40, 0.805), (0.52, 0.80)])]
        self.assertTrue(is_recognizable_lesson13_pair(value, 'L'))

    def test_uppercase_l_accepts_short_visible_feet(self):
        for width in (0.057, 0.050, 0.044, 0.040):
            with self.subTest(width=width):
                value = [stroke([(0.30, 0.16), (0.30, 0.82)]), stroke([(0.30, 0.82), (0.30 + width, 0.82)])]
                self.assertTrue(is_recognizable_lesson13_pair(value, 'L'))

    def test_uppercase_l_rejects_extremely_tiny_foot(self):
        value = [stroke([(0.30, 0.16), (0.30, 0.82)]), stroke([(0.30, 0.82), (0.31, 0.82)])]
        self.assertFalse(is_recognizable_lesson13_pair(value, 'L'))

    def test_one_stroke_uppercase_l_is_rejected(self):
        value = [stroke([(0.30, 0.16), (0.30, 0.45), (0.30, 0.82), (0.42, 0.82), (0.52, 0.82)])]
        self.assertFalse(is_recognizable_lesson13_pair(value, 'L'))

    def test_reversed_uppercase_l_rejected(self):
        value = [stroke([(0.30, 0.82), (0.30, 0.45), (0.30, 0.16)]), stroke([(0.52, 0.82), (0.30, 0.82)])]
        self.assertFalse(is_recognizable_lesson13_pair(value, 'L'))

    def test_incomplete_or_wrong_direction_l_rejected(self):
        self.assertFalse(is_recognizable_lesson13_pair([stroke([(0.30, 0.82), (0.30, 0.16)]), stroke([(0.30, 0.82), (0.52, 0.82)])], 'L'))
        self.assertFalse(is_recognizable_lesson13_pair([stroke([(0.30, 0.16), (0.30, 0.82)]), stroke([(0.52, 0.82), (0.30, 0.82)])], 'L'))

    def test_valid_lowercase_l(self):
        self.assertTrue(is_recognizable_lesson13_pair([stroke([(0.35, 0.18), (0.35, 0.48), (0.36, 0.82)])], 'l'))

    def test_too_short_lowercase_l_rejected(self):
        self.assertFalse(is_recognizable_lesson13_pair([stroke([(0.35, 0.42), (0.35, 0.52)])], 'l'))

    def test_valid_uppercase_k(self):
        value = [stroke([(0.30, 0.16), (0.30, 0.48), (0.30, 0.82)]), stroke([(0.30, 0.49), (0.52, 0.17)]), stroke([(0.30, 0.49), (0.54, 0.82)])]
        self.assertTrue(is_recognizable_lesson13_pair(value, 'K'))

    def test_missing_diagonal_k_rejected(self):
        value = [stroke([(0.30, 0.16), (0.30, 0.48), (0.30, 0.82)]), stroke([(0.30, 0.49), (0.52, 0.17)])]
        self.assertFalse(is_recognizable_lesson13_pair(value, 'K'))

    def test_valid_lowercase_k(self):
        value = [stroke([(0.35, 0.22), (0.35, 0.50), (0.35, 0.82)]), stroke([(0.35, 0.51), (0.55, 0.30)]), stroke([(0.35, 0.51), (0.56, 0.82)])]
        self.assertTrue(is_recognizable_lesson13_pair(value, 'k'))

    def test_k_accepts_reversed_diagonal_endpoint_order(self):
        value = [stroke([(0.30, 0.16), (0.30, 0.48), (0.30, 0.82)]), stroke([(0.52, 0.17), (0.30, 0.49)]), stroke([(0.54, 0.82), (0.30, 0.49)])]
        self.assertTrue(is_recognizable_lesson13_pair(value, 'K'))

    def test_lowercase_k_accepts_reversed_diagonal_endpoint_order(self):
        value = [stroke([(0.35, 0.22), (0.35, 0.50), (0.35, 0.82)]), stroke([(0.55, 0.30), (0.35, 0.51)]), stroke([(0.56, 0.82), (0.35, 0.51)])]
        self.assertTrue(is_recognizable_lesson13_pair(value, 'k'))

    def test_k_accepts_short_diagonals_and_a_crooked_stem(self):
        value = [stroke([(0.30, 0.17), (0.305, 0.48), (0.32, 0.80)]), stroke([(0.32, 0.50), (0.36, 0.43)]), stroke([(0.32, 0.50), (0.365, 0.57)])]
        self.assertTrue(is_recognizable_lesson13_pair(value, 'K'))

    def test_k_accepts_small_connection_gaps_and_uneven_diagonals(self):
        value = [stroke([(0.35, 0.18), (0.35, 0.50), (0.35, 0.80)]), stroke([(0.35, 0.47), (0.39, 0.30)]), stroke([(0.35, 0.54), (0.48, 0.78)])]
        self.assertTrue(is_recognizable_lesson13_pair(value, 'k'))

    def test_random_scribble_rejected(self):
        value = [stroke([(0.20, 0.20), (0.45, 0.70), (0.20, 0.70), (0.45, 0.20), (0.20, 0.20), (0.45, 0.70)])]
        self.assertFalse(is_recognizable_lesson13_pair(value, 'L'))
