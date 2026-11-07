# 4FusionLab Fusion add-in development contract

Read [4FusionLab shared engineering rules](https://github.com/4FusionLab/.github/blob/main/AGENTS.md) and [the release platform](https://github.com/4FusionLab/.github/blob/main/RELEASE_PLATFORM.md) first.

## Working model

- This is an Autodesk Fusion Python add-in. The initial package is `FusionAddin/`; the initializer replaces its name and generates stable IDs.
- Discuss requirements and plans in Russian. Use clear English for Fusion commands, controls, diagnostics, and stable API names. Maintain separate English and Russian README files.
- Treat the official Autodesk Fusion API documentation as the source of truth. Never invent SDK symbols; do not imply successful CAD acceptance based solely on offline CI.
- Put calculations and domain rules into `FusionAddin/core.py` or modules that **do not import adsk**. Fusion API interactions belong in adapters, event handlers and commands running in Fusion's permitted execution context.
- Design commands to be safe: validate active document, entities, units, parameters, and timeline state; use native previews where applicable. Never modify a user's CAD data during tests or without an explicit command action.
- Retain event handler instances while active; detach UI controls and command definitions in `stop(context)`. Keep identifiers stable after initial scaffolding. Avoid global state tied to stale documents.
- Add meaningful unit and offline integration tests. Test real Fusion flows on Windows/macOS separately when they matter; report what has and has not actually been verified.

## Versioning and publishing

- `python scripts/init_addin.py --name NewAddin` is a **one-time** setup; never regenerate an existing product manifest UUID or command IDs.
- Version uses GitVersion.Tool **6.8.2**, Conventional Commits and the shared pinned Actions. Direct push or PR merge into `main` triggers a release **only** for shipped paths listed in `.github/release-paths.txt`.
- All checks must pass before publish. Documentation/tests/CI edits do not publish a new release. Do not create tags manually, overwrite published ZIPs or move existing tags.
- Only the publishing job has `contents: write`. Package ZIP, embedded manifest version, checksums and release notes must agree. The ZIP must install as a Fusion Add-in folder.
- Do not commit credentials, private CAD files, signing keys, platform-generated artifacts, or user paths. Review repository licensing before public distribution.

## Commands

- Offline tests: `python -m unittest discover -s tests -v`.
- Project validator: `python scripts/check_project.py`.
- Product ZIP: `python scripts/build.py --version 0.1.0`.
- Manual CAD acceptance checklist: `docs/DEVELOPMENT.md`.
