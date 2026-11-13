"""Offline contract check for the packaged renderer with a synthetic Fusion API."""
import importlib
import sys
import types
import unittest
from unittest.mock import patch


class Point:
    def __init__(self, x, y, z): self.x, self.y, self.z = x, y, z


class Matrix:
    def __init__(self): self.origin = None; self.axes = None
    def setWithCoordinateSystem(self, origin, x, y, z):
        self.origin = origin; self.axes = (x, y, z); return True


class Group:
    def __init__(self): self.lines = None; self.text = None; self.isValid = True
    def addLines(self, coordinates, indices, strip):
        self.lines = types.SimpleNamespace(coords=coordinates); return self.lines
    def addText(self, caption, font, size, matrix):
        self.text = types.SimpleNamespace(caption=caption, width=1.0, transform=matrix, size=size)
        return self.text
    def deleteMe(self): return True


class FakeAPI:
    def __enter__(self):
        core = types.ModuleType('adsk.core'); fusion = types.ModuleType('adsk.fusion')
        core.Point3D = types.SimpleNamespace(create=Point)
        core.Vector3D = types.SimpleNamespace(create=Point)
        core.Matrix3D = types.SimpleNamespace(create=Matrix)
        core.Color = types.SimpleNamespace(create=lambda *a: a)
        fusion.CustomGraphicsCoordinates = types.SimpleNamespace(create=lambda coords: tuple(coords))
        fusion.CustomGraphicsSolidColorEffect = types.SimpleNamespace(create=lambda color: color)
        fusion.CustomGraphicsViewScale = types.SimpleNamespace(create=lambda scale, anchor: (scale, anchor))
        adsk = types.ModuleType('adsk'); adsk.core = core; adsk.fusion = fusion
        self.patch = patch.dict(sys.modules, {'adsk': adsk, 'adsk.core': core, 'adsk.fusion': fusion})
        self.patch.start(); sys.modules.pop('Mesora.renderer', None)
        return importlib.import_module('Mesora.renderer')
    def __exit__(self, *args):
        sys.modules.pop('Mesora.renderer', None); self.patch.stop()


class Eval:
    def getParameterExtents(self): return True, 0, 1
    def getLengthAtParameter(self, a, b): return True, 10
    def getEndPoints(self): return True, Point(0, 0, 0), Point(10, 0, 0)


