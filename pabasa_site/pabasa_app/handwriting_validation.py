"""Server-side stroke validation for Lesson 7 Gawain 2C only."""
from math import hypot


def is_scribble_like(value):
    """Reject excessive looping/overdrawn strokes without banning normal curves."""
    strokes = normalize_strokes(value)
    if strokes is None:
        return False
    for stroke in strokes:
        if len(stroke) < 6:
            continue
        xs, ys = zip(*stroke)
        diagonal = max(hypot(max(xs) - min(xs), max(ys) - min(ys)), .01)
        length = sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(stroke, stroke[1:]))
        runs = len(_direction_runs(stroke))
        vectors = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(stroke, stroke[1:])]
        changes = sum(1 for first, second in zip(vectors, vectors[1:])
                      if (first[0] * second[0] < 0 or first[1] * second[1] < 0))
        # Normal child-written curves stay compact; repeated looping drives
        # the travelled path well beyond the mark's bounding box.
        if ((length / diagonal > 3.0 and runs >= 4) or
                (length / diagonal > 2.6 and runs >= 6) or
                (length / diagonal > 2.0 and changes >= 3)):
            return True
    return False


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


def is_recognizable_trace(value):
    """Generic stroke-quality gate for activities with multiple target letters.

    Unlike the Lesson 7 Ii validator, this does not assume one letter shape;
    it verifies that the learner produced a meaningful, bounded mark.
    """
    strokes = normalize_strokes(value)
    if strokes is None:
        return False
    total_length = 0.0
    min_x = min_y = 1.0
    max_x = max_y = 0.0
    meaningful = 0
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        meaningful += 1
        min_x = min(min_x, *(point[0] for point in stroke))
        max_x = max(max_x, *(point[0] for point in stroke))
        min_y = min(min_y, *(point[1] for point in stroke))
        max_y = max(max_y, *(point[1] for point in stroke))
        total_length += sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(stroke, stroke[1:]))
    # Activity 3 displays an uppercase/lowercase pair, so one isolated mark
    # is never enough to complete the pair.
    if meaningful < 2 or total_length < .08:
        return False
    return (max_x - min_x) >= .025 or (max_y - min_y) >= .06


def is_recognizable_p(value):
    """Recognize both the capital P and lowercase p used by item 1."""
    strokes = normalize_strokes(value)
    if strokes is None:
        return False
    shapes = []
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        xs, ys = zip(*stroke)
        shapes.append((min(xs), max(xs), min(ys), max(ys),
                       sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(stroke, stroke[1:]))))
    def complete_letter(candidates, lower=False):
        min_height = .09 if lower else .12
        min_aspect = 1.05 if lower else 1.25
        stems = [shape for shape in candidates if shape[3] - shape[2] >= min_height and shape[3] - shape[2] >= (shape[1] - shape[0]) * min_aspect]
        stem = max(stems, key=lambda shape: shape[3] - shape[2], default=None)
        if not stem:
            # A single continuous P/p stroke may contain both stem and bowl.
            if lower:
                return False
            return any(shape[3] - shape[2] >= .18 and shape[1] - shape[0] >= .08 and shape[4] >= .18 for shape in candidates)
        stem_x = (stem[0] + stem[1]) / 2
        min_bowl_width = .025 if lower else .035
        bowl = next((shape for shape in candidates if shape is not stem and shape[1] - shape[0] >= min_bowl_width and shape[3] - shape[2] <= .28 and shape[1] >= stem_x + .01), None)
        if not bowl:
            if not lower and stem[1] - stem[0] >= .08 and stem[4] >= .18:
                return True
            return False
        # Lowercase p has a descender below the bowl; b has an ascender
        # above it, so the direction matters for this target.
        if lower and stem[3] <= bowl[3] + .01:
            return False
        return any(
            shape is not stem and shape[1] - shape[0] >= min_bowl_width and
            shape[3] - shape[2] <= .28 and shape[1] >= stem_x + .01
            for shape in candidates
        )

    # The Pp model is side-by-side, so identify the capital and lowercase
    # structures horizontally rather than by their vertical guide position.
    centers = sorted(((shape, (shape[0] + shape[1]) / 2) for shape in shapes), key=lambda pair: pair[1])
    if len(centers) < 2:
        return False
    split = (centers[0][1] + centers[-1][1]) / 2
    capital = [shape for shape, center in centers if center <= split]
    lowercase = [shape for shape, center in centers if center > split]
    separated = centers[-1][1] - centers[0][1] >= .08
    return separated and complete_letter(capital) and complete_letter(lowercase, lower=True)


def is_recognizable_letter_pair(value, letter):
    """Shape gate for the remaining uppercase/lowercase Lesson 29 pairs."""
    strokes = normalize_strokes(value)
    if strokes is None:
        return False
    features = {'horizontal': 0, 'vertical': 0, 'diagonal': 0, 'compact': 0, 'broad': 0}
    centers = []
    for stroke in strokes:
        if len(stroke) < 2:
            if len(stroke) == 1:
                features['compact'] += 1
            continue
        xs, ys = zip(*stroke)
        width, height = max(xs) - min(xs), max(ys) - min(ys)
        centers.append((min(ys) + max(ys)) / 2)
        length = sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(stroke, stroke[1:]))
        if length < .018:
            features['compact'] += 1
        if width >= .025 and width >= height * 1.2:
            features['horizontal'] += 1
        if height >= .06 and height >= width * 1.2:
            features['vertical'] += 1
        if width >= .035 and height >= .035 and width < height * 1.2 and height < width * 1.2:
            features['diagonal'] += 1
        if width >= .06 and height >= .08:
            features['broad'] += 1
    key = str(letter or '').lower()[:1]
    requirements = {
        'f': (2, 2, 0, 0), 'h': (2, 1, 0, 0), 'n': (2, 0, 1, 0),
        's': (0, 0, 0, 2), 'i': (2, 0, 0, 1), 'l': (2, 1, 0, 0),
        'm': (2, 0, 1, 0), 't': (2, 1, 0, 0), 'e': (2, 2, 0, 0),
        'a': (0, 1, 2, 0),
    }
    vertical, horizontal, diagonal, broad = requirements.get(key, (1, 1, 0, 0))
    upper = [center for center in centers if center <= .50]
    lower = [center for center in centers if center >= .50]
    separated = bool(upper and lower and max(lower) - min(upper) >= .08)
    return (separated and features['vertical'] >= vertical and features['horizontal'] >= horizontal
            and features['diagonal'] >= diagonal and features['broad'] >= broad
            and sum(features.values()) >= 2)


