# Automatic release policy for generated 4FusionLab Fusion add-ins

- Trigger: direct push or merged PR to `main`, but only when shipped paths in `.github/release-paths.txt` changed. A `workflow_dispatch` or PR validation run is always read-only.
- The initializer is one-time; it generates stable Fusion UUIDs and does not publish an initial Hello World release.
- GitVersion.Tool 6.8.2 derives `MAJOR.MINOR.PATCH` from full Git history. Use Conventional Commits. CI builds the versioned ZIP and SHA-256, stamps its embedded manifest and verifies it with shared 4FusionLab Actions.
- All Linux/macOS/Windows offline tests must succeed. This does **not** prove native Fusion acceptance.
- Only the release job can write contents. It creates a previously nonexistent immutable `vMAJOR.MINOR.PATCH` tag and GitHub Release automatically. No manually pushed tags; never overwrite tags, releases, or artifacts.
- Do not publish for README, docs, tests, workflows, `AGENTS.md`, policies or GitVersion-only changes.
- Shared Actions are pinned to audited commit `ad9d60ba4aabc494b4f2c85d6c566a50ca423751` in 4FusionLab/.github. See [shared release platform](https://github.com/4FusionLab/.github/blob/main/RELEASE_PLATFORM.md).

