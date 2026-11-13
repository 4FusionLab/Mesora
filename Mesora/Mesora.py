"""Mesora: persistent informational 3D measurements."""
import traceback
from pathlib import Path
import adsk.core
import adsk.fusion
from .dimensions.fusion_geometry import measure, reference_for, resolve
from . import renderer
from .dimensions.batch import Batch, RowDraft, duplicate_rows
from .dimensions.event_scope import EventScope
from .dimensions.runtime_persistence import load_state, save_state
from .dimensions.update_fingerprint import geometry_fingerprint

APP = adsk.core.Application.get()
UI = APP.userInterface
HANDLERS = []
COMMAND_SCOPES = []
DEFINITIONS = []
CONTROLS = []
STATES = []
WORKSPACE_CHANGING = False
UPDATE_EVENT_ID = '4FusionLab.Mesora.GeometryUpdate'
UPDATE_PENDING = False
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


def graphics_workspace():
    """Do not update design graphics during a workspace transition or in Drawing."""
    if WORKSPACE_CHANGING:
        return False
    try:
        workspace = UI.activeWorkspace
        return bool(workspace and workspace.id in {entry[0] for entry in INSPECT_PANELS})
    except RuntimeError:
        return False  # No active session (Home or an intermediate workspace).


def visibility_button(button, visible, subject):
    button.resourceFolder = icon('visibility' if visible else 'visibility_off')
    button.tooltip = ('Hide ' if visible else 'Show ') + subject


class State:
    def __init__(self, doc, design):
        self.doc, self.design = doc, design
        self.items, self.groups = [], []
        self.offsets = {}
        self.visible = True
        self.hidden_ids = set()
        self.removed_for_save = False
        self.preview = None
        self.live_preview = []
        self.next_id = 1
        self.fingerprint = None
        self.editor_open = False
        self.restore_requested = False

    def load(self):
        stored = load_state(self.design)
        self.items = stored.items
        self.offsets = stored.offsets
        self.hidden_ids = stored.hidden_ids
        self.visible = stored.visible
        self.next_id = stored.next_id

    def persist(self):
        return save_state(self.design, self.items, self.offsets,
                          self.hidden_ids, self.visible)

    def erase_preview(self):
        if self.preview is not None:
            if self.preview.isValid and not self.preview.deleteMe():
                raise RuntimeError('Could not remove preview graphics')
            renderer.forget(self.preview)
            self.preview = None

    def erase(self, keep=()):
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
        # Fusion Undo can revive a deleted group using a different API wrapper.
        # Reconcile by our own persistent group IDs, never by clearing another
        # add-in's graphics. New command groups awaiting adoption must survive.
        for group in renderer.erase_owned(self.design, keep=keep):
            if group not in failed:
                failed.append(group)
        self.groups = [group for group in failed if group.isValid]
        if self.groups: raise RuntimeError('Could not remove every dimensions graphics group')

    def refresh(self):
        if not graphics_workspace():
            return []
        self.erase()
        errors = []
        if self.visible:
            for ident, kind, refs in self.items:
                if ident in self.hidden_ids:
                    continue
                try:
                    entities = [resolve(self.design, ref) for ref in refs]
                    self.groups.append(renderer.render(self.design, kind, entities, APP.activeViewport.camera, ident, offset=self.offsets.get(ident, 0.0)))
                except Exception as ex:
                    errors.append(str(ex))
        try:
            renderer.arrange_labels(self.groups, APP.activeViewport.camera, APP.activeViewport)
        except Exception as ex:
            errors.append('Caption layout: ' + str(ex))
        APP.activeViewport.refresh()
        self.removed_for_save = False
        self.fingerprint = geometry_fingerprint(self.design, self.items, resolve, measure)
        self.restore_requested = False
        return errors

    def remove_item(self, ident):
        if not any(item[0] == ident for item in self.items):
            raise ValueError('Measurement not found')
        self.erase()
        save_state(self.design, [item for item in self.items if item[0] != ident],
                   {key: value for key, value in self.offsets.items() if key != ident},
                   self.hidden_ids - {ident}, self.visible)
        self.items = [item for item in self.items if item[0] != ident]
        self.offsets.pop(ident, None)
        self.hidden_ids.discard(ident)
        return self.refresh()


