# Mesora development

[Русская версия](DEVELOPMENT.ru.md)

`Mesora/Mesora.py` owns commands and events, `Mesora/renderer.py` owns graphics,
and `Mesora/dimensions/` contains measurement, persistence and layout logic. The
top-level `dimensions/` directory is historical offline code; the shipped package
is `Mesora/`.

## Checks and packaging

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_project.py
```

Build with the numeric version resolved by GitVersion 6.8.2, for example after
setting `MESORA_PACKAGE_VERSION` to that result:

```sh
python3 scripts/build.py --version "$MESORA_PACKAGE_VERSION"
```

The builder writes a deterministic ZIP and SHA-256 in `dist/` and stamps the archive
manifest without changing the checkout. Check the manifest, archive contents,
checksum and release notes together. CI checks Linux, macOS and Windows; it does
not run Fusion. The accepted runtime passed 144 offline tests and
[CI run 15](https://github.com/4FusionLab/Mesora/actions/runs/43475119273).
The 56-file package was installed and exercised in macOS Fusion.

## Runtime contracts

- Explicit commits store references, types, offsets and visibility through
  `dimensions/runtime_persistence.py`. Schema v2 reads v1; unknown, damaged and
  future payloads must not be silently overwritten. Recalculate values from geometry.
- Model commands queue updates through `commandTerminated` and a custom event.
  Opening/startup loads definitions; activation resumes an existing restore request.
  Render only in the permitted Fusion context.
- Refresh/save/stop reconcile owned graphics by their IDs, including fresh wrappers
  revived by Undo. Preserve other add-ins' groups and staged command graphics.
- Arrange captions for explicit preview, commit, model refresh and restoration.
  Camera events only orient text: do not repack captions or rebuild angular arcs.
- Saving removes graphics and clears the restore request. Do not recreate them in
  `documentSaved`; explicit Mesora/Refresh restores display after a save.
- Retain active handlers and detach command scopes on destruction. Cancel must
  restore the committed set without applying draft visibility or offsets.

## Native acceptance

The final independent review found no open Blocker or Major in the authorized
macOS release scope. Native type probing confirmed 13 actual UI events; Inspect
on the same cylindrical face reported Loop Length 339.292 mm, Area 5089.38 mm²,
Radius 27 mm and Diameter 54 mm, matching Mesora. Previous evidence also covers
Undo/Redo ownership, model update/Undo/Redo, save/reopen, Save As, Drawing transition,
normal restart, nested/transformed reference measurements and operation without
Mesora. The reproduced caption-overlap/orbit case passed user acceptance.

Keep scope precise: the parameter-change transaction test is not manual Change
Parameters UI acceptance, and the Drawing check canceled Base View placement.
Windows Fusion, real failed-cloud-save recovery and exhaustive geometry/picking
combinations remain unverified. Windows unavailability is not a separate release
blocker under the accepted macOS scope. See [coverage](fusion-safety.md),
[native evidence](validation/stability-native-2026-11-13.ru.md) and
[traceability](validation/stable-release-cjm-2026-11-13.ru.md).

For new regressions use synthetic documents. Saved acceptance fixtures were removed;
follow the user's current no-CAD-save constraint rather than creating new cloud files.
Event evidence requires an observer run as a managed Fusion add-in. Direct MCP
import did not deliver observer callbacks and cannot prove their absence in the
managed product. Development observer/driver scripts are excluded from the ZIP.

Publishing and immutable tags follow [release policy](../.github/RELEASE_POLICY.md).
Mesora uses [PolyForm Noncommercial 1.0.0](../LICENSE); commercial use outside its
permitted purposes requires a separate agreement.