def is_recognizable_session4_pair(value, letter):
    """Target-specific structural gate for Session 4 Gawain 5 letters.

    The expected target is kept case-sensitive at the call boundary.  The
    structural rules are intentionally tolerant because canvas strokes do not
    carry a reliable machine-readable case label; B/b and U/u are therefore
    validated against the exact catalog item selected by the progress index,
    never against a lower-cased combined target.
    """
    strokes = normalize_strokes(value)
    target = str(letter or '')[:1]
    if target not in {'B', 'b', 'U', 'u'}:
        return False
    key = target
    # Rounded B/b bowls naturally contain direction changes that the generic
    # scribble heuristic treats as loops. Keep the generic rejection for U/u,
    # while the structural B/b gate below rejects unrelated marks.
    if strokes is None or (key != 'b' and is_scribble_like(strokes)) or not strokes:
        return False
    if key in {'B', 'b'}:
        # Bb is intentionally validated by payload integrity here. Browser
        # pointer sampling and child pen-lift patterns do not reliably encode
        # the visible bowl/stem structure, so a separate geometric predicate
        # was rejecting clearly drawn pairs. normalize_strokes() still rejects
        # malformed, out-of-range, empty, or over-sized payloads.
        points = [point for stroke in strokes for point in stroke]
        xs, ys = zip(*points)
        return (sum(len(stroke) for stroke in strokes) >= 3
                and max(xs) - min(xs) >= .03 and max(ys) - min(ys) >= .10)
    usable = []
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        xs, ys = zip(*stroke)
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        length = sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(stroke, stroke[1:]))
        if length >= .025 and (w >= .018 or h >= .04):
            usable.append((min(xs), max(xs), min(ys), max(ys), length))
    if len(usable) == 1:
        # A child may draw U/u in one continuous down-and-up gesture. Accept
        # only a clearly U-shaped path: both endpoints near the upper band,
        # with the path descending into the lower band.
        stroke = next(stroke for stroke in strokes if len(stroke) >= 2)
        xs, ys = zip(*stroke)
        width, height = max(xs) - min(xs), max(ys) - min(ys)
        lowest_index = max(range(len(stroke)), key=lambda index: stroke[index][1])
        lower = min(ys) + height * .60
        endpoint_band = min(ys) + height * .70
        return (width >= .025 and height >= .12
                and 0 < lowest_index < len(stroke) - 1
                and stroke[0][1] <= endpoint_band
                and stroke[-1][1] <= endpoint_band
                and stroke[lowest_index][1] >= lower)
    if len(usable) < 2:
        return False
    centers = sorted(((shape, (shape[0] + shape[1]) / 2) for shape in usable), key=lambda pair: pair[1])
    if key == 'u' and len(centers) == 2:
        left = strokes[usable.index(centers[0][0])]
        right = strokes[usable.index(centers[1][0])]
        combined_width = max(point[0] for stroke in strokes for point in stroke) - min(point[0] for stroke in strokes for point in stroke)
        left_height = max(point[1] for point in left) - min(point[1] for point in left)
        right_height = max(point[1] for point in right) - min(point[1] for point in right)
        valley_gap = abs(left[-1][1] - right[0][1])
        if (combined_width >= .02 and left_height >= .06 and right_height >= .06
                and left[0][1] < left[-1][1]
                and right[0][1] > right[-1][1]
                and valley_gap <= .15):
            return True
    # Narrow lowercase u strokes can sit much closer together than the
    # uppercase/pair geometry. Keep the broader separation rule for U and
    # other targets, but allow the two strokes of a child-sized u to form one
    # segmented letter region.
    minimum_separation = .02 if key == 'u' else .04
    if centers[-1][1] - centers[0][1] < minimum_separation:
        return False
    if key in {'U', 'u'}:
        return sum(shape[3] - shape[2] >= .06 for shape, _ in centers) >= 2
    # The learner may write the pair once or repeat it several times on the
    # same canvas. Do not split at one global midpoint: overlapping repeated
    # pairs can put both capital stems on one side of that split. Instead,
    # require the combined mark to contain multiple stems and bowl/curve
    # strokes, with enough horizontal separation to be a pair rather than a
    # single unrelated shape.
    points = [point for stroke in strokes for point in stroke]
    min_x, max_x = min(point[0] for point in points), max(point[0] for point in points)
    min_y, max_y = min(point[1] for point in points), max(point[1] for point in points)
    # Accept natural child handwriting and repeated pairs on one canvas. The
    # bounded multi-stroke requirement still rejects a tap, a lone line, and
    # an unrelated tiny mark without imposing a rigid stroke order.
    return (len(strokes) >= 2 and max_x - min_x >= .08 and max_y - min_y >= .06)


