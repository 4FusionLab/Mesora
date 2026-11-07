import unittest
from types import SimpleNamespace as O
from Mesora.dimensions.batch import Batch, compatible
from Mesora.dimensions.fusion_geometry import measure


def entity(kind, **kw):
    return O(objectType='adsk::fusion::' + kind, **kw)


class BatchTest(unittest.TestCase):
    def test_face_measurements_include_all_boundary_edges(self):
        def edge(length):
            return O(evaluator=O(getParameterExtents=lambda: (True, 0, 1), getLengthAtParameter=lambda a, b: (True, length)))
        face = entity('BRepFace', area=12, edges=[edge(3), edge(4)])
        self.assertEqual(measure('area', [face]), 12)
        self.assertEqual(measure('perimeter', [face]), 7)
        self.assertEqual(compatible([face]), ['area', 'perimeter'])

    def test_points_are_paired_and_ids_are_never_reused(self):
        p = lambda x: entity('BRepVertex', geometry=O(x=x, y=0, z=0))
        batch = Batch()
        self.assertIsNone(batch.add(p(0)))
        self.assertEqual(batch.add(p(1)).id, 'm1')
        batch.remove('m1')
        batch.add(p(2))
        self.assertEqual(batch.add(p(3)).id, 'm2')

    def test_round_edge_compatible_kinds_and_independent_choice(self):
        ev=O(getParameterExtents=lambda: (True, 0, 1), getLengthAtParameter=lambda a,b: (True, 3))
        edge=entity('BRepEdge', evaluator=ev, geometry=O(objectType='adsk::core::Circle3D', radius=2))
        batch=Batch(); first=batch.add(edge); second=batch.add(edge)
        self.assertEqual(first.options, ['edge_length', 'radius', 'diameter'])
        batch.set_kind(first.id, 'diameter')
        self.assertEqual((first.kind, second.kind), ('diameter', 'edge_length'))
        with self.assertRaises(ValueError): batch.set_kind(first.id, 'area')

class DuplicateMeasurementTest(unittest.TestCase):
    def test_same_geometry_and_kind_is_duplicate_but_other_kind_is_allowed(self):
        from Mesora.dimensions.batch import duplicate_rows
        face = object()
        rows = [O(id='m1',kind='area',entities=(face,)), O(id='m2',kind='perimeter',entities=(face,)), O(id='m3',kind='area',entities=(face,))]
        self.assertEqual(duplicate_rows(rows), {'m3'})

    def test_reversed_distance_is_duplicate(self):
        from Mesora.dimensions.batch import duplicate_rows
        a,b=object(),object()
        rows=[O(id='m1',kind='distance',entities=(a,b)),O(id='m2',kind='distance',entities=(b,a))]
        self.assertEqual(duplicate_rows(rows), {'m2'})

    def test_reversed_angle_is_duplicate(self):
        from Mesora.dimensions.batch import duplicate_rows
        a,b=object(),object()
        rows=[O(id='m1',kind='angle',entities=(a,b)),O(id='m2',kind='angle',entities=(b,a))]
        self.assertEqual(duplicate_rows(rows), {'m2'})

    def test_angle_preserves_both_objects_when_selected(self):
        from unittest.mock import patch
        from Mesora.dimensions.batch import RowDraft
        a=entity('BRepFace',area=5,edges=[]);b=entity('BRepFace',area=5,edges=[])
        with patch('Mesora.dimensions.batch.measure', side_effect=lambda kind, entities: 1 if kind in ('angle', 'area') else (_ for _ in ()).throw(ValueError())):
            row=RowDraft('m1');row.set_first(a);row.set_second(b);row.set_kind('distance')
            self.assertIn('angle', row.options)
            row.set_kind('angle')
            self.assertTrue(row.complete)
            self.assertEqual(row.entities, (a,b))

class RowDraftTest(unittest.TestCase):
    def test_independent_rows_can_replace_and_clear_geometry(self):
        from Mesora.dimensions.batch import RowDraft
        face1=entity('BRepFace',area=5,edges=[]); face2=entity('BRepFace',area=7,edges=[])
        a,b=RowDraft('m1'),RowDraft('m2')
        a.set_first(face1); b.set_first(face2)
        a.set_first(face2)
        self.assertIs(a.entities[0],face2)
        a.set_first(None)
        self.assertFalse(a.complete)
        self.assertTrue(b.complete)
    def test_point_pair_stays_incomplete_until_second_is_selected(self):
        from Mesora.dimensions.batch import RowDraft
        p=lambda x: entity('BRepVertex', geometry=O(x=x,y=0,z=0))
        draft=RowDraft('m1'); draft.set_first(p(0))
        self.assertFalse(draft.complete)
        draft.set_second(p(1)); self.assertTrue(draft.complete)
        self.assertEqual(draft.kind,'distance')
        draft.set_second(None); self.assertFalse(draft.complete)

class GeometryReplacementTest(unittest.TestCase):
    def test_replacing_first_object_preserves_second_for_distance(self):
        from Mesora.dimensions.batch import RowDraft
        face=lambda area: entity('BRepFace', area=area, edges=[])
        first, second, replacement = face(1), face(2), face(3)
        row=RowDraft('m1'); row.set_first(first); row.set_second(second); row.set_kind('distance')
        row.set_first(None)
        self.assertIs(row.second, second)
        row.set_first(replacement)
        self.assertEqual(row.kind, 'distance')
        self.assertEqual(row.entities, (replacement, second))

class FaceDistanceDraftTest(unittest.TestCase):
    def test_face_can_switch_to_distance_and_wait_for_second_geometry(self):
        from Mesora.dimensions.batch import RowDraft
        ev=O(getParameterExtents=lambda: (True,0,1), getLengthAtParameter=lambda a,b: (True,2))
        face=entity('BRepFace',area=5,edges=[O(evaluator=ev)])
        row=RowDraft('m1'); row.set_first(face)
        self.assertIn('area', row.options)
        self.assertIn('perimeter', row.options)
        self.assertNotIn('distance', row.options)
        self.assertNotIn('angle', row.options)
        with self.assertRaises(ValueError): row.set_kind('distance')
        row.set_second(entity('BRepFace',area=7,edges=[]))
        self.assertIn('distance', row.options)
        self.assertNotIn('area', row.options)
        self.assertNotIn('perimeter', row.options)
        with self.assertRaises(ValueError): row.set_kind('area')
        with self.assertRaises(ValueError): row.set_kind('perimeter')
        row.set_second(None)
        self.assertIn('area', row.options)
        self.assertIn('perimeter', row.options)
        self.assertNotIn('distance', row.options)
        self.assertNotIn('angle', row.options)
