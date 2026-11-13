"""Read-only invalidation snapshots; no Fusion objects or tokens in equality.

Call on Fusion's main thread. Snapshots are session-local and never persisted.
"""
import math


def _get(obj, name):
    try:
        return getattr(obj, name, None)
    except (RuntimeError, AttributeError):
        return None


def _number(value):
    if isinstance(value, (float, int)):
        return value if math.isfinite(value) else ('nonfinite', str(value))
    return None


def _point(value):
    if value is None:
        return None
    coordinates = tuple(_number(_get(value, axis)) for axis in ('x', 'y', 'z'))
    return coordinates if all(v is not None for v in coordinates) else None


def _matrix(value):
    if value is None:
        return None
    try:
        return tuple(_number(v) for v in value.asArray())
    except (RuntimeError, AttributeError, TypeError):
        return ('unavailable',)


def _bounds(value):
    return (_point(_get(value, 'minPoint')), _point(_get(value, 'maxPoint')))


def _geometry(value):
    if value is None:
        return None
    return (_get(value, 'objectType'), _point(value),
            tuple((name, _point(_get(value, name))) for name in
                  ('center', 'origin', 'startPoint', 'endPoint', 'normal',
                   'direction', 'axis', 'majorAxis', 'minorAxis')),
            tuple((name, _number(_get(value, name))) for name in
                  ('radius', 'majorRadius', 'minorRadius', 'startAngle', 'endAngle')))


def _body(body):
    return (_get(body, 'revisionId'), _get(body, 'isVisible'),
            _bounds(_get(body, 'boundingBox')))


def _entity(entity):
    if entity is None or _get(entity, 'isValid') is False:
        return ('missing',)
    occurrence = _get(entity, 'assemblyContext')
    return (_get(entity, 'objectType'), _bounds(_get(entity, 'boundingBox')),
            _geometry(_get(entity, 'worldGeometry')),
            _geometry(_get(entity, 'geometry')),
            _point(_get(entity, 'pointOnFace')),
            _body(_get(entity, 'body')),
            _matrix(_get(occurrence, 'transform2')))


def geometry_fingerprint(design, items, resolve_fn, measure_fn):
    """Snapshot measurements plus placement dependencies, retaining missing rows.

    Runtime items have the shape ``(id, kind, references)``. Token strings are
    deliberately excluded: Fusion can issue different tokens for one entity.
    Changes to hidden bodies also invalidate placement and measurements.
    """
    root = design.rootComponent
    bodies = tuple(_body(body) for body in root.bRepBodies)
    occurrences = tuple((_get(occurrence, 'isVisible'),
                         _matrix(_get(occurrence, 'transform2')),
                         tuple(_body(body) for body in occurrence.bRepBodies))
                        for occurrence in root.allOccurrences)
    rows = []
    for ident, kind, references in items:
        entities, snapshots = [], []
        missing = False
        for reference in references:
            try:
                entity = resolve_fn(design, reference)
                snapshot = _entity(entity)
                entities.append(entity)
                missing = missing or snapshot == ('missing',)
                snapshots.append(snapshot)
            except (ValueError, RuntimeError, AttributeError):
                missing = True
                snapshots.append(('missing',))
        try:
            value = ('missing',) if missing else _number(measure_fn(kind, entities))
        except (ValueError, RuntimeError, AttributeError):
            value = ('unmeasurable',)
        rows.append((ident, kind, tuple(snapshots), value))
    return (design.unitsManager.defaultLengthUnits, bodies, occurrences, tuple(rows))