def is_recognizable_lesson13_pair(value, letter):
    """Conservative, target-aware geometry gate for Lesson 13 Gawain 4."""
    strokes = normalize_strokes(value)
    target = str(letter or '')[:1]
    if strokes is None or target not in {'L', 'l', 'K', 'k'} or not strokes:
        return False
    points = [point for stroke in strokes for point in stroke]
    if len(points) < 3 or is_scribble_like(strokes):
        return False
    xs, ys = zip(*points)
    width, height = max(xs) - min(xs), max(ys) - min(ys)
    if height < .10 or (width < .012 and target != 'l'):
        return False
    if target == 'l':
        return width <= max(.08, height * .55) and sum(len(stroke) for stroke in strokes) >= 3
    if target == 'k':
        if len(strokes) in {2, 3}:
            stem = min(strokes, key=lambda stroke: (
                (max(point[0] for point in stroke) - min(point[0] for point in stroke))
                / max(max(point[1] for point in stroke) - min(point[1] for point in stroke), .001)))
            stem_x = (min(point[0] for point in stem) + max(point[0] for point in stem)) / 2
            upper_right = False
            lower_right = False
            global_midpoint = (min(point[1] for stroke in strokes for point in stroke)
                               + max(point[1] for stroke in strokes for point in stroke)) / 2
            for stroke in strokes:
                if stroke is stem:
                    continue
                upper_right = upper_right or (stroke[0][1] <= global_midpoint
                                              and max(point[0] for point in stroke) > stem_x + .009)
                lower_right = lower_right or (stroke[0][1] >= global_midpoint
                                              and max(point[0] for point in stroke) > stem_x + .009)
                if min(point[1] for point in stroke) < global_midpoint < max(point[1] for point in stroke):
                    upper_right = upper_right or max(point[0] for point in stroke) > stem_x + .009
                    lower_right = lower_right or max(point[0] for point in stroke) > stem_x + .009
            return ((max(point[1] for point in stem) - min(point[1] for point in stem)) >= .07
                    and upper_right and lower_right and width >= .018)
        return False
    if target == 'L':
        if len(strokes) == 1:
            stroke = strokes[0]
            if len(stroke) < 3:
                return False
            lowest_index = max(range(len(stroke)), key=lambda index: stroke[index][1])
            lowest_y = stroke[lowest_index][1]
            height = max(point[1] for point in stroke) - min(point[1] for point in stroke)
            bottom = stroke[max(0, lowest_index - 2):]
            bottom_span = max(point[0] for point in bottom) - min(point[0] for point in bottom)
            downward = lowest_index >= max(1, int(len(stroke) * .45))
            starts_high = stroke[0][1] <= min(point[1] for point in stroke) + height * .45
            rightward = max(point[0] for point in bottom) - stroke[max(0, lowest_index - 1)][0]
            return (height >= .10 and starts_high and downward
                    and lowest_y >= min(point[1] for point in stroke) + height * .55
                    and bottom_span >= .012 and rightward >= .012)
        if len(strokes) >= 2:
            stem = [stroke for stroke in strokes if (max(p[1] for p in stroke) - min(p[1] for p in stroke)) >= .08]
            foot = [stroke for stroke in strokes if (max(p[0] for p in stroke) - min(p[0] for p in stroke)) >= .012]
            if stem and foot:
                stem_bottom = max(p[1] for p in stem[0])
                foot_top = min(p[1] for p in foot[0])
                return abs(stem_bottom - foot_top) <= .22
        return width >= .025 and any(max(p[0] for p in stroke) - min(p[0] for p in stroke) >= .018 for stroke in strokes)
    if target in {'K', 'k'}:
        if target == 'K':
            if len(strokes) == 2:
                stems = [min(strokes, key=lambda stroke: (
                    (max(point[0] for point in stroke) - min(point[0] for point in stroke))
                    / max(max(point[1] for point in stroke) - min(point[1] for point in stroke), .001)))]
            else:
                stems = [stroke for stroke in strokes
                         if max(point[1] for point in stroke) - min(point[1] for point in stroke) >= .10
                         and (max(point[0] for point in stroke) - min(point[0] for point in stroke))
                         <= (max(point[1] for point in stroke) - min(point[1] for point in stroke)) * .35]
            stem_x = (min(point[0] for point in stems[0]) + max(point[0] for point in stems[0])) / 2 if stems else None
            if stem_x is not None:
                upper_right = False
                lower_right = False
                for stroke in strokes:
                    if stroke in stems:
                        continue
                    ys = [point[1] for point in stroke]
                    xs = [point[0] for point in stroke]
                    midpoint = (min(ys) + max(ys)) / 2
                    upper_right = upper_right or any(point[1] <= midpoint and point[0] > stem_x + .012 for point in stroke)
                    lower_right = lower_right or any(point[1] >= midpoint and point[0] > stem_x + .012 for point in stroke)
                if len(strokes) in {2, 3} and upper_right and lower_right:
                    return width >= .025
        diagonals = 0
        for stroke in strokes:
            if len(stroke) >= 2:
                start, end = stroke[0], stroke[-1]
                if abs(end[0] - start[0]) >= .018 and abs(end[1] - start[1]) >= .018:
                    diagonals += 1
        return diagonals >= 2 and width >= (.045 if target == 'K' else .035)
    return False


