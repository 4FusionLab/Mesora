"""Own event-handler references for one active command, without importing adsk."""


class EventScope:
    def __init__(self):
        self.bindings = []

    def bind(self, event, handler):
        if not event.add(handler):
            raise RuntimeError('Failed to attach Fusion command event')
        self.bindings.append((event, handler))

    def close(self, destroyed=False):
        """Detach active events, or release references after command destruction.

        Destroyed command event wrappers may already be invalid. Keeping them
        then would retain deleted inputs and the document through their handlers.
        During add-in stop, failures on still-active commands remain retryable.
        """
        failed = []
        for event, handler in reversed(self.bindings):
            try:
                if not event.remove(handler) and not destroyed:
                    failed.append((event, handler))
            except Exception:
                if not destroyed:
                    failed.append((event, handler))
        self.bindings[:] = reversed(failed)
        return not self.bindings
