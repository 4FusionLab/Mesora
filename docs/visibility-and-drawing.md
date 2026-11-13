# Visibility, saving and Drawing

[Русская версия](visibility-and-drawing.ru.md)

## Show or hide dimensions

Each measurement row has an eye button. It hides or shows the dimension without
removing its geometry references, type or offset. Hidden rows remain editable.
The eye beside **+**, **−** and the trash button controls the whole set. Showing
the set again preserves individually hidden rows.

Visibility changes preview immediately. **OK** stores definitions, offsets and
visibility in the design; **Cancel** discards the draft. Values are recalculated
from the geometry rather than saved as cached numbers. Missing references remain
available for repair or removal instead of displaying an old value.

## Place labels and rotate the model

Mesora spaces labels apart when dimensions are added or edited. Rotating or zooming
keeps their positions and leader lines fixed in the model; only text orientation
changes for readability. Angular arcs also stay fixed. A new view can project
labels onto each other; use **Refresh Dimensions** to arrange them for that view.
Model, geometry, offset and visibility changes can arrange the whole set again.

## Save and reopen

Definitions and settings are saved with the model. Mesora removes its displayed
graphics before saving and does not redraw them in `documentSaved`. This keeps
the source clean when Drawing needs to save it. After a save, open Mesora or use
**Refresh Dimensions** to show dimensions again.

Opening a document or starting Mesora loads the saved definitions and requests
display in a suitable Design context. Without Mesora running, the model is editable
and the dimensions are not displayed. A canceled Save As preserves the current set.

## Drawing and verification

macOS acceptance confirmed a Drawing transition with visible dimensions and one
source save, followed by a clean return to the model. Base View placement was
canceled; completed drawing creation and detailing were not part of that check.

The accepted macOS scope also includes visibility, Undo/Redo without duplicate
graphics, geometry updates, save/reopen, Save As, normal Fusion restart and the
absence of labels when Mesora is stopped. The user confirmed that normal orbit
no longer makes labels jump. Windows remains natively unverified. See the
[native evidence](validation/stability-native-2026-11-13.ru.md),
[acceptance matrix](validation/stable-release-cjm-2026-11-13.ru.md) and
[coverage notes](fusion-safety.md).
