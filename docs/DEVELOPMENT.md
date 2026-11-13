# Mesora development

[Русская версия](DEVELOPMENT.ru.md)

`Mesora/Mesora.py` contains the Fusion command and event lifecycle; `Mesora/renderer.py` handles graphics, and `Mesora/dimensions/` contains measurement and layout logic. The top-level `dimensions/` directory is retained as historical offline code; the shipped package is `Mesora/`.

## Offline checks and package

```sh
python3 scripts/check_project.py
python3 -m unittest discover -s tests -v
python3 scripts/build.py --version 1.0.0
```

The builder writes a deterministic ZIP and SHA-256 in `dist/`. The manifest version in the archive is stamped without changing the checkout. CI checks Linux, macOS and Windows; it does not run Fusion.

## Candidate status and persistence

The current source is an experimental validation candidate, not an accepted stable
release. Explicit command commits store references and settings in design
attributes through `dimensions/runtime_persistence.py`; values are recalculated.
Schema v2 supports all current measurement types and reads schema v1. Unknown,
corrupted or future data must not be silently overwritten. Automatic model updates
use `commandTerminated` and a deferred custom event. Loading on document open and
startup requests a restore; activation resumes an existing request and saving
clears it. Managed macOS GUI testing confirmed startup/reopen restoration,
visibility application, Save/Save As cleanup and Save As cancellation. Undo/Redo
restored visibility metadata, but graphics Undo failed: a revived untracked group
plus deferred rendering produced two actual groups while State tracked one.
Cleanup correction and native retesting remain required.
The checked model reopened without dimensions while Mesora was stopped, remained
editable/savable, and restored current measurements when Mesora started.

Earlier orphan findings came from a different Python loading/API path and do not
establish a failure of the current managed GUI save path. Separately rerun API
Save/Save As with managed startup. Manual **Refresh Dimensions** after save remains
a workaround, and full save/recovery acceptance is incomplete.

For independent event evidence, run the development observer through Fusion's
managed add-in lifecycle, using `scripts/prepare_native_observer.py`. A direct
MCP import did not deliver observer callbacks and cannot establish their absence
in the managed product. Neither observer script is part of the shipped add-in.

Parametric acceptance was interrupted during CUA accessibility inspection of
Change Parameters; the observed AX/Qt stack does not establish Mesora causality.
Manual recovery was requested without force terminating an unsaved user document.
This scenario remains inconclusive. Stable publication is withheld pending
Undo graphics cleanup/retesting, parametric changes, latest-candidate Drawing, full Fusion restart, Windows and
remaining save/recovery gates. See the
[native report](validation/stability-native-2026-11-13.ru.md),
[observer/recovery notes](validation/observer-and-ax-recovery-2026-11-13.ru.md) and
[CJM and acceptance traceability](validation/stable-release-cjm-2026-11-13.ru.md).

## Native acceptance

For the Drawing save-loop regression and row/global visibility controls, follow the
checks in [Visibility and Drawing](visibility-and-drawing.md).

Use disposable designs. Check installation and command lifecycle, picking and cancellation, measurement types, units and camera movement, transformed and nested occurrences, and multiple documents. Test save, Save As, cancellation, failed save, close and reopen in both macOS and Windows, including a full Fusion restart. For each save path, stop the add-in and inspect reopened files visually as well as checking group counts. Acceptance of all CustomGraphics save/reopen paths is **not complete**; do not save valuable designs while the add-in is running. See [Fusion safety notes](fusion-safety.md).

Release automation and immutable tags follow [release policy](../.github/RELEASE_POLICY.md). Mesora is distributed under PolyForm Noncommercial 1.0.0; commercial use outside its permitted purposes requires a separate agreement.
