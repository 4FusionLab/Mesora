import unittest
from Mesora.dimensions import layout


class ClearanceTests(unittest.TestCase):
    def test_avoids_blocked_preferred_side(self):
        side, distance = layout.find_clear_placement((1, 0, 0), (0, -1, 0), 1, lambda s, d: s[1] > .5)
        self.assertGreater(side[1], .5)
        self.assertEqual(distance, 1)

    def test_uses_shorter_offset_for_narrow_space(self):
        side, distance = layout.find_clear_placement((1, 0, 0), (0, 1, 0), 1, lambda s, d: s[1] > .99 and d <= .3)
        self.assertLessEqual(distance, .3)
        self.assertGreater(distance, 0)

    def test_no_clear_placement_is_explicit(self):
        with self.assertRaisesRegex(ValueError, 'clear'):
            layout.find_clear_placement((1, 0, 0), (0, 1, 0), 1, lambda s, d: False)

    def test_reversed_edge_has_identical_result(self):
        check = lambda s, d: s[2] > .5
        a = layout.find_clear_placement((1, 0, 0), (0, 1, 0), 1, check)
        b = layout.find_clear_placement((-1, 0, 0), (0, 1, 0), 1, check)
        self.assertEqual(a, b)

class ClippedIntervalsTests(unittest.TestCase):
    def test_discards_material_intervals_and_keeps_visible_pieces(self):
        pieces = layout.clear_intervals(10, [3, 5], .01, lambda a, b: b <= 3 or a >= 5)
        self.assertEqual(len(pieces), 2)
        self.assertEqual(pieces[0][0], 0)
        self.assertLess(pieces[0][1], 3)
        self.assertGreater(pieces[1][0], 5)
        self.assertEqual(pieces[1][1], 10)

    def test_tiny_and_duplicate_hit_intervals_are_ignored(self):
        pieces = layout.clear_intervals(1, [0, .5, .5, 1], .001, lambda a, b: True)
        self.assertEqual(len(pieces), 2)
        self.assertGreater(pieces[1][0], pieces[0][1])

class SurfaceSeparationTests(unittest.TestCase):
    def test_chooses_clear_direction_away_from_both_adjacent_planes(self):
        side, distance = layout.find_clear_placement(
            (0, 0, 1), (-1, 0, 0), 1,
            lambda s, d: s[0] < -.1 and s[1] > .1,
            surface_normals=[(1, 0, 0), (0, 1, 0)])
        self.assertGreater(min(abs(side[0]), abs(side[1])), .65)
        self.assertEqual(distance, 1)

class GlobalAxisPlacementTests(unittest.TestCase):
    def test_prefers_clear_axis_over_diagonal_between_adjacent_faces(self):
        direction = (.8870108331782217, 0, -.461748613235034)
        normal = (.461748613235034, 0, .8870108331782217)
        side, _ = layout.find_clear_placement(direction, (0, 1, 0), 1,
            lambda candidate, distance: candidate[1] >= -1e-9 and layout.dot(candidate, normal) >= -1e-9,
            surface_normals=[normal, (0, 1, 0)])
        self.assertAlmostEqual(side[0], 0)
        self.assertAlmostEqual(side[1], 1)
        self.assertAlmostEqual(side[2], 0)

    def test_prefers_global_vertical_when_clear_of_adjacent_face(self):
        side, _ = layout.find_clear_placement((0,1,0),(.887,0,-.462),1,lambda s,d:s[2]>.8,surface_normals=[(.462,0,.887)])
        self.assertGreater(side[2], .98)
