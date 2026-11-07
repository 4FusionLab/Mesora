# Mesora

Mesora is an experimental Autodesk Fusion add-in for informational 3D dimensions.
The experimental build is available under Design → Solid → Inspect → Mesora — Add
Dimension. Select geometry repeatedly to build a table of measurements. Two point
selections form one distance; each other supported selection forms its own row.
Each row has a session ID and a choice of compatible measurement types. Select a
row and use Remove selected to delete it; Cancel point clears an unfinished pair.
The same menu provides show/hide, refresh and clear. Use disposable documents while testing.

The planned MVP keeps dimension definitions in memory only. Nothing is intentionally
written to `Design.attributes`; closing the document or stopping the add-in loses the
session dimensions. CustomGraphics can mark a document modified even when groups are
deleted. Fusion may serialize CustomGraphics into an inaccessible persistent artifact;
removing groups in `documentSaving` and restoring after `documentSaved` is implemented
but has not been validated by save/reopen testing. It is not a safety guarantee. Use
only disposable documents, and do not save them with the experimental build enabled.

The source package is in `Mesora/`. Unit tests run with:

```sh
python3 -m unittest discover -s tests -v
```

Native read-only measurement and direct render/create/delete calls have been tried on
macOS Fusion. The command was exercised on a temporary macOS design using programmatic Fusion
selection events and UI confirmation. Physical picking, broader event lifecycle, safe
save/reopen, transformed occurrences, Windows, and appearance/rotation acceptance remain open.
See [research and test notes](docs/fusion-safety.md).

## Installation

Build `python3 scripts/build.py --version 1.0.0`, extract the ZIP into the Fusion AddIns directory so that `Mesora/Mesora.manifest` and `Mesora/Mesora.py` are directly inside the extracted folder, then start Mesora from Fusion's Add-Ins dialog. The ZIP is also intended for GitHub Releases when published. Restarting or stopping the add-in clears session measurements.

No distribution license has yet been selected. See [licensing](docs/LICENSING.md).