class RendererPlaneTest(unittest.TestCase):
    def test_owned_cleanup_retains_staged_groups_and_reports_failed_deletion(self):
        with FakeAPI() as renderer:
            staged, failed, successful, unrelated = (Group() for _ in range(4))
            for group in (staged, failed, successful):
                group.id = renderer.OWNERSHIP_PREFIX + str(id(group))
            unrelated.id = ''
            deleted = []
            staged.deleteMe = lambda: self.fail('Staged group must survive cleanup')
            unrelated.deleteMe = lambda: self.fail('Untagged group belongs to another owner')
            failed.deleteMe = lambda: False
            successful.deleteMe = lambda: deleted.append(successful) or True
            groups = [staged, failed, successful, unrelated]
            collection = types.SimpleNamespace(count=len(groups), item=lambda i: groups[i])
            design = types.SimpleNamespace(rootComponent=types.SimpleNamespace(customGraphicsGroups=collection))
            renderer._LABELS[id(failed)] = 'retained failure bookkeeping'
            renderer._LABELS[id(successful)] = 'removed success bookkeeping'
            self.assertEqual(renderer.erase_owned(design, keep=[staged]), [failed])
            self.assertEqual(deleted, [successful])
            self.assertIn(id(failed), renderer._LABELS)
            self.assertNotIn(id(successful), renderer._LABELS)

    def test_undo_restored_owned_groups_are_cleaned_without_other_addins(self):
        owned = Group()
        owned.id = '4FusionLab.Mesora.89072f8c-cdca-48bf-8a2a-440c9ae898e6.graphics.v1:restored'
        other = Group()
        other.id = 'AnotherAddon.graphics'
        groups = [owned, other]
        def delete_owned():
            groups.remove(owned)
            owned.isValid = False
            return True
        owned.deleteMe = delete_owned
        collection = types.SimpleNamespace(count=2, item=lambda i: groups[i])
        design = types.SimpleNamespace(rootComponent=types.SimpleNamespace(customGraphicsGroups=collection))
        with FakeAPI() as renderer:
            self.assertEqual(renderer.erase_owned(design), [])
        self.assertEqual(groups, [other])

    def test_clearance_signature_invalidates_internal_body_changes(self):
        body = types.SimpleNamespace(revisionId='before',
            boundingBox=types.SimpleNamespace(minPoint=Point(0,0,0), maxPoint=Point(1,1,1)))
        with FakeAPI() as renderer, patch.object(renderer, 'visible_solids', return_value=[body]):
            before = renderer.obstacle_signature(object())
            body.revisionId = 'after'  # A hole changes without changing bounds.
            self.assertNotEqual(before, renderer.obstacle_signature(object()))

    def test_angle_layout_tracks_screen_scale_and_extends_short_sides(self):
        import math
        with FakeAPI() as renderer:
            camera = types.SimpleNamespace(viewExtents=1)
            def layout(scale):
                vp = types.SimpleNamespace(modelToViewSpace=lambda p: types.SimpleNamespace(x=p.x*scale, y=p.y*scale))
                return renderer.angle_layout((0,0,0), (1,0,0), (0,1,0), math.pi/2, 0, camera, vp)
            first, _ = layout(100)
            second, _ = layout(50)
            radius = math.dist(first[0][0], first[0][1])
            self.assertGreater(radius*100, 85)
            self.assertAlmostEqual(math.dist(second[0][0], second[0][1]), radius*2)
            self.assertGreater(radius, .01)  # Arc can extend beyond a 0.1 mm edge.

    def test_angle_draws_arc_with_degree_units(self):
        group = Group()
        units = types.SimpleNamespace(defaultLengthUnits='mm', formatValue=lambda v, unit, show: unit)
        design = types.SimpleNamespace(rootComponent=types.SimpleNamespace(customGraphicsGroups=types.SimpleNamespace(add=lambda: group)), unitsManager=units)
        camera = types.SimpleNamespace(eye=Point(0,0,10), upVector=Point(0,1,0))
        with FakeAPI() as renderer, patch.object(renderer, 'measure', return_value=1.5707963267948966), patch.object(renderer, 'angle_geometry', return_value=(1.5707963267948966, ((1,0,0),(0,0,0),(0,1,0)))):
            renderer.render(design, 'angle', [object(), object()], camera, 'm1')
            self.assertFalse(renderer._LABELS[id(group)][-1])
            self.assertAlmostEqual(abs(renderer.dot(renderer._LABELS[id(group)][2], (-2**-.5, 2**-.5, 0))), 1)
        self.assertEqual(group.text.caption, 'm1: deg')
        self.assertTrue(group.id.startswith(renderer.OWNERSHIP_PREFIX))
        self.assertFalse(group.isChildrenSelectable)
        self.assertFalse(group.isSelectable)
        self.assertGreater(len(group.lines.coords), 24)
        self.assertEqual(group.lines.coords[:3], (0,0,0))

    def test_command_layout_cache_reuses_only_matching_signature(self):
        with FakeAPI() as renderer:
            cache = {}
            calls = []
            def calculate():
                calls.append(True)
                return len(calls)
            self.assertEqual(renderer.cached_layout(cache, 'm1', ('edge', 0), calculate), 1)
            self.assertEqual(renderer.cached_layout(cache, 'm1', ('edge', 0), calculate), 1)
            self.assertEqual(renderer.cached_layout(cache, 'm1', ('edge', 1), calculate), 2)
            self.assertEqual(renderer.cached_layout(cache, 'm2', ('edge', 1), calculate), 3)
            self.assertEqual(renderer.cached_layout(None, 'm1', ('edge', 0), calculate), 4)

    def test_linear_output_uses_model_plane_with_camera_readable_text(self):
        face = types.SimpleNamespace(geometry=types.SimpleNamespace(objectType='adsk::core::Plane', normal=Point(0,0,1)), pointOnFace=Point(5,3,0), isPointOnFace=lambda p: p.y > 0)
        edge = types.SimpleNamespace(objectType='adsk::fusion::BRepEdge', geometry=types.SimpleNamespace(objectType='adsk::core::Line3D'), evaluator=Eval(), faces=[face])
        groups = []
        def add_group():
            group = Group(); groups.append(group); return group
        design = types.SimpleNamespace(rootComponent=types.SimpleNamespace(customGraphicsGroups=types.SimpleNamespace(add=add_group)), unitsManager=types.SimpleNamespace(defaultLengthUnits='mm', formatValue=lambda v, unit, show: '100 mm'))
        with FakeAPI() as renderer:
            camera = types.SimpleNamespace(eye=Point(5,-10,10), upVector=Point(0,0,1))
            with patch.object(renderer, 'edge_clearance', side_effect=lambda root, edge, a, b, off, side: (side, off)):
                group = renderer.render(design, 'edge_length', [edge], camera)
            self.assertEqual(group.lines.weight, 1)
            self.assertEqual(group.lines.color, (0,0,0,255))
            self.assertEqual(group.text.caption, '100 mm')
            axis_z = group.text.transform.axes[2]
            self.assertAlmostEqual(abs(axis_z.z), 1)
            coords = group.lines.coords
            self.assertEqual(coords[:3], (0, 0, 0))
            self.assertEqual(coords[6:9], (10, 0, 0))
            self.assertLess(coords[4], 0)  # Away from the face interior.

    def test_linear_offset_is_relative_to_automatic_placement(self):
        face = types.SimpleNamespace(geometry=types.SimpleNamespace(objectType='adsk::core::Plane', normal=Point(0,0,1)), pointOnFace=Point(5,3,0), isPointOnFace=lambda p: p.y > 0)
        edge = types.SimpleNamespace(objectType='adsk::fusion::BRepEdge', geometry=types.SimpleNamespace(objectType='adsk::core::Line3D'), evaluator=Eval(), faces=[face])
        design = types.SimpleNamespace(rootComponent=types.SimpleNamespace(customGraphicsGroups=types.SimpleNamespace(add=Group)), unitsManager=types.SimpleNamespace(defaultLengthUnits='mm', formatValue=lambda *a: '100 mm'))
        camera = types.SimpleNamespace(eye=Point(5,-10,10), upVector=Point(0,0,1))
        with FakeAPI() as renderer, patch.object(renderer, 'edge_clearance', side_effect=lambda root, edge, a, b, off, side: (side, off)):
            baseline = renderer.render(design, 'edge_length', [edge], camera)
            shifted = renderer.render(design, 'edge_length', [edge], camera, offset=2)
            self.assertAlmostEqual(abs(shifted.lines.coords[13] - baseline.lines.coords[13]), 2)

    def test_face_annotation_is_in_face_plane_and_has_bounded_text_size(self):
        face = types.SimpleNamespace(objectType='adsk::fusion::BRepFace', area=10000,
            pointOnFace=Point(0, 0, 0),
            evaluator=types.SimpleNamespace(getNormalAtPoint=lambda p: (True, Point(1, 0, 0))))
        groups = []
        def add_group():
            group = Group(); groups.append(group); return group
        design = types.SimpleNamespace(rootComponent=types.SimpleNamespace(customGraphicsGroups=types.SimpleNamespace(add=add_group)), unitsManager=types.SimpleNamespace(defaultLengthUnits='mm', formatValue=lambda *a: '1000000 mm^2'))
        with FakeAPI() as renderer:
            camera = types.SimpleNamespace(eye=Point(10,10,10), upVector=Point(0,0,1))
            group = renderer.render(design, 'area', [face], camera, 'm1')
            for axis in group.text.transform.axes[:2]:
                self.assertAlmostEqual(axis.x, 0)
            self.assertLess(group.text.size, 2)
            self.assertEqual(group.text.caption, 'm1: A = 1000000 mm^2')

    def test_inner_edge_uses_local_face_not_remote_interior_point(self):
        # The local face is above this inner edge even though the arbitrary
        # pointOnFace is across the hole. The outside is below the edge.
        face = types.SimpleNamespace(geometry=types.SimpleNamespace(objectType='adsk::core::Plane', normal=Point(0,0,1)), pointOnFace=Point(5,-5,0), isPointOnFace=lambda p: p.y > 0)
        edge = types.SimpleNamespace(objectType='adsk::fusion::BRepEdge', geometry=types.SimpleNamespace(objectType='adsk::core::Line3D'), evaluator=Eval(), faces=[face])
        with FakeAPI() as renderer:
            normal, outward = renderer.edge_plane(edge, (5, 0, 0))
            self.assertLess(outward[1], 0)


