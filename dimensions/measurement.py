"""Pure measurement functions. Coordinates and lengths use Fusion centimetres."""

import math


class MeasurementError(ValueError):
    pass


def _positive_finite(value, label):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MeasurementError(f"Invalid {label}") from exc
    if not math.isfinite(value) or value <= 0:
        raise MeasurementError(f"Invalid {label}")
    return value


def distance(first, second):
    """Euclidean distance, without projection. Reject coincident/invalid points."""
    try:
        a, b = tuple(first), tuple(second)
        if len(a) != 3 or len(b) != 3:
            raise ValueError("Expected 3D coordinates")
        return _positive_finite(math.dist(a, b), "distance")
    except (TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, MeasurementError):
            raise
        raise MeasurementError("Invalid points") from exc


def edge_length(evaluator):
    """Measure the trimmed edge, including closed curves, using its evaluator."""
    try:
        ok, start, end = evaluator.getParameterExtents()
        if not ok or not math.isfinite(start) or not math.isfinite(end) or end <= start:
            raise MeasurementError("Invalid edge parameter extents")
        ok, length = evaluator.getLengthAtParameter(start, end)
        if not ok:
            raise MeasurementError("Edge length evaluation failed")
        return _positive_finite(length, "edge length")
    except (TypeError, ValueError, AttributeError, RuntimeError) as exc:
        if isinstance(exc, MeasurementError):
            raise
        raise MeasurementError("Edge length evaluation failed") from exc


def radius(value):
    return _positive_finite(value, "radius")


def diameter(value):
    return _positive_finite(radius(value) * 2.0, "diameter")