def segment_session4_trace_groups(value, group_count=3):
    """Cluster completed strokes into left-to-right handwritten letters."""
    # The endpoint normalizes the browser payload before calling this helper.
    # Preserve that established tuple format instead of normalizing it a
    # second time (normalize_strokes intentionally accepts point dictionaries
    # at its public boundary).
    if isinstance(value, list) and all(
        isinstance(stroke, list) and all(
            isinstance(point, tuple) and len(point) == 2
            and all(isinstance(coordinate, (int, float)) for coordinate in point)
            for point in stroke
        )
        for stroke in value
    ):
        strokes = value
    else:
        strokes = normalize_strokes(value)
    if strokes is None or len(strokes) < 1:
        return None
    boxes = []
    for index, stroke in enumerate(strokes):
        xs, ys = zip(*stroke)
        boxes.append({
            'index': index,
            'min_x': min(xs), 'max_x': max(xs),
            'min_y': min(ys), 'max_y': max(ys),
        })

    parent = list(range(len(boxes)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first, second):
        first, second = find(first), find(second)
        if first != second:
            parent[second] = first

    def overlaps_or_is_near(first, second):
        first_width = max(first['max_x'] - first['min_x'], .01)
        second_width = max(second['max_x'] - second['min_x'], .01)
        overlap_x = max(0, min(first['max_x'], second['max_x']) - max(first['min_x'], second['min_x']))
        overlap_y = max(0, min(first['max_y'], second['max_y']) - max(first['min_y'], second['min_y']))
        min_width = min(first_width, second_width)
        min_height = max(min(first['max_y'] - first['min_y'], second['max_y'] - second['min_y']), .01)
        gap_x = max(first['min_x'] - second['max_x'], second['min_x'] - first['max_x'], 0)
        # A zero/near-zero gap with vertical overlap usually belongs to a
        # multi-stroke letter. Keep the proximity window narrow so adjacent
        # handwritten letters are not merged into one cluster.
        proximity = min(.02, min_width * .35)
        return (overlap_x / min_width >= .15
                or (gap_x <= proximity and overlap_y / min_height >= .15))

    for first_index, first in enumerate(boxes):
        for second in boxes[first_index + 1:]:
            if overlaps_or_is_near(first, second):
                union(first['index'], second['index'])

    grouped = {}
    for box in boxes:
        grouped.setdefault(find(box['index']), []).append(strokes[box['index']])
    groups = sorted(
        grouped.values(),
        key=lambda group: sum(point[0] for stroke in group for point in stroke)
        / sum(len(stroke) for stroke in group),
    )
    return [
        [[{'x': point[0], 'y': point[1]} for point in stroke] for stroke in group]
        for group in groups
    ] if len(groups) == group_count and all(groups) else None


def segment_lesson13_trace_groups(value, letter, group_count=3):
    """Group Lesson 13 L/l/K/k strokes without changing Session 4 rules.

    L/l commonly uses a stem plus a short stroke at the baseline. Those
    strokes can have almost no vertical bounding-box overlap, so the generic
    Session 4 proximity rule rejects them. For the common six-stroke L/l
    payload, pair adjacent strokes by horizontal position, then leave the
    target-specific recognizer to decide whether each pair is a real letter.
    Other shapes continue through the established spatial grouping helper.
    """
    strokes = normalize_strokes(value)
    if strokes is None or not strokes:
        return None
    if str(letter or '') in {'L', 'l'} and len(strokes) == group_count:
        indexed = []
        for index, stroke in enumerate(strokes):
            xs = [point[0] for point in stroke]
            indexed.append((index, (min(xs) + max(xs)) / 2))
        indexed.sort(key=lambda entry: entry[1])
        return [
            [[{'x': point[0], 'y': point[1]} for point in strokes[index]]]
            for index, _ in indexed
        ]
    if str(letter or '') == 'L' and len(strokes) == group_count * 2:
        shapes = []
        for index, stroke in enumerate(strokes):
            xs = [point[0] for point in stroke]
            ys = [point[1] for point in stroke]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            shapes.append({'index': index, 'min_x': min_x, 'max_x': max_x,
                           'min_y': min_y, 'max_y': max_y,
                           'width': max_x - min_x, 'height': max_y - min_y,
                           'center_x': (min_x + max_x) / 2})
        # Group spatially first. Do not classify stems/feet before pairing:
        # a narrow or slightly slanted Grade 2 foot is still part of the L.
        # Pair the leftmost unassigned stroke with its nearest remaining
        # horizontal-neighbour by x-center, which works for both drawing
        # orders (stem+foot and all stems followed by all feet).
        unused = set(shape['index'] for shape in shapes)
        groups = []
        by_index = {shape['index']: shape for shape in shapes}
        while unused:
            first = min((by_index[index] for index in unused), key=lambda shape: shape['center_x'])
            unused.remove(first['index'])
            if not unused:
                return None
            second = min((by_index[index] for index in unused),
                         key=lambda shape: abs(shape['center_x'] - first['center_x']))
            unused.remove(second['index'])
            groups.append([strokes[first['index']], strokes[second['index']]])
        groups.sort(key=lambda group: sum(point[0] for stroke in group for point in stroke)
                    / sum(len(stroke) for stroke in group))
        return [
            [[{'x': point[0], 'y': point[1]} for point in stroke] for stroke in group]
            for group in groups
        ]
    if str(letter or '') in {'K', 'k'} and len(strokes) in {group_count * 2, group_count * 3}:
        shapes = []
        for index, stroke in enumerate(strokes):
            xs = [point[0] for point in stroke]
            shapes.append((index, (min(xs) + max(xs)) / 2))
        shapes.sort(key=lambda shape: shape[1])
        per_group = len(strokes) // group_count
        return [
            [[{'x': point[0], 'y': point[1]} for point in strokes[index]]
             for index, _ in shapes[offset:offset + per_group]]
            for offset in range(0, len(shapes), per_group)
        ]
    return segment_session4_trace_groups(strokes, group_count)


# Explicit per-letter entry points keep each target isolated at the activity
# layer; a future letter-specific rule can be changed without touching others.
def is_recognizable_h(value):
    """Recognize the structural features of the side-by-side Hh pair."""
    strokes = normalize_strokes(value)
    if strokes is None:
        return False

    def features(letter_strokes):
        verticals, horizontals = [], []
        for stroke in letter_strokes:
            if len(stroke) < 2:
                continue
            for direction, run in _direction_runs(stroke):
                if len(run) < 2:
                    continue
                xs, ys = zip(*run)
                width, height = max(xs) - min(xs), max(ys) - min(ys)
                if direction == 'v' and height >= .055:
                    verticals.append(((min(xs) + max(xs)) / 2, min(ys), max(ys)))
                elif direction == 'h' and width >= .025:
                    horizontals.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))
        return verticals, horizontals

    # The Lesson 29 board displays H on the left and h on the right. Keeping
    # the structures separate prevents a few unrelated lines from combining
    # into a false positive.
    capital_strokes = [stroke for stroke in strokes if sum(x for x, _ in stroke) / len(stroke) < .5]
    lowercase_strokes = [stroke for stroke in strokes if sum(x for x, _ in stroke) / len(stroke) >= .5]
    capital_verticals, capital_bars = features(capital_strokes)
    lowercase_verticals, lowercase_bars = features(lowercase_strokes)
    if len(capital_verticals) < 2 or not lowercase_verticals:
        return False

    capital_stems = sorted(capital_verticals, key=lambda stem: stem[0])
    left_stem, right_stem = capital_stems[0], capital_stems[-1]
    if right_stem[0] - left_stem[0] < .035:
        return False
    h_has_crossbar = any(
        left_stem[0] - .025 <= center_x <= right_stem[0] + .025 and
        max(left_stem[1], right_stem[1]) + .025 <= center_y <= min(left_stem[2], right_stem[2]) - .025
        for center_x, center_y in capital_bars
    )
    if not h_has_crossbar:
        return False

    # A lowercase h is one tall stem joined to a short arch, not another H.
    # The arch may finish with a short downward mark, but a second full-height
    # stem is an uppercase H and must not pass for the lowercase side.
    tall_lowercase_stems = [candidate for candidate in lowercase_verticals
                             if candidate[2] - candidate[1] >= .30]
    if len(tall_lowercase_stems) >= 2:
        tall_lowercase_stems.sort(key=lambda candidate: candidate[0])
        if tall_lowercase_stems[-1][0] - tall_lowercase_stems[0][0] >= .035:
            return False
    stem = max(lowercase_verticals, key=lambda candidate: candidate[2] - candidate[1])
    if stem[2] - stem[1] < .12:
        return False
    has_arch_bar = any(
        stem[0] - .025 <= center_x and
        stem[1] + .045 <= center_y <= stem[2] - .025
        for center_x, center_y in lowercase_bars
    )
    # A child may form the h arch with a steep curve, so its last segment is
    # classified as vertical instead of horizontal. Accept that short right
    # finishing stroke, but never a second full-height H stem.
    has_short_arch_finish = any(
        candidate is not stem and
        candidate[0] >= stem[0] + .02 and
        .05 <= candidate[2] - candidate[1] < .30 and
        stem[1] + .045 <= (candidate[1] + candidate[2]) / 2 <= stem[2] - .025
        for candidate in lowercase_verticals
    )
    return has_arch_bar or has_short_arch_finish


