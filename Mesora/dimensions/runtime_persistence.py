"""Translate committed runtime definitions to document storage, without adsk.

Loading restores references only. Callers resolve and remeasure them against the
current model, retaining unresolved definitions for later repair/removal.
"""
from dataclasses import dataclass
import re

from .model import Dimension, SchemaError, serialize
from .persistence import GROUP, NAME, load, save


@dataclass
class RuntimeDefinitions:
    items: list
    offsets: dict
    hidden_ids: set
    visible: bool
    next_id: int


def load_state(design):
    dimensions, visible = load(design)
    numeric_ids = [int(d.id[1:]) for d in dimensions if re.fullmatch(r'm[1-9][0-9]*', d.id)]
    return RuntimeDefinitions(
        [(d.id, d.kind, d.references) for d in dimensions],
        {d.id: d.placement.get('offset', 0.0) for d in dimensions},
        {d.id for d in dimensions if not d.display.get('visible', True)},
        visible, max(numeric_ids, default=0) + 1)


def save_state(design, items, offsets, hidden_ids, visible):
    """Persist an explicit command commit; return whether an attribute was written.

    Validate existing data first, and do not replace extension fields that this
    runtime does not understand. This is safer than silently losing user data.
    """
    previous, _ = load(design)
    for dimension in previous:
        if set(dimension.placement) - {'offset'} or set(dimension.display) - {'visible'}:
            raise SchemaError('Stored dimension settings are not supported by this Mesora version')
    items = list(items)
    ids = {item[0] for item in items}
    if set(offsets) - ids or set(hidden_ids) - ids:
        raise SchemaError('Settings reference an unknown measurement')
    dimensions = [Dimension(ident, kind, tuple(refs),
                            {'offset': offsets.get(ident, 0.0)},
                            {'visible': ident not in hidden_ids})
                  for ident, kind, refs in items]
    payload = serialize(dimensions, visible)
    attribute = design.attributes.itemByName(GROUP, NAME)
    if attribute and attribute.value == payload:
        return False
    if attribute is None and not dimensions and visible:
        return False
    save(design, dimensions, visible)
    return True
