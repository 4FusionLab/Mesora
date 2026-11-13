"""Read-only Fusion event observer for synthetic Mesora acceptance documents.

Import inside Fusion, then call start('/absolute/path/trace.jsonl'), probe(),
snapshot('label') and stop(). Keep this module imported until stop completes.
It never calls Mesora handlers, changes event cancellation, measures geometry,
creates graphics, or edits/saves/closes documents. Only documents whose names
start with 'Mesora' contribute document or product state. Other names are redacted.
Attribute contents and entity tokens are never written; only a SHA-256 is emitted.

The observer is development tooling and is not included in the add-in ZIP.
API references:
https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Application.htm
https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_UserInterface_commandStarting.htm
https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Application_fireCustomEvent.htm
"""
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid
from datetime import datetime, timezone

import adsk.core
import adsk.fusion


# Retain every callback until its event has actually detached.
HANDLERS = []
_SESSION = None
_ATTRIBUTE_GROUP = '4FusionLab.Dimensions'
_ATTRIBUTE_NAME = 'definitions'


def _get(obj, name, fallback=None):
    try:
        return getattr(obj, name) if obj is not None else fallback
    except Exception:
        return fallback


def _same(left, right):
    try:
        return left is not None and right is not None and left == right
    except Exception:
        return False


def _document(doc):
    if doc is None:
        return {'present': False}
    name = _get(doc, 'name')
    if not isinstance(name, str) or not name.startswith('Mesora'):
        return {'present': True, 'included': False}
    return {'present': True, 'included': True, 'name': name,
            'is_modified': _get(doc, 'isModified'), 'is_valid': _get(doc, 'isValid')}


def _product_module():
    # Inspect already-loaded modules only; importing Mesora could itself run code.
    for module in tuple(sys.modules.values()):
        namespace = _get(module, '__dict__', {})
        filename = namespace.get('__file__')
        if (isinstance(filename, str) and Path(filename).name == 'Mesora.py'
                and isinstance(namespace.get('STATES'), list)):
            return module
    return None


def _state_for(doc):
    module = _product_module()
    for state in _get(module, 'STATES', []):
        if _same(_get(state, 'doc'), doc):
            groups = _get(state, 'groups', [])
            live = _get(state, 'live_preview', [])
            return {'matched': True, 'tracked_groups': len(groups),
                    'valid_tracked_groups': sum(bool(_get(g, 'isValid', False)) for g in groups),
                    'live_preview_groups': len(live),
                    'has_preview': _get(state, 'preview') is not None,
                    'removed_for_save': _get(state, 'removed_for_save'),
                    'editor_open': _get(state, 'editor_open'),
                    'measurement_count': len(_get(state, 'items', [])),
                    'visible': _get(state, 'visible'),
                    'hidden_count': len(_get(state, 'hidden_ids', set()))}
    return {'matched': False, 'module_loaded': module is not None}


def _design_info(doc):
    try:
        product = doc.products.itemByProductType('DesignProductType')
        design = adsk.fusion.Design.cast(product)
        if not design:
            return {'present': False}
        attribute = design.attributes.itemByName(_ATTRIBUTE_GROUP, _ATTRIBUTE_NAME)
        result = {'present': True, 'definitions_present': bool(attribute),
                  'custom_graphics_group_count': design.rootComponent.customGraphicsGroups.count}
        if attribute:
            result['definitions_sha256'] = hashlib.sha256(attribute.value.encode('utf-8')).hexdigest()
        return result
    except Exception as exc:
        # Exception messages can contain paths or values; persist the class only.
        return {'inspection_error': type(exc).__name__}


def _context(event_doc=None):
    app = adsk.core.Application.get()
    ui = app.userInterface
    active = _get(app, 'activeDocument')
    target = event_doc if event_doc is not None else active
    active_info, target_info = _document(active), _document(target)
    data = {'active_command': _get(ui, 'activeCommand'),
            'active_workspace': _get(_get(ui, 'activeWorkspace'), 'id'),
            'active_document': active_info, 'event_document': target_info,
            'event_document_matches_active': _same(target, active)}
    if target_info.get('included'):
        data['mesora_state'] = _state_for(target)
        data['design'] = _design_info(target)
    return data


def _trace(event, event_doc=None, **extra):
    session = _SESSION
    if session is None:
        return None
    # Timestamp callback entry before any document or product-state inspection.
    entered = time.monotonic_ns()
    session['counter'] += 1
    record = {'session': session['id'], 'counter': session['counter'],
              'monotonic_ns': entered, 'elapsed_ns': entered - session['started_ns'],
              'utc': datetime.now(timezone.utc).isoformat(),
              'event': event, 'phase': 'entry'}
    record.update(extra)
    try:
        record.update(_context(event_doc))
    except Exception as exc:
        record['context_error'] = type(exc).__name__
    session['stream'].write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
    session['stream'].flush()
    return record['counter']