def current_state(create=True):
    state = state_for_document(APP.activeDocument, create)
    if state is None and create:
        raise RuntimeError('Open a Fusion design first')
    return state


def state_for(doc):
    return next((s for s in STATES if s.doc == doc), None)


def state_for_document(doc, create=True):
    """Load definitions from this document, including when it is not active.

    Loading is read-only; drawing graphics is deferred to the custom event.
    """
    if not doc or not getattr(doc, 'isValid', True):
        return None
    existing = state_for(doc)
    if existing is not None or not create:
        return existing
    design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
    if design is None:
        return None
    state = State(doc, design)
    state.load()
    state.restore_requested = bool(state.items)
    STATES[:] = [entry for entry in STATES if getattr(entry.doc, 'isValid', True)]
    STATES.append(state)
    return state


def request_document_restore(doc):
    """Queue at most one deferred restore; never create graphics in open events."""
    global UPDATE_PENDING
    state = state_for_document(doc)
    if (state is not None and getattr(state, 'restore_requested', False)
            and APP.activeDocument == doc and not UPDATE_PENDING):
        UPDATE_PENDING = APP.fireCustomEvent(UPDATE_EVENT_ID)
    return state


def restore_open_documents():
    """Read definitions at startup; one corrupt document cannot block the others."""
    for doc in APP.documents:
        try:
            request_document_restore(doc)
        except Exception:
            log_error()


class DocumentOpened(adsk.core.DocumentEventHandler):
    def notify(self, args):
        try:
            request_document_restore(args.document)
        except Exception:
            log_error()


class DocumentActivated(adsk.core.DocumentEventHandler):
    def notify(self, args):
        # Activation also occurs while Drawing saves its source. Only restore a
        # request created by opening/startup, never manufacture a fresh one here.
        state = state_for(args.document)
        if state is None or not getattr(state, 'restore_requested', False):
            return
        try:
            request_document_restore(args.document)
        except Exception:
            log_error()


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
        if getattr(self.state, 'removed_for_save', False) or getattr(self.state, 'restore_requested', False):
            self.state.refresh()
        self.visible = getattr(self.state, 'visible', True)
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
        visibility = inputs.addBoolValueInput('visible_' + ident, '', True, icon('visibility'), draft.visible)
        visibility_button(visibility, draft.visible, ident)
        geometry = inputs.addBoolValueInput('geometry_' + ident, '', False, icon('geometry'), False)
        geometry.tooltip = 'Edit geometry for ' + ident
        dropdown = inputs.addDropDownCommandInput('kind_' + ident, '', adsk.core.DropDownStyles.TextListDropDownStyle)
        dropdown.listItems.add('Select geometry', True, '')
        value = inputs.addTextBoxCommandInput('value_' + ident, '', '—', 1, True)
        offset = inputs.addValueInput('offset_' + ident, '', self.state.design.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(draft.offset))
        offset.tooltip = 'Offset from automatic placement for ' + ident
        clear = inputs.addBoolValueInput('clear_' + ident, '', False, icon('clear'), False)
        clear.tooltip = 'Clear geometry in this measurement'
        for column, item in enumerate((label, visibility, geometry, dropdown, value, offset, clear)):
            if not table.addCommandInput(item, index, column):
                raise RuntimeError('Cannot add measurement row')
        self.row_inputs[ident] = (draft, dropdown, value)
        if draft.first is not None or getattr(draft, 'unresolved_refs', None):
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
        if tuple(entities) == tuple(draft.entities) and not getattr(draft, 'unresolved_refs', None):
            return
        draft.unresolved_refs = None
        draft.reference_error = None
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
        if getattr(draft, 'unresolved_refs', None):
            if draft.kind is not None:
                dropdown.listItems.add(NAMES.get(draft.kind, draft.kind), True, '')
                value.text = 'Reference unavailable — edit or clear geometry'
                value.tooltip = str(getattr(draft, 'reference_error', 'Reference unavailable'))
                return
            # Explicit Clear resets kind through RowDraft.set_first(None).
            draft.unresolved_refs = None
            draft.reference_error = None
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
            draft = RowDraft(ident)
            try:
                entities = [resolve(self.state.design, ref) for ref in refs]
                draft.set_first(entities[0])
                if len(entities) == 2:
                    draft.set_second(entities[1])
                    draft.set_kind('distance')
                draft.set_kind(kind)
                measure(kind, draft.entities)
            except Exception as ex:
                # Retain the definition without displaying a stale measured value.
                # Another row's broken token must not prevent editing this document.
                draft = RowDraft(ident)
                draft.kind = kind
                draft.unresolved_refs = tuple(refs)
                draft.reference_error = str(ex)
            draft.offset = self.state.offsets.get(ident, 0.0)
            draft.visible = ident not in self.state.hidden_ids
            self.add_row(self.inputs, draft, activate=False)

    def sync_batch(self):
        drafts = [item[0] for item in self.row_inputs.values()]
        self.batch.rows = [draft for draft in drafts if draft.complete or getattr(draft, 'unresolved_refs', None)]
        complete = [draft for draft in self.batch.rows if not getattr(draft, 'unresolved_refs', None)]
        incomplete = [draft.id for draft in drafts if not getattr(draft, 'unresolved_refs', None)
                      and (draft.first is not None or draft.second is not None) and not draft.complete]
        return incomplete, duplicate_rows(complete)


