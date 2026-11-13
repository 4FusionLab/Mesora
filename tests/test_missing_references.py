"""An unavailable reference stays editable without blocking other measurements."""
import importlib
import sys
import types
import unittest
from unittest.mock import patch

from test_table_command import Input, Inputs, Table


class MissingReferencesTest(unittest.TestCase):
    def setUp(self):
        core = types.ModuleType('adsk.core')
        core.Application = types.SimpleNamespace(get=lambda: types.SimpleNamespace(userInterface=None))
        core.DropDownStyles = types.SimpleNamespace(TextListDropDownStyle=1)
        core.ValueInput = types.SimpleNamespace(createByReal=lambda value: value)
        for name in ('CommandCreatedEventHandler', 'InputChangedEventHandler', 'ValidateInputsEventHandler',
                     'CommandEventHandler', 'DocumentEventHandler', 'CameraEventHandler', 'WorkspaceEventHandler', 'ApplicationCommandEventHandler', 'CustomEventHandler'):
            setattr(core, name, type(name, (), {}))
        adsk = types.ModuleType('adsk'); adsk.core = core; adsk.fusion = types.ModuleType('adsk.fusion')
        self.modules = patch.dict(sys.modules, {'adsk': adsk, 'adsk.core': core, 'adsk.fusion': adsk.fusion})
        self.modules.start()
        sys.modules.pop('Mesora.Mesora', None); sys.modules.pop('Mesora.renderer', None)
        self.m = importlib.import_module('Mesora.Mesora')
        self.face = types.SimpleNamespace(objectType='adsk::fusion::BRepFace', area=5, edges=[])
        self.state = types.SimpleNamespace(next_id=3, live_preview=[], items=[('m1', 'area', ('missing',)), ('m2', 'area', ('good',))],
                                          hidden_ids={'m1'}, offsets={'m1': 2.5}, design=types.SimpleNamespace(unitsManager=types.SimpleNamespace(defaultLengthUnits='mm')))
        def resolve(design, ref):
            if ref == 'missing': raise ValueError('Deleted face')
            return self.face
        self.patches = [patch.object(self.m, 'current_state', return_value=self.state),
                        patch.object(self.m, 'resolve', side_effect=resolve),
                        patch.object(self.m, 'reference_for', side_effect=lambda e: e),
                        patch.object(self.m, 'measure', return_value=5),
                        patch.object(self.m, 'format_value', return_value='5 mm²')]
        for item in self.patches: item.start()
        self.c = self.m.BatchCommand()
        self.c.inputs = Inputs(); self.c.table = Table(); self.c.picker = Input()
        self.c.editor_heading = Input(); self.c.active_row = self.c.active_selection = None
        self.c.load_existing()

    def tearDown(self):
        for item in reversed(self.patches): item.stop()
        sys.modules.pop('Mesora.Mesora', None); sys.modules.pop('Mesora.renderer', None)
        self.modules.stop()

    def test_broken_row_is_retained_and_healthy_row_loads(self):
        broken, _, text = self.c.row_inputs['m1']
        self.assertEqual(broken.unresolved_refs, ('missing',))
        self.assertEqual(broken.kind, 'area')
        self.assertFalse(broken.visible)
        self.assertEqual(broken.offset, 2.5)
        self.assertIn('Reference unavailable', text.text)
        self.assertTrue(self.c.row_inputs['m2'][0].complete)
        self.assertEqual(self.c.sync_batch(), ([], set()))
        self.assertEqual([r.id for r in self.c.batch.rows], ['m1', 'm2'])
        args = types.SimpleNamespace(areInputsValid=False)
        self.m.Validate(self.c).notify(args)
        self.assertTrue(args.areInputsValid)

    def test_replace_geometry_recovers_broken_row(self):
        self.c.open_editor('m1')
        self.c.picker.addSelection(self.face)
        self.c.accept_selection()
        draft, _, text = self.c.row_inputs['m1']
        self.assertIsNone(draft.unresolved_refs)
        self.assertTrue(draft.complete)
        self.assertEqual(text.text, '5 mm²')

    def test_clear_and_remove_are_explicit_deletion(self):
        draft = self.c.row_inputs['m1'][0]
        draft.set_first(None); draft.set_second(None)
        self.c.refresh_row('m1')
        self.assertIsNone(draft.unresolved_refs)
        self.c.sync_batch()
        self.assertEqual([r.id for r in self.c.batch.rows], ['m2'])
        self.c.table.selectedRow = 1
        self.c.remove_selected()
        self.assertNotIn('m2', self.c.row_inputs)
