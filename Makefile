# Ouroboros — common development commands
# Usage: make test, make lint, make health

.PHONY: test lint health verify clean vault vault-verify vault-graph vault-gaps evolve-status identity-update scratchpad-update system-info

# Run smoke tests (fast, no external deps needed at runtime)
test:
	python3 -m pytest tests/ -q --tb=short

# Run smoke tests with verbose output
test-v:
	python3 -m pytest tests/ -v --tb=long

# Run codebase health check (requires ouroboros importable)
health:
	python3 -c "from ouroboros.review import collect_sections, compute_complexity_metrics; \
		import pathlib, json; \
		sections, stats = collect_sections(pathlib.Path('.'), pathlib.Path('/home/runner/.jo_data')); \
		m = compute_complexity_metrics(sections); \
		print(json.dumps(m, indent=2, default=str))"

# Verify code compiles and tests pass before commit
verify:
	@echo "Verifying code..."
	@python3 -m py_compile ouroboros/*.py 2>/dev/null && echo "OK: All Ouroboros modules compile" || { echo "FAIL: Syntax errors found"; exit 1; }
	@python3 -m py_compile supervisor/*.py 2>/dev/null && echo "OK: All Supervisor modules compile" || { echo "FAIL: Syntax errors found"; exit 1; }
	@python3 -m py_compile ouroboros/tools/*.py 2>/dev/null && echo "OK: All Tools modules compile" || { echo "FAIL: Syntax errors found"; exit 1; }
	@echo "Verifying version sync..."
	@python3 -c "from pathlib import Path; v=Path('VERSION').read_text().strip(); r=Path('README.md').read_text(); assert v in r, f'Version mismatch: VERSION={v} not in README'; assert v == Path('pyproject.toml').read_text().split('version = ')[1].split('\\n')[0].strip('\"'), f'Version mismatch: VERSION={v} != pyproject.toml'; print(f'OK: Version sync ({v})')"
	@echo "Running tests..."
	@python3 -m pytest tests/ -q --tb=short
	@echo "Verification complete."

# Clean Python cache files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# Vault operations
vault:
	python3 -c "from ouroboros.vault_manager import VaultManager; \
		from pathlib import Path; \
		v = VaultManager(Path('vault'), Path('vault')); \
		notes = v.list_notes(); \
		print(f'Vault: {len(notes)} notes'); \
		for n in notes[:10]: print(f'  - {n}')"

vault-verify:
	python3 -c "from ouroboros.vault_manager import VaultManager; \
		from pathlib import Path; \
		v = VaultManager(Path('vault'), Path('vault')); \
		results = v.verify_integrity(); \
		print(f'Integrity check: {results['total_notes']} notes, {len(results['orphaned'])} orphaned, {len(results['duplicate_content'])} duplicates'); \
		if results['orphaned']: print('Orphaned:', results['orphaned']); \
		if results['duplicate_content']: print('Duplicates:', results['duplicate_content'])"

vault-graph:
	python3 -c "from ouroboros.vault_manager import VaultManager; \
		from pathlib import Path; \
		v = VaultManager(Path('vault'), Path('vault')); \
		graph = v.get_knowledge_graph(); \
		print(f'Graph: {graph['node_count']} nodes, {graph['edge_count']} edges'); \
		print('Top connected nodes:'); \
		for n in sorted(graph['edges'], key=lambda x: x['count'], reverse=True)[:5]: print(f'  {n}')"

vault-gaps:
	python3 -c "from ouroboros.vault_manager import VaultManager; \
		from pathlib import Path; \
		v = VaultManager(Path('vault'), Path('vault')); \
		gaps = v.find_gaps(); \
		print(f'Gaps: {len(gaps)} orphaned nodes'); \
		if gaps: print('Orphaned notes:', gaps[:10])"

# Evolution status
evolve-status:
	@echo "Evolution Cycle Status"
	@echo "--------------------"
	@python3 -c "from pathlib import Path; v=Path('VERSION').read_text().strip(); print(f'Version: {v}')"
	@git log --oneline -5
	@echo ""
	@echo "Recent evolution-related vault notes:"
	@find vault -name '*evolution*.md' -o -name '*refactor*.md' -o -name '*modularization*.md' | head -5 | xargs -I{} basename {}

# Identity and scratchpad management
identity-update:
	python3 -c "from ouroboros.memory import get_identity; \
		identity = get_identity(); \
		print(f'Identity length: {len(identity)} chars'); \
		print('Last 500 chars:'); \
		print(identity[-500:])"

scratchpad-update:
	python3 -c "from pathlib import Path; \
		s = Path('memory/scratchpad.md').read_text(); \
		print(f'Scratchpad: {len(s)} chars, {s.count(chr(10))} lines')"

# System information
system-info:
	@echo "Jo System Information"
	@echo "--------------------"
	@python3 --version
	@echo ""
	@echo "Repository status:"
	@grep -E 'branch|ahead|behind' <<< "$$(git status)" || true
	@echo ""
	@echo "Protected files (read-only):"
	@cat .jo_protected | grep -v '^#' | grep -v '^$$'
	@echo ""
	@echo "Tool registry:"
	@python3 -c "from ouroboros.tools.registry import ToolRegistry; import pathlib; tr = ToolRegistry(pathlib.Path('.')); print(f'{len(tr.schemas())} tools available')"
	@echo ""
	@echo "Vault status:"
	@find vault -name '*.md' | wc -l | xargs echo 'Notes:'
	@echo ""
	@echo "Memory files:"
	@ls -lh memory/ 2>/dev/null || echo "  (none)"
