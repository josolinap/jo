Version: 6.5.0

## Changelog

### v6.5.0 - 2026-03-25

**Breaking changes:**
- None

**New features:**
- None

**Fixes:**
- None

**Technical improvements:**
- Vault refactoring: split intelligent_vault.py (1616 lines) into three focused modules
  * vault_engine.py (539 lines): Core graph engine
  * vault_improvements.py (664 lines): Auto-fixing and guardrails
  * vault_search.py (445 lines): Semantic search
- Improved maintainability and adherence to Principle 5 (Minimalism)
- All 23 vault tests pass; backward compatibility maintained

**Documentation:**
- None

*(Keep existing changelog entries below)*