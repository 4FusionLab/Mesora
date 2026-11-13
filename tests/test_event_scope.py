import gc
import unittest
import weakref

from Mesora.dimensions.event_scope import EventScope


class Event:
    def __init__(self): self.handlers = []
    def add(self, handler): self.handlers.append(handler); return True
    def remove(self, handler): self.handlers.remove(handler); return True


class Handler:
    def __init__(self, context): self.context = context


class Context:
    pass


class EventScopeTest(unittest.TestCase):
    def test_destroyed_command_releases_context_without_touching_other_command(self):
        first, second = EventScope(), EventScope()
        context = Context()
        ref = weakref.ref(context)
        event, other = Event(), Event()
        first.bind(event, Handler(context))
        second.bind(other, Handler(Context()))
        del context
        first.close(destroyed=True)
        gc.collect()
        self.assertIsNone(ref())
        self.assertEqual(event.handlers, [])
        self.assertEqual(len(other.handlers), 1)
        second.close()

    def test_active_detach_failure_is_retained_for_retry(self):
        scope, event = EventScope(), Event()
        handler = Handler(Context())
        scope.bind(event, handler)
        remove = event.remove
        event.remove = lambda handler: False
        self.assertFalse(scope.close())
        self.assertEqual(len(scope.bindings), 1)
        event.remove = remove
        self.assertTrue(scope.close())

    def test_destroyed_invalid_event_does_not_keep_deleted_context(self):
        scope, event = EventScope(), Event()
        scope.bind(event, Handler(Context()))
        def invalid(handler): raise RuntimeError('Deleted Fusion event')
        event.remove = invalid
        self.assertTrue(scope.close(destroyed=True))
        self.assertEqual(scope.bindings, [])
