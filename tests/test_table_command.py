"""Exercise row-local selection without requiring a running Fusion process."""
import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch


class ListItems:
    def __init__(self): self.items=[]
    def add(self, name, selected, icon):
        item=types.SimpleNamespace(name=name, isSelected=selected)
        self.items.append(item)
        return item
    def clear(self): self.items.clear()


class Input:
    def __init__(self):
        self.text=''; self.isVisible=True; self.hasFocus=False; self.listItems=ListItems()
        self.entities=[]
    @property
    def selectionCount(self): return len(self.entities)
    def selection(self, i): return types.SimpleNamespace(entity=self.entities[i])
    def clearSelection(self): self.entities.clear()
    def addSelection(self, entity): self.entities.append(entity); return True


class Inputs:
    def __init__(self): self.items={'status':Input()}
    def itemById(self, ident): return self.items[ident]
    def make(self, ident, *args):
        value=Input(); self.items[ident]=value; return value
    addTextBoxCommandInput=make
    addBoolValueInput=make
    addDropDownCommandInput=make
    addValueInput=make


class Table:
    def __init__(self): self.rows=[]; self.selectedRow=0
    @property
    def rowCount(self): return len(self.rows)
    def addCommandInput(self, item, row, column):
        if row == len(self.rows): self.rows.append([])
        self.rows[row].append(item); return True
    def deleteRow(self, row): self.rows.pop(row); return True


class TableCommandTest(unittest.TestCase):
    def test_add_focus_select_and_clear_are_independent_per_row(self):
        core=types.ModuleType('adsk.core'); fusion=types.ModuleType('adsk.fusion')
        core.Application=types.SimpleNamespace(get=lambda:types.SimpleNamespace(userInterface=None))
        core.DropDownStyles=types.SimpleNamespace(TextListDropDownStyle=1)
        core.ValueInput=types.SimpleNamespace(createByReal=lambda value:value)
        for n in ('CommandCreatedEventHandler','InputChangedEventHandler','ValidateInputsEventHandler','CommandEventHandler','DocumentEventHandler','CameraEventHandler','WorkspaceEventHandler', 'ApplicationCommandEventHandler', 'CustomEventHandler'):
            setattr(core,n,type(n,(),{}))
        adsk=types.ModuleType('adsk'); adsk.core=core; adsk.fusion=fusion
        with patch.dict(sys.modules,{'adsk':adsk,'adsk.core':core,'adsk.fusion':fusion}):
            sys.modules.pop('Mesora.Mesora',None); sys.modules.pop('Mesora.renderer',None)
            m=importlib.import_module('Mesora.Mesora')
            state=types.SimpleNamespace(next_id=1,live_preview=[],items=[],offsets={},design=types.SimpleNamespace(unitsManager=types.SimpleNamespace(defaultLengthUnits='mm')))
            with patch.object(m,'current_state',return_value=state), patch.object(m,'reference_for',side_effect=lambda e:e), patch.object(m,'measure',return_value=5), patch.object(m,'format_value',return_value='50 mm'):
                c=m.BatchCommand(); c.inputs=Inputs(); c.table=Table(); c.picker=Input(); c.editor_heading=Input(); c.active_selection=None; c.active_row=None
                first=c.add_row(c.inputs)
                self.assertEqual(c.active_row, 'm1'); self.assertTrue(c.picker.hasFocus)
                face=types.SimpleNamespace(objectType='adsk::fusion::BRepFace',area=5,edges=[])
                other=types.SimpleNamespace(objectType='adsk::fusion::BRepFace',area=8,edges=[])
                c.picker.addSelection(face); c.accept_selection()
                self.assertEqual(first.kind, 'area'); self.assertTrue(first.complete)
                c.picker.addSelection(other); c.accept_selection()
                self.assertEqual(first.kind, 'distance'); self.assertEqual(first.entities, (face, other))
                first.options.append('angle')
                # A type change must not rebuild its own dropdown or restore
                # selections: Fusion delivers further inputChanged events.
                with patch.object(first, 'set_kind', side_effect=lambda kind: setattr(first, 'kind', kind)), patch.object(c, 'refresh_row', side_effect=AssertionError('Rebuilt dropdown during type change')):
                    m.Changed(c).notify(types.SimpleNamespace(input=types.SimpleNamespace(id='kind_m1', selectedItem=types.SimpleNamespace(name='Angle'))))
                self.assertEqual(first.kind, 'angle')
                c.accept_selection()
                self.assertEqual(first.kind, 'angle')
                self.assertEqual(first.entities, (face, other))
                first.kind = 'distance'
                offset=c.inputs.itemById('offset_m1'); offset.id='offset_m1'; offset.value=1.25
                m.Changed(c).notify(types.SimpleNamespace(input=offset))
                self.assertEqual(first.offset, 1.25)
                second=c.add_row(c.inputs)
                self.assertIsNone(second.first)
                c.open_editor('m1')
                self.assertEqual(first.offset, 1.25)
                self.assertEqual(second.offset, 0)
                c.command=Mock()
                eye=c.inputs.itemById('visible_m1'); eye.id='visible_m1'; eye.value=False
                m.Changed(c).notify(types.SimpleNamespace(input=eye))
                self.assertFalse(first.visible)
                self.assertTrue(second.visible)
                self.assertEqual(first.entities, (face, other))
                global_eye=Input(); global_eye.id='visible_all'; global_eye.value=False
                m.Changed(c).notify(types.SimpleNamespace(input=global_eye))
                self.assertFalse(c.visible)
                global_eye.value=True
                m.Changed(c).notify(types.SimpleNamespace(input=global_eye))
                self.assertTrue(c.visible)
                self.assertFalse(first.visible)
                self.assertTrue(second.visible)
                self.assertEqual(c.command.doExecutePreview.call_count, 3)
                self.assertEqual(c.picker.entities, [face, other])
                c.picker.entities.pop(1); c.accept_selection()
                self.assertIs(first.first, face); self.assertIsNone(first.second)
                self.assertEqual(second.entities, ())
                c.clear_all()
                self.assertEqual(c.row_inputs, {})
                self.assertEqual(c.table.rowCount, 0)
                self.assertIsNone(c.active_row)
            sys.modules.pop('Mesora.Mesora',None); sys.modules.pop('Mesora.renderer',None)
