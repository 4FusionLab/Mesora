"""Read-only adapter for Fusion entities; no document or graphics mutations."""
import math

from .measurement import MeasurementError, diameter, distance, edge_length, radius, _positive_finite
from .model import EntityReference


class ResolutionError(ValueError):
    pass


def _type(obj):
    return getattr(obj, 'objectType', '')


def _unique(design, token):
    entities = design.findEntityByToken(token)
    if len(entities) != 1 or not getattr(entities[0], 'isValid', True):
        raise ResolutionError('Reference is missing, invalid or ambiguous')
    return entities[0]


def reference_for(entity):
    """Record the native object and, separately, its occurrence context."""
    if not entity or not getattr(entity, 'isValid', True):
        raise ResolutionError('Invalid entity')
    occurrence = getattr(entity, 'assemblyContext', None)
    native = getattr(entity, 'nativeObject', None) if occurrence else entity
    if native is None:
        raise ResolutionError('Cannot obtain native entity')
    try:
        return EntityReference(native.entityToken, occurrence.entityToken if occurrence else None)
    except (AttributeError, RuntimeError, ValueError) as exc:
        raise ResolutionError('Entity cannot be referenced') from exc


def resolve(design, reference):
    entity = _unique(design, reference.token)
    if reference.occurrence_token:
        occurrence = _unique(design, reference.occurrence_token)
        if _type(occurrence) != 'adsk::fusion::Occurrence':
            raise ResolutionError('Occurrence reference has unexpected type')
        try:
            entity = entity.createForAssemblyContext(occurrence)
        except (AttributeError, RuntimeError) as exc:
            raise ResolutionError('Cannot restore assembly context') from exc
        if not entity or not getattr(entity, 'isValid', True):
            raise ResolutionError('Cannot restore assembly context')
    elif getattr(entity, 'assemblyContext', None):
        raise ResolutionError('Unexpected assembly context')
    return entity


def point(entity):
    kind = _type(entity)
    if kind == 'adsk::fusion::SketchPoint':
        geometry = entity.worldGeometry
    elif kind == 'adsk::fusion::BRepVertex':
        geometry = entity.geometry
    else:
        raise MeasurementError('Expected a BRep vertex or sketch point')
    if not geometry:
        raise MeasurementError('Point geometry is unavailable')
    return (geometry.x, geometry.y, geometry.z)


def circular_radius(entity):
    """Accept only circular edge/sketch geometry or an analytic cylinder."""
    kind = _type(entity)
    if kind in ('adsk::fusion::SketchCircle', 'adsk::fusion::SketchArc'):
        geometry = entity.worldGeometry
        accepted = ('adsk::core::Circle3D', 'adsk::core::Arc3D')
    elif kind == 'adsk::fusion::BRepEdge':
        geometry = entity.geometry
        accepted = ('adsk::core::Circle3D', 'adsk::core::Arc3D')
    elif kind == 'adsk::fusion::BRepFace':
        geometry = entity.geometry
        accepted = ('adsk::core::Cylinder',)
    else:
        raise MeasurementError('Expected a circular curve or cylindrical face')
    if not geometry or _type(geometry) not in accepted:
        raise MeasurementError('Geometry is not circular or cylindrical')
    return radius(geometry.radius)


def minimum_distance(first, second):
    point_types = ('adsk::fusion::BRepVertex', 'adsk::fusion::SketchPoint')
    if _type(first) in point_types and _type(second) in point_types:
        a, b = point(first), point(second)
        return distance(a, b), a, b
    import adsk.core
    result = adsk.core.Application.get().measureManager.measureMinimumDistance(first, second)
    if result is None or result.positionOne is None or result.positionTwo is None:
        raise MeasurementError('Cannot measure minimum distance')
    value = float(result.value)
    a = (result.positionOne.x, result.positionOne.y, result.positionOne.z)
    b = (result.positionTwo.x, result.positionTwo.y, result.positionTwo.z)
    if not math.isfinite(value) or value < 0 or not all(math.isfinite(x) for x in a + b):
        raise MeasurementError('Invalid minimum distance')
    return value, a, b


