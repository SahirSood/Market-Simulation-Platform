# GitHub Configuration

This directory contains repository automation that should stay safe to publish.

## Workflows

- `workflows/ci.yml` runs the release-quality checks for pull requests and
  pushes to `main`.
- CI scans tracked files for secrets, runs the Python test suite, applies
  database migrations, builds the native C++ engine, validates the production
  environment contract, and builds both Docker images.

## Maintenance Notes

- Keep local editor, agent, and machine-specific settings out of this directory.
- Use placeholder credentials in workflow files; real values belong in GitHub
  Actions secrets or the deployment host's secret manager.
- When adding a new release-critical command, add it to CI and document it in
  `docs/operations/RELEASE.md`.
