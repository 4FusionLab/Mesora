# Contributing to 4FusionLab add-ins

[Русская версия](CONTRIBUTING.ru.md)

Welcome! Keep contributions focused, testable, and safe to run in Autodesk Fusion.

- Discuss breaking CAD/UX changes before implementing.
- Prefer one concise PR per logical change and Conventional Commits (`feat:`, `fix:`, `perf:`, `docs:`, `refactor:`).
- Keep domain logic independent of the Autodesk runtime, with meaningful offline tests.
- Do not commit customer CAD data, credentials, keys or absolute user paths.
- Run `python -m unittest discover -s tests -v` and `python scripts/build.py --version 0.1.0` locally; CI validates three operating systems.
- Distinguish offline test results from actual Fusion CAD acceptance.
- Update both README language versions when user-facing behavior changes.
- Runtime changes merged to `main` publish automatically only after green CI; do not create release tags yourself.

See [development guide](docs/DEVELOPMENT.md) for the complete contract.

