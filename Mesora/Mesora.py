"""Mesora: experimental session-only build."""
import traceback
from pathlib import Path
import adsk.core
import adsk.fusion
from .dimensions.fusion_geometry import measure, reference_for, resolve
from . import renderer
from .dimensions.batch import Batch, RowDraft, duplicate_rows

APP = adsk.core.Application.get()
UI = APP.userInterface
HANDLERS = []
DEFINITIONS = []
CONTROLS = []
STATES = []
PANEL_ID = 'InspectPanel'
INSPECT_PANELS = (
    ('FusionSolidEnvironment', 'InspectPanel'),
    ('FusionSolidEnvironment', 'PlasticPartsInspectPanel'),
    ('FusionSolidEnvironment', 'InspectMeshPanel'),
    ('FusionSolidEnvironment', 'ToolsInspectPanel'),
    ('CAMEnvironment', 'CAMInspectPanel'),
    ('CAMEnvironment', 'CAMPartAlignmentInspectPanel'),
    ('CAMEnvironment', 'SimulationInspectPanel'),
    ('SimulationEnvironment', 'InspectPanel'),
    ('SimulationEnvironment', 'ResultsInspectPanel'),
    ('SimulationEnvironment', 'ViewerInspectPanel'),
    ('GenerativeEnvironment', 'GenInspectPanel'),
)
KINDS = {'Distance':'distance', 'Angle':'angle', 'Edge Length':'edge_length', 'Radius':'radius', 'Diameter':'diameter', 'Area':'area', 'Perimeter':'perimeter'}
NAMES = {value: key for key, value in KINDS.items()}


def icon(name):
    return str(Path(__file__).parent / 'resources' / name)


def log_error():
    APP.log(traceback.format_exc())


def bind(event, handler):
    if not event.add(handler): raise RuntimeError('Failed to attach Fusion event')
    HANDLERS.append((event, handler))


class State:
    def __init__(self, doc, design):
        self.doc, self.design = doc, design
        self.items, self.groups = [], []
        self.offsets = {}
        self.visible = True
        self.removed_for_save = False
        self.preview = None
        self.live_preview = []
        self.next_id = 1

    def erase_preview(self):
        if self.preview is not None:
            if self.preview.isValid and not self.preview.deleteMe():
                raise RuntimeError('Could not remove preview graphics')
            renderer.forget(self.preview)
            self.preview = None

    def erase(self):
        self.erase_preview()
        for group in list(self.live_preview):
            if group.isValid and not group.deleteMe():
                raise RuntimeError('Could not remove preview graphics')
            renderer.forget(group)
            self.live_preview.remove(group)
        failed = []
        for group in self.groups:
            try:
                if group.isValid and not group.deleteMe(): failed.append(group)
                else: renderer.forget(group)
            except Exception:
                failed.append(group)
        self.groups = failed
        if failed: raise RuntimeError('Could not remove every dimensions graphics group')

    def refresh(self):
        self.erase()
        errors = []
        if self.visible:
            for ident, kind, refs in self.items:
                try:
                    entities = [resolve(self.design, ref) for ref in refs]
                    self.groups.append(renderer.render(self.design, kind, entities, APP.activeViewport.camera, ident, offset=self.offsets.get(ident, 0.0)))
                except Exception as ex:
                    errors.append(str(ex))
        APP.activeViewport.refresh()
        return errors

    def remove_item(self, ident):
        if not any(item[0] == ident for item in self.items):
            raise ValueError('Measurement not found')
        self.erase()
        self.items = [item for item in self.items if item[0] != ident]
        self.offsets.pop(ident, None)
        return self.refresh()


def current_state(create=True):
    doc = APP.activeDocument
    design = adsk.fusion.Design.cast(APP.activeProduct)
    if not design and doc:
        design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
    if not doc or not design: raise RuntimeError('Open a Fusion design first')
    for state in STATES:
        if state.doc == doc: return state
    if not create: return None
    state = State(doc, design); STATES.append(state); return state


def state_for(doc):
    return next((s for s in STATES if s.doc == doc), None)


def format_value(design, kind, value):
    units = design.unitsManager
    unit = 'deg' if kind == 'angle' else units.defaultLengthUnits + '^2' if kind == 'area' else units.defaultLengthUnits
    return units.formatValue(value, unit, True)


class BatchCommand:
    def __init__(self):
        self.batch = Batch()
        self.batch.next_id = current_state().next_id
        self.busy = False
        self.state = current_state()
        self.preview_groups = self.state.live_preview
        self.row_inputs = {}
        self.layout_cache = {}

    def clear_preview(self):
        for group in self.preview_groups:
            if group.isValid and not group.deleteMe():
                raise RuntimeError('Could not remove preview')
            renderer.forget(group)
        self.preview_groups.clear()

    def update_status(self, inputs, message=None):
        if message is None:
            if self.active_selection:
                ident, _ = self.active_selection
                message = 'Select one or two objects for ' + ident
            else:
                message = 'Select a row to remove it, or add a measurement.'
        inputs.itemById('status').text = message

    def add_row(self, inputs, draft=None, activate=True):
        if draft is None:
            ident = 'm' + str(self.batch.next_id)
            self.batch.next_id += 1
            draft = RowDraft(ident)
        else:
            ident = draft.id
        table = self.table
        index = table.rowCount
        label = inputs.addTextBoxCommandInput('id_' + ident, '', ident, 1, True)
        geometry = inputs.addBoolValueInput('geometry_' + ident, '', False, icon('geometry'), False)
        geometry.tooltip = 'Edit geometry for ' + ident
        dropdown = inputs.addDropDownCommandInput('kind_' + ident, '', adsk.core.DropDownStyles.TextListDropDownStyle)
        dropdown.listItems.add('Select geometry', True, '')
        value = inputs.addTextBoxCommandInput('value_' + ident, '', '—', 1, True)
        offset = inputs.addValueInput('offset_' + ident, '', self.state.design.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(draft.offset))
        offset.tooltip = 'Offset from automatic placement for ' + ident
        clear = inputs.addBoolValueInput('clear_' + ident, '', False, icon('clear'), False)
        clear.tooltip = 'Clear geometry in this measurement'
        for column, item in enumerate((label, geometry, dropdown, value, offset, clear)):
            if not table.addCommandInput(item, index, column):
                raise RuntimeError('Cannot add measurement row')
        self.row_inputs[ident] = (draft, dropdown, value)
        if draft.first is not None:
            self.refresh_row(ident)
        if activate:
            self.start_selection(ident, 1)
        return draft

    def open_editor(self, ident):
        draft = self.row_inputs[ident][0]
        self.picker.clearSelection()
        self.picker.isVisible = False
        self.active_row = ident
        self.active_selection = None
        self.editor_heading.text = ident + ' — Geometry'
        self.picker.isVisible = True
        for entity in (draft.first, draft.second):
            if entity is not None and not self.picker.addSelection(entity):
                raise RuntimeError('Cannot restore selected geometry for ' + ident)
        self.picker.hasFocus = True

    def start_selection(self, ident, position=1):
        if self.active_row != ident:
            self.open_editor(ident)
        self.active_selection = (ident, 1)
        self.picker.hasFocus = True
        self.update_status(self.inputs)

    def accept_selection(self):
        if self.active_row is None:
            return
        ident = self.active_row
        entities = [self.picker.selection(i).entity for i in range(self.picker.selectionCount)]
        for entity in entities:
            reference_for(entity)
        draft = self.row_inputs[ident][0]
        if tuple(entities) == tuple(draft.entities):
            return
        draft.set_second(None)
        draft.set_first(entities[0] if entities else None)
        if len(entities) == 2:
            draft.set_second(entities[1])
            draft.set_kind('distance')
            if 'angle' in draft.options and measure('distance', draft.entities) <= 1e-7:
                draft.set_kind('angle')
        self.refresh_row(ident)
        self.active_selection = (ident, 1)

    def refresh_row(self, ident):
        draft, dropdown, value = self.row_inputs[ident]
        dropdown.listItems.clear()
        if draft.options:
            selected = None
            for kind in draft.options:
                item = dropdown.listItems.add(NAMES[kind], False, '')
                if kind == draft.kind:
                    selected = item
            if selected is not None:
                selected.isSelected = True
        else:
            dropdown.listItems.add('Select geometry', True, '')
        if draft.complete:
            value.text = format_value(self.state.design, draft.kind, measure(draft.kind, draft.entities))
        elif draft.needs_second:
            value.text = 'Select second object'
        else:
            value.text = '—'

    def remove_selected(self):
        index = self.table.selectedRow
        ids = list(self.row_inputs)
        if not 0 <= index < len(ids):
            raise ValueError('Select a measurement row to remove')
        ident = ids[index]
        if self.active_row == ident:
            self.picker.clearSelection(); self.picker.isVisible = False
            self.active_selection = None
            self.active_row = None
            self.editor_heading.text = 'Select a measurement to edit geometry.'
        if not self.table.deleteRow(index):
            raise RuntimeError('Cannot remove measurement')
        del self.row_inputs[ident]
        self.layout_cache.pop(ident, None)

    def clear_all(self):
        self.picker.clearSelection()
        self.picker.isVisible = False
        self.active_selection = self.active_row = None
        self.editor_heading.text = 'Select a measurement to edit geometry.'
        for index in reversed(range(self.table.rowCount)):
            if not self.table.deleteRow(index):
                raise RuntimeError('Cannot remove measurement')
        self.row_inputs.clear()
        self.layout_cache.clear()

    def load_existing(self):
        for ident, kind, refs in self.state.items:
            entities = [resolve(self.state.design, ref) for ref in refs]
            draft = RowDraft(ident)
            draft.set_first(entities[0])
            if len(entities) == 2:
                draft.set_second(entities[1])
                draft.set_kind('distance')
            draft.set_kind(kind)
            draft.offset = self.state.offsets.get(ident, 0.0)
            self.add_row(self.inputs, draft, activate=False)

    def sync_batch(self):
        drafts = [item[0] for item in self.row_inputs.values()]
        self.batch.rows = [draft for draft in drafts if draft.complete]
        incomplete = [draft.id for draft in drafts if (draft.first is not None or draft.second is not None) and not draft.complete]
        return incomplete, duplicate_rows(self.batch.rows)


