<h1 align="center">Mesora for Autodesk Fusion</h1>
<p align="center"><strong>Informational dimensions, in the model.</strong><br>Measure supported geometry and keep a table of 3D dimensions for the current session.</p>

<p align="center"><a href="https://github.com/4FusionLab/Mesora/releases/tag/v1.0.0"><strong>Download experimental 1.0.0</strong></a> · <a href="README.ru.md">Русский</a> · <a href="https://github.com/4FusionLab/Mesora/issues">Report a problem</a></p>

> **Experimental: use disposable documents only.** Save and reopen safety has not been established. Do not save documents while this build is enabled: Fusion CustomGraphics may leave an inaccessible persistent artifact even after graphics are removed. The implemented remove-before-save and restore-after-save behavior is unverified and is not a safety guarantee. See [safety research](docs/fusion-safety.md).

## Measure in context

Open **Design → Solid → Inspect → Mesora — Add Dimension**, select geometry, and build a table of measurements. Rows have session IDs such as `m1`; edit their geometry, choose a compatible measurement type, adjust the placement offset, or remove rows. Confirm the command to display the dimensions. The Mesora menu also provides visibility, refresh, and removal commands.

Depending on the selected geometry, the table offers **Distance**, **Angle**, **Edge Length**, **Radius**, **Diameter**, **Area**, or **Perimeter**. Distance and angle use two compatible objects; other types use one supported object. The choices depend on the selection, and unsupported combinations are rejected.

## Install and try

1. Download `Mesora-1.0.0.zip` from the [experimental release](https://github.com/4FusionLab/Mesora/releases/tag/v1.0.0) and extract it to a permanent folder.
2. In Fusion, open **Utilities → Scripts and Add-Ins → Add-Ins**. Use **+ → Script or add-in from device** and select the `Mesora` folder containing `Mesora.py` and `Mesora.manifest`.
3. Select **Mesora → Run**. If desired, enable **Run on Startup**; observe the safety warning above whenever the add-in is enabled.
4. Open a disposable design and use **Design → Solid → Inspect → Mesora — Add Dimension**. Select one or two objects for a row, review the compatible type and preview, then confirm.

Keep the extracted folder in place while Fusion uses it. No separate Python installation is needed for the release archive.

## Status and limits

- Measurements are **session-only**. Definitions are kept in memory, not intentionally written to `Design.attributes`; closing the document or stopping the add-in loses them.
- Creating or deleting CustomGraphics can mark a document as modified. Save/reopen behavior remains unverified; the warning above applies even when graphics have been cleared.
- Read-only measurements and direct graphic creation/deletion were tried in macOS Fusion. The command was exercised on a temporary macOS design using programmatic selection events and UI confirmation. Physical picking, broader event lifecycle, appearance and rotation, transformed or nested occurrences, and Windows remain to be validated. Offline tests do not establish native Fusion acceptance.
- The manifest declares Windows and macOS; that declaration is not evidence of native testing on both systems.

## Development and support

The add-in source is in `Mesora/`. To run offline tests or build a local archive:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_project.py
python3 scripts/build.py --version 1.0.0
```

[Safety and test notes](docs/fusion-safety.md) · [Development](docs/DEVELOPMENT.md) · [Contributing](CONTRIBUTING.md) · [Report a problem](https://github.com/4FusionLab/Mesora/issues)

Mesora is available under the [PolyForm Noncommercial License 1.0.0](LICENSE). Commercial use outside its permitted purposes requires a separate agreement with the copyright holder; contact 4FusionLab.

Mesora is an independent [4FusionLab](https://github.com/4FusionLab) project and is not affiliated with or endorsed by Autodesk.
