"""Read-only adapter for Fusion entities; no document or graphics mutations."""

from .measurement import MeasurementError, diameter, distance, edge_length, radius
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


def measure(kind, entities):
    if kind == 'distance' and len(entities) == 2:
        return distance(point(entities[0]), point(entities[1]))
    if len(entities) != 1:
        raise MeasurementError('Incorrect number of entities')
    entity = entities[0]
    if kind == 'edge_length':
        if _type(entity) != 'adsk::fusion::BRepEdge':
            raise MeasurementError('Expected a BRep edge')
        return edge_length(entity.evaluator)
    if kind in ('radius', 'diameter'):
        value = circular_radius(entity)
        return diameter(value) if kind == 'diameter' else value
    raise MeasurementError('Unknown dimension type')
