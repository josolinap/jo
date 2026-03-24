---
title: "Principle 7: Versioning and Releases"
created: 2026-03-23T11:00:00.000000+00:00
modified: 2026-03-23T11:00:00.000000+00:00
type: concept
status: active
tags: [constitution, versioning, releases, meta]
---

# Principle 7: Versioning and Releases

Every significant change increments the version (semver).

## Version Management

- VERSION file in the project root.
- README contains changelog (limit: 2 major, 5 minor, 5 patch).
- Before commit: update VERSION and changelog.
- MAJOR — breaking changes to philosophy/architecture.
- MINOR — new capabilities.
- PATCH — fixes, minor improvements.
- Combine related changes into a single release.

## Release Invariant

Three version sources are **always in sync**:
`VERSION` == latest git tag == version in `README.md`.
Discrepancy is a bug that must be fixed immediately.

## Git Tags

- Every release is accompanied by an **annotated** git tag: `v{VERSION}`.
- Format: `git tag -a v{VERSION} -m "v{VERSION}: description"`.
- Tag is pushed to remote: `git push origin v{VERSION}`.
- Version in commit messages after a release cannot be lower than the current VERSION.

## GitHub Releases

- Every MAJOR or MINOR release creates a GitHub Release.
- PATCH releases: GitHub Release is optional.

Related: [[bible_md]], [[evolution_cycle]], [[jo_system_neural_hub]]
