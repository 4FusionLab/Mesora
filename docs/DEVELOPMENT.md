# 4FusionLab add-in development

## Architecture

- `<Product>/<Product>.py`: Autodesk Fusion entry point, command and event lifecycle. This module imports `adsk`, so **do not import it in offline unit tests**.
- `<Product>/config.py`: stable command identifier and product metadata. Generated once.
- `<Product>/core.py`: plain Python, independently testable calculation and domain logic.
- `<Product>/<Product>.manifest`: Autodesk Fusion add-in metadata; the release builder stamps the computed version into the ZIP without rewriting the checkout.
- `scripts/build.py`: deterministic archive, SHA-256, secret/symlink guardrails.
- `.github/release-paths.txt`: reviewed allowlist of files that affect the shipped runtime.

## Workflow for a new product

1. Create a new repository from the GitHub template. The source template deliberately cannot be published.
2. Run **Actions → Initialize add-in** on `main`. This workflow is unavailable on the template itself and deletes itself from the generated project. It creates the project-specific manifest UUID and command ID.
3. The initializer pushes a generated commit using GitHub's built-in token; that push does **not** automatically trigger other push workflows. It explicitly dispatches a read-only CI workflow to validate the generated project, without making a release.
4. If local initialization was used instead, run `python scripts/init_addin.py --name MyAddin --repo 4FusionLab/MyAddin`, `python scripts/check_project.py` and tests, then push to your repository.
5. Implement the command. Keep all Fusion API calls on the appropriate Fusion execution thread and separate them from pure computation. Add test coverage and native Fusion acceptance evidence.
6. When shipped runtime files change, push to `main` or merge a PR. Green CI and an eligible runtime path automatically publish a versioned stable GitHub Release.
7. Do not add direct releases for docs, tests, CI, or policy-only changes. Do not create tags manually.

## Local validation

```bash
python scripts/check_project.py
python -m unittest discover -s tests -v
python scripts/build.py --version 0.1.0
```

An uninitialized source template may be tested using `--allow-template` but **cannot** publish; new products must not use that flag in release scripts.

## Install in Fusion

1. Download the ZIP from the product's GitHub Releases, or build it locally.
2. Extract it so the Fusion API AddIns folder contains `<Product>/<Product>.manifest` and `<Product>/<Product>.py`. Do not install the ZIP as a double-nested directory.
3. Open Autodesk Fusion, go to **Utilities → Add-Ins** and start the add-in. Check the add-in entry in the SOLID **ADD-INS** panel.
4. Run the starter command. It should show a message and **must not modify the design**. Disable the add-in and verify the command/control disappears.
5. Repeat on macOS and Windows for OS-specific dependencies/geometry/UI, noting differences. Do not claim that CI has run native Fusion acceptance.

## Native acceptance checklist

- Install, start, stop and restart without duplicated controls or leaking handlers.
- Command can be opened, cancelled and executed; result is correct and safe.
- Active document changes, missing documents and model deletion do not cause unsafe writes.
- Test parametric and direct modeling as applicable; verify timeline updates, units, undo and redo.
- CAD API interactions, UI event order, preview lifecycle and performance are checked inside Fusion.
- Release ZIP has a valid manifest, matching GitVersion-derived version and checksum.
- Review operating system/native dependency portability and any required signing.
- Keep EN/RU documentation accurate and publish real limitations.

## Release policy

The shared Actions are pinned to 4FusionLab/.github commit `ad9d60ba4aabc494b4f2c85d6c566a50ca423751`. The org's [RELEASE_PLATFORM.md](https://github.com/4FusionLab/.github/blob/main/RELEASE_PLATFORM.md) is authoritative. Product code changes are eligible when their filenames match `.github/release-paths.txt`; all required cross-platform tests and ZIP validation must pass before publication.

After a project is created, choose and review its distribution/license strategy. The template does not impose a default project license. Before distributing code or binaries, explicitly choose a license compatible with your product strategy (for example, GPL-3.0 for reciprocal open source, MIT for permissive open source, or an appropriate proprietary license for commercial distribution). See [licensing guide](LICENSING.md).

