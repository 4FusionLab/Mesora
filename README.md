# 4FusionLab · Fusion Add-in Template

[Русская версия](README.ru.md)

A reusable **Autodesk Fusion add-in starter** for 4FusionLab. It includes a working command, a Fusion manifest, offline tests, cross-platform CI, deterministic ZIP packaging and the shared 4FusionLab automatic release policy.

## Create a new add-in

1. Click **Use this template** → **Create a new repository**, preferably in the `4FusionLab` organization.
2. In the new repository open **Actions → Initialize add-in → Run workflow**. The repository name becomes the Python add-in package name; you can enter a friendly display name and description.
3. The initialization commit generates a **new manifest UUID and command ID**, renames the add-in package and prepares the bilingual project README files.
4. Develop your add-in in its package directory. Run `python -m unittest discover -s tests -v` and `python scripts/build.py --version 0.1.0` for a local verification.
5. After initialization, every push or merged PR to `main` which touches **shipped runtime files** is eligible for an automatic release, subject to green CI. Documentation and test-only changes do not publish.

If Actions cannot be enabled yet, run the initializer locally: `python scripts/init_addin.py --name MyNewAddin --display-name "My New Add-in"`, commit its changes and push.

> Never install or publish the uninitialized `FusionAddin` placeholder as a real product.

## What is shared?

- GitVersion.Tool **6.8.2** and conventional commit conventions.
- Immutable, SHA-pinned composite Actions from [4FusionLab/.github](https://github.com/4FusionLab/.github).
- CI on Linux, macOS and Windows; offline tests are distinct from real Fusion acceptance.
- ZIP and SHA-256 verification; no manually created release tags.
- Separate English and Russian documentation and `AGENTS.md` rules for coding agents.

The repository is a template, not an existing 4FusionLab product. See `docs/DEVELOPMENT.md` after scaffolding is installed.