class Created(adsk.core.CommandCreatedEventHandler):
    def __init__(self, operation):
        super().__init__(); self.operation = operation
    def notify(self, args):
        try:
            cmd = args.command
            if self.operation == 'add':
                cmd.setDialogInitialSize(570, 400)
                cmd.setDialogMinimumSize(500, 300)
                inputs = cmd.commandInputs
                context = BatchCommand()
                context.inputs = inputs
                context.active_selection = None
                context.active_row = None
                table = inputs.addTableCommandInput('measurements', 'Measurements', 6, '2:1:4:3:3:1')
                table.minimumVisibleRows = 3
                table.maximumVisibleRows = 8
                context.table = table
                add = inputs.addBoolValueInput('add_row', '', False, icon('add'), False)
                remove = inputs.addBoolValueInput('remove_row', '', False, icon('remove'), False)
                clear_all = inputs.addBoolValueInput('clear_all', '', False, icon('delete_all'), False)
                add.tooltip = 'Add measurement'
                remove.tooltip = 'Remove selected measurement'
                clear_all.tooltip = 'Remove all measurements'
                if not table.addToolbarCommandInput(add) or not table.addToolbarCommandInput(remove) or not table.addToolbarCommandInput(clear_all):
                    raise RuntimeError('Cannot create measurement toolbar')
                context.editor_heading = inputs.addTextBoxCommandInput('editor_heading', '', 'Select a measurement.', 1, True)
                picker = inputs.addSelectionInput('picker', 'Objects', 'Select one or two objects')
                for name in ('Vertices', 'SketchPoints', 'Edges', 'Faces', 'SketchCurves'):
                    if not picker.addSelectionFilter(name): raise RuntimeError('Selection filter unavailable: ' + name)
                picker.setSelectionLimits(0, 2)
                picker.isUseCurrentSelections = False
                picker.isVisible = False
                context.picker = picker
                inputs.addTextBoxCommandInput('status', '', 'Add a measurement to begin.', 2, True)
                context.load_existing()
                if not context.row_inputs:
                    context.add_row(inputs)
                else:
                    context.update_status(inputs)
                for group in context.state.groups:
                    if group.isValid:
                        group.isVisible = False
                bind(cmd.inputChanged, Changed(context))
                bind(cmd.validateInputs, Validate(context))
                bind(cmd.executePreview, Preview(context))
                bind(cmd.destroy, DestroyPreview(context))
                bind(cmd.execute, Execute(self.operation, context))
            elif self.operation == 'remove_one':
                state = current_state()
                inputs = cmd.commandInputs
                dropdown = inputs.addDropDownCommandInput('remove_id', 'Measurement', adsk.core.DropDownStyles.TextListDropDownStyle)
                for i, (ident, kind, refs) in enumerate(state.items):
                    dropdown.listItems.add(ident + ' — ' + NAMES.get(kind, kind), i == 0, '')
                inputs.addTextBoxCommandInput('remove_hint', '', 'Choose a measurement to remove.', 2, True)
                bind(cmd.execute, Execute(self.operation))
            else:
                bind(cmd.execute, Execute(self.operation))
        except Exception:
            log_error(); UI.messageBox('Mesora: failed to open command. See Text Commands log.')


