import unittest
from Mesora.dimensions.label_layout import choose_caption, projected_caption_size, projection_scale


class CaptionLayoutTest(unittest.TestCase):
    def test_retina_projection_uses_logical_viewport_coordinate_scale(self):
        self.assertEqual(projection_scale(1710, 692, (1709, 692)), 2)
        self.assertEqual(projection_scale(1710, 692, (855, 346)), 1)
        self.assertEqual(projection_scale(1000, 600, (0, 0)), 1)

    def test_rotated_caption_bounds_cover_full_baseline_height(self):
        width, height = projected_caption_size(200, 20, (1, 1), (-1, 1))
        self.assertAlmostEqual(width, 220/2**.5)
        self.assertAlmostEqual(height, 220/2**.5)

    def test_layout_keeps_caption_inside_viewport(self):
        selected, _ = choose_caption(100, 20, [],
            [((10, 50), 'clipped'), ((60, 50), 'inside')], bounds=(0, 0, 200, 200))
        self.assertEqual(selected, 'inside')
    def test_coincident_captions_move_to_distinct_rectangles(self):
        occupied = []
        first, rect = choose_caption(100, 20, occupied, [((0, 0), 'original')])
        occupied.append(rect)
        second, other = choose_caption(100, 20, occupied,
            [((0, 0), 'overlap'), ((0, 35), 'clear')])
        self.assertEqual((first, second), ('original', 'clear'))
        self.assertGreater(other[1], rect[3])

    def test_long_captions_do_not_accept_small_horizontal_displacement(self):
        _, rect = choose_caption(200, 20, [], [((0, 0), None)])
        selected, _ = choose_caption(200, 20, [rect],
            [((50, 0), 'still-overlaps'), ((220, 0), 'clear')])
        self.assertEqual(selected, 'clear')