if __name__ == '__main__': unittest.main()

class SegmentClearanceTest(unittest.TestCase):
    def test_clipped_leaders_begin_at_measurement_points_when_clear(self):
        with FakeAPI() as renderer:
            with patch.object(renderer, 'visible_solids', return_value=[]), patch.object(renderer, 'visible_segments', side_effect=lambda root, bodies, start, end, tolerance: [(start, end)]), patch.object(renderer, 'segment_is_clear', return_value=True):
                _, _, segments = renderer.clipped_edge_layout(object(), (0, 0, 0), (10, 0, 0), 2, (0, 1, 0))
            self.assertEqual(segments[0][0], (0, 0, 0))
            self.assertEqual(segments[1][0], (10, 0, 0))

    def test_rejects_thin_obstacle_between_containment_samples(self):
        class Collection(list):
            @property
            def count(self): return len(self)
        class Root:
            def findBRepUsingRay(self, origin, direction, kind, tolerance, visible, hits):
                hits.append(Point(.13, 0, 0))
                return Collection([object()])
        with FakeAPI() as renderer:
            renderer.adsk.core.ObjectCollection = types.SimpleNamespace(create=Collection)
            renderer.adsk.fusion.PointContainment = types.SimpleNamespace(PointOutsidePointContainment=2)
            renderer.adsk.fusion.BRepEntityTypes = types.SimpleNamespace(BRepFaceEntityType=1)
            body = types.SimpleNamespace(pointContainment=lambda p: 2)
            self.assertFalse(renderer.segment_is_clear(Root(), [body], (0, 0, 0), (1, 0, 0), .0001))

    def test_rejects_line_wholly_inside_solid_even_without_ray_hits(self):
        class Root:
            def findBRepUsingRay(self, *args):
                self.fail('must reject inside point before casting ray')
        with FakeAPI() as renderer:
            renderer.adsk.fusion.PointContainment = types.SimpleNamespace(PointOutsidePointContainment=2)
            body = types.SimpleNamespace(pointContainment=lambda p: 0)
            self.assertFalse(renderer.segment_is_clear(Root(), [body], (0, 0, 0), (1, 0, 0), .0001))

