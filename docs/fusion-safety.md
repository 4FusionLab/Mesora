# Fusion lifecycle and acceptance coverage

[Русская версия](fusion-safety.ru.md)

## Accepted macOS scope

The independent final product review found no open Blocker or Major in the agreed
macOS release scope. Evidence covers all seven measurement types, actual selection
and type-change events, visibility, Undo/Redo, model updates, save/reopen, Save As,
Drawing transition, normal restart, reference measurements in transformed/nested
occurrences, multi-document isolation and installing the package ZIP. Windows
Fusion remains natively unverified; it is not a separate release blocker under
the accepted macOS scope.

The final native type probe confirmed 13 actual UI events. For the same cylindrical
face, Fusion Inspect and Mesora agreed on Loop Length 339.292 mm, Area 5089.38 mm²,
Radius 27 mm and Diameter 54 mm. Do not confuse that perimeter with the length of
one circular edge. The [Measure reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/GUID-D070A3CB-729F-410F-9DA4-D9DF7F4D55B5.htm)
lists the face measurements available in Inspect.

The reproduced caption overlap and duplicate-graphics Undo defects passed retests.
Camera changes now preserve model-space caption anchors, leaders and angular arcs;
the user confirmed that normal orbit no longer jumps. A new view can still project
labels together; **Refresh Dimensions** arranges them for that view.

See [native evidence](validation/stability-native-2026-11-13.ru.md) and
[acceptance traceability](validation/stable-release-cjm-2026-11-13.ru.md).
Historical entries in those reports retain their original failures and subsequent
retests; they are not the current product status.

## Saving and CustomGraphics

Definitions and settings persist in design attributes. Graphics are display state:
Mesora removes them before saving and does not recreate them in `documentSaved`.
Open Mesora or use **Refresh Dimensions** after saving to display them again.
Opening a saved document or starting the add-in restores the definitions and
requests display. Stop/reopen checks found no labels without Mesora, and the
model remained editable and savable without the add-in.

This strategy avoids the repeated source-save loop during Drawing creation.
The accepted Drawing test reached the sheet and canceled Base View placement;
it does not claim completed drawing detailing. An [Autodesk forum report](https://forums.autodesk.com/t5/fusion-support-forum/bug-report-custom-graphics-serialized-into-a-document-are/td-p/14142906)
describes inaccessible graphics serialized into a file. Earlier local observations
using a different Python loading/API path are historical and are not attributed
to the accepted managed GUI lifecycle. No CAD archive modification is used.

The [Application API](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Application.htm)
documents document lifecycle events. Current [DocumentEventArgs](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_DocumentEventArgs.htm)
uses `isOperationCancelled` and `cancelReason`. A failed cleanup must retain owned
groups for retry and cancel saving. A zero graphics count alone is not proof of
an annotation-free saved file: native acceptance also used visual inspection.

## Geometry and event contracts

Use the [BRep edge evaluator](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepEdge_evaluator.htm)
and [getLengthAtParameter](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_CurveEvaluator3D_getLengthAtParameter.htm)
for curve length, not chord length. Restore entity and occurrence references in
their proper context; do not compare token strings as object identity. Missing or
ambiguous references must not display stale values, and unsupported/corrupt stored
definitions must not be silently overwritten.

Deferred work runs through Fusion's custom event queue in its permitted thread.
Independent event evidence came from an observer started as a managed add-in.
Importing the observer directly through MCP did not deliver callbacks and cannot
prove that callbacks are absent from the managed product. Development helpers
are excluded from the ZIP.

## Limits and future regression work

The radius update/Undo/Redo test used a native acceptance command with its own
Fusion transaction, not manual Change Parameters UI. The earlier UI attempt was
interrupted during AX/Qt accessibility inspection; its cause was not established
as Mesora. Real failed-cloud-save recovery, every API save route and exhaustive
geometry/picking combinations are not covered by the release acceptance. Nested
reference measurements do not claim a separate complete annotation auto-update
workflow for every assembly edit.

Use synthetic documents for future regressions and preserve user CAD data. The
saved acceptance fixtures were deleted. Current testing follows the user's
no-CAD-save instruction; do not recreate cloud fixtures without authorization.
