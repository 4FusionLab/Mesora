"""Camera-independent bases for dimension planes."""
import math


def add(a, b): return tuple(x + y for x, y in zip(a, b))
def sub(a, b): return tuple(x - y for x, y in zip(a, b))
def mul(a, k): return tuple(x * k for x in a)
def dot(a, b): return sum(x*y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def unit(a):
    n = math.sqrt(dot(a, a))
    if n < 1e-10: raise ValueError('Degenerate direction')
    return mul(a, 1/n)


def canonical(v):
    v = unit(v)
    # Reverse selection order must not reverse the chosen plane or side.
    for coordinate in v:
        if abs(coordinate) > 1e-9:
            return v if coordinate > 0 else mul(v, -1)
    return v


def face_axis(normal, screen_right):
    """Choose the closest global axis projected into a face's tangent plane."""
    normal = unit(normal)
    candidates = []
    for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
        projected = sub(axis, mul(normal, dot(axis, normal)))
        length2 = dot(projected, projected)
        if length2 > 1e-12:
            direction = unit(projected)
            candidates.append((round(length2, 8), abs(dot(direction, screen_right)), direction))
    return max(candidates, key=lambda x: (x[0], x[1]))[2]


def basis(direction, normal=None, outward=None):
    x = canonical(direction)
    if normal is not None:
        n = sub(normal, mul(x, dot(normal, x)))
        if dot(n, n) < 1e-12:
            normal = None
    if normal is None:
        # Prefer an upright dimension plane; use X when direction is vertical.
        up = (0, 0, 1) if abs(x[2]) < .95 else (1, 0, 0)
        side = unit(sub(up, mul(x, dot(up, x))))
    else:
        side = unit(cross(unit(n), x))
    if outward is not None and abs(dot(side, outward)) > 1e-9:
        if dot(side, outward) < 0: side = mul(side, -1)
    else:
        side = canonical(side)
    return x, side, unit(cross(x, side))


def readable_axes(x, y, eye_direction, camera_up, previous_normal=None):
    """Choose a quarter-turn around the dimension axis, with hysteresis."""
    x, y = unit(x), unit(y)
    normal = unit(cross(x, y))
    eye = unit(eye_direction)
    right = unit(cross(mul(eye, -1), camera_up))
    up = unit(cross(right, mul(eye, -1)))
    horizontal, vertical = dot(x, right), dot(x, up)
    if horizontal < -1e-8 or (abs(horizontal) <= 1e-8 and vertical < 0):
        x = mul(x, -1)
    candidates = (normal, y, mul(normal, -1), mul(y, -1))
    best = max(candidates, key=lambda n: dot(n, eye))
    if previous_normal is not None:
        old = max(candidates, key=lambda n: dot(n, previous_normal))
        if dot(old, previous_normal) > .99 and dot(old, eye) > 0 and dot(best, eye) - dot(old, eye) < .08:
            best = old
    return x, unit(cross(best, x)), best


def find_clear_placement(direction, preferred_side, desired, is_clear, surface_normals=()):
    """Search model-fixed directions, favouring a full-size clear placement."""
    axis = canonical(direction)
    side = unit(sub(preferred_side, mul(axis, dot(preferred_side, axis))))
    other = unit(cross(axis, side))
    candidates = []
    for i in range(24):
        angle = (i if i <= 12 else i - 24) * math.pi / 12
        candidate = add(mul(side, math.cos(angle)), mul(other, math.sin(angle)))
        separation = min((abs(dot(candidate, unit(n))) for n in surface_normals), default=0)
        candidates.append((separation, i, candidate))
    if surface_normals:
        for world_axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            v = sub(world_axis, mul(axis, dot(world_axis, axis)))
            if dot(v, v) > 1e-12:
                for sign in (1, -1):
                    candidate = mul(unit(v), sign)
                    separation = min(abs(dot(candidate, unit(n))) for n in surface_normals)
                    candidates.append((separation, len(candidates), candidate))
        # Prefer an axis-aligned clear direction. Separation from adjacent
        # faces breaks ties; it must not force a diagonal when an axis works.
        candidates.sort(key=lambda item: (-(max(abs(v) for v in item[2]) >= .999999),
                                         -round(item[0], 8),
                                         -round(max(abs(v) for v in item[2]), 8), item[1]))
    for fraction in (1, .75, .5, .25, .125, .0625):
        for _, _, candidate in candidates:
            if is_clear(candidate, desired * fraction):
                return candidate, desired * fraction
    raise ValueError('No clear dimension placement found near this edge')


def clear_intervals(length, intersections, margin, is_clear):
    """Return checked intervals, leaving a small gap at each intersection."""
    stops = [0.0]
    for distance in sorted(intersections):
        if margin < distance < length - margin and distance - stops[-1] > margin:
            stops.append(distance)
    stops.append(length)
    result = []
    for index, (left, right) in enumerate(zip(stops, stops[1:])):
        start = left + (margin if index else 0)
        end = right - (margin if index < len(stops) - 2 else 0)
        if end - start > margin and is_clear(start, end):
            result.append((start, end))
    return result
