# Visibility, persistence and Drawing

[Русская версия](visibility-and-drawing.ru.md)

**Status: experimental validation candidate; stable release withheld.** Undo
reproduced duplicate graphics; cleanup correction and native retesting are required. Managed
macOS GUI testing passed save cleanup and the checked save/reopen/edit path without
Mesora: no dimensions were visible while the add-in was stopped. Starting Mesora
restored definitions, visibility, offsets and current values. Earlier orphan
observations came from a different Python loading/API path and do not establish a
failure of the current managed GUI save path. Use disposable documents while the
remaining gates are open. See [native evidence](validation/stability-native-2026-11-13.ru.md).

Each measurement row has an eye button. Click it to hide or show that measurement
without removing its geometry references, type or offset. A crossed-out eye means
the row is hidden. Hidden rows remain editable.

The eye next to **+**, **−** and the trash button hides or shows the whole set.
It preserves individual row settings: showing the set again keeps individually
hidden rows hidden. Visibility changes preview immediately; **OK** stores committed
geometry references, measurement types, offsets and visibility in the design's
attributes. **Cancel** discards the draft and restores committed visibility.
Measured values are recalculated from current geometry rather than stored.
Unsupported or damaged stored definitions are not silently overwritten.

Automatic updates are implemented through `commandTerminated` followed by a custom
event on Fusion's permitted execution thread. GUI eye application passed on the
macOS fixture. Undo/Redo restored visibility metadata, but Undo revived an untracked
graphics group and deferred rendering added another: actual groups reached two
while State tracked one. Graphics Undo acceptance failed; cleanup needs correction
and native retesting. Parametric edits and full recovery also need acceptance; implementation and offline tests do not establish every native path.

The candidate also implements definition loading on document open and Mesora
startup. Display is requested through a deferred custom event; activation may
resume an existing open/startup request, while workspace, active-document and
active-command checks gate rendering. Saving clears the pending restore request.
Managed macOS startup/reopen restored two definitions, a hidden row, offsets and
the current edge length after geometry was edited without Mesora. An independently
managed observer confirmed custom-event delivery and real save callbacks. Direct
MCP import of an observer did not confirm callbacks and cannot establish their
absence in the managed add-in. See [native evidence](validation/stability-native-2026-11-13.ru.md);
no full Fusion restart acceptance has been completed.

When the UI save event runs, Mesora removes tracked graphics before saving. It
deliberately does not recreate them inside `documentSaved`: that makes the source
design modified again and can make Drawing creation repeatedly save the source.
After a save, open Mesora or use **Refresh Dimensions** to show the dimensions
again. Document activation alone does not create a new restore request, because
Drawing can activate its source during creation; it may only resume an existing
open/startup request. Workspace activation does not recreate graphics. The camera handler does
not update model graphics in Drawing or during workspace transitions.

Managed GUI Save and Save As confirmed cleanup; cancellation preserved dimensions.
The checked file reopened without dimensions while Mesora was stopped, remained
editable and savable, and restored current measurements when Mesora started.
Manual refresh after save remains a workaround. API Save/Save As with the managed
lifecycle, copy isolation and remaining recovery paths need separate acceptance.
The earlier orphan file is historical evidence from a different loading/API path;
a zero API group count alone is still insufficient to prove an annotation-free file.

## Acceptance checklist

Use a new disposable model on each supported OS. Record a result and evidence for
each step; this checklist itself does not mark any gate passed.

1. Create two measurements. Hide one row; verify its graphic disappears and its
   row, geometry, type and offset remain. Change the offset while hidden.
2. Hide and show the whole set. Verify the individually hidden row stays hidden.
3. Apply, reopen Mesora, and verify both eye states. Show the hidden row and
   cancel; verify the committed visibility remains unchanged.
4. Apply with all measurements globally hidden, reopen and show them; verify
   individual settings are retained. Remove a hidden row and add another row.
5. Change the referenced geometry, then Undo and Redo. Verify values and placement
   update, and missing/ambiguous references do not display stale measurements.
6. Test UI Save, API save and Save As independently with dimensions shown. Verify
   cleanup, document cleanliness and explicit **Refresh Dimensions** behavior.
7. Stop Mesora, close and reopen, then fully restart Fusion and reopen. Inspect
   visually for persistent annotations as well as checking API group counts.
   Reload Mesora and verify definitions, offsets and both visibility levels.
8. With dimensions shown, create a Drawing from the design. Verify creation reaches
   the drawing sheet and Base View, with no endless source-version increments.
9. Return to the model and verify measurements and visibility. Test canceled/failed
   save and close paths without discarding or overwriting definitions.

Undo graphics cleanup/retesting, parametric changes, latest-candidate Drawing,
Windows, full Fusion restart and
remaining API save/recovery gates still prevent a stable release. See [Fusion safety notes](fusion-safety.md)
and the [product acceptance matrix](validation/stable-release-cjm-2026-11-13.ru.md).
