import importlib
import sys
import types
import unittest
from unittest.mock import patch


class ApplyTest(unittest.TestCase):
    def test_camera_change_updates_preview_when_committed_dimensions_hidden(self):
        core = types.ModuleType('adsk.core'); fusion = types.ModuleType('adsk.fusion')
        core.Application = types.SimpleNamespace(get=lambda: types.SimpleNamespace(userInterface=None))
        for name in ('CommandCreatedEventHandler', 'InputChangedEventHandler', 'ValidateInputsEventHandler', 'CommandEventHandler', 'DocumentEventHandler', 'CameraEventHandler', 'WorkspaceEventHandler', 'ApplicationCommandEventHandler', 'CustomEventHandler'):
            setattr(core, name, type(name, (), {}))
        adsk = types.ModuleType('adsk'); adsk.core = core; adsk.fusion = fusion
        with patch.dict(sys.modules, {'adsk': adsk, 'adsk.core': core, 'adsk.fusion': fusion}):
            sys.modules.pop('Mesora.Mesora', None); sys.modules.pop('Mesora.renderer', None)
            mod = importlib.import_module('Mesora.Mesora')
            mod.APP = types.SimpleNamespace(activeDocument=object())
            mod.UI = types.SimpleNamespace(activeWorkspace=types.SimpleNamespace(id='FusionSolidEnvironment'))
            state = types.SimpleNamespace(removed_for_save=False, visible=False, groups=['hidden'], live_preview=['preview'], preview=None)
            camera = object()
            with patch.object(mod, 'state_for', return_value=state), patch.object(mod.renderer, 'arrange_labels'), patch.object(mod.renderer, 'orient_text') as orient:
                mod.CameraChanged().notify(types.SimpleNamespace(viewport=types.SimpleNamespace(camera=camera)))
                orient.assert_called_once_with('preview', camera)
            sys.modules.pop('Mesora.Mesora', None); sys.modules.pop('Mesora.renderer', None)

    def test_delete_committed_measurement_keeps_others(self):
        core = types.ModuleType('adsk.core'); fusion = types.ModuleType('adsk.fusion')
        core.Application = types.SimpleNamespace(get=lambda: types.SimpleNamespace(userInterface=None))
        for name in ('CommandCreatedEventHandler', 'InputChangedEventHandler', 'ValidateInputsEventHandler', 'CommandEventHandler', 'DocumentEventHandler', 'CameraEventHandler', 'WorkspaceEventHandler', 'ApplicationCommandEventHandler', 'CustomEventHandler'):
            setattr(core, name, type(name, (), {}))
        adsk = types.ModuleType('adsk'); adsk.core = core; adsk.fusion = fusion
        with patch.dict(sys.modules, {'adsk': adsk, 'adsk.core': core, 'adsk.fusion': fusion}):
            sys.modules.pop('Mesora.Mesora', None); sys.modules.pop('Mesora.renderer', None)
            mod = importlib.import_module('Mesora.Mesora')
            state = mod.State(None, None)
            state.items = [('m1', 'area', ('a',)), ('m2', 'radius', ('b',))]
            state.erase = lambda: None
            state.refresh = lambda: []
            with patch.object(mod, 'save_state'):
                state.remove_item('m1')
            self.assertEqual([row[0] for row in state.items], ['m2'])
            with self.assertRaises(ValueError): state.remove_item('missing')
            sys.modules.pop('Mesora.Mesora', None); sys.modules.pop('Mesora.renderer', None)

    def test_explicitly_showing_hidden_state_restores_all_measurements(self):
        core = types.ModuleType('adsk.core'); fusion = types.ModuleType('adsk.fusion')
        core.Application = types.SimpleNamespace(get=lambda: types.SimpleNamespace(userInterface=types.SimpleNamespace()))
        for name in ('CommandCreatedEventHandler', 'InputChangedEventHandler', 'ValidateInputsEventHandler', 'CommandEventHandler', 'DocumentEventHandler', 'CameraEventHandler', 'WorkspaceEventHandler', 'ApplicationCommandEventHandler', 'CustomEventHandler'):
            setattr(core, name, type(name, (), {}))
        adsk = types.ModuleType('adsk'); adsk.core = core; adsk.fusion = fusion
        with patch.dict(sys.modules, {'adsk': adsk, 'adsk.core': core, 'adsk.fusion': fusion}):
            sys.modules.pop('Mesora.Mesora', None); sys.modules.pop('Mesora.renderer', None)
            mod = importlib.import_module('Mesora.Mesora')
            state = types.SimpleNamespace(items=[('m1','radius',('old',))], groups=[], visible=False, next_id=2, erase=lambda keep=(): None)
            old_row = types.SimpleNamespace(id='m1', kind='radius', entities=('old',))
            row = types.SimpleNamespace(id='m2', kind='radius', entities=('new',))
            ctx = types.SimpleNamespace(batch=types.SimpleNamespace(rows=[old_row, row], next_id=3), clear_preview=lambda: None, visible=True)
            mod.APP = types.SimpleNamespace(activeViewport=types.SimpleNamespace(camera=None))
            state.design = object()
            with patch.object(mod.renderer, 'arrange_labels'), patch.object(mod, 'geometry_fingerprint', return_value=('snapshot',)), patch.object(mod, 'save_state'), patch.object(mod, 'current_state', return_value=state), patch.object(mod, 'reference_for', side_effect=lambda e:e), patch.object(mod, 'resolve', side_effect=lambda d,r:r), patch.object(mod.renderer, 'render', side_effect=['old group','new group']):
                mod.Execute('add', ctx).notify(None)
            self.assertTrue(state.visible)
            self.assertEqual(state.groups, ['old group','new group'])
            self.assertEqual([i[0] for i in state.items], ['m1','m2'])
            sys.modules.pop('Mesora.Mesora', None); sys.modules.pop('Mesora.renderer', None)
