import unittest

from Mesora.dimensions.layout import basis, dot, readable_axes


class DimensionPlaneTest(unittest.TestCase):
    def test_outward_from_planar_face_and_reversal(self):
        first = basis((10, 0, 0), (0, 0, 1), (0, -3, 0))
        reverse = basis((-10, 0, 0), (0, 0, 1), (0, -3, 0))
        self.assertEqual(first, reverse)
        x, y, z = first
        self.assertGreater(dot(y, (0, -3, 0)), 0)
        self.assertAlmostEqual(dot(x, y), 0)
        self.assertAlmostEqual(dot(z, (0, 0, 1)), -1)

    def test_vertical_fallback_is_stable(self):
        x, y, z = basis((0, 0, 3))
        self.assertAlmostEqual(dot(x, y), 0)
        self.assertAlmostEqual(dot(x, z), 0)
        self.assertAlmostEqual(dot(y, z), 0)
        self.assertEqual((x, y, z), basis((0, 0, -3)))

    def test_text_faces_front_and_back_without_leaving_plane(self):
        for eye in ((0, -1, 2), (0, 1, -2)):
            x, y, z = readable_axes((1, 0, 0), (0, 1, 0), eye, (0, 0, 1))
            self.assertGreater(dot(z, eye), 0)
            self.assertAlmostEqual(abs(z[2]), 1)
            self.assertAlmostEqual(dot(x, (0, 0, 1)), 0)

    def test_edge_on_text_turns_quarter_turn_and_remains_aligned(self):
        x, y, z = readable_axes((1, 0, 0), (0, 1, 0), (0, -1, .01), (0, 0, 1))
        self.assertAlmostEqual(z[1], -1)
        self.assertAlmostEqual(x[2], 0)
        self.assertAlmostEqual(abs(y[2]), 1)

    def test_quarter_turn_hysteresis_avoids_boundary_jitter(self):
        args = ((1, 0, 0), (0, 1, 0))
        _, _, first = readable_axes(*args, (0, .69, .72), (0, 0, 1))
        _, _, held = readable_axes(*args, (0, .72, .69), (0, 0, 1), first)
        _, _, switched = readable_axes(*args, (0, .9, .4), (0, 0, 1), held)
        self.assertEqual(first, held)
        self.assertAlmostEqual(dot(first, switched), 0)
        self.assertGreater(dot(switched, (0, .9, .4)), 0)


if __name__ == '__main__': unittest.main()

class GlobalAxesTests(unittest.TestCase):
    def test_prefers_global_axis_in_face_tangent_plane(self):
        from Mesora.dimensions.layout import face_axis
        axis = face_axis((.85, 0, -.53), (1, 0, 0))
        self.assertAlmostEqual(abs(axis[1]), 1.0)
        self.assertAlmostEqual(axis[0], 0.0)
        self.assertAlmostEqual(axis[2], 0.0)
