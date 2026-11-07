"""Example domain logic: never import adsk in this module."""


def ready_message(display_name, document_name):
    """Build a harmless user-facing message for the demonstration command."""
    if not display_name or not display_name.strip():
        raise ValueError('Display name must not be empty.')
    if document_name:
        return f'{display_name} is ready. Active document: {document_name}.'
    return f'{display_name} is ready. Open a design to begin.'
