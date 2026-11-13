"""Command destruction must release temporary handlers without stopping Mesora."""
import gc
import types
import unittest
import weakref

import test_visibility_lifecycle as lifecycle


class Event:
    def __init__(self): self.handlers = []
    def add(self, handler): self.handlers.append(handler); return True
    def remove(self, handler): self.handlers.remove(handler); return True


class CommandHandlerLifetimeTest(unittest.TestCase):
    def setUp(self):
        self.fixture = lifecycle.LifecycleTest(methodName='runTest')
        self.fixture.setUp()
        self.m = self.fixture.m

    def tearDown(self):
        self.fixture.tearDown()

    def test_repeated_native_command_lifetimes_keep_app_handlers_bounded(self):
        app_event, app_handler = Event(), object()
        self.m.bind(app_event, app_handler)
        for _ in range(3):
            command = types.SimpleNamespace(execute=Event(), destroy=Event())
            self.m.Created('toggle').notify(types.SimpleNamespace(command=command))
            self.assertEqual(len(self.m.HANDLERS), 1)
            self.assertEqual(len(self.m.COMMAND_SCOPES), 1)
            self.assertEqual(len(command.execute.handlers), 1)
            command.destroy.handlers[0].notify(None)
            self.assertEqual(command.execute.handlers, [])
            self.assertEqual(command.destroy.handlers, [])
            self.assertEqual(self.m.COMMAND_SCOPES, [])
            self.assertEqual(self.m.HANDLERS, [(app_event, app_handler)])

    def test_destroy_cleanup_failure_drops_document_context_and_scope(self):
        scope = self.m.EventScope()
        self.m.COMMAND_SCOPES.append(scope)
        class Context:
            def clear_preview(self): raise RuntimeError('Preview removal failed')
        context = Context()
        context.state = self.fixture.state
        context.state.editor_open = True
        group = types.SimpleNamespace(isValid=True, isVisible=False)
        context.state.groups = [group]
        destroyed = self.m.DestroyPreview(context, scope)
        scope.bind(Event(), self.m.Preview(context))
        scope.bind(Event(), destroyed)
        ref = weakref.ref(context)
        del context
        destroyed.notify(None)
        gc.collect()
        self.assertIsNone(ref())
        self.assertTrue(group.isVisible)
        self.assertFalse(self.fixture.state.editor_open)
        self.assertEqual(self.m.COMMAND_SCOPES, [])

    def test_addin_stop_detaches_still_active_command_scope(self):
        command = types.SimpleNamespace(execute=Event(), destroy=Event())
        self.m.Created('toggle').notify(types.SimpleNamespace(command=command))
        self.m.APP.unregisterCustomEvent = lambda ident: True
        self.m.stop(None)
        self.assertEqual(command.execute.handlers, [])
        self.assertEqual(command.destroy.handlers, [])
        self.assertEqual(self.m.COMMAND_SCOPES, [])
