"""Deferred restore from document attributes, never from the active product."""
import types
from unittest.mock import Mock, patch
import unittest
import test_visibility_lifecycle as lifecycle


class DocumentRestoreTest(unittest.TestCase):
    tearDown = lifecycle.LifecycleTest.tearDown
    def setUp(self):
        lifecycle.LifecycleTest.setUp(self)
        self.m.STATES.clear()
        self.design = object()
        self.doc.isValid = True
        self.doc.products = types.SimpleNamespace(itemByProductType=Mock(return_value=self.design))
        self.m.adsk.fusion.Design = types.SimpleNamespace(cast=lambda product: product)
        self.m.APP.fireCustomEvent = Mock(return_value=True)
        self.m.APP.documents = [self.doc]
        self.stored = types.SimpleNamespace(items=[('m1', 'radius', ('edge',))], offsets={'m1': 2},
                                            hidden_ids={'m1'}, visible=True, next_id=2)

    def test_open_loads_from_document_and_defers_graphics(self):
        with patch.object(self.m, 'load_state', return_value=self.stored), \
                patch.object(self.m.State, 'refresh') as render:
            self.m.DocumentOpened().notify(types.SimpleNamespace(document=self.doc))
        state = self.m.state_for(self.doc)
        self.assertEqual(state.items, self.stored.items)
        self.assertEqual(state.offsets, self.stored.offsets)
        self.assertEqual(state.hidden_ids, {'m1'})
        self.assertTrue(state.restore_requested)
        self.assertIsNone(state.fingerprint)
        self.assertIs(state.design, self.design)
        self.m.APP.fireCustomEvent.assert_called_once_with(self.m.UPDATE_EVENT_ID)
        render.assert_not_called()

    def test_startup_reads_existing_documents_and_coalesces_restore(self):
        with patch.object(self.m, 'load_state', return_value=self.stored), \
                patch.object(self.m.State, 'refresh') as render:
            self.m.restore_open_documents()
            self.m.restore_open_documents()
        self.assertEqual(len(self.m.STATES), 1)
        self.assertTrue(self.m.state_for(self.doc).restore_requested)
        self.m.APP.fireCustomEvent.assert_called_once()
        render.assert_not_called()

    def test_non_design_does_not_create_or_queue_state(self):
        self.doc.products.itemByProductType.return_value = None
        self.m.DocumentOpened().notify(types.SimpleNamespace(document=self.doc))
        self.assertEqual(self.m.STATES, [])
        self.m.APP.fireCustomEvent.assert_not_called()

    def test_background_document_loaded_without_queue_for_wrong_active_document(self):
        self.m.APP.activeDocument = object()
        with patch.object(self.m, 'load_state', return_value=self.stored):
            self.m.DocumentOpened().notify(types.SimpleNamespace(document=self.doc))
        self.assertTrue(self.m.state_for(self.doc).restore_requested)
        self.m.APP.fireCustomEvent.assert_not_called()

    def test_saved_or_activated_never_requests_new_restore(self):
        self.state.restore_requested = False
        self.state.removed_for_save = True
        self.m.STATES.append(self.state)
        self.state.refresh = Mock()
        for mode in ('saved', 'activated'):
            self.m.DocumentEvent(mode).notify(types.SimpleNamespace(document=self.doc))
        self.assertFalse(self.state.restore_requested)
        self.m.APP.fireCustomEvent.assert_not_called()
        self.state.refresh.assert_not_called()

    def test_drawing_open_retains_pending_definition_without_direct_render(self):
        self.m.UI.activeWorkspace.id = 'FusionDocumentationEnvironment'
        with patch.object(self.m, 'load_state', return_value=self.stored), \
                patch.object(self.m.State, 'refresh') as render:
            self.m.DocumentOpened().notify(types.SimpleNamespace(document=self.doc))
        self.assertTrue(self.m.state_for(self.doc).restore_requested)
        render.assert_not_called()

    def test_activation_only_queues_existing_restore_request(self):
        self.m.DocumentActivated().notify(types.SimpleNamespace(document=self.doc))
        self.assertEqual(self.m.STATES, [])
        self.m.APP.fireCustomEvent.assert_not_called()
        with patch.object(self.m, 'load_state', return_value=self.stored):
            self.m.state_for_document(self.doc)
        self.m.DocumentActivated().notify(types.SimpleNamespace(document=self.doc))
        self.m.APP.fireCustomEvent.assert_called_once()
        self.m.UPDATE_PENDING = False
        self.m.APP.fireCustomEvent.reset_mock()
        self.m.state_for(self.doc).restore_requested = False
        self.m.DocumentActivated().notify(types.SimpleNamespace(document=self.doc))
        self.m.APP.fireCustomEvent.assert_not_called()

    def test_startup_corrupt_document_cannot_block_valid_document(self):
        corrupt_design = object()
        corrupt = types.SimpleNamespace(isValid=True, products=types.SimpleNamespace(
            itemByProductType=lambda _: corrupt_design))
        self.m.APP.documents = [corrupt, self.doc]
        def load(design):
            if design is corrupt_design:
                raise ValueError('Future schema')
            return self.stored
        with patch.object(self.m, 'load_state', side_effect=load):
            self.m.restore_open_documents()
        self.assertIsNone(self.m.state_for(corrupt))
        self.assertEqual(self.m.state_for(self.doc).items, self.stored.items)
        self.m.APP.fireCustomEvent.assert_called_once()
        self.m.APP.log.assert_called_once()

    def test_saved_state_blocks_queued_initial_restore(self):
        with patch.object(self.m, 'load_state', return_value=self.stored):
            state = self.m.state_for_document(self.doc)
        self.assertTrue(state.restore_requested)
        state.groups = [types.SimpleNamespace(isValid=True, deleteMe=Mock(return_value=True))]
        with patch.object(self.m, 'geometry_fingerprint', return_value=('saved',)):
            self.m.DocumentEvent('saving').notify(types.SimpleNamespace(document=self.doc))
        self.assertFalse(state.restore_requested)
        self.m.DocumentActivated().notify(types.SimpleNamespace(document=self.doc))
        self.m.APP.fireCustomEvent.assert_not_called()

    def test_initial_restore_waits_out_drawing_then_renders_current_model(self):
        self.stored.items.append(('m2', 'radius', ('another-edge',)))
        self.stored.next_id = 3
        with patch.object(self.m, 'load_state', return_value=self.stored):
            self.m.DocumentOpened().notify(types.SimpleNamespace(document=self.doc))
        state = self.m.state_for(self.doc)
        self.m.UI.activeWorkspace.id = 'FusionDocumentationEnvironment'
        with patch.object(self.m, 'geometry_fingerprint', return_value=('initial',)), \
                patch.object(self.m, 'resolve', return_value=object()), \
                patch.object(self.m.renderer, 'render', return_value=object()) as render, \
                patch.object(self.m, 'load_state', return_value=self.stored):
            self.m.UpdateDimensions().notify(None)
            render.assert_not_called()
            self.assertTrue(state.restore_requested)
            self.m.UI.activeWorkspace.id = 'FusionSolidEnvironment'
            self.m.DocumentActivated().notify(types.SimpleNamespace(document=self.doc))
            self.m.UpdateDimensions().notify(None)
        render.assert_called_once()  # Hidden m1 is retained; visible m2 renders.
        self.assertFalse(state.restore_requested)
        self.assertEqual(state.fingerprint, ('initial',))
        self.assertEqual(state.hidden_ids, {'m1'})