class Created(adsk.core.CommandCreatedEventHandler):
    def __init__(self, operation):
        super().__init__(); self.operation = operation
    def notify(self, args):
        scope = EventScope()
        COMMAND_SCOPES.append(scope)
        destroyed = DestroyPreview(None, scope)
        try:
            cmd = args.command
            scope.bind(cmd.destroy, destroyed)
            if self.operation == 'add':
                cmd.setDialogInitialSize(620, 400)
                cmd.setDialogMinimumSize(550, 300)
                inputs = cmd.commandInputs
                context = BatchCommand()
                destroyed.context = context
                context.command = cmd
                context.inputs = inputs
                context.active_selection = None
                context.active_row = None
                table = inputs.addTableCommandInput('measurements', 'Measurements', 7, '2:1:1:4:3:3:1')
                table.minimumVisibleRows = 3
                table.maximumVisibleRows = 8
                context.table = table
                add = inputs.addBoolValueInput('add_row', '', False, icon('add'), False)
                remove = inputs.addBoolValueInput('remove_row', '', False, icon('remove'), False)
                clear_all = inputs.addBoolValueInput('clear_all', '', False, icon('delete_all'), False)
                visibility = inputs.addBoolValueInput('visible_all', '', True, icon('visibility'), context.visible)
                visibility_button(visibility, context.visible, 'all measurements')
                add.tooltip = 'Add measurement'
                remove.tooltip = 'Remove selected measurement'
                clear_all.tooltip = 'Remove all measurements'
                if not all(table.addToolbarCommandInput(item) for item in (add, remove, clear_all, visibility)):
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
                scope.bind(cmd.inputChanged, Changed(context))
                scope.bind(cmd.validateInputs, Validate(context))
                scope.bind(cmd.executePreview, Preview(context))
                scope.bind(cmd.execute, Execute(self.operation, context))
                context.state.editor_open = True
            elif self.operation == 'remove_one':
                state = current_state()
                inputs = cmd.commandInputs
                dropdown = inputs.addDropDownCommandInput('remove_id', 'Measurement', adsk.core.DropDownStyles.TextListDropDownStyle)
                for i, (ident, kind, refs) in enumerate(state.items):
                    dropdown.listItems.add(ident + ' — ' + NAMES.get(kind, kind), i == 0, '')
                inputs.addTextBoxCommandInput('remove_hint', '', 'Choose a measurement to remove.', 2, True)
                scope.bind(cmd.execute, Execute(self.operation))
            else:
                scope.bind(cmd.execute, Execute(self.operation))
        except Exception:
            destroyed.finish()
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
            elif ident == 'visible_all':
                c.visible = args.input.value
                visibility_button(args.input, c.visible, 'all measurements')
            elif ident.startswith('visible_'):
                draft = c.row_inputs[ident[8:]][0]
                draft.visible = args.input.value
                visibility_button(args.input, draft.visible, draft.id)
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
            if ident.startswith('visible_'):
                c.command.doExecutePreview()
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
                if getattr(row, 'unresolved_refs', None):
                    continue
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
            if not graphics_workspace() or not c.visible:
                args.isValidResult = False
                return
            errors = []
            _, duplicates = c.sync_batch()
            obstacles = renderer.obstacle_signature(state.design.rootComponent) if c.batch.rows else None
            for row in c.batch.rows:
                if getattr(row, 'unresolved_refs', None) or row.id in duplicates or not row.visible: continue
                try:
                    c.preview_groups.append(renderer.render(state.design, row.kind, row.entities, APP.activeViewport.camera, row.id, offset=getattr(row, 'offset', 0.0), layout_cache=c.layout_cache, obstacles=obstacles))
                except Exception as ex:
                    errors.append(row.id + ': ' + str(ex))
            try:
                renderer.arrange_labels(c.preview_groups, APP.activeViewport.camera, APP.activeViewport)
            except Exception as ex:
                errors.append('Caption layout: ' + str(ex))
            if errors: c.update_status(args.command.commandInputs, '; '.join(errors))
            args.isValidResult = False
        except Exception: log_error()


