# Fusion API safety research

[Русская версия](fusion-safety.ru.md)

## CustomGraphics persistence

An [Autodesk forum report](https://forums.autodesk.com/t5/fusion-support-forum/bug-report-custom-graphics-serialized-into-a-document-are/td-p/14142906)
describes custom graphics present during a save remaining visible after reopening
while becoming unavailable through the API. A forum reply describes removing
graphics before save and recreating them afterward; this is an anecdotal workaround,
not a documented guarantee. No archive modification is implemented or recommended.

The official [Application API](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Application.htm)
documents `documentSaving` at the start of saving, `documentSaved` after completion,
`documentOpened` at the end of opening, `documentActivated` and `documentClosing`.
Saving can be canceled through `DocumentEventArgs.isSaveCanceled`. Documentation
does not establish that deleting every custom graphic in `documentSaving` prevents
all cached-scene serialization paths, nor that a canceled or failed save always
delivers `documentSaved`. Treat those as open questions. Do not claim persistence
is safe or restore graphics blindly after an interrupted save.

Before enabling graphics, exercise save, Save As, cancel, failed save, close,
reopen, multiple open documents, shutdown and add-in stop on disposable designs,
with both macOS and Windows. Verify actual event order, deletion outcomes and
absence of orphaned graphics after a full Fusion restart. An experiment cannot
prove all possible crash and save paths safe; document the remaining risk.

## Measurements and references

[Edge evaluator](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepEdge_evaluator.htm)
and [getLengthAtParameter](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_CurveEvaluator3D_getLengthAtParameter.htm)
provide the curve length between parameters rather than a chord measurement.
[SketchPoint.worldGeometry](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_SketchPoint_worldGeometry.htm)
is documented in root-component space including assembly context. Other object
types and token resolution need their own context tests. Token strings must not be
compared as identity; unresolved or ambiguous references must not render old data.

## Current validation

Offline unit tests exercise arithmetic, evaluator and persistence stubs, schema
handling, and reference failure cases. A read-only run on the open macOS Fusion
design measured one full circular edge (radius 0.51 cm, length 3.2044245067 cm),
one cylindrical face (diameter 1.02 cm), two vertices, sketch arcs and circles,
and resolved an edge and a vertex in an occurrence. The inspected occurrence had
zero translation; this does not validate transformed or nested occurrences. The
document's modified flag was false both before and after. There has been no live
attribute write, save/reopen test or Windows test. A direct native renderer smoke
test created and deleted groups for distance, circular edge length, radius and
cylindrical diameter; the group count returned to zero. This did not test the
interactive command or establish visual quality. Fusion marked the open design
modified, and it was not saved. Attempts to enable the add-in through the manager
did not produce registered commands; the cause has not yet been established.
