"""Design attribute storage. Calling save modifies the Fusion document."""

from .model import deserialize, serialize

GROUP = '4FusionLab.Dimensions'
NAME = 'definitions'
MAX_BYTES = 2 * 1024 * 1024


class PersistenceError(RuntimeError):
    pass


def load(design):
    attribute = design.attributes.itemByName(GROUP, NAME)
    if not attribute:
        return [], True
    # Refuse to interpret or overwrite corrupt and future schemas.
    return deserialize(attribute.value)


def save(design, dimensions, visible):
    # Do not overwrite a schema we cannot understand, including corrupted data.
    load(design)
    payload = serialize(dimensions, visible)
    if len(payload.encode('utf-8')) > MAX_BYTES:
        raise PersistenceError('Dimension definitions exceed Fusion attribute limit')
    attribute = design.attributes.add(GROUP, NAME, payload)
    if not attribute or attribute.value != payload:
        raise PersistenceError('Fusion did not store the dimension definitions')