class Changed(adsk.core.InputChangedEventHandler):
    def __init__(self, context): super().__init__(); self.context = context
    def notify(self, args):
        c = self.context
        if c.busy: return
        c.busy = True
        try:
            inputs = c.inputs
            ident = args.input.id
            if ident == 'add_row':
                c.add_row(inputs)
            elif ident == 'remove_row':
                c.remove_selected()
            elif ident == 'clear_all':
                c.clear_all()
            elif ident.startswith('geometry_'):
                c.open_editor(ident[9:])
            elif ident == 'picker':
                c.accept_selection()
            elif ident.startswith('offset_'):
                c.row_inputs[ident[7:]][0].offset = args.input.value
            elif ident.startswith('clear_'):
                row_id = ident[6:]
                c.row_inputs[row_id][0].set_first(None)
                c.row_inputs[row_id][0].set_second(None)
                c.refresh_row(row_id)
                if c.active_row == row_id:
                    c.open_editor(row_id)
            elif ident.startswith('kind_'):
                row_id = ident[5:]
                draft = c.row_inputs[row_id][0]
                if args.input.selectedItem and args.input.selectedItem.name in KINDS:
                    draft.set_kind(KINDS[args.input.selectedItem.name])
                    c.row_inputs[row_id][2].text = format_value(c.state.design, draft.kind, measure(draft.kind, draft.entities)) if draft.complete else 'Select second object'
                    if not draft.needs_second:
                        c.open_editor(row_id)
                    if draft.needs_second and draft.second is None:
                        c.start_selection(row_id)
            incomplete, duplicates = c.sync_batch()
            if duplicates:
                c.update_status(inputs, 'Duplicate measurements: ' + ', '.join(sorted(duplicates)))
            elif incomplete:
                c.update_status(inputs, 'Complete or clear: ' + ', '.join(incomplete))
            else:
                c.update_status(inputs)
        except Exception as ex:
            log_error()
            c.update_status(c.inputs, str(ex))
        finally:
            c.busy = False


class Validate(adsk.core.ValidateInputsEventHandler):
    def __init__(self, context): super().__init__(); self.context = context
    def notify(self, args):
        try:
            batch = self.context.batch
            incomplete, duplicates = self.context.sync_batch()
            args.areInputsValid = not incomplete and not duplicates and (bool(batch.rows) or bool(self.context.state.items))
            for row in batch.rows:
                measure(row.kind, row.entities)
                for entity in row.entities: reference_for(entity)
        except Exception:
            args.areInputsValid = False


