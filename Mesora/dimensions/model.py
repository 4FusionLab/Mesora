"""Versioned, deliberately strict dimension definitions.

No measured value is persisted: geometry is the source of truth.
"""

from dataclasses import dataclass, field
import json
import uuid

SCHEMA_VERSION = 1
KINDS = {"distance": 2, "edge_length": 1, "radius": 1, "diameter": 1}


class SchemaError(ValueError):
    pass


@dataclass(frozen=True)
class EntityReference:
    token: str
    # An occurrence is stored separately: never identify geometry by comparing tokens.
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
        try:
            uuid.UUID(self.id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise SchemaError("Invalid dimension ID") from exc
        if self.kind not in KINDS or len(self.references) != KINDS[self.kind]:
            raise SchemaError("Invalid dimension kind or reference count")
        if not all(isinstance(ref, EntityReference) for ref in self.references):
            raise SchemaError("Invalid entity reference")
        if not isinstance(self.placement, dict) or not isinstance(self.display, dict):
            raise SchemaError("Placement and display must be objects")

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
    if len({d.id for d in dimensions}) != len(dimensions):
        raise SchemaError("Duplicate dimension IDs")
    try:
        return json.dumps({"schema_version": SCHEMA_VERSION, "visible": visible,
                           "dimensions": [d.to_dict() for d in dimensions]},
                          ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise SchemaError("Invalid JSON data") from exc


def deserialize(payload):
    try:
        data = json.loads(payload, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
            raise SchemaError("Unsupported schema version")
        if not isinstance(data.get("visible"), bool) or not isinstance(data.get("dimensions"), list):
            raise SchemaError("Invalid document payload")
        dimensions = []
        for item in data["dimensions"]:
            refs = tuple(EntityReference(ref["token"], ref.get("occurrence_token"))
                         for ref in item["references"])
            dimensions.append(Dimension(item["id"], item["type"], refs,
                                        item["placement"], item["display"]))
        if len({d.id for d in dimensions}) != len(dimensions):
            raise SchemaError("Duplicate dimension IDs")
        return dimensions, data["visible"]
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        if isinstance(exc, SchemaError):
            raise
        raise SchemaError("Invalid dimension payload") from exc
