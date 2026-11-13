"""Command-local grouping of selections and compatible measurements."""
from dataclasses import dataclass
from .fusion_geometry import measure


def duplicate_rows(rows):
    """Identify later rows measuring the same geometry in the same way."""
    seen = []
    duplicates = set()
    for row in rows:
        def matches(other):
            if row.kind != other.kind or len(row.entities) != len(other.entities):
                return False
            same = all(a == b for a, b in zip(row.entities, other.entities))
            reverse = row.kind in ('distance', 'angle') and all(a == b for a, b in zip(row.entities, reversed(other.entities)))
            return same or reverse
        if any(matches(other) for other in seen):
            duplicates.add(row.id)
        else:
            seen.append(row)
    return duplicates


def compatible(entities):
    kinds = ('distance', 'angle') if len(entities) == 2 else ('edge_length', 'radius', 'diameter', 'area', 'perimeter')
    result = []
    for kind in kinds:
        try:
            measure(kind, entities)
        except (ValueError, AttributeError, RuntimeError, TypeError):
            continue
        result.append(kind)
    return result


@dataclass
class Row:
    id: str
    entities: tuple
    options: list
    kind: str


class RowDraft:
    """Independent, possibly incomplete geometry selections for one row."""
    def __init__(self, ident):
        self.id = ident
        self.first = self.second = None
        self.entities = ()
        self.options = []
        self.kind = None
        self.offset = 0.0
        self.visible = True

    @property
    def needs_second(self):
        return self.kind in ('distance', 'angle') or getattr(self.first, 'objectType', '') in ('adsk::fusion::BRepVertex', 'adsk::fusion::SketchPoint')

    @property
    def complete(self):
        return bool(self.options and self.kind in self.options and (not self.needs_second or self.second is not None))

    def set_first(self, entity):
        self.first = entity
        self._update()

    def set_second(self, entity):
        self.second = entity
        if entity is not None and self.kind not in ('distance', 'angle'):
            self.kind = 'distance'
        self._update()

    def set_kind(self, kind):
        if kind not in self.options:
            raise ValueError('Incompatible measurement type')
        self.kind = kind
        if kind not in ('distance', 'angle'): self.second = None
        self._update()

    def _update(self):
        if self.first is None:
            self.entities = ()
        elif self.needs_second:
            self.entities = (self.first, self.second) if self.second is not None else (self.first,)
        else:
            self.entities = (self.first,)
        first_type = getattr(self.first, 'objectType', '')
        is_point = first_type in ('adsk::fusion::BRepVertex', 'adsk::fusion::SketchPoint')
        if not self.first:
            self.options = []
        elif is_point:
            self.options = ['distance'] if self.second is not None else []
        else:
            self.options = compatible((self.first,)) if self.second is None else ['distance']
            if self.second is not None:
                try:
                    measure('angle', (self.first, self.second))
                    self.options.append('angle')
                except (ValueError, AttributeError, RuntimeError, TypeError):
                    pass
        if self.kind not in self.options and not (self.first is None and self.second is not None and self.kind == 'distance'):
            self.kind = self.options[0] if self.options else None
        self.entities = (() if self.first is None else (self.first, self.second)
                         if self.kind in ('distance', 'angle') and self.second is not None else (self.first,))


class Batch:
    def __init__(self):
        self.rows = []
        self.pending = None
        self.next_id = 1

    def add(self, entity):
        is_point = getattr(entity, 'objectType', '') in ('adsk::fusion::BRepVertex', 'adsk::fusion::SketchPoint')
        if self.pending is not None:
            if not is_point:
                raise ValueError('Select a second point or cancel the pending point')
            entities = (self.pending, entity)
        elif is_point:
            self.pending = entity
            return None
        else:
            entities = (entity,)
        options = compatible(entities)
        if not options:
            raise ValueError('No compatible measurement for this selection')
        row = Row('m' + str(self.next_id), entities, options, options[0])
        self.next_id += 1
        self.pending = None
        self.rows.append(row)
        return row

    def set_kind(self, ident, kind):
        row = next(row for row in self.rows if row.id == ident)
        if kind not in row.options:
            raise ValueError('Incompatible measurement type')
        row.kind = kind

    def remove(self, ident):
        self.rows = [row for row in self.rows if row.id != ident]