class _DocumentHandler(adsk.core.DocumentEventHandler):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def notify(self, args):
        _trace(self.name, _get(args, 'document'))


class _CommandHandler(adsk.core.ApplicationCommandEventHandler):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def notify(self, args):
        _trace(self.name, command_id=_get(args, 'commandId'))


class _ProbeHandler(adsk.core.CustomEventHandler):
    def notify(self, args):
        # additionalInfo is our generated UUID, never an arbitrary caller payload.
        session = _SESSION
        if session is not None:
            session['probe_callbacks'] += 1
        _trace('customEvent.callback', probe_id=_get(args, 'additionalInfo'),
               delivered_callbacks=session['probe_callbacks'] if session else 0)


def _bind(event, handler):
    if not event.add(handler):
        raise RuntimeError('Could not attach acceptance observer handler')
    HANDLERS.append((event, handler))


def start(output_path):
    """Attach independent observers and return a unique session ID.

    The caller must invoke this on Fusion's permitted main thread. Existing JSONL
    is appended, not overwritten. Starting while already active is rejected.
    """
    global _SESSION
    if _SESSION is not None:
        raise RuntimeError('Acceptance observer is already active; call stop first')
    path = Path(output_path).expanduser()
    if not path.is_absolute():
        raise ValueError('Observer output_path must be absolute')
    path.parent.mkdir(parents=True, exist_ok=True)
    session_id = str(uuid.uuid4())
    _SESSION = {'id': session_id, 'counter': 0, 'started_ns': time.monotonic_ns(),
                'stream': path.open('a', encoding='utf-8', buffering=1),
                'custom_id': 'MesoraAcceptanceObserver.' + session_id,
                'custom_registered': False, 'probe_callbacks': 0}
    app = adsk.core.Application.get()
    try:
        for name in ('documentSaving', 'documentSaved', 'documentOpened',
                     'documentClosing', 'documentCreated', 'documentActivated'):
            _bind(getattr(app, name), _DocumentHandler(name))
        for name in ('commandStarting', 'commandTerminated'):
            _bind(getattr(app.userInterface, name), _CommandHandler(name))
        event = app.registerCustomEvent(_SESSION['custom_id'])
        if not event:
            raise RuntimeError('Could not register acceptance probe')
        _SESSION['custom_registered'] = True
        _bind(event, _ProbeHandler())
        _trace('observer.started', fusion_version=_get(app, 'version'),
               attached_handlers=len(HANDLERS))
        return session_id
    except Exception:
        stop()
        raise


def snapshot(label):
    """Record current read-only state. Labels must contain no confidential data."""
    if _SESSION is None:
        raise RuntimeError('Acceptance observer is not running')
    return _trace('observer.snapshot', label=str(label))


def probe():
    """Queue the observer's own probe; only callback records prove delivery."""
    if _SESSION is None:
        raise RuntimeError('Acceptance observer is not running')
    ident = str(uuid.uuid4())
    _trace('customEvent.request', probe_id=ident)
    queued = adsk.core.Application.get().fireCustomEvent(_SESSION['custom_id'], ident)
    _trace('customEvent.queued', probe_id=ident, queued=bool(queued))
    return {'session': _SESSION['id'], 'probe_id': ident, 'queued': bool(queued)}


def stop():
    """Detach all observers and unregister the probe, retaining failures for retry."""
    global _SESSION
    if _SESSION is None:
        return {'running': False, 'remaining_handlers': len(HANDLERS)}
    failed = []
    for event, handler in reversed(HANDLERS):
        try:
            if event.remove(handler):
                HANDLERS.remove((event, handler))
            else:
                failed.append(type(handler).__name__)
        except Exception as exc:
            failed.append(type(exc).__name__)
    if not HANDLERS and _SESSION['custom_registered']:
        try:
            if adsk.core.Application.get().unregisterCustomEvent(_SESSION['custom_id']):
                _SESSION['custom_registered'] = False
            else:
                failed.append('CustomEventUnregisterFailed')
        except Exception as exc:
            failed.append(type(exc).__name__)
    complete = not HANDLERS and not _SESSION['custom_registered']
    _trace('observer.stopped' if complete else 'observer.detach_failed',
           remaining_handlers=len(HANDLERS), detach_errors=failed)
    result = {'session': _SESSION['id'], 'running': not complete,
              'remaining_handlers': len(HANDLERS), 'errors': failed}
    if complete:
        _SESSION['stream'].close()
        _SESSION = None
    return result
