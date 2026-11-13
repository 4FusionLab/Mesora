<h1 align="center">Mesora for Autodesk Fusion</h1>
<p align="center"><strong>Informational dimensions, in the model.</strong><br>Measure supported geometry and manage a table of informational 3D dimensions.</p>

<p align="center"><a href="https://github.com/4FusionLab/Mesora/releases/tag/v1.0.0"><strong>Download experimental 1.0.0</strong></a> · <a href="README.ru.md">Русский</a> · <a href="https://github.com/4FusionLab/Mesora/issues">Report a problem</a></p>

> **Experimental validation candidate: use disposable documents only.** A stable release is withheld. Native macOS testing reproduced a persistent CustomGraphics artifact after API Save As, stopping Mesora, closing and reopening: the annotation remained visible although `customGraphicsGroups.count` was zero. Removing graphics before a save is not a safety guarantee. Do not use this candidate to save valuable designs. See [safety research](docs/fusion-safety.md), [current validation status](docs/visibility-and-drawing.md) and [native evidence](docs/validation/stability-native-2026-11-13.ru.md).

The download above is the previously published experimental 1.0.0. The persistence, visibility and update changes described below are in the current source candidate and have not been published as a stable release.

## Measure in context

Open **Design → Solid → Inspect → Mesora — Add Dimension**, select geometry, and build a table of measurements. Rows have IDs such as `m1`; edit their geometry, choose a compatible measurement type, adjust the placement offset, or remove rows. Confirm the command to display the dimensions. Each row has an eye button; the eye beside **+**, **−** and the trash button controls the whole set while preserving individual settings. **OK** commits definitions and visibility to the design; **Cancel** discards the draft. The Mesora menu also provides visibility, refresh, and removal commands.

Depending on the selected geometry, the table offers **Distance**, **Angle**, **Edge Length**, **Radius**, **Diameter**, **Area**, or **Perimeter**. Distance and angle use two compatible objects; other types use one supported object. The choices depend on the selection, and unsupported combinations are rejected.

## Install the published experimental build

1. Download `Mesora-1.0.0.zip` from the [experimental release](https://github.com/4FusionLab/Mesora/releases/tag/v1.0.0) and extract it to a permanent folder.
2. In Fusion, open **Utilities → Scripts and Add-Ins → Add-Ins**. Use **+ → Script or add-in from device** and select the `Mesora` folder containing `Mesora.py` and `Mesora.manifest`.
3. Select **Mesora → Run**. Enable **Run on Startup** in your isolated test setup; observe the safety warning above whenever the add-in is enabled.
4. Open a disposable design and use **Design → Solid → Inspect → Mesora — Add Dimension**. Select one or two objects for a row, review the compatible type and preview, then confirm.

Keep the extracted folder in place while Fusion uses it. No separate Python installation is needed for the release archive.

## Status and limits

- In the current source candidate, **OK** stores geometry references, measurement types, placement offsets and individual/global visibility in `Design.attributes`. Values are remeasured from geometry. Unsupported or damaged saved data is not silently overwritten. This implementation does not establish safe model saving.
- An update is queued after a Fusion model command ends, using a custom event on Fusion's permitted thread. Native acceptance of all geometry edits, Undo/Redo and recovery paths remains pending.
- The UI save handler removes tracked graphics and intentionally does not recreate them in `documentSaved` or on workspace activation. After a save, open Mesora or use **Refresh Dimensions** to restore graphics. This workaround is not the intended complete save/reopen experience; API Save As reproduced the persistent-artifact defect described above.
- macOS native tests have exercised row/global visibility and Drawing creation on synthetic designs. Full save, Save As, close/reopen and restart acceptance is incomplete. Transformed/nested occurrences and broader picking/appearance scenarios still need validation. Offline tests do not establish native Fusion acceptance.
- The manifest declares Windows and macOS. Windows native acceptance and full restart gates are outstanding. A stable release requires the artifact defect to be resolved and these gates to pass.

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