class DestroyPreview(adsk.core.CommandEventHandler):
    def __init__(self, context, scope=None):
        super().__init__(); self.context = context; self.scope = scope
    def notify(self, args):
        self.finish()

    def finish(self):
        # Locals retain this callback and context until destruction cleanup ends.
        context, scope = self.context, self.scope
        try:
            if context is not None:
                try:
                    context.clear_preview()
                finally:
                    for group in context.state.groups:
                        if group.isValid:
                            group.isVisible = context.state.visible and graphics_workspace()
                    if (graphics_workspace() and context.state.doc == APP.activeDocument
                            and not context.state.removed_for_save):
                        renderer.arrange_labels(context.state.groups, APP.activeViewport.camera, APP.activeViewport)
        except Exception: log_error()
        finally:
            if context is not None:
                context.state.editor_open = False
            if scope is not None:
                scope.close(destroyed=True)
                if scope in COMMAND_SCOPES:
                    COMMAND_SCOPES.remove(scope)
            self.context = self.scope = None


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
                        unresolved = getattr(row, 'unresolved_refs', None)
                        refs = unresolved or tuple(reference_for(e) for e in row.entities)
                        entities = [] if unresolved else [resolve(state.design, ref) for ref in refs]
                        group = None
                        if not unresolved and getattr(self.context, 'visible', True) and getattr(row, 'visible', True):
                            group = renderer.render(state.design, row.kind, entities, APP.activeViewport.camera, row.id, offset=getattr(row, 'offset', 0.0), layout_cache=getattr(self.context, 'layout_cache', None), obstacles=obstacles)
                        staged.append((row.id, row.kind, refs, group))
                    # Arrange the whole new set before touching committed graphics
                    # or definitions, so placement failure can roll back the draft.
                    renderer.arrange_labels([entry[3] for entry in staged if entry[3] is not None],
                                            APP.activeViewport.camera, APP.activeViewport)
                    state.erase(keep=[entry[3] for entry in staged if entry[3] is not None])
                    save_state(state.design, [(i, k, r) for i, k, r, _ in staged],
                               {r.id: getattr(r, 'offset', 0.0) for r in self.context.batch.rows},
                               {r.id for r in self.context.batch.rows if not getattr(r, 'visible', True)},
                               getattr(self.context, 'visible', True))
                except Exception:
                    for group in [entry[3] for entry in staged if entry[3] is not None]:
                        try:
                            if group.isValid and not group.deleteMe():
                                state.live_preview.append(group)
                            else:
                                renderer.forget(group)
                        except Exception:
                            state.live_preview.append(group)
                    raise
                state.items = [(ident, kind, refs) for ident, kind, refs, _ in staged]
                state.groups = [group for _, _, _, group in staged if group is not None]
                state.hidden_ids = {row.id for row in self.context.batch.rows if not getattr(row, 'visible', True)}
                if hasattr(state, 'offsets'):
                    state.offsets = {row.id: getattr(row, 'offset', 0.0) for row in self.context.batch.rows}
                state.next_id = self.context.batch.next_id
                state.visible = getattr(self.context, 'visible', True)
                state.removed_for_save = False
                state.restore_requested = False
                state.fingerprint = geometry_fingerprint(state.design, state.items, resolve, measure)
            elif self.operation == 'remove_one':
                item = args.command.commandInputs.itemById('remove_id').selectedItem
                if item is None: raise ValueError('No measurement selected')
                errors = state.remove_item(item.name.split(' — ', 1)[0])
                if errors: UI.messageBox('Some dimensions cannot be resolved:\n' + '\n'.join(errors[:5]))
            elif self.operation == 'toggle':
                state.erase()
                save_state(state.design, state.items, state.offsets, state.hidden_ids, not state.visible)
                state.visible = not state.visible
                errors = state.refresh()
                if errors: UI.messageBox('Some dimensions cannot be resolved:\n' + '\n'.join(errors[:5]))
            elif self.operation == 'refresh':
                errors = state.refresh()
                if errors: UI.messageBox('Some dimensions cannot be resolved:\n' + '\n'.join(errors[:5]))
            else:
                state.erase()
                save_state(state.design, [], {}, set(), state.visible)
                state.items.clear(); state.offsets.clear(); state.hidden_ids.clear(); APP.activeViewport.refresh()
        except Exception as ex:
            log_error(); UI.messageBox('Mesora: ' + str(ex))


