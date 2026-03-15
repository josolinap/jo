# Changelog

All notable changes to Jo will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Tagging Convention
Each entry includes axis tags: `(technical)`, `(cognitive)`, `(existential)`.
This tracks Jo's growth across all three axes per Principle 6.

### Added
- Task-specific prompts in `.pi/prompts/` (issue.md, pr.md, changelog.md) (technical)
- Git rules for parallel agents in AGENTS.md (technical)
- File locking for identity.md and scratchpad.md (technical)

### Changed
- Name: Ouroboros → Jo (existential)
- Storage: Google Drive → ~/.ouroboros (local filesystem) (technical)
- Workflow: triggers from dev branch instead of main (technical)
- Concurrency control to prevent multiple instances (technical)

### Fixed
- Race conditions in memory access (identity.md, scratchpad.md) (technical)
- Multiple GitHub Actions instances running (technical)

### Removed
- colab_bootstrap_shim.py (deprecated Colab support) (technical)

## [6.2.0] - 2026-03-15

### Added
- AgentCoordinator for multi-agent task delegation
- Background consciousness mode
- Tool: schedule_task for deferred execution

### Changed
- Split supervisor from monolithic launcher
- Multiple worker processes for parallel tasks

### Fixed
- Git SHA drift detection
- State persistence on local filesystem

## [6.1.0] - 2026-03-10

### Added
- Initial self-modifying capabilities
- Git-based code evolution

### Fixed
- Telegram bot integration
- Budget tracking