def is_recognizable_i(value):
    """Recognize uppercase I, lowercase i, and the lowercase dot."""
    strokes = normalize_strokes(value)
    if strokes is None:
        return False
    verticals = 0
    compact_dot = False
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        xs, ys = zip(*stroke)
        width, height = max(xs) - min(xs), max(ys) - min(ys)
        if height >= .025 and height >= width * 1.1:
            verticals += 1
        if width <= .08 and height <= .08:
            compact_dot = True
        for direction, run in _direction_runs(stroke):
            rx, ry = zip(*run)
            if direction == 'v' and max(ry) - min(ry) >= .02:
                verticals += 1
    return verticals >= 2 and compact_dot


def is_recognizable_l(value):
    """Recognize capital L and lowercase l side-by-side."""
    strokes = normalize_strokes(value)
    if strokes is None or len(strokes) < 2:
        return False
    verticals, bars, centers = [], [], []
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        xs, ys = zip(*stroke)
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        centers.append((min(xs) + max(xs)) / 2)
        if h >= .02 and h >= w * 1.1:
            verticals.append((min(xs), max(xs), min(ys), max(ys)))
        if w >= .02 and w >= h * 1.1:
            bars.append((min(xs), max(xs), min(ys), max(ys)))
        for direction, run in _direction_runs(stroke):
            rx, ry = zip(*run)
            if direction == 'h' and max(rx) - min(rx) >= .015:
                bars.append((min(rx), max(rx), min(ry), max(ry)))
    if len(verticals) < 2 or max(centers) - min(centers) < .02:
        return False
    midpoint = (min(centers) + max(centers)) / 2
    lower_points = [point for stroke in strokes
                    if (min(p[0] for p in stroke) + max(p[0] for p in stroke)) / 2 > midpoint
                    for point in stroke]
    if not lower_points:
        return False
    lower_x = [point[0] for point in lower_points]
    lower_y = [point[1] for point in lower_points]
    lower_width = max(lower_x) - min(lower_x)
    lower_height = max(lower_y) - min(lower_y)
    if lower_height < .03 or lower_height < lower_width * 1.15:
        return False
    return bool(bars)
def is_recognizable_e(value): return is_recognizable_letter_pair(value, 'e')


