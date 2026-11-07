import unittest
from types import SimpleNamespace

from dimensions.fusion_geometry import ResolutionError, measure, reference_for, resolve
from dimensions.measurement import MeasurementError
from dimensions.model import EntityReference


def obj(kind, **kwargs):
    return SimpleNamespace(objectType='adsk::' + kind, isValid=True, **kwargs)


class Design:
    def __init__(self, objects):
        self.objects = objects

    def findEntityByToken(self, token):
        return self.objects.get(token, [])


class GeometryTest(unittest.TestCase):
    def test_ambiguous_and_missing_references_are_rejected(self):
        design = Design({'ambiguous': [obj('fusion::BRepEdge'), obj('fusion::BRepEdge')]})
        for token in ('ambiguous', 'missing'):
            with self.assertRaises(ResolutionError):
                resolve(design, EntityReference(token))

    def test_radius_requires_analytic_circular_type(self):
        cylinder = obj('fusion::BRepFace', geometry=obj('core::Cylinder', radius=0.5))
        self.assertEqual(measure('diameter', [cylinder]), 1.0)
        ellipse = obj('fusion::BRepEdge', geometry=obj('core::Ellipse3D', radius=5))
        with self.assertRaises(MeasurementError):
            measure('radius', [ellipse])

    def test_points_use_world_geometry_for_sketch_points(self):
        a = obj('fusion::SketchPoint', worldGeometry=SimpleNamespace(x=1, y=2, z=3))
        b = obj('fusion::BRepVertex', geometry=SimpleNamespace(x=1, y=2, z=13))
        self.assertEqual(measure('distance', [a, b]), 10)

    def test_occurrence_reference_restores_proxy(self):
        occurrence = obj('fusion::Occurrence', entityToken='occ')
        native = obj('fusion::BRepEdge', entityToken='edge')
        proxy = obj('fusion::BRepEdge', nativeObject=native, assemblyContext=occurrence)
        native.createForAssemblyContext = lambda context: proxy if context is occurrence else None
        ref = reference_for(proxy)
        self.assertEqual(ref, EntityReference('edge', 'occ'))
        self.assertIs(resolve(Design({'edge': [native], 'occ': [occurrence]}), ref), proxy)

class MinimumDistanceTests(unittest.TestCase):
    def test_face_distance_uses_fusion_closest_points(self):
        from unittest.mock import patch
        from types import SimpleNamespace as O, ModuleType
        import sys
        from Mesora.dimensions.fusion_geometry import minimum_distance
        first, second = object(), object()
        p1,p2=O(x=0,y=0,z=0),O(x=0,y=0,z=2)
        manager=O(measureMinimumDistance=lambda a,b: O(value=2,positionOne=p1,positionTwo=p2))
        core=ModuleType('adsk.core'); core.Application=O(get=lambda:O(measureManager=manager))
        adsk=ModuleType('adsk'); adsk.core=core
        with patch.dict(sys.modules, {'adsk':adsk,'adsk.core':core}):
            value,a,b=minimum_distance(first,second)
        self.assertEqual((value,a,b),(2,(0,0,0),(0,0,2)))
