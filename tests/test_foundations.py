import json
import math
import unittest

from dimensions.measurement import MeasurementError, diameter, distance, edge_length, radius
from dimensions.model import Dimension, EntityReference, SchemaError, deserialize, serialize


class Evaluator:
    def __init__(self, length, ok=True):
        self.length, self.ok = length, ok

    def getParameterExtents(self):
        return True, 0.0, math.pi / 2

    def getLengthAtParameter(self, start, end):
        return self.ok, self.length


class MeasurementsTest(unittest.TestCase):
    def test_three_dimensional_distance(self):
        self.assertAlmostEqual(distance((0, 0, 0), (3, 4, 12)), 13)

    def test_arc_uses_length_not_chord(self):
        # Fusion uses centimetres: radius 20 mm, quarter circumference.
        self.assertAlmostEqual(edge_length(Evaluator(math.pi)), math.pi)
        self.assertNotAlmostEqual(edge_length(Evaluator(math.pi)), math.sqrt(8))

    def test_closed_edge_does_not_require_endpoints(self):
        self.assertAlmostEqual(edge_length(Evaluator(2 * math.pi)), 2 * math.pi)

    def test_invalid_geometry_fails_closed(self):
        for fn in (lambda: distance((0, 0, 0), (0, 0, 0)),
                   lambda: distance((0, 0, 0), (float('nan'), 0, 0)),
                   lambda: edge_length(Evaluator(1, False)),
                   lambda: radius(-1), lambda: diameter(float('inf'))):
            with self.assertRaises(MeasurementError):
                fn()

    def test_radius_and_diameter(self):
        self.assertEqual(radius(2), 2)
        self.assertEqual(diameter(2), 4)


class SchemaTest(unittest.TestCase):
    def test_roundtrip_and_no_cached_value(self):
        dim = Dimension.create('distance', [EntityReference('a'), EntityReference('b', 'occ')])
        payload = serialize([dim], False)
        self.assertNotIn('value', json.loads(payload)['dimensions'][0])
        dims, visible = deserialize(payload)
        self.assertEqual(dims, [dim])
        self.assertFalse(visible)

    def test_rejects_invalid_and_future_data(self):
        dim = Dimension.create('radius', [EntityReference('a')])
        for payload in ('{}', '{"schema_version":2}',
                        '{"schema_version":1,"visible":true,"dimensions":NaN}'):
            with self.assertRaises(SchemaError):
                deserialize(payload)
        with self.assertRaises(SchemaError):
            serialize([dim, dim])
        with self.assertRaises(SchemaError):
            Dimension.create('distance', [EntityReference('a')])


if __name__ == '__main__':
    unittest.main()
