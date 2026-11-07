# Mesora development

`Mesora/Mesora.py` contains the Fusion command and event lifecycle; `Mesora/renderer.py` handles graphics, and `Mesora/dimensions/` contains measurement and layout logic. The top-level `dimensions/` directory is retained as historical offline code; the shipped package is `Mesora/`.

## Offline checks and package

```sh
python3 scripts/check_project.py
python3 -m unittest discover -s tests -v
python3 scripts/build.py --version 1.0.0
```

The builder writes a deterministic ZIP and SHA-256 in `dist/`. The manifest version in the archive is stamped without changing the checkout. CI checks Linux, macOS and Windows; it does not run Fusion.

## Native acceptance

Use disposable designs. Check installation and command lifecycle, picking and cancellation, measurement types, units and camera movement, transformed and nested occurrences, and multiple documents. Test save, Save As, cancellation, failed save, close and reopen in both macOS and Windows, including a full Fusion restart. CustomGraphics save/reopen safety is **not established**; do not save valuable designs while the add-in is running. See [Fusion safety notes](fusion-safety.md).

Release automation and immutable tags follow [release policy](../.github/RELEASE_POLICY.md). Choose and review a distribution license before distributing code or binaries; see [licensing guide](LICENSING.md).