class TextLegibilityTest(unittest.TestCase):
    def test_label_uses_screen_scale_independent_of_measured_value(self):
        face = types.SimpleNamespace(objectType='adsk::fusion::BRepFace', area=.27,
            pointOnFace=Point(0, 0, 0),
            evaluator=types.SimpleNamespace(getNormalAtPoint=lambda p: (True, Point(0, 0, 1))))
        group = Group()
        design = types.SimpleNamespace(rootComponent=types.SimpleNamespace(customGraphicsGroups=types.SimpleNamespace(add=lambda: group)), unitsManager=types.SimpleNamespace(defaultLengthUnits='mm', formatValue=lambda *a: '27 mm^2'))
        with FakeAPI() as renderer:
            renderer.adsk.fusion.CustomGraphicsViewScale = types.SimpleNamespace(create=lambda scale, anchor: (scale, anchor))
            camera = types.SimpleNamespace(eye=Point(0,0,10), upVector=Point(0,1,0))
            renderer.render(design, 'area', [face], camera)
            self.assertGreaterEqual(group.text.size * group.text.viewScale[0], 14)
            anchor = group.text.viewScale[1]
            self.assertAlmostEqual(anchor.x, group.text.width / 2)
            self.assertAlmostEqual(anchor.y, -group.text.size * .25)

