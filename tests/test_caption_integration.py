"""Exercise batch placement through actual command/document lifecycle handlers."""
import types
import unittest
from unittest.mock import Mock, patch

import test_visibility_lifecycle as lifecycle
from test_renderer_model_plane import Matrix, Point


class Group:
    def __init__(self, ident):
        self.id = ident
        self.isValid = self.isVisible = True
        self.deleted = False

    def addLines(self, coordinates, indices, strip):
        return types.SimpleNamespace(coordinates=coordinates)

    def deleteMe(self):
        self.deleted = True
        self.isValid = False
        return True


class CaptionIntegrationTest(unittest.TestCase):
    tearDown = lifecycle.LifecycleTest.tearDown

    def setUp(self):
        lifecycle.LifecycleTest.setUp(self)
        self.arrangement_patch.stop()  # Exercise the actual screen-space arranger.
        # Other suites reload adsk stubs; bind both adapters to this fixture's API.
        renderer_api = patch.object(self.m.renderer, 'adsk', self.m.adsk)
        renderer_api.start()
        self.addCleanup(renderer_api.stop)
        core, fusion = self.m.adsk.core, self.m.adsk.fusion
        core.Point3D = types.SimpleNamespace(create=Point)
        core.Vector3D = types.SimpleNamespace(create=Point)
        core.Matrix3D = types.SimpleNamespace(create=Matrix)
        fusion.CustomGraphicsCoordinates = types.SimpleNamespace(create=lambda value: tuple(value))
        self.m.APP.activeViewport.camera = types.SimpleNamespace(eye=Point(0, 0, 10), upVector=Point(0, 1, 0))
        self.m.APP.activeViewport.modelToViewSpace = lambda p: Point(p.x * 100, p.y * 100, 0)
        self.m.UI.messageBox = Mock()
        self.state.design = types.SimpleNamespace(rootComponent=object())
        self.created = []

    def render(self, design, kind, entities, camera, ident, **kwargs):
        group = Group(ident)
        self.created.append(group)
        # Real placement data, deliberately coincident for every measurement.
        self.m.renderer._LABELS[id(group)] = (
            types.SimpleNamespace(width=10, color=(0, 0, 0, 255)),
            (0, 0, 0), (1, 0, 0), (0, 1, 0), 1, None, False)
        return group

    def assert_separated(self, groups):
        boxes = []
        for group in groups:
            anchor = self.m.renderer._LABELS[id(group)][1]
            p = self.m.APP.activeViewport.modelToViewSpace(Point(*anchor))
            rect = (p.x - 85, p.y - 15, p.x + 85, p.y + 15)
            self.assertTrue(all(rect[2] <= other[0] or other[2] <= rect[0] or
                                rect[3] <= other[1] or other[3] <= rect[1]
                                for other in boxes), 'Captions from the same batch overlap')
            boxes.append(rect)

    def rows(self, count):
        return [types.SimpleNamespace(id='m' + str(i), kind='radius',
                                      entities=('edge' + str(i),), visible=True, offset=.25)
                for i in range(1, count + 1)]

    def test_refresh_and_preview_pack_six_simultaneous_captions_without_changing_offsets(self):
        self.state.items = [(r.id, r.kind, r.entities) for r in self.rows(6)]
        self.state.offsets = {row[0]: .25 for row in self.state.items}
        with patch.object(self.m, 'resolve', side_effect=lambda d, r: r), \
                patch.object(self.m, 'geometry_fingerprint', return_value=('current',)), \
                patch.object(self.m.renderer, 'render', side_effect=self.render):
            self.assertEqual(self.state.refresh(), [])
        self.assertEqual(len(self.state.groups), 6)
        self.assert_separated(self.state.groups)
        self.assertEqual(set(self.state.offsets.values()), {.25})
        context = types.SimpleNamespace(visible=True, batch=types.SimpleNamespace(rows=self.rows(6)),
                                        layout_cache={}, preview_groups=[], sync_batch=lambda: ([], set()),
                                        update_status=Mock())
        context.clear_preview = lambda: context.preview_groups.clear()
        args = types.SimpleNamespace(command=types.SimpleNamespace(commandInputs=object()), isValidResult=True)
        with patch.object(self.m.renderer, 'render', side_effect=self.render), \
                patch.object(self.m.renderer, 'obstacle_signature', return_value=()):
            self.m.Preview(context).notify(args)
            self.assertEqual(len(context.preview_groups), 6)
            self.assert_separated(context.preview_groups)
            # Hidden rows must not keep occupying a previous preview's rectangle.
            context.batch.rows[0].visible = False
            self.m.Preview(context).notify(args)
        self.assertEqual(len(context.preview_groups), 5)
        self.assertEqual(self.m.renderer._LABELS[id(context.preview_groups[0])][1], (0, 0, 0))
        self.assert_separated(context.preview_groups)
        self.assertEqual([r.offset for r in context.batch.rows], [.25] * 6)
        self.assertFalse(args.isValidResult)

    def test_execute_packs_new_set_before_persisting_and_keeps_offsets_as_user_values(self):
        context = types.SimpleNamespace(clear_preview=Mock(), visible=True,
                                        batch=types.SimpleNamespace(rows=self.rows(6), next_id=7))
        def persist(design, items, offsets, hidden, visible):
            self.assert_separated(self.created)
            self.assertEqual(offsets, {'m' + str(i): .25 for i in range(1, 7)})
        with patch.object(self.m, 'reference_for', side_effect=lambda e: e), \
                patch.object(self.m, 'resolve', side_effect=lambda d, r: r), \
                patch.object(self.m, 'geometry_fingerprint', return_value=('new',)), \
                patch.object(self.m, 'save_state', side_effect=persist), \
                patch.object(self.m.renderer, 'render', side_effect=self.render):
            self.m.Execute('add', context).notify(None)
        self.assertEqual(len(self.state.groups), 6)
        self.assert_separated(self.state.groups)
        self.assertEqual(set(self.state.offsets.values()), {.25})
        self.m.UI.messageBox.assert_not_called()

    def test_execute_placement_failure_preserves_committed_graphics_and_definitions(self):
        old = self.render(None, None, None, None, 'old')
        self.state.groups = [old]
        self.state.items = [('m9', 'radius', ('committed',))]
        self.created.clear()
        context = types.SimpleNamespace(clear_preview=Mock(), visible=True,
                                        batch=types.SimpleNamespace(rows=self.rows(2), next_id=3))
        with patch.object(self.m, 'reference_for', side_effect=lambda e: e), \
                patch.object(self.m, 'resolve', side_effect=lambda d, r: r), \
                patch.object(self.m.renderer, 'render', side_effect=self.render), \
                patch.object(self.m.renderer, 'arrange_labels', side_effect=ValueError('No caption space')):
            self.m.Execute('add', context).notify(None)
        self.assertTrue(old.isValid)
        self.assertEqual(self.state.groups, [old])
        self.assertEqual(self.state.items, [('m9', 'radius', ('committed',))])
        self.m.save_state.assert_not_called()
        self.assertTrue(all(g.deleted for g in self.created))
        self.m.UI.messageBox.assert_called_once()

    def test_orbit_preserves_preview_placement_and_cancel_reflows_restored_committed_set(self):
        committed = [self.render(None, None, None, None, 'committed' + str(i)) for i in range(2)]
        for group in committed:
            group.isVisible = False
        preview = [self.render(None, None, None, None, 'preview' + str(i)) for i in range(2)]
        self.state.groups, self.state.live_preview = committed, preview
        self.m.renderer.arrange_labels(preview, self.m.APP.activeViewport.camera, self.m.APP.activeViewport)
        context = types.SimpleNamespace(state=self.state)
        def clear():
            for group in preview:
                group.deleteMe()
                self.m.renderer.forget(group)
            preview.clear()
        context.clear_preview = clear
        self.m.CameraChanged().notify(types.SimpleNamespace(viewport=self.m.APP.activeViewport))
        self.assert_separated(preview)
        self.assertEqual(self.m.renderer._LABELS[id(preview[0])][1], (0, 0, 0))
        self.m.DestroyPreview(context).notify(None)
        self.assertTrue(all(g.isVisible for g in committed))
        self.assert_separated(committed)
        self.assertFalse(self.state.editor_open)
        self.assertEqual(self.state.live_preview, [])

    def test_camera_collision_does_not_reposition_world_captions_or_leaders(self):
        groups = [self.render(None, None, None, None, 'm' + str(i)) for i in range(2)]
        self.state.live_preview = groups
        viewport = self.m.APP.activeViewport
        self.m.renderer.arrange_labels(groups, viewport.camera, viewport)
        self.assert_separated(groups)
        anchors = [self.m.renderer._LABELS[id(group)][1] for group in groups]
        leader = self.m.renderer._CAPTIONS[id(groups[1])]['leader']
        leader_coordinates = leader.coordinates
        arc = types.SimpleNamespace(coordinates=('unchanged dimension arc',))
        self.m.renderer._ANGLES[id(groups[0])] = (arc, (0, 0, 0), (1, 0, 0), (0, 1, 0), 1.57, 0)
        # An edge-on projection makes the previously separated captions overlap.
        # Camera movement must not silently choose new world positions to fix it.
        viewport.modelToViewSpace = lambda p: Point(p.x * 100, 0, 0)
        self.assertEqual(viewport.modelToViewSpace(Point(*anchors[0])).y,
                         viewport.modelToViewSpace(Point(*anchors[1])).y)
        for eye_x in (.01, .1, .5):
            viewport.camera.eye.x = eye_x
            self.m.CameraChanged().notify(types.SimpleNamespace(viewport=viewport))
            self.assertEqual([self.m.renderer._LABELS[id(g)][1] for g in groups], anchors)
            self.assertEqual(leader.coordinates, leader_coordinates)
            self.assertEqual(arc.coordinates, ('unchanged dimension arc',))
        self.assertEqual(self.state.live_preview, groups)
        self.assertTrue(all(g.isValid for g in groups))
        self.m.APP.log.assert_not_called()


if __name__ == '__main__':
    unittest.main()