class DocumentEvent(adsk.core.DocumentEventHandler):
    def __init__(self, mode): super().__init__(); self.mode = mode
    def notify(self, args):
        state = state_for(args.document)
        if not state: return
        try:
            if self.mode == 'saving':
                state.erase()
                state.removed_for_save = True
                state.restore_requested = False
                state.fingerprint = geometry_fingerprint(state.design, state.items, resolve, measure)
            elif self.mode == 'saved' and state.removed_for_save:
                # Creating CustomGraphics dirties the document. Drawing saves its
                # source until clean, so rendering here causes an endless save loop.
                # Restore only on an explicit Mesora action. Drawing may also
                # activate the source document as part of its save workflow.
                pass
            elif self.mode == 'closing':
                state.erase()
                # Closing may be canceled; retain definitions until document invalidation.
        except Exception:
            if self.mode == 'saving':
                args.isOperationCancelled = True
                args.cancelReason = 'Mesora could not remove informational graphics safely.'
            log_error()
            UI.messageBox('Mesora could not remove graphics. Do not save until the add-in can remove them.')


class CameraChanged(adsk.core.CameraEventHandler):
    def __init__(self):
        super().__init__()
        self.busy = False

    def notify(self, args):
        if self.busy or not graphics_workspace():
            return
        try:
            state = state_for(APP.activeDocument)
            if state is None or state.removed_for_save:
                return
            self.busy = True
            camera = args.viewport.camera
            groups = (list(state.groups) if state.visible else []) + list(state.live_preview) + ([state.preview] if state.preview is not None else [])
            groups = [group for group in groups
                      if getattr(group, 'isValid', True) and getattr(group, 'isVisible', True)]
            # Orbit changes readability only. Keep caption anchors and leader
            # geometry fixed even if this view projects them onto each other.
            # Explicit preview/apply/refresh actions may arrange the whole set.
            for group in groups:
                renderer.orient_text(group, camera)
        except Exception:
            log_error()
        finally:
            self.busy = False


class WorkspaceChanged(adsk.core.WorkspaceEventHandler):
    def __init__(self, changing):
        super().__init__()
        self.changing = changing

    def notify(self, args):
        global WORKSPACE_CHANGING
        WORKSPACE_CHANGING = self.changing