class FaceLabelDirectionTest(unittest.TestCase):
    def test_face_label_prefers_projected_screen_horizontal(self):
        face = types.SimpleNamespace(objectType='adsk::fusion::BRepFace', area=10,
            pointOnFace=Point(0, 0, 0),
            evaluator=types.SimpleNamespace(getNormalAtPoint=lambda p: (True, Point(1, 0, 0))))
        group = Group()
        design = types.SimpleNamespace(rootComponent=types.SimpleNamespace(customGraphicsGroups=types.SimpleNamespace(add=lambda: group)), unitsManager=types.SimpleNamespace(defaultLengthUnits='mm', formatValue=lambda *a: '100 mm^2'))
        with FakeAPI() as renderer:
            camera = types.SimpleNamespace(eye=Point(10,10,10), upVector=Point(0,0,1))
            renderer.render(design, 'area', [face], camera)
            x = group.text.transform.axes[0]
            self.assertGreater(abs(x.y), .99)
            self.assertAlmostEqual(x.z, 0)


class RadialGeometryTest(unittest.TestCase):
    def test_radius_label_anchor_is_at_end_of_leader(self):
        face = types.SimpleNamespace(objectType='adsk::fusion::BRepFace', geometry=types.SimpleNamespace(objectType='adsk::core::Cylinder', radius=1, axis=Point(0,0,1), origin=Point(0,0,0)), pointOnFace=Point(1,0,0))
        group=Group()
        design=types.SimpleNamespace(rootComponent=types.SimpleNamespace(customGraphicsGroups=types.SimpleNamespace(add=lambda: group)), unitsManager=types.SimpleNamespace(defaultLengthUnits='mm', formatValue=lambda *a: '10 mm'))
        camera=types.SimpleNamespace(eye=Point(0,-10,0), upVector=Point(0,0,1), viewExtents=10)
        with FakeAPI() as renderer:
            renderer.render(design, 'radius', [face], camera)
            _, label, *_ = renderer._LABELS[id(group)]
            self.assertEqual(label, group.lines.coords[-3:])

    def test_concave_radius_offset_is_not_silently_clamped(self):
        face = types.SimpleNamespace(objectType='adsk::fusion::BRepFace', geometry=types.SimpleNamespace(objectType='adsk::core::Cylinder', radius=5, axis=Point(0,0,1), origin=Point(0,0,0)), pointOnFace=Point(5,0,0), body=types.SimpleNamespace(pointContainment=lambda p: 0 if p.x > 5 else 2))
        design=types.SimpleNamespace(rootComponent=types.SimpleNamespace(customGraphicsGroups=types.SimpleNamespace(add=Group)), unitsManager=types.SimpleNamespace(defaultLengthUnits='mm', formatValue=lambda *a: '50 mm'))
        camera=types.SimpleNamespace(eye=Point(0,-10,0), upVector=Point(0,0,1), viewExtents=1)
        with FakeAPI() as renderer:
            renderer.adsk.fusion.PointContainment = types.SimpleNamespace(PointOutsidePointContainment=2)
            with patch.object(renderer, 'segment_is_clear', return_value=True), patch.object(renderer, 'visible_solids', return_value=[face.body]):
                g1=renderer.render(design,'radius',[face],camera,offset=4)
                g2=renderer.render(design,'radius',[face],camera,offset=6)
            self.assertAlmostEqual(g1.lines.coords[-3] - g2.lines.coords[-3], 2)
            with patch.object(renderer, 'segment_is_clear', return_value=False), patch.object(renderer, 'visible_solids', return_value=[face.body]):
                with self.assertRaisesRegex(ValueError, 'intersects a solid'):
                    renderer.render(design, 'radius', [face], camera, offset=6)

    def test_radial_label_stays_along_leader_when_camera_moves(self):
        face = types.SimpleNamespace(objectType='adsk::fusion::BRepFace',
            geometry=types.SimpleNamespace(objectType='adsk::core::Cylinder', radius=1, axis=Point(0,0,1), origin=Point(0,0,0)), pointOnFace=Point(1,0,0))
        group=Group()
        design=types.SimpleNamespace(rootComponent=types.SimpleNamespace(customGraphicsGroups=types.SimpleNamespace(add=lambda: group)), unitsManager=types.SimpleNamespace(defaultLengthUnits='mm', formatValue=lambda *a: '10 mm'))
        camera=types.SimpleNamespace(eye=Point(0,-10,0), upVector=Point(0,0,1), viewExtents=10)
        with FakeAPI() as renderer:
            renderer.render(design, 'radius', [face], camera)
            text, anchor, *_ = renderer._LABELS[id(group)]
            self.assertGreater(anchor[0], 1)
            self.assertFalse(renderer._LABELS[id(group)][-1])
            original_lines = group.lines.coords
            camera.eye = Point(0, 0, 10)
            camera.upVector = Point(0, 1, 0)
            renderer.orient_text(group, camera)
            axis = renderer.xyz(group.text.transform.axes[0])
            self.assertAlmostEqual(abs(renderer.dot(axis, (1, 0, 0))), 1)
            self.assertEqual(group.lines.coords, original_lines)
            self.assertEqual(group.lines.coords[:6], (0,0,0,1,0,0))

    def test_concave_radius_label_stays_outside_solid(self):
        face = types.SimpleNamespace(objectType='adsk::fusion::BRepFace',
            geometry=types.SimpleNamespace(objectType='adsk::core::Cylinder', radius=5, axis=Point(0,0,1), origin=Point(0,0,0)),
            pointOnFace=Point(5,0,0), body=types.SimpleNamespace(pointContainment=lambda p: 0 if p.x > 5 else 2))
        group=Group()
        design=types.SimpleNamespace(rootComponent=types.SimpleNamespace(customGraphicsGroups=types.SimpleNamespace(add=lambda: group)), unitsManager=types.SimpleNamespace(defaultLengthUnits='mm', formatValue=lambda *a: '50 mm'))
        camera=types.SimpleNamespace(eye=Point(0,-10,0), upVector=Point(0,0,1), viewExtents=1)
        with FakeAPI() as renderer:
            renderer.adsk.fusion.PointContainment = types.SimpleNamespace(PointOutsidePointContainment=2)
            renderer.render(design, 'radius', [face], camera)
            _, anchor, *_ = renderer._LABELS[id(group)]
            self.assertLess(anchor[0], 5)
            self.assertEqual(face.body.pointContainment(Point(*anchor)), 2)
            self.assertEqual(group.lines.coords[:6], (0,0,0,5,0,0))

    def test_cylinder_radius_line_connects_centre_to_circumference(self):
        face = types.SimpleNamespace(objectType='adsk::fusion::BRepFace',
            geometry=types.SimpleNamespace(objectType='adsk::core::Cylinder', radius=1, axis=Point(0,0,1), origin=Point(0,0,0)),
            pointOnFace=Point(1,0,0))
        group=Group()
        design=types.SimpleNamespace(rootComponent=types.SimpleNamespace(customGraphicsGroups=types.SimpleNamespace(add=lambda: group)), unitsManager=types.SimpleNamespace(defaultLengthUnits='mm', formatValue=lambda *a: '10 mm'))
        with FakeAPI() as renderer:
            renderer.render(design, 'radius', [face], types.SimpleNamespace(eye=Point(10,10,10), upVector=Point(0,0,1)))
        self.assertEqual(group.lines.coords[:6], (0,0,0,1,0,0))

class MinimumDistanceRenderTest(unittest.TestCase):
    def test_zero_distance_creates_marker_without_degenerate_axis(self):
        group=Group()
        design=types.SimpleNamespace(rootComponent=types.SimpleNamespace(customGraphicsGroups=types.SimpleNamespace(add=lambda: group)), unitsManager=types.SimpleNamespace(defaultLengthUnits='mm', formatValue=lambda *a:'0.0 mm'))
        camera=types.SimpleNamespace(eye=Point(4,4,5),upVector=Point(0,0,1))
        with FakeAPI() as renderer:
            with patch.object(renderer,'measure',return_value=0), patch.object(renderer,'minimum_distance',return_value=(0,(0,0,0),(0,0,0))):
                renderer.render(design,'distance',[object(),object()],camera,'m1')
            self.assertEqual(group.text.caption,'m1: Min = 0.0 mm')
            self.assertEqual(len(group.lines.coords),12)
