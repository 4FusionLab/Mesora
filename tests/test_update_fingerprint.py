import unittest
from types import SimpleNamespace as NS

from Mesora.dimensions.update_fingerprint import geometry_fingerprint


def point(x=0, y=0, z=0):
    return NS(x=x, y=y, z=z)


class FingerprintTest(unittest.TestCase):
    def setUp(self):
        self.body = NS(revisionId='v1', isVisible=False,
                       boundingBox=NS(minPoint=point(), maxPoint=point(5, 5, 5)))
        self.entity = NS(isValid=True, objectType='SketchCircle',
                         worldGeometry=NS(objectType='Circle3D', center=point(), radius=1),
                         body=self.body)
        self.design = NS(rootComponent=NS(bRepBodies=[self.body], allOccurrences=[]),
                         unitsManager=NS(defaultLengthUnits='mm'))
        self.items = [('m1', 'radius', ['token'])]
        self.resolve = lambda design, ref: self.entity

    def fingerprint(self):
        return geometry_fingerprint(self.design, self.items, self.resolve, lambda kind, entities: 1)

    def test_same_value_sketch_translation_invalidates(self):
        before = self.fingerprint()
        self.entity.worldGeometry.center.x = 8
        self.assertNotEqual(before, self.fingerprint())

    def test_hidden_body_internal_change_invalidates_without_bounds_change(self):
        before = self.fingerprint()
        self.body.revisionId = 'v2'
        self.assertNotEqual(before, self.fingerprint())

    def test_missing_reference_and_restoration_invalidate(self):
        before = self.fingerprint()
        self.entity.isValid = False
        missing = self.fingerprint()
        self.assertNotEqual(before, missing)
        self.assertEqual(missing, self.fingerprint())
        self.entity.isValid = True
        self.assertEqual(before, self.fingerprint())

    def test_occurrence_move_with_same_value_invalidates(self):
        values = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        occurrence = NS(isVisible=True, transform2=NS(asArray=lambda: values), bRepBodies=[])
        self.design.rootComponent.allOccurrences = [occurrence]
        before = self.fingerprint()
        values[3] = 2
        self.assertNotEqual(before, self.fingerprint())

    def test_reissued_token_does_not_invalidate(self):
        before = self.fingerprint()
        self.items[0] = ('m1', 'radius', ['another token for same entity'])
        self.assertEqual(before, self.fingerprint())

    def test_units_change_invalidates_caption(self):
        before = self.fingerprint()
        self.design.unitsManager.defaultLengthUnits = 'in'
        self.assertNotEqual(before, self.fingerprint())
