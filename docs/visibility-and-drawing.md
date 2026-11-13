# Visibility, persistence and Drawing

[Русская версия](visibility-and-drawing.ru.md)

**Status: experimental validation candidate; stable release withheld.** Native
macOS acceptance reproduced an inaccessible persistent CustomGraphics annotation
after API Save As, stopping Mesora, closing and reopening the synthetic model.
The annotation was visible while `customGraphicsGroups.count` was zero. A zero
count is not proof that the model contains no saved graphics. Use disposable
documents only. See the [native evidence](validation/stability-native-2026-11-13.ru.md).

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
event on Fusion's permitted execution thread. Native acceptance of geometry edits,
Undo/Redo and full recovery is still pending; implementation and offline tests are
not evidence that every native path works.

The candidate also implements definition loading on document open and Mesora
startup. Display is requested through a deferred custom event; activation may
resume an existing open/startup request, while workspace, active-document and
active-command checks gate rendering. Saving clears the pending restore request.
This code is not native acceptance: actual callback delivery and automatic display
after managed add-in restart/reopen remain unconfirmed. See the latest rerun in
[native evidence](validation/stability-native-2026-11-13.ru.md); no full Fusion
restart acceptance has been completed.

When the UI save event runs, Mesora removes tracked graphics before saving. It
deliberately does not recreate them inside `documentSaved`: that makes the source
design modified again and can make Drawing creation repeatedly save the source.
After a save, open Mesora or use **Refresh Dimensions** to show the dimensions
again. Document activation alone does not create a new restore request, because
Drawing can activate its source during creation; it may only resume an existing
open/startup request. Workspace activation does not recreate graphics. The camera handler does
not update model graphics in Drawing or during workspace transitions.

This is a temporary workaround, not complete normal save/reopen behavior. The API
Save As path reproduced a persistent annotation despite this event strategy.
Stopping the add-in does not guarantee removal of an already saved artifact.

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

The persistent-artifact defect, Windows native acceptance and full restart gates
remain blockers for a stable release. See [Fusion safety notes](fusion-safety.md)
and the [product acceptance matrix](validation/stable-release-cjm-2026-11-13.ru.md).
