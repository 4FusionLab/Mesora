"""Exercise the actual packaged adapter, not the earlier standalone copy."""
import math
import unittest
from types import SimpleNamespace

from Mesora.dimensions.fusion_geometry import measure
from Mesora.dimensions.measurement import MeasurementError


class ArcEvaluator:
    def getParameterExtents(self):
        return True, 0.0, math.pi / 2

    def getLengthAtParameter(self, start, end):
        return True, 2.0 * (end - start)


class ArcLengthTest(unittest.TestCase):
    def test_sketch_arc_uses_trimmed_arc_length_not_chord(self):
        arc = SimpleNamespace(objectType='adsk::fusion::SketchArc',
                              worldGeometry=SimpleNamespace(evaluator=ArcEvaluator()))
        self.assertAlmostEqual(measure('edge_length', [arc]), math.pi)
        self.assertNotAlmostEqual(measure('edge_length', [arc]), math.sqrt(8))

    def test_other_sketch_curves_do_not_produce_invented_length(self):
        line = SimpleNamespace(objectType='adsk::fusion::SketchLine')
        with self.assertRaises(MeasurementError):
            measure('edge_length', [line])


if __name__ == '__main__':
    unittest.main()