class Preview(adsk.core.CommandEventHandler):
    def __init__(self, context): super().__init__(); self.context = context
    def notify(self, args):
        c = self.context
        try:
            c.clear_preview()
            state = current_state()
            errors = []
            _, duplicates = c.sync_batch()
            obstacles = renderer.obstacle_signature(state.design.rootComponent) if c.batch.rows else None
            for row in c.batch.rows:
                if row.id in duplicates: continue
                try:
                    c.preview_groups.append(renderer.render(state.design, row.kind, row.entities, APP.activeViewport.camera, row.id, offset=getattr(row, 'offset', 0.0), layout_cache=c.layout_cache, obstacles=obstacles))
                except Exception as ex:
                    errors.append(row.id + ': ' + str(ex))
            if errors: c.update_status(args.command.commandInputs, '; '.join(errors))
            args.isValidResult = False
        except Exception: log_error()


class DestroyPreview(adsk.core.CommandEventHandler):
    def __init__(self, context): super().__init__(); self.context = context
    def notify(self, args):
        try:
            self.context.clear_preview()
            for group in self.context.state.groups:
                if group.isValid:
                    group.isVisible = self.context.state.visible
        except Exception: log_error()


class Execute(adsk.core.CommandEventHandler):
    def __init__(self, operation, context=None):
        super().__init__(); self.operation = operation; self.context = context
    def notify(self, args):
        try:
            state = current_state()
            if self.operation == 'add':
                self.context.clear_preview()
                staged = []
                try:
                    obstacles = renderer.obstacle_signature(state.design.rootComponent) if getattr(self.context, 'layout_cache', None) is not None and self.context.batch.rows else None
                    for row in self.context.batch.rows:
                        refs = tuple(reference_for(e) for e in row.entities)
                        entities = [resolve(state.design, ref) for ref in refs]
                        group = renderer.render(state.design, row.kind, entities, APP.activeViewport.camera, row.id, offset=getattr(row, 'offset', 0.0), layout_cache=getattr(self.context, 'layout_cache', None), obstacles=obstacles)
                        staged.append((row.id, row.kind, refs, group))
                except Exception:
                    for group in [entry[3] for entry in staged]:
                        group.deleteMe(); renderer.forget(group)
                    raise
                state.erase()
                state.items = [(ident, kind, refs) for ident, kind, refs, _ in staged]
                state.groups = [group for _, _, _, group in staged]
                if hasattr(state, 'offsets'):
                    state.offsets = {row.id: getattr(row, 'offset', 0.0) for row in self.context.batch.rows}
                state.next_id = self.context.batch.next_id
                state.visible = True
            elif self.operation == 'remove_one':
                item = args.command.commandInputs.itemById('remove_id').selectedItem
                if item is None: raise ValueError('No measurement selected')
                errors = state.remove_item(item.name.split(' — ', 1)[0])
                if errors: UI.messageBox('Some dimensions cannot be resolved:\n' + '\n'.join(errors[:5]))
            elif self.operation == 'toggle':
                state.visible = not state.visible
                errors = state.refresh()
                if errors: UI.messageBox('Some dimensions cannot be resolved:\n' + '\n'.join(errors[:5]))
            elif self.operation == 'refresh':
                errors = state.refresh()
                if errors: UI.messageBox('Some dimensions cannot be resolved:\n' + '\n'.join(errors[:5]))
            else:
                state.erase(); state.items.clear(); state.offsets.clear(); APP.activeViewport.refresh()
        except Exception as ex:
            log_error(); UI.messageBox('Mesora: ' + str(ex))


class DocumentEvent(adsk.core.DocumentEventHandler):
    def __init__(self, mode): super().__init__(); self.mode = mode
    def notify(self, args):
        state = state_for(args.document)
        if not state: return
        try:
            if self.mode == 'saving' and (state.groups or state.preview is not None):
                state.erase()
                state.removed_for_save = True
            elif self.mode == 'saved' and state.removed_for_save:
                state.removed_for_save = False
                if state.doc == APP.activeDocument:
                    errors = state.refresh()
                    if errors: APP.log('Dimensions could not be restored: ' + '; '.join(errors))
            elif self.mode == 'activated' and state.removed_for_save:
                state.removed_for_save = False
                state.refresh()
            elif self.mode == 'closing':
                state.erase()
                # Closing may be canceled; retain definitions until document invalidation.
        except Exception:
            if self.mode in ('saving', 'closing'): args.isSaveCanceled = True
            log_error()
            UI.messageBox('Mesora could not remove graphics. The operation was canceled; do not save until the add-in can remove them.')


