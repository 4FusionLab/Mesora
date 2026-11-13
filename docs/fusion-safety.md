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
The current [DocumentEventArgs reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_DocumentEventArgs.htm)
documents `isOperationCancelled` and `cancelReason` for saving. Fusion 2706.1.17
exposes those properties and does not expose `isSaveCanceled`; the older Application
event description still mentions that obsolete name. Native fault-injection must
verify actual cancellation, beyond checking that the property exists. Documentation
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

## Historical validation before the stability candidate

The observations below document an earlier investigation. For later command checks and remaining limitations, see the [README](../README.md) and the stability candidate section below.

Offline unit tests exercise arithmetic, evaluator and persistence stubs, schema
handling, and reference failure cases. A read-only run on the open macOS Fusion
design measured one full circular edge (radius 0.51 cm, length 3.2044245067 cm),
one cylindrical face (diameter 1.02 cm), two vertices, sketch arcs and circles,
and resolved an edge and a vertex in an occurrence. The inspected occurrence had
zero translation; this does not validate transformed or nested occurrences. The
document's modified flag was false both before and after. At that stage there had been no live
attribute write, save/reopen test or Windows test. A direct native renderer smoke
test created and deleted groups for distance, circular edge length, radius and
cylindrical diameter; the group count returned to zero. This did not test the
interactive command or establish visual quality. Fusion marked the open design
modified, and it was not saved. Attempts to enable the add-in through the manager
did not produce registered commands; the cause had not been established at that stage.

## Stability candidate, 2026-11-13

Commands are now registered. The candidate stores definitions and visibility in
design attributes and implements deferred geometry updates and startup/open
restoration. Earlier direct-handler tests establish handler behavior, not event
delivery.

A historical Python loading/API Save As path reproduced an orphan annotation with
zero API groups. That result must not be attributed to the current managed GUI
save path. The latest managed macOS GUI run (`f090654`) confirmed actual Save and
Save As cleanup, cancellation preserving state, and no dimensions after stopping
Mesora and reopening the checked fixture. Editing and saving its circle without
Mesora also reopened without dimensions. Starting Mesora restored references,
hidden-row settings, offsets and the updated edge length. GUI eye settings and visibility metadata
Undo/Redo passed on the synthetic fixture. Graphics Undo failed: Undo revived a
group missing from State, then deferred rendering added a duplicate (two actual
groups, one tracked). Cleanup correction and native retesting are required. Copy isolation and API save paths under
the managed lifecycle remain to be accepted.

Event evidence came from an independent development observer run as a managed
Fusion add-in: its custom callback and documentSaving/documentSaved callbacks were
observed. An observer imported directly through MCP did not receive callbacks;
that absence is not evidence of absent managed product events. The observer is
development tooling and is excluded from the shipped ZIP.

The parametric update scenario was interrupted by an unresponsive Fusion session
after CUA accessibility inspection of Change Parameters. The sampled main thread
showed an AX/Qt accessibility and signal-handler stack, without Python/Mesora
frames; causality is unestablished. No force termination was used with an unsaved
user document open; manual recovery was requested. This is INCONCLUSIVE, not a
passed update or restart test. See [native evidence](validation/stability-native-2026-11-13.ru.md)
and [observer/recovery notes](validation/observer-and-ax-recovery-2026-11-13.ru.md).
Stable publication remains withheld pending Undo graphics cleanup/retesting,
parametric changes, current Drawing,
full Fusion restart, Windows and remaining save/recovery acceptance.