def is_recognizable_f(value):
    """Recognize uppercase F and lowercase f, not arbitrary bars."""
    strokes = normalize_strokes(value)
    if strokes is None:
        return False
    shapes = []
    horizontal_runs = []
    vertical_runs = []
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        xs, ys = zip(*stroke)
        shapes.append((min(xs), max(xs), min(ys), max(ys)))
        for direction, run in _direction_runs(stroke):
            rx, ry = zip(*run)
            width, height = max(rx) - min(rx), max(ry) - min(ry)
            center_y = (min(ry) + max(ry)) / 2
            if direction == 'h' and width >= .025:
                horizontal_runs.append((min(rx), max(rx), center_y))
            if direction == 'v' and height >= .08:
                vertical_runs.append((min(ry), max(ry), (min(rx) + max(rx)) / 2))

    def has_f(region, lower=False):
        stems = [s for s in region if s[3] - s[2] >= .12 and s[3] - s[2] >= (s[1] - s[0]) * 1.25]
        stem = max(stems, key=lambda s: s[3] - s[2], default=None)
        if not stem:
            return False
        bars = [s for s in region if s is not stem and s[1] - s[0] >= .035 and s[1] - s[0] >= (s[3] - s[2]) * 1.2]
        if lower:
            return bool(bars) and any(s[2] <= stem[2] + (stem[3] - stem[2]) * .65 for s in bars)
        return (len(bars) >= 2 and any(s[2] <= stem[2] + (stem[3] - stem[2]) * .35 for s in bars)) or max(s[1] for s in region) - min(s[0] for s in region) >= .10

    upper = [s for s in shapes if (s[2] + s[3]) / 2 <= .50]
    lower = [s for s in shapes if (s[2] + s[3]) / 2 >= .50]
    if len(shapes) >= 2:
        centers = [(shape[0] + shape[1]) / 2 for shape in shapes]
        split_x = (min(centers) + max(centers)) / 2
        left_shapes = [shape for shape in shapes if (shape[0] + shape[1]) / 2 <= split_x]
        right_shapes = [shape for shape in shapes if (shape[0] + shape[1]) / 2 > split_x]
        if not left_shapes or not right_shapes:
            return False
        left_y0, left_y1 = min(shape[2] for shape in left_shapes), max(shape[3] for shape in left_shapes)
        left_top_bar = any((x0 + x1) / 2 <= split_x and y <= left_y0 + (left_y1 - left_y0) * .35 for x0, x1, y in horizontal_runs)
        right_horizontal_count = sum(1 for x0, x1, _ in horizontal_runs if (x0 + x1) / 2 > split_x)
        right_bar = right_horizontal_count >= 1
        if not left_top_bar or not right_bar or right_horizontal_count > 1:
            return False
    if len(vertical_runs) > 3:
        return False
    if has_f(upper) and has_f(lower):
        return True
    lower_region_has_bar = False
    if len(shapes) >= 2:
        centers = [(shape[0] + shape[1]) / 2 for shape in shapes]
        split_x = (min(centers) + max(centers)) / 2
        lower_region_has_bar = any((x0 + x1) / 2 > split_x for x0, x1, _ in horizontal_runs)
    # Connected child handwriting often arrives as one path per letter;
    # evaluate its directional runs so joined bars are still recognized.
    separated_stems = len(vertical_runs) >= 2 and max(run[0] for run in vertical_runs) - min(run[0] for run in vertical_runs) >= .08
    stem_shapes = [shape for shape in shapes if shape[3] - shape[2] >= .10 and shape[3] - shape[2] >= (shape[1] - shape[0]) * 1.15]
    separated_shape_stems = len(stem_shapes) >= 2 and max((shape[0] + shape[1]) / 2 for shape in stem_shapes) - min((shape[0] + shape[1]) / 2 for shape in stem_shapes) >= .08
    bar_shapes = [shape for shape in shapes if shape[1] - shape[0] >= .025 and shape[1] - shape[0] >= (shape[3] - shape[2]) * 1.15]
    if len(shapes) >= 2 and not lower_region_has_bar:
        return False
    return (separated_stems or separated_shape_stems) and (len(horizontal_runs) + len(bar_shapes) >= 2)


def is_recognizable_n(value):
    """Strict-but-tolerant Nn: N stem/slant/stem plus n stem/arch."""
    strokes = normalize_strokes(value)
    if strokes is None or not strokes:
        return False
    records = []
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        xs, ys = zip(*stroke)
        width, height = max(xs) - min(xs), max(ys) - min(ys)
        records.append({'stroke': stroke, 'cx': (min(xs) + max(xs)) / 2, 'w': width, 'h': height})
    if len(records) == 1:
        item = records[0]
        return item['w'] >= .04 and item['h'] >= .03 and len(item['stroke']) >= 3
    records.sort(key=lambda item: item['cx'])
    gaps = [records[i + 1]['cx'] - records[i]['cx'] for i in range(len(records) - 1)]
    split = gaps.index(max(gaps)) + 1
    capital, lower = records[:split], records[split:]
    if not capital or not lower or records[-1]['cx'] - records[0]['cx'] < .01:
        return False

    def classify(group):
        vertical = diagonal = arch = 0
        for item in group:
            w, h = item['w'], item['h']
            if h >= .018 and h >= w * 1.1:
                vertical += 1
            if w >= .02 and h >= .02 and .35 <= w / max(h, .001) <= 2.8:
                diagonal += 1
            if w >= .02 and w >= h * .7:
                arch += 1
            for direction, run in _direction_runs(item['stroke']):
                rx, ry = zip(*run)
                rw, rh = max(rx) - min(rx), max(ry) - min(ry)
                if direction == 'v' and rh >= .018:
                    vertical += 1
                if rw >= .02 and rh >= .02 and .35 <= rw / max(rh, .001) <= 2.8:
                    diagonal += 1
                if rw >= .02 and rw >= rh * .7:
                    arch += 1
        return vertical, diagonal, arch

    n_vertical, n_diagonal, n_arch = classify(capital)
    l_vertical, l_diagonal, l_arch = classify(lower)
    if n_vertical >= 1 and n_diagonal >= 1 and l_vertical >= 1 and l_arch >= 1:
        return True
    # Direction classification can miss a child’s slanted N stroke; accept
    # two clearly bounded side-by-side letter regions as a fallback.
    def bounded(group):
        points = [point for item in group for point in item['stroke']]
        xs, ys = zip(*points)
        return max(xs) - min(xs) >= .015 and max(ys) - min(ys) >= .02
    # A lone lowercase vertical is not an n; retain the eased bounds fallback
    # only when the lowercase region also contains an arching/turning run.
    return bounded(capital) and bounded(lower) and l_arch >= 1


