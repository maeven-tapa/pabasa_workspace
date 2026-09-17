"""Server-side stroke validation for Lesson 7 Gawain 2C only."""
from math import hypot


def normalize_strokes(value):
    if not isinstance(value, list) or not value or len(value) > 40:
        return None
    result = []
    for stroke in value:
        # A lowercase i dot can legitimately be a single deliberate tap.
        # The full Ii structure is still required below, so a tap alone cannot pass.
        if not isinstance(stroke, list) or not 1 <= len(stroke) <= 500:
            return None
        points = []
        for point in stroke:
            if not isinstance(point, dict) or not all(isinstance(point.get(key), (int, float)) for key in ('x', 'y')):
                return None
            x, y = float(point['x']), float(point['y'])
            if not (0 <= x <= 1 and 0 <= y <= 1):
                return None
            points.append((x, y))
        result.append(points)
    return result


def _direction_runs(stroke):
    """Extract horizontal and vertical runs, including runs in one connected stroke."""
    runs, direction, points = [], None, []
    for start, end in zip(stroke, stroke[1:]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        if hypot(dx, dy) < .003:
            continue
        current = 'h' if abs(dx) >= abs(dy) else 'v'
        if direction is not None and current != direction:
            runs.append((direction, points))
            points = [start]
        elif not points:
            points = [start]
        points.append(end)
        direction = current
    if direction is not None and points:
        runs.append((direction, points))
    return runs


def is_recognizable_ii(value):
    strokes = normalize_strokes(value)
    if strokes is None:
        return False

    horizontal, vertical, dots, shapes = [], [], [], []
    for stroke in strokes:
        xs, ys = zip(*stroke)
        width, height = max(xs) - min(xs), max(ys) - min(ys)
        length = sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(stroke, stroke[1:]))
        shapes.append({
            'x': sum(xs) / len(xs), 'min_y': min(ys), 'max_y': max(ys),
            'width': width, 'height': height, 'length': length,
        })
        # A dot is a tap or a very compact mark; an I crossbar is not a dot.
        if ((len(stroke) <= 2 and length <= .02) or
                (length <= .04 and width <= .025 and height <= .025)):
            dots.append((sum(xs) / len(xs), sum(ys) / len(ys)))
        # Whole-stroke checks keep naturally wobbly, short child handwriting
        # from being split into too many tiny directional runs.
        if width >= .008 and width >= height * 1.15:
            horizontal.append((min(xs), max(xs), sum(ys) / len(ys)))
        if height >= .04 and height >= width * 1.15:
            vertical.append((min(ys), max(ys), sum(xs) / len(xs)))
        for direction, run in _direction_runs(stroke):
            rx, ry = zip(*run)
            run_width, run_height = max(rx) - min(rx), max(ry) - min(ry)
            if direction == 'h' and run_width >= .008:
                horizontal.append((min(rx), max(rx), sum(ry) / len(ry)))
            if direction == 'v' and run_height >= .04:
                vertical.append((min(ry), max(ry), sum(rx) / len(rx)))

    for top in horizontal:
        for bottom in horizontal:
            if bottom[2] - top[2] < .08:
                continue
            for upper in vertical:
                if upper[0] > top[2] + .10 or upper[1] < bottom[2] - .10:
                    continue
                if not (top[0] - .06 <= upper[2] <= top[1] + .06 and bottom[0] - .06 <= upper[2] <= bottom[1] + .06):
                    continue
                for lower in vertical:
                    height = lower[1] - lower[0]
                    if abs(lower[2] - upper[2]) < .008 or height < .04:
                        continue
                    if any(dot_y < lower[0] - .001 and lower[0] - dot_y <= max(.42, height * 1.9) and abs(dot_x - lower[2]) <= max(.09, height * .7) for dot_x, dot_y in dots):
                        return True

    # A child may draw the capital I as one continuous top-bar → stem →
    # bottom-bar stroke.  Recognise that structure from its total path length
    # when touch-point direction changes are noisy.
    tall = [shape for shape in shapes if shape['height'] >= .04 and shape['height'] >= shape['width'] * 1.1]
    compact = [shape for shape in shapes if shape['length'] <= .10 and shape['width'] <= .06 and shape['height'] <= .06]
    for upper in tall:
        has_two_bars = upper['width'] >= .012 and upper['length'] >= upper['height'] + (upper['width'] * 1.5)
        if not has_two_bars:
            continue
        for lower in tall:
            if lower is upper or abs(lower['x'] - upper['x']) < .006:
                continue
            if any(
                dot['min_y'] < lower['min_y'] - .001
                and lower['min_y'] - dot['min_y'] <= max(.42, lower['height'] * 1.9)
                and abs(dot['x'] - lower['x']) <= max(.10, lower['height'] * .75)
                for dot in compact
            ):
                return True

    # Pointer devices can report a child's short I crossbars with too few
    # samples to survive directional-run extraction.  Keep the full Ii
    # structure requirement, but accept a clearly taller capital stem beside a
    # lowercase stem with its own dot.  A lone vertical line, an undotted i,
    # and ordinary scribbles still cannot satisfy this branch.
    for upper in tall:
        for lower in tall:
            if lower is upper or upper['height'] < max(.10, lower['height'] * 1.25):
                continue
            if abs(lower['x'] - upper['x']) < .015:
                continue
            if any(
                dot['min_y'] < lower['min_y'] - .001
                and lower['min_y'] - dot['min_y'] <= max(.50, lower['height'] * 2.1)
                and abs(dot['x'] - lower['x']) <= max(.12, lower['height'] * .8)
                for dot in compact
            ):
                return True
    return False
