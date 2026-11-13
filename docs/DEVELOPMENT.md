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
use `commandTerminated` and a deferred custom event; native acceptance remains
incomplete. Definition loading on document open and add-in startup now requests
an event-gated deferred restore; document activation only resumes an existing
request, and saving clears it. Actual native callback delivery and automatic
rendering after managed add-in restart/reopen remain unconfirmed. See the latest
rerun in the native report below; full Fusion restart acceptance is still pending.
The independent `scripts/native_acceptance_observer.py` is development tooling,
not part of the shipped add-in.

A macOS API Save As test reproduced a visible persistent CustomGraphics annotation
after stopping Mesora and reopening the file, even with a zero API group count.
The UI save cleanup/manual **Refresh Dimensions** workaround does not establish
normal save/reopen safety. The stable release is withheld pending resolution,
Windows native acceptance and full restart gates. See the
[native report](validation/stability-native-2026-11-13.ru.md) and
[CJM and acceptance traceability](validation/stable-release-cjm-2026-11-13.ru.md).

## Native acceptance

For the Drawing save-loop regression and row/global visibility controls, follow the
checks in [Visibility and Drawing](visibility-and-drawing.md).

Use disposable designs. Check installation and command lifecycle, picking and cancellation, measurement types, units and camera movement, transformed and nested occurrences, and multiple documents. Test save, Save As, cancellation, failed save, close and reopen in both macOS and Windows, including a full Fusion restart. For each save path, stop the add-in and inspect reopened files visually as well as checking group counts. CustomGraphics save/reopen safety is **not established**, and an inaccessible saved annotation has been reproduced; do not save valuable designs while the add-in is running. See [Fusion safety notes](fusion-safety.md).

Release automation and immutable tags follow [release policy](../.github/RELEASE_POLICY.md). Mesora is distributed under PolyForm Noncommercial 1.0.0; commercial use outside its permitted purposes requires a separate agreement.
