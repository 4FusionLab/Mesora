"""Autodesk Fusion entry point: one non-destructive example command.

The module is imported only by Fusion; tests target core.py without adsk.
"""

import traceback

import adsk.core

from . import config, core


_ui = None
_command_definition = None
_control = None
_handlers = []
_sessions = []


class _Executed(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            document = app.activeDocument
            document_name = document.name if document else None
            app.userInterface.messageBox(core.ready_message(config.DISPLAY_NAME, document_name))
        except Exception:
            adsk.core.Application.get().log(traceback.format_exc())


class _Destroyed(adsk.core.CommandEventHandler):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def notify(self, args):
        if self.session in _sessions:
            _sessions.remove(self.session)


class _Session:
    def __init__(self, command):
        self.executed = _Executed()
        self.destroyed = _Destroyed(self)
        command.execute.add(self.executed)
        command.destroy.add(self.destroyed)
        command.commandInputs.addTextBoxCommandInput(
            '4fl_intro', '', config.DESCRIPTION, 2, True
        )


class _Created(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            _sessions.append(_Session(args.command))
        except Exception:
            adsk.core.Application.get().log(traceback.format_exc())


def run(context):
    """Register the add-in under SOLID -> ADD-INS. No document is modified."""
    global _ui, _command_definition, _control

    if not config.INITIALIZED:
        raise RuntimeError('This is a template. Run scripts/init_addin.py before installing.')

    try:
        app = adsk.core.Application.get()
        _ui = app.userInterface
        workspace = _ui.workspaces.itemById('FusionSolidEnvironment')
        if workspace is None:
            raise RuntimeError('Fusion SOLID workspace is not available.')
        panel = workspace.toolbarPanels.itemById('SolidScriptsAddinsPanel')
        if panel is None:
            raise RuntimeError('Fusion ADD-INS toolbar panel is not available.')

        definition = _ui.commandDefinitions.itemById(config.COMMAND_ID)
        if definition is None:
            definition = _ui.commandDefinitions.addButtonDefinition(
                config.COMMAND_ID, config.DISPLAY_NAME, config.DESCRIPTION
            )
        _command_definition = definition
        handler = _Created()
        definition.commandCreated.add(handler)
        _handlers.append(handler)
        control = panel.controls.itemById(config.COMMAND_ID)
        if control is None:
            control = panel.controls.addCommand(definition)
        _control = control
    except Exception:
        adsk.core.Application.get().log(traceback.format_exc())
        stop(context)
        raise


def stop(context):
    """Remove toolbar items and event references, including after a failed start."""
    global _ui, _command_definition, _control

    try:
        if _control is not None and _control.isValid:
            _control.deleteMe()
        if _command_definition is not None and _command_definition.isValid:
            _command_definition.deleteMe()
    finally:
        _control = None
        _command_definition = None
        _sessions.clear()
        _handlers.clear()
        _ui = None
