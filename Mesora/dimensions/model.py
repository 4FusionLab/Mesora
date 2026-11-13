"""Versioned dimension definitions. Geometry, never cached values, is persisted."""

from dataclasses import dataclass, field
import json
import math
import re
import uuid

SCHEMA_VERSION = 2
KINDS = {"distance": 2, "angle": 2, "edge_length": 1, "radius": 1,
         "diameter": 1, "area": 1, "perimeter": 1}
LEGACY_KINDS = {"distance", "edge_length", "radius", "diameter"}


class SchemaError(ValueError):
    pass


def _valid_id(ident, legacy=False):
    if not isinstance(ident, str):
        return False
    if not legacy and re.fullmatch(r"m[1-9][0-9]*", ident):
        return True
    try:
        uuid.UUID(ident)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _json_object(value):
    if not isinstance(value, dict):
        raise SchemaError("Placement and display must be objects")
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SchemaError("Invalid JSON data") from exc


@dataclass(frozen=True)
class EntityReference:
    token: str
    occurrence_token: str | None = None

    def __post_init__(self):
        if not isinstance(self.token, str) or not self.token:
            raise SchemaError("Entity token must be a nonempty string")
        if self.occurrence_token is not None and (
            not isinstance(self.occurrence_token, str) or not self.occurrence_token
        ):
            raise SchemaError("Occurrence token must be a nonempty string or null")

    def to_dict(self):
        return {"token": self.token, "occurrence_token": self.occurrence_token}


@dataclass(frozen=True)
class Dimension:
    id: str
    kind: str
    references: tuple[EntityReference, ...]
    placement: dict = field(default_factory=dict)
    display: dict = field(default_factory=dict)

    def __post_init__(self):
        if not _valid_id(self.id):
            raise SchemaError("Invalid dimension ID")
        if self.kind not in KINDS or len(self.references) != KINDS[self.kind]:
            raise SchemaError("Invalid dimension kind or reference count")
        if not all(isinstance(ref, EntityReference) for ref in self.references):
            raise SchemaError("Invalid entity reference")
        _json_object(self.placement)
        _json_object(self.display)
        offset = self.placement.get('offset', 0.0)
        if isinstance(offset, bool) or not isinstance(offset, (int, float)) or not math.isfinite(offset):
            raise SchemaError("Offset must be a finite number")
        if not isinstance(self.display.get('visible', True), bool):
            raise SchemaError("Row visibility must be a boolean")

    @classmethod
    def create(cls, kind, references, placement=None, display=None):
        return cls(str(uuid.uuid4()), kind, tuple(references), placement or {}, display or {})

    def to_dict(self):
        return {"id": self.id, "type": self.kind,
                "references": [ref.to_dict() for ref in self.references],
                "placement": self.placement, "display": self.display}


def serialize(dimensions, visible=True):
    dimensions = list(dimensions)
    if not isinstance(visible, bool):
        raise SchemaError("visible must be a boolean")
    if not all(isinstance(d, Dimension) for d in dimensions):
        raise SchemaError("Invalid dimension")
    if len({d.id for d in dimensions}) != len(dimensions):
        raise SchemaError("Duplicate dimension IDs")
    try:
        return json.dumps({"schema_version": SCHEMA_VERSION, "visible": visible,
                           "dimensions": [d.to_dict() for d in dimensions]},
                          ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise SchemaError("Invalid JSON data") from exc


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SchemaError("Duplicate JSON object key")
        result[key] = value
    return result


def deserialize(payload):
    try:
        data = json.loads(payload, object_pairs_hook=_unique_object,
                          parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        if not isinstance(data, dict):
            raise SchemaError("Invalid document payload")
        version = data.get("schema_version")
        if type(version) is not int or version not in (1, SCHEMA_VERSION):
            raise SchemaError("Unsupported schema version")
        if set(data) != {'schema_version', 'visible', 'dimensions'}:
            raise SchemaError("Unrecognized document fields")
        if not isinstance(data.get("visible"), bool) or not isinstance(data.get("dimensions"), list):
            raise SchemaError("Invalid document payload")
        dimensions = []
        for item in data["dimensions"]:
            if set(item) != {'id', 'type', 'references', 'placement', 'display'}:
                raise SchemaError("Unrecognized dimension fields")
            if not isinstance(item['references'], list):
                raise SchemaError("References must be an array")
            if version == 1 and (not _valid_id(item['id'], legacy=True) or item['type'] not in LEGACY_KINDS):
                raise SchemaError("Invalid legacy dimension")
            refs = []
            for ref in item['references']:
                if not isinstance(ref, dict) or not {'token'} <= set(ref) <= {'token', 'occurrence_token'}:
                    raise SchemaError("Invalid reference fields")
                refs.append(EntityReference(ref['token'], ref.get('occurrence_token')))
            dimensions.append(Dimension(item["id"], item["type"], tuple(refs),
                                        item["placement"], item["display"]))
        if len({d.id for d in dimensions}) != len(dimensions):
            raise SchemaError("Duplicate dimension IDs")
        return dimensions, data["visible"]
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        if isinstance(exc, SchemaError):
            raise
        raise SchemaError("Invalid dimension payload") from exc