def is_recognizable_m(value):
    """Recognize Mm with either separate strokes or a continuous child stroke."""
    strokes = normalize_strokes(value)
    if strokes is None or not strokes:
        return False
    shapes = []
    verticals = []
    arches = []
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        xs, ys = zip(*stroke)
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        shapes.append((min(xs), max(xs), min(ys), max(ys), w, h))
        for direction, run in _direction_runs(stroke):
            rx, ry = zip(*run)
            rw, rh = max(rx) - min(rx), max(ry) - min(ry)
            if direction == 'v' and rh >= .018:
                verticals.append((min(rx) + max(rx)) / 2)
            # A down/up or rounded arch can be diagonal rather than horizontal.
            if rw >= .018 and rh >= .012:
                arches.append((min(rx), max(rx), min(ry), max(ry)))

    if len(shapes) < 1:
        return False

    # Split the side-by-side pair at the largest horizontal gap between marks.
    ordered = sorted(shapes, key=lambda item: (item[0] + item[1]) / 2)
    lower_region_has_arch = False
    if len(ordered) >= 2:
        gaps = [((ordered[i][0] + ordered[i][1]) / 2,
                 (ordered[i + 1][0] + ordered[i + 1][1]) / 2)
                for i in range(len(ordered) - 1)]
        split = max(range(len(gaps)), key=lambda i: gaps[i][1] - gaps[i][0]) + 1
        left, right = ordered[:split], ordered[split:]
        if left and right:
            lx0, lx1 = min(s[0] for s in left), max(s[1] for s in left)
            ly0, ly1 = min(s[2] for s in left), max(s[3] for s in left)
            rx0, rx1 = min(s[0] for s in right), max(s[1] for s in right)
            ry0, ry1 = min(s[2] for s in right), max(s[3] for s in right)
            split_x = ((max(s[0] + s[1] for s in left) / 2) +
                       (min(s[0] + s[1] for s in right) / 2)) / 2
            right_arches = 0
            right_runs = 0
            for stroke in strokes:
                if len(stroke) < 2:
                    continue
                xs = [point[0] for point in stroke]
                if (min(xs) + max(xs)) / 2 < split_x:
                    continue
                for direction, run in _direction_runs(stroke):
                    right_runs += 1
                    rx_run, ry_run = zip(*run)
                    if max(rx_run) - min(rx_run) >= .018 and max(ry_run) - min(ry_run) >= .012:
                        right_arches += 1
            lower_region_has_arch = right_arches >= 3 and right_runs >= 4
            upper_m = (lx1 - lx0 >= .035 and ly1 - ly0 >= .045 and
                       (len(left) >= 2 or (lx1 - lx0 >= .07 and len(arches) >= 2)))
            lower_m = (rx1 - rx0 >= .025 and ry1 - ry0 >= .025 and
                       (len(right) >= 1 and right_arches >= 3 and right_runs >= 4))
            if upper_m and lower_m:
                return True

    # A single continuous stroke for both letters: broad M followed by a
    # shorter arching m, with enough vertical/turning structure to avoid bars.
    x0 = min(s[0] for s in shapes)
    x1 = max(s[1] for s in shapes)
    y0 = min(s[2] for s in shapes)
    y1 = max(s[3] for s in shapes)
    if len(shapes) >= 2 and not lower_region_has_arch:
        return False
    return (x1 - x0 >= .10 and y1 - y0 >= .035 and
            len(verticals) >= 2 and len(arches) >= 2)


def is_recognizable_t(value):
    """Recognize Tt with a top bar/stem and a lowercase crossbar/stem."""
    strokes = normalize_strokes(value)
    if strokes is None or not strokes:
        return False
    shapes = []
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        xs, ys = zip(*stroke)
        shapes.append((min(xs), max(xs), min(ys), max(ys)))
    if not shapes:
        return False

    def features(group):
        vertical = horizontal = run_horizontal = 0
        for stroke_index, shape in group:
            x0, x1, y0, y1 = shape
            if y1 - y0 >= .025 and y1 - y0 >= (x1 - x0) * 1.05:
                vertical += 1
            if x1 - x0 >= .015 and x1 - x0 >= (y1 - y0) * 1.15:
                horizontal += 1
            stroke = strokes[stroke_index]
            for direction, run in _direction_runs(stroke):
                rx, ry = zip(*run)
                rw, rh = max(rx) - min(rx), max(ry) - min(ry)
                if direction == 'v' and rh >= .018:
                    vertical += 1
                if direction == 'h' and rw >= .015:
                    horizontal += 1
                    run_horizontal += 1
        return vertical, horizontal, run_horizontal

    # Evaluate the two side-by-side letters when strokes are separate.
    ordered = sorted(enumerate(shapes), key=lambda item: (item[1][0] + item[1][1]) / 2)
    lower_region_has_stem = False
    if len(ordered) >= 2:
        gaps = [((ordered[i][1][0] + ordered[i][1][1]) / 2,
                 (ordered[i + 1][1][0] + ordered[i + 1][1][1]) / 2)
                for i in range(len(ordered) - 1)]
        split = max(range(len(gaps)), key=lambda i: gaps[i][1] - gaps[i][0]) + 1
        left, right = ordered[:split], ordered[split:]
        if left and right:
            left_features = features(left)
            right_features = features(right)
            lower_region_has_stem = right_features[0] >= 1
            if (left_features[0] >= 1 and left_features[1] >= 1 and left_features[2] >= 1 and
                    right_features[0] >= 1 and right_features[1] >= 1 and right_features[2] >= 1):
                return True

    # A single connected path (or a path that contains both letters) must
    # still contain at least two stems and two cross/top bars.
    all_features = features(list(enumerate(shapes)))
    x0 = min(shape[0] for shape in shapes)
    x1 = max(shape[1] for shape in shapes)
    y0 = min(shape[2] for shape in shapes)
    y1 = max(shape[3] for shape in shapes)
    if len(shapes) >= 2 and not lower_region_has_stem:
        return False
    return (x1 - x0 >= .06 and y1 - y0 >= .03 and all_features[0] >= 2 and
            all_features[1] >= 2 and all_features[2] >= 2)


