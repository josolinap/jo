# Security Audit Skill (inspired by cloudflare/security-audit-skill)

## Purpose

Run a multi-phase security audit of the Jo codebase with independently verified,
machine-readable findings. Use before any release or when touching auth, secrets,
network, or shell execution paths.

## Phases

### Phase 1 — Secret & Credential Scan
- Search for hardcoded tokens, API keys, passwords in source and config.
- Check `.env.example`, workflows, and committed data files.
- Verify no secrets in `memory/`, `vault/`, or logs.

### Phase 2 — Input & Injection Review
- Audit `run_shell`, `code_edit`, `repo_write_commit` and any subprocess calls
  for command injection and path traversal.
- Verify `safe_relpath` usage in `ToolContext.repo_path` / `drive_path`.
- Check FastAPI endpoints in `server/app.py` for unvalidated input.

### Phase 3 — Dependency & Supply Chain
- Review `requirements.txt` for unpinned or vulnerable packages.
- Check GitHub Actions workflows for unpinned third-party actions and
  excessive permissions (`contents: write`, `pages: write`).

### Phase 4 — Auth & Access Control
- Verify tunnel/backend endpoints require appropriate tokens.
- Check that `JO_WEB_USE_AGENT` and debug endpoints are gated.

### Phase 5 — Reporting
- Produce a machine-readable JSON findings list:
  `{"id", "phase", "severity", "file", "line", "description", "recommendation"}`.
- Severity levels: critical, high, medium, low, info.
- Only mark a finding "verified" after reproducing or confirming via code read.

## Output

Write findings to `vault/journal/security_audit_<date>.md` and a JSON file
under `memory/` if available. Summarize counts by severity.
