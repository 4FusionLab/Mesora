"""Command and document lifecycle regressions using the real add-in handlers."""
import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch


class LifecycleTest(unittest.TestCase):
    def setUp(self):
        core = types.ModuleType('adsk.core')
        fusion = types.ModuleType('adsk.fusion')
        core.Application = types.SimpleNamespace(get=lambda: types.SimpleNamespace(userInterface=None))
        for name in ('CommandCreatedEventHandler', 'InputChangedEventHandler',
                     'ValidateInputsEventHandler', 'CommandEventHandler',
                     'DocumentEventHandler', 'CameraEventHandler', 'WorkspaceEventHandler', 'ApplicationCommandEventHandler', 'CustomEventHandler'):
            setattr(core, name, type(name, (), {}))
        adsk = types.ModuleType('adsk'); adsk.core = core; adsk.fusion = fusion
        self.modules = patch.dict(sys.modules, {'adsk': adsk, 'adsk.core': core, 'adsk.fusion': fusion})
        self.modules.start()
        sys.modules.pop('Mesora.Mesora', None); sys.modules.pop('Mesora.renderer', None)
        self.m = importlib.import_module('Mesora.Mesora')
        self.storage_patch = patch.object(self.m, 'save_state', return_value=True)
        self.storage_patch.start()
        # These older lifecycle fixtures have no Fusion graphics collection.
        # Real tagged ownership reconciliation is covered in test_owned_lifecycle.
        self.ownership_patch = patch.object(self.m.renderer, 'erase_owned', return_value=[])
        self.ownership_patch.start()
        def fake_owned_groups(design, keep=()):
            state = next((entry for entry in self.m.STATES if entry.design is design), None)
            result = []
            for group in state.groups if state else []:
                if getattr(group, 'isValid', True):
                    if not hasattr(group, 'id'):
                        group.id = 'unit-fixture-' + str(id(group))
                    result.append(group)
            return result
        self.owned_collection_patch = patch.object(self.m.renderer, 'owned_groups', side_effect=fake_owned_groups)
        self.owned_collection_patch.start()
        self.doc = types.SimpleNamespace(isModified=False)
        self.m.APP = types.SimpleNamespace(activeDocument=self.doc,
            activeViewport=types.SimpleNamespace(camera=object(), refresh=Mock()), log=Mock())
        self.m.UI = types.SimpleNamespace(activeCommand='SelectCommand', activeWorkspace=types.SimpleNamespace(id='FusionSolidEnvironment'))
        self.state = self.m.State(self.doc, object())
        self.m.STATES.append(self.state)
        self.load_patch = patch.object(self.m, 'load_state', side_effect=lambda design: types.SimpleNamespace(
            items=list(self.state.items), offsets=dict(self.state.offsets), hidden_ids=set(self.state.hidden_ids),
            visible=self.state.visible, next_id=self.state.next_id))
        self.load_patch.start()

    def tearDown(self):
        self.storage_patch.stop()
        self.ownership_patch.stop()
        self.owned_collection_patch.stop()
        self.load_patch.stop()
        self.modules.stop()
        sys.modules.pop('Mesora.Mesora', None); sys.modules.pop('Mesora.renderer', None)

    def test_drawing_save_stays_clean_without_recreating_graphics(self):
        self.state.items = [('m1', 'radius', ('edge',))]
        self.state.groups = [types.SimpleNamespace(isValid=True, deleteMe=lambda: True)]
        def refresh():
            self.doc.isModified = True
        self.state.refresh = Mock(side_effect=refresh)
        args = types.SimpleNamespace(document=self.doc)
        with patch.object(self.m, 'geometry_fingerprint', return_value=('at-save',)):
            self.m.DocumentEvent('saving').notify(args)
        self.doc.isModified = False  # Fusion has just saved the source for Drawing.
        self.m.DocumentEvent('saved').notify(args)
        self.assertFalse(self.doc.isModified, 'Post-save rendering restarts the Drawing save loop')
        self.state.refresh.assert_not_called()
        self.assertTrue(self.state.removed_for_save)

    def test_camera_does_not_touch_graphics_in_drawing(self):
        self.m.UI.activeWorkspace.id = 'FusionDrawingEnvironment'
        self.state.groups = ['design graphics']
        with patch.object(self.m.renderer, 'orient_text') as orient:
            self.m.CameraChanged().notify(types.SimpleNamespace(viewport=self.m.APP.activeViewport))
        orient.assert_not_called()

    def test_refresh_skips_hidden_rows_without_resolving_them(self):
        self.state.items = [('m1', 'radius', ('hidden',)), ('m2', 'radius', ('shown',))]
        self.state.hidden_ids = {'m1'}
        with patch.object(self.m, 'geometry_fingerprint', return_value=('snapshot',)), \
                patch.object(self.m, 'resolve', side_effect=lambda d, r: r) as resolve, \
                patch.object(self.m.renderer, 'render', return_value='graphics'):
            self.assertEqual(self.state.refresh(), [])
        self.assertEqual(resolve.call_args_list[0].args[1], 'shown')
        self.assertEqual(resolve.call_count, 1)
        self.assertEqual(len(self.state.items), 2)

    def test_apply_preserves_hidden_definitions_and_global_visibility(self):
        rows = [types.SimpleNamespace(id='m1', kind='radius', entities=('a',), visible=False),
                types.SimpleNamespace(id='m2', kind='radius', entities=('b',), visible=True)]
        ctx = types.SimpleNamespace(batch=types.SimpleNamespace(rows=rows, next_id=3),
                                    clear_preview=Mock(), visible=True)
        with patch.object(self.m, 'geometry_fingerprint', return_value=('snapshot',)), \
                patch.object(self.m, 'current_state', return_value=self.state), \
                patch.object(self.m, 'reference_for', side_effect=lambda e: e), \
                patch.object(self.m, 'resolve', side_effect=lambda d, r: r), \
                patch.object(self.m.renderer, 'render', return_value=types.SimpleNamespace(
                    isValid=True, deleteMe=lambda: True)) as render:
            self.m.Execute('add', ctx).notify(None)
            self.assertEqual(self.state.hidden_ids, {'m1'})
            self.assertEqual(len(self.state.items), 2)
            self.assertEqual(len(self.state.groups), 1)
            self.assertEqual(render.call_count, 1)
            ctx.visible = False
            render.reset_mock()
            self.m.Execute('add', ctx).notify(None)
            render.assert_not_called()
            self.assertFalse(self.state.visible)
            self.assertEqual(self.state.hidden_ids, {'m1'})
            self.assertEqual(len(self.state.items), 2)

    def test_hidden_preview_does_not_render_but_keeps_rows(self):
        ctx = types.SimpleNamespace(clear_preview=Mock(), visible=False)
        args = types.SimpleNamespace(isValidResult=True)
        with patch.object(self.m, 'current_state', return_value=self.state), \
                patch.object(self.m.renderer, 'render') as render:
            self.m.Preview(ctx).notify(args)
        ctx.clear_preview.assert_called_once()
        render.assert_not_called()
        self.assertFalse(args.isValidResult)

    def test_cancel_restores_committed_visibility_without_applying_draft(self):
        group = types.SimpleNamespace(isValid=True, isVisible=False)
        self.state.groups = [group]
        self.state.hidden_ids = {'m2'}
        ctx = types.SimpleNamespace(clear_preview=Mock(), state=self.state, visible=False)
        self.m.DestroyPreview(ctx).notify(None)
        self.assertTrue(group.isVisible)
        self.assertTrue(self.state.visible)
        self.assertEqual(self.state.hidden_ids, {'m2'})

    def test_workspace_and_document_activation_never_restart_the_save_loop(self):
        self.state.removed_for_save = True
        self.state.refresh = Mock()
        self.m.WorkspaceChanged(True).notify(None)
        self.assertFalse(self.m.graphics_workspace())
        self.m.UI.activeWorkspace.id = 'FusionDrawingEnvironment'
        self.m.WorkspaceChanged(False).notify(None)
        self.state.refresh.assert_not_called()
        self.m.UI.activeWorkspace.id = 'FusionSolidEnvironment'
        self.m.WorkspaceChanged(False).notify(None)
        self.m.DocumentEvent('activated').notify(types.SimpleNamespace(document=self.doc))
        self.state.refresh.assert_not_called()
        self.assertTrue(self.m.graphics_workspace())


    def test_save_cleanup_failure_cancels_document_operation(self):
        self.m.UI.messageBox = Mock()
        self.state.groups = [types.SimpleNamespace(isValid=True, deleteMe=lambda: False)]
        args = types.SimpleNamespace(document=self.doc, isOperationCancelled=False, cancelReason='')
        self.m.DocumentEvent('saving').notify(args)
        self.assertTrue(args.isOperationCancelled)
        self.assertIn('Mesora', args.cancelReason)
        self.assertFalse(hasattr(args, 'isSaveCanceled'))
        self.assertEqual(len(self.state.groups), 1)
        self.assertFalse(self.state.removed_for_save)

    def test_model_end_coalesces_and_excludes_editor_and_mesora(self):
        self.state.items = [('m1', 'radius', ('edge',))]
        self.m.APP.fireCustomEvent = Mock(return_value=True)
        event = self.m.ModelCommandEnded()
        self.state.editor_open = True
        event.notify(types.SimpleNamespace(commandId='Extrude'))
        self.state.editor_open = False
        event.notify(types.SimpleNamespace(commandId='MesoraAdd'))
        self.m.APP.fireCustomEvent.assert_not_called()
        event.notify(types.SimpleNamespace(commandId='Extrude'))
        event.notify(types.SimpleNamespace(commandId='Move'))
        self.m.APP.fireCustomEvent.assert_called_once_with(self.m.UPDATE_EVENT_ID)
        self.assertTrue(self.m.UPDATE_PENDING)

    def test_updates_only_changed_geometry_and_save_never_recreates_same(self):
        self.state.items = [('m1', 'radius', ('edge',))]
        self.state.fingerprint = ('before',)
        self.state.removed_for_save = True
        self.state.refresh = Mock()
        event = self.m.UpdateDimensions()
        with patch.object(self.m, 'geometry_fingerprint', return_value=('before',)):
            self.m.UPDATE_PENDING = True
            event.notify(None)
            self.assertFalse(self.m.UPDATE_PENDING)
            self.state.refresh.assert_not_called()
        with patch.object(self.m, 'geometry_fingerprint', return_value=('after',)):
            event.notify(None)
        self.state.refresh.assert_called_once()

    def test_execute_old_cleanup_failure_does_not_persist_and_tracks_staged_failures(self):
        self.m.UI.messageBox = Mock()
        old = types.SimpleNamespace(isValid=True, deleteMe=Mock(return_value=False))
        self.state.items = [('m1', 'radius', ('old-ref',))]
        self.state.groups = [old]
        staged = types.SimpleNamespace(isValid=True, deleteMe=Mock(return_value=False))
        row = types.SimpleNamespace(id='m2', kind='radius', entities=('new',), visible=True)
        context = types.SimpleNamespace(clear_preview=Mock(), visible=True,
                                        batch=types.SimpleNamespace(rows=[row], next_id=3))
        with patch.object(self.m, 'current_state', return_value=self.state), \
                patch.object(self.m, 'reference_for', side_effect=lambda e: e), \
                patch.object(self.m, 'resolve', side_effect=lambda d, r: r), \
                patch.object(self.m.renderer, 'render', return_value=staged), \
                patch.object(self.m, 'save_state') as save:
            self.m.Execute('add', context).notify(None)
            save.assert_not_called()
        old.deleteMe.assert_called_once()
        staged.deleteMe.assert_called_once()
        self.assertEqual(self.state.items, [('m1', 'radius', ('old-ref',))])
        self.assertIs(self.state.groups[0], old)
        self.assertIs(self.state.live_preview[0], staged)
        # Retained references remain reachable by the next save cleanup attempt.
        args = types.SimpleNamespace(document=self.doc, isOperationCancelled=False)
        self.m.DocumentEvent('saving').notify(args)
        self.assertTrue(args.isOperationCancelled)
        self.assertEqual(staged.deleteMe.call_count, 2)

    def test_staged_cleanup_exception_retains_reference_for_retry(self):
        self.m.UI.messageBox = Mock()
        self.state.erase = Mock(side_effect=RuntimeError('old cleanup failed'))
        staged = types.SimpleNamespace(isValid=True, deleteMe=Mock(side_effect=RuntimeError('new cleanup failed')))
        context = types.SimpleNamespace(clear_preview=Mock(), visible=True,
            batch=types.SimpleNamespace(rows=[types.SimpleNamespace(id='m2', kind='radius', entities=('new',))], next_id=3))
        with patch.object(self.m, 'current_state', return_value=self.state), \
                patch.object(self.m, 'reference_for', side_effect=lambda e: e), \
                patch.object(self.m, 'resolve', side_effect=lambda d, r: r), \
                patch.object(self.m.renderer, 'render', return_value=staged), \
                patch.object(self.m, 'save_state') as save:
            self.m.Execute('add', context).notify(None)
            save.assert_not_called()
        self.assertIs(self.state.live_preview[0], staged)

    def test_stop_unregister_failure_still_cleans_ui_and_retains_failed_state(self):
        self.state.erase = Mock(side_effect=RuntimeError('graphics remain'))
        healthy = types.SimpleNamespace(erase=Mock())
        self.m.STATES.append(healthy)
        event = types.SimpleNamespace(remove=Mock())
        handler = object()
        self.m.HANDLERS.append((event, handler))
        control = types.SimpleNamespace(deleteMe=Mock(return_value=True))
        definition = types.SimpleNamespace(deleteMe=Mock(return_value=True))
        self.m.CONTROLS.append(control); self.m.DEFINITIONS.append(definition)
        self.m.APP.unregisterCustomEvent = Mock(side_effect=RuntimeError('unregister failed'))
        self.m.stop(None)
        event.remove.assert_called_once_with(handler)
        control.deleteMe.assert_called_once()
        definition.deleteMe.assert_called_once()
        self.assertEqual(self.m.HANDLERS, [])
        self.assertEqual(self.m.CONTROLS, [])
        self.assertEqual(self.m.DEFINITIONS, [])
        self.assertEqual(self.m.STATES, [self.state])
        self.state.erase = Mock()
        self.m.stop(None)
        self.assertEqual(self.m.STATES, [])

    def test_active_native_command_excludes_metadata_and_graphics_mutation(self):
        self.state.items = [('m1', 'radius', ('edge',))]
        self.state.refresh = Mock()
        with patch.object(self.m, 'load_state') as load, \
                patch.object(self.m, 'geometry_fingerprint') as fingerprint:
            for active in ('Extrude', 'FusionDrawingViewBaseCommand', 'SketchCircle'):
                self.m.UI.activeCommand = active
                self.m.UPDATE_PENDING = True
                self.m.UpdateDimensions().notify(None)
                self.assertFalse(self.m.UPDATE_PENDING)
            load.assert_not_called()
            fingerprint.assert_not_called()
            self.state.refresh.assert_not_called()

    def test_save_barrier_uses_geometry_at_save_not_old_runtime_snapshot(self):
        self.state.items = [('m1', 'radius', ('edge',))]
        # Also cover another save while the previous save has already removed
        # graphics: a queued update must not restore them after that save.
        for groups in ([types.SimpleNamespace(isValid=True, deleteMe=Mock(return_value=True))], []):
            with self.subTest(graphics_present=bool(groups)):
                self.state.groups = groups
                self.state.fingerprint = ('old',)
                self.state.refresh = Mock()
                args = types.SimpleNamespace(document=self.doc)
                with patch.object(self.m, 'geometry_fingerprint', return_value=('current-at-save',)):
                    self.m.DocumentEvent('saving').notify(args)
                    self.assertEqual(self.state.fingerprint, ('current-at-save',))
                    self.assertEqual(self.state.groups, [])
                    self.m.DocumentEvent('saved').notify(args)
                    self.m.UpdateDimensions().notify(None)
                self.state.refresh.assert_not_called()
                self.assertTrue(self.state.removed_for_save)

    def test_destroy_clears_editor_exclusion_even_on_preview_cleanup_failure(self):
        self.state.editor_open = True
        context = types.SimpleNamespace(state=self.state, clear_preview=Mock(side_effect=RuntimeError('delete failed')))
        self.m.DestroyPreview(context).notify(None)
        self.assertFalse(self.state.editor_open)

    def test_undo_last_deleted_row_reloads_saved_metadata(self):
        self.state.items = []  # Clear / remove committed earlier in this session.
        self.state.fingerprint = ('empty',)
        restored = types.SimpleNamespace(items=[('m1', 'radius', ('edge',))], offsets={'m1': 2.5},
                                         hidden_ids={'m1'}, visible=False, next_id=2)
        self.m.APP.fireCustomEvent = Mock(return_value=True)
        self.m.ModelCommandEnded().notify(types.SimpleNamespace(commandId='UndoCommand'))
        self.m.APP.fireCustomEvent.assert_called_once_with(self.m.UPDATE_EVENT_ID)
        self.state.refresh = Mock()
        with patch.object(self.m, 'load_state', return_value=restored), \
                patch.object(self.m, 'geometry_fingerprint', return_value=('restored',)):
            self.m.UpdateDimensions().notify(None)
        self.assertEqual(self.state.items, restored.items)
        self.assertEqual(self.state.offsets, {'m1': 2.5})
        self.assertEqual(self.state.hidden_ids, {'m1'})
        self.assertFalse(self.state.visible)
        self.assertEqual(self.state.next_id, 2)
        self.state.refresh.assert_called_once()
        self.assertFalse(self.m.UPDATE_PENDING)

    def test_undo_creation_to_empty_definitions_erases_previous_graphics(self):
        self.state.items = [('m1', 'radius', ('edge',))]
        self.state.fingerprint = ('old',)
        self.state.groups = [types.SimpleNamespace(isValid=True, deleteMe=Mock(return_value=True))]
        old = self.state.groups[0]
        empty = types.SimpleNamespace(items=[], offsets={}, hidden_ids=set(), visible=True, next_id=1)
        with patch.object(self.m, 'load_state', return_value=empty), \
                patch.object(self.m, 'geometry_fingerprint', return_value=('empty',)):
            self.m.UpdateDimensions().notify(None)
        old.deleteMe.assert_called_once()
        self.assertEqual(self.state.items, [])
        self.assertEqual(self.state.groups, [])
        self.assertEqual(self.state.fingerprint, ('empty',))

    def test_update_work_is_dropped_in_workspace_transition_drawing_and_editor(self):
        self.state.items = [('m1', 'radius', ('edge',))]
        self.state.fingerprint = ('before',)
        self.state.refresh = Mock()
        with patch.object(self.m, 'geometry_fingerprint') as fingerprint:
            self.m.WORKSPACE_CHANGING = True
            self.m.UpdateDimensions().notify(None)
            self.m.WORKSPACE_CHANGING = False
            self.m.UI.activeWorkspace.id = 'FusionDocumentationEnvironment'
            self.m.UpdateDimensions().notify(None)
            self.m.UI.activeWorkspace.id = 'FusionSolidEnvironment'
            self.state.editor_open = True
            self.m.UpdateDimensions().notify(None)
            fingerprint.assert_not_called()
            self.state.refresh.assert_not_called()


if __name__ == '__main__':
    unittest.main()
