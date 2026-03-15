# Changelog

All notable changes to Jo will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Task-specific prompts in `.pi/prompts/` (issue.md, pr.md, changelog.md)
- Git rules for parallel agents in AGENTS.md
- File locking for identity.md and scratchpad.md

### Changed
- Name: Ouroboros → Jo
- Storage: Google Drive → ~/.ouroboros (local filesystem)
- Workflow: triggers from dev branch instead of main
- Concurrency control to prevent multiple instances

### Fixed
- Race conditions in memory access (identity.md, scratchpad.md)
- Multiple GitHub Actions instances running

### Removed
- colab_bootstrap_shim.py (deprecated Colab support)

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