def angle_geometry(first, second):
    def category(entity):
        typ = _type(entity)
        geometry = getattr(entity, 'worldGeometry', None) if typ == 'adsk::fusion::SketchLine' else getattr(entity, 'geometry', None)
        geo_type = _type(geometry)
        if typ in ('adsk::fusion::BRepEdge', 'adsk::fusion::SketchLine') and geo_type == 'adsk::core::Line3D':
            return 'line'
        if typ == 'adsk::fusion::BRepFace' and geo_type == 'adsk::core::Plane':
            return 'plane'
        return None
    first_category = category(first)
    if not first_category or first_category != category(second):
        raise MeasurementError('Angle requires two straight edges or two planar faces')
    import adsk.core
    result = adsk.core.Application.get().measureManager.measureAngle(first, second)
    if result is None or not all((result.positionOne, result.positionTwo, result.positionThree)):
        raise MeasurementError('Cannot determine angle geometry')
    value = float(result.value)
    points = tuple((p.x, p.y, p.z) for p in (result.positionOne, result.positionTwo, result.positionThree))
    if not math.isfinite(value) or not all(math.isfinite(v) for p in points for v in p):
        raise MeasurementError('Invalid angle')
    u = tuple(a - b for a, b in zip(points[0], points[1]))
    v = tuple(a - b for a, b in zip(points[2], points[1]))
    cross = (u[1]*v[2] - u[2]*v[1], u[2]*v[0] - u[0]*v[2], u[0]*v[1] - u[1]*v[0])
    if math.dist((0, 0, 0), cross) <= 1e-10 * math.dist((0, 0, 0), u) * math.dist((0, 0, 0), v):
        raise MeasurementError('Parallel objects do not define a visible angle arc')
    if first_category == 'plane':
        # The API's apex can lie anywhere along the intersection of the
        # infinite planes. Anchor it beside the actual trimmed faces instead.
        _, nearest_first, nearest_second = minimum_distance(first, second)
        target = tuple((a+b)*.5 for a,b in zip(nearest_first, nearest_second))
        length = math.sqrt(sum(v*v for v in cross))
        axis = tuple(v/length for v in cross)
        along = sum((a-b)*d for a,b,d in zip(target, points[1], axis))
        shift = tuple(along*d for d in axis)
        points = tuple(tuple(a+b for a,b in zip(p,shift)) for p in points)
    return value, points


def measure(kind, entities):
    if kind == 'distance' and len(entities) == 2:
        return minimum_distance(entities[0], entities[1])[0]
    if kind == 'angle' and len(entities) == 2:
        return angle_geometry(entities[0], entities[1])[0]
    if len(entities) != 1:
        raise MeasurementError('Incorrect number of entities')
    entity = entities[0]
    if kind == 'edge_length':
        if _type(entity) == 'adsk::fusion::BRepEdge':
            return edge_length(entity.evaluator)
        if _type(entity) in ('adsk::fusion::SketchArc', 'adsk::fusion::SketchCircle'):
            return edge_length(entity.worldGeometry.evaluator)
        raise MeasurementError('Expected a BRep edge, sketch arc or sketch circle')
    if kind in ('area', 'perimeter'):
        if _type(entity) != 'adsk::fusion::BRepFace':
            raise MeasurementError('Expected a face')
        if kind == 'area':
            return _positive_finite(entity.area, 'area')
        return _positive_finite(sum(edge_length(edge.evaluator) for edge in entity.edges), 'perimeter')
    if kind in ('radius', 'diameter'):
        value = circular_radius(entity)
        return diameter(value) if kind == 'diameter' else value
    raise MeasurementError('Unknown dimension type')
