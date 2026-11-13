<h1 align="center">Mesora for Autodesk Fusion</h1>
<p align="center"><strong>Informational dimensions, in the model.</strong><br>Measure geometry, save your measurement definitions, and control each dimension's visibility.</p>

<p align="center"><a href="https://github.com/4FusionLab/Mesora/releases"><strong>Download</strong></a> · <a href="README.ru.md">Русский</a> · <a href="https://github.com/4FusionLab/Mesora/issues">Report a problem</a></p>

## Measure in context

Open **Design → Solid → Inspect → Mesora — Add Dimension**, select geometry, and build a table of measurements. Edit a row's geometry, choose a compatible type, adjust its placement offset, or remove it. **OK** saves the definitions and visibility settings in the design; **Cancel** discards the draft.

Depending on the selected geometry, the table offers **Distance**, **Angle**, **Edge Length**, **Radius**, **Diameter**, **Area**, or **Perimeter**. Distance and angle use two compatible objects; the other types use one supported object. Values are recalculated from the current geometry after model commands.

Each row has an eye button. The eye beside **+**, **−** and the trash button hides or shows the whole set while preserving individual settings. Mesora spaces labels apart when dimensions are added or edited. Rotating or zooming keeps their positions and leader lines fixed in the model; only text orientation changes for readability. Use **Refresh Dimensions** to arrange labels for a new view.

## Save and return

Definitions, geometry references, offsets and visibility settings are stored with the model. Saving clears the displayed graphics so they do not become part of the saved model. After saving, open Mesora or use **Refresh Dimensions** to display them again. Opening the document or starting Mesora restores the saved set.

Without Mesora running, the model remains editable and the dimensions are not displayed. The measurements are informational; they do not create driving constraints. See [visibility, saving and Drawing](docs/visibility-and-drawing.md).

## Install

1. Download the ZIP from [GitHub Releases](https://github.com/4FusionLab/Mesora/releases) and extract it to a permanent folder.
2. In Fusion, open **Utilities → Scripts and Add-Ins → Add-Ins**. Use **+ → Script or add-in from device** and select the `Mesora` folder containing `Mesora.py` and `Mesora.manifest`.
3. Select **Mesora → Run** and enable **Run on Startup**.
4. Open a design and use **Design → Solid → Inspect → Mesora — Add Dimension**.

Keep the extracted folder in place while Fusion uses it. No separate Python installation is needed for the release archive.

## Compatibility

Native macOS acceptance covered measurement types and real selection/type changes, visibility, Undo/Redo, model updates, saving and reopening, Save As, Drawing transition, normal Fusion restart, operation without the add-in, and installation from the package ZIP. The reproduced label-overlap and orbit-jump cases passed retesting. See the [acceptance evidence](docs/validation/stability-native-2026-11-13.ru.md).

The manifest supports Windows and macOS. **Windows Fusion has not been natively tested.** A completed production drawing and every cloud-save failure/recovery path are outside the accepted scope; the detailed [coverage notes](docs/fusion-safety.md) distinguish those limits from verified behavior.

## Development and support

The add-in source is in `Mesora/`. Offline checks:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_project.py
```

[Development and packaging](docs/DEVELOPMENT.md) · [Contributing](CONTRIBUTING.md) · [Report a problem](https://github.com/4FusionLab/Mesora/issues)

Mesora is available under the [PolyForm Noncommercial License 1.0.0](LICENSE). Commercial use outside its permitted purposes requires a separate agreement with the copyright holder; contact 4FusionLab.

Mesora is an independent [4FusionLab](https://github.com/4FusionLab) project and is not affiliated with or endorsed by Autodesk.