class CameraChanged(adsk.core.CameraEventHandler):
    def __init__(self):
        super().__init__()
        self.busy = False

    def notify(self, args):
        if self.busy:
            return
        try:
            state = state_for(APP.activeDocument)
            if state is None or state.removed_for_save:
                return
            self.busy = True
            camera = args.viewport.camera
            for group in (list(state.groups) if state.visible else []) + list(state.live_preview) + ([state.preview] if state.preview is not None else []):
                renderer.orient_text(group, camera)
        except Exception:
            log_error()
        finally:
            self.busy = False


def install_inspect_controls(definitions):
    for workspace_id, panel_id in INSPECT_PANELS:
        workspace = UI.workspaces.itemById(workspace_id)
        panel = workspace.toolbarPanels.itemById(panel_id) if workspace else None
        if not panel:
            continue
        for definition in definitions:
            if panel.controls.itemById(definition.id):
                continue
            anchor = 'MeasureCommand' if definition.id == 'MesoraAdd' and panel.controls.itemById('MeasureCommand') else ''
            control = panel.controls.addCommand(definition, anchor, False) if anchor else panel.controls.addCommand(definition)
            if not control:
                raise RuntimeError('Could not add Mesora to ' + workspace_id + '/' + panel_id)
            CONTROLS.append(control)


def run(context):
    try:
        workspace = UI.workspaces.itemById('FusionSolidEnvironment')
        panel = workspace.toolbarPanels.itemById(PANEL_ID) if workspace else None
        if not panel: raise RuntimeError('Solid toolbar panel unavailable')
        for suffix, title, description in [
            ('Add','Mesora — Add Dimension','Create a session-only informational 3D dimension'),
            ('Toggle','Show/Hide Dimensions','Toggle dimensions in this document'),
            ('Refresh','Refresh Dimensions','Recalculate dimensions in this document'),
            ('Remove','Remove Dimension','Remove one session dimension by ID'),
            ('Clear','Clear Dimensions','Remove session dimensions in this document')]:
            ident = 'Mesora' + suffix
            definition = UI.commandDefinitions.itemById(ident)
            if definition: definition.deleteMe()
            command_icon = {'Add': 'dimension', 'Toggle': 'visibility', 'Refresh': 'refresh', 'Remove': 'delete_dimension', 'Clear': 'delete_all'}[suffix]
            definition = UI.commandDefinitions.addButtonDefinition(ident, title, description, icon(command_icon))
            if not definition: raise RuntimeError('Could not create command ' + title)
            DEFINITIONS.append(definition)
            operation = {'Add':'add','Toggle':'toggle','Refresh':'refresh','Remove':'remove_one','Clear':'clear'}[suffix]
            bind(definition.commandCreated, Created(operation))
        install_inspect_controls(DEFINITIONS)
        bind(APP.documentSaving, DocumentEvent('saving'))
        bind(APP.documentSaved, DocumentEvent('saved'))
        bind(APP.documentActivated, DocumentEvent('activated'))
        bind(APP.documentClosing, DocumentEvent('closing'))
        bind(APP.cameraChanged, CameraChanged())
    except Exception:
        log_error(); stop(context); UI.messageBox('Mesora failed to start. See Text Commands log.')


def stop(context):
    for state in STATES:
        try: state.erase()
        except Exception: log_error()
    STATES.clear()
    for event, handler in reversed(HANDLERS):
        try: event.remove(handler)
        except Exception: pass
    HANDLERS.clear()
    for control in reversed(CONTROLS):
        try: control.deleteMe()
        except Exception: pass
    CONTROLS.clear()
    for definition in reversed(DEFINITIONS):
        try: definition.deleteMe()
        except Exception: pass
    DEFINITIONS.clear()