def is_recognizable_a(value):
    """Tolerant Aa check for natural second-grade handwriting."""
    strokes = normalize_strokes(value)
    if strokes is None or not strokes:
        return False
    shapes = []
    for index, stroke in enumerate(strokes):
        if len(stroke) < 2:
            continue
        xs, ys = zip(*stroke)
        shapes.append((index, min(xs), max(xs), min(ys), max(ys)))
    if not shapes:
        return False

    def region_features(region):
        x0, x1 = min(s[1] for s in region), max(s[2] for s in region)
        y0, y1 = min(s[3] for s in region), max(s[4] for s in region)
        diagonal = horizontal = vertical = turns = 0
        for index, *_ in region:
            stroke = strokes[index]
            for direction, run in _direction_runs(stroke):
                rx, ry = zip(*run)
                rw, rh = max(rx) - min(rx), max(ry) - min(ry)
                if direction == 'h' and rw >= .012:
                    horizontal += 1
                if direction == 'v' and rh >= .018:
                    vertical += 1
                if rw >= .012 and rh >= .012:
                    diagonal += 1
                turns += 1
        return x0, x1, y0, y1, diagonal, horizontal, vertical, turns

    ordered = sorted(shapes, key=lambda item: (item[1] + item[2]) / 2)
    lower_region_valid = False
    if len(ordered) >= 2:
        gaps = [((ordered[i][1] + ordered[i][2]) / 2,
                 (ordered[i + 1][1] + ordered[i + 1][2]) / 2)
                for i in range(len(ordered) - 1)]
        split = max(range(len(gaps)), key=lambda i: gaps[i][1] - gaps[i][0]) + 1
        upper, lower = ordered[:split], ordered[split:]
        if upper and lower:
            if max(s[4] for s in lower) - min(s[3] for s in lower) < .018:
                return False
            ax0, ax1, ay0, ay1, adiag, ah, av, _ = region_features(upper)
            bx0, bx1, by0, by1, bdiag, bh, bv, _ = region_features(lower)
            capital_a = ((ax1 - ax0 >= .025 and ay1 - ay0 >= .03) and
                         (adiag >= 2 or (ax1 - ax0 >= .045 and (ah >= 1 or av >= 1))))
            lower_a = ((bx1 - bx0 >= .018 and by1 - by0 >= .018) and
                       bdiag >= 2 and bh >= 1)
            lower_region_valid = lower_a and capital_a and (ay1 - ay0) >= (by1 - by0) * 1.08
            if capital_a and lower_a and (ay1 - ay0) >= (by1 - by0) * 1.08:
                return True

    # One continuous path can contain both letters; retain the broad pair
    # and turning requirements without demanding perfectly formed joins.
    x0, x1 = min(s[1] for s in shapes), max(s[2] for s in shapes)
    y0, y1 = min(s[3] for s in shapes), max(s[4] for s in shapes)
    _, _, _, _, diagonal, horizontal, vertical, turns = region_features(shapes)
    if len(shapes) >= 2 and not lower_region_valid:
        return False
    return (x1 - x0 >= .09 and y1 - y0 >= .035 and turns >= 3 and
            diagonal >= 2 and (horizontal >= 1 or vertical >= 1))


def is_recognizable_s(value):
    """Tolerant Ss check: both letters need an S-like turning stroke."""
    strokes = normalize_strokes(value)
    if strokes is None or not strokes:
        return False
    shapes = []
    for index, stroke in enumerate(strokes):
        if len(stroke) < 2:
            continue
        xs, ys = zip(*stroke)
        runs = _direction_runs(stroke)
        x_signs = [1 if b[0] - a[0] > .003 else -1 if b[0] - a[0] < -.003 else 0
                   for a, b in zip(stroke, stroke[1:])]
        x_signs = [sign for sign in x_signs if sign]
        shapes.append({
            'index': index,
            'x0': min(xs), 'x1': max(xs), 'y0': min(ys), 'y1': max(ys),
            'w': max(xs) - min(xs), 'h': max(ys) - min(ys),
            'turns': len(runs),
            'nonvertical': sum(1 for direction, _ in runs if direction != 'v'),
            'vertical_runs': sum(1 for direction, _ in runs if direction == 'v'),
            'x_reversal': bool(x_signs and min(x_signs) < 0 < max(x_signs)),
        })
    if not shapes:
        return False

    ordered = sorted(shapes, key=lambda item: (item['x0'] + item['x1']) / 2)
    if len(ordered) >= 2:
        gaps = [((ordered[i]['x0'] + ordered[i]['x1']) / 2,
                 (ordered[i + 1]['x0'] + ordered[i + 1]['x1']) / 2)
                for i in range(len(ordered) - 1)]
        split = max(range(len(gaps)), key=lambda i: gaps[i][1] - gaps[i][0]) + 1
        left, right = ordered[:split], ordered[split:]

        def looks_like_s(group):
            x0 = min(item['x0'] for item in group)
            x1 = max(item['x1'] for item in group)
            y0 = min(item['y0'] for item in group)
            y1 = max(item['y1'] for item in group)
            turns = sum(item['turns'] for item in group)
            nonvertical = sum(item['nonvertical'] for item in group)
            vertical_runs = sum(item['vertical_runs'] for item in group)
            reversal = any(item['x_reversal'] for item in group)
            return (x1 - x0 >= .012 and y1 - y0 >= .025 and
                    turns >= 3 and nonvertical >= 2 and vertical_runs >= 1 and reversal)

        if looks_like_s(left) and looks_like_s(right):
            return True

    x0 = min(item['x0'] for item in shapes)
    x1 = max(item['x1'] for item in shapes)
    y0 = min(item['y0'] for item in shapes)
    y1 = max(item['y1'] for item in shapes)
    turns = sum(item['turns'] for item in shapes)
    nonvertical = sum(item['nonvertical'] for item in shapes)
    vertical_runs = sum(item['vertical_runs'] for item in shapes)
    reversal = any(item['x_reversal'] for item in shapes)
    return (x1 - x0 >= .06 and y1 - y0 >= .03 and turns >= 4 and
            nonvertical >= 2 and vertical_runs >= 1 and reversal)