class ModelCommandEnded(adsk.core.ApplicationCommandEventHandler):
    """Queue work after Fusion has committed the model command's transaction."""
    def notify(self, args):
        global UPDATE_PENDING
        if UPDATE_PENDING or args.commandId.startswith('Mesora'):
            return
        state = state_for(APP.activeDocument)
        if state is None or state.editor_open:
            return
        UPDATE_PENDING = APP.fireCustomEvent(UPDATE_EVENT_ID)


class UpdateDimensions(adsk.core.CustomEventHandler):
    def notify(self, args):
        global UPDATE_PENDING
        UPDATE_PENDING = False
        try:
            if not graphics_workspace() or UI.activeCommand != 'SelectCommand':
                return
            state = state_for(APP.activeDocument)
            if state is None or state.editor_open:
                return
            stored = load_state(state.design)
            definitions_changed = (stored.items != state.items or stored.offsets != state.offsets or
                                   stored.hidden_ids != state.hidden_ids or stored.visible != state.visible)
            if definitions_changed:
                # Undo/Redo restores document attributes in Fusion's transaction.
                # Runtime state must follow them, including undoing the last row.
                state.load()
            owned = renderer.owned_groups(state.design)
            valid_tracked = [group for group in state.groups if group.isValid]
            graphics_changed = (len(owned) != len(state.groups) or
                                len(valid_tracked) != len(state.groups) or
                                {group.id for group in owned} != {group.id for group in valid_tracked})
            if not state.items and not definitions_changed and not state.restore_requested and not graphics_changed:
                return
            fingerprint = geometry_fingerprint(state.design, state.items, resolve, measure)
            # Saving itself, camera motion, and workspace activation must never
            # recreate graphics and restart the Drawing source-save loop.
            if state.restore_requested or definitions_changed or graphics_changed or (state.fingerprint is not None and fingerprint != state.fingerprint):
                state.refresh()
        except Exception:
            log_error()


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
            ('Add','Mesora — Add Dimension','Create and manage informational 3D measurements'),
            ('Toggle','Show/Hide Dimensions','Toggle dimensions in this document'),
            ('Refresh','Refresh Dimensions','Recalculate dimensions in this document'),
            ('Remove','Remove Dimension','Remove one measurement by ID'),
            ('Clear','Clear Dimensions','Remove measurements in this document')]:
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
        bind(APP.documentClosing, DocumentEvent('closing'))
        bind(APP.documentOpened, DocumentOpened())
        bind(APP.documentActivated, DocumentActivated())
        bind(APP.cameraChanged, CameraChanged())
        bind(UI.workspacePreDeactivate, WorkspaceChanged(True))
        bind(UI.workspacePreActivate, WorkspaceChanged(True))
        bind(UI.workspaceActivated, WorkspaceChanged(False))
        update_event = APP.registerCustomEvent(UPDATE_EVENT_ID)
        if not update_event:
            raise RuntimeError('Could not register Mesora geometry update event')
        bind(update_event, UpdateDimensions())
        bind(UI.commandTerminated, ModelCommandEnded())
        restore_open_documents()
    except Exception:
        log_error(); stop(context); UI.messageBox('Mesora failed to start. See Text Commands log.')


def stop(context):
    global WORKSPACE_CHANGING, UPDATE_PENDING
    WORKSPACE_CHANGING = False
    UPDATE_PENDING = False
    for scope in list(COMMAND_SCOPES):
        if scope.close():
            COMMAND_SCOPES.remove(scope)
    failed_states = []
    for state in STATES:
        try: state.erase()
        except Exception:
            failed_states.append(state)
            log_error()
    STATES[:] = failed_states
    for event, handler in reversed(HANDLERS):
        try: event.remove(handler)
        except Exception: pass
    HANDLERS.clear()
    try: APP.unregisterCustomEvent(UPDATE_EVENT_ID)
    except Exception: log_error()
    for control in reversed(CONTROLS):
        try: control.deleteMe()
        except Exception: pass
    CONTROLS.clear()
    for definition in reversed(DEFINITIONS):
        try: definition.deleteMe()
        except Exception: pass
    DEFINITIONS.clear()
