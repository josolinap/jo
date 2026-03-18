# Ouroboros — common development commands
# Usage: make test, make lint, make health

.PHONY: test lint health verify clean

# Run smoke tests (fast, no external deps needed at runtime)
test:
	python3 -m pytest tests/ -q --tb=short

# Run smoke tests with verbose output
test-v:
	python3 -m pytest tests/ -v --tb=long

# Run codebase health check (requires ouroboros importable)
health:
	python3 -c "from ouroboros.review import compute_complexity_metrics; \
		import pathlib, json; \
		m = compute_complexity_metrics(pathlib.Path('.')); \
		print(json.dumps(m, indent=2, default=str))"

# Verify code compiles and tests pass before commit
verify:
	@echo "Verifying code..."
	@python3 -m py_compile ouroboros/*.py 2>/dev/null && echo "OK: All Ouroboros modules compile" || { echo "FAIL: Syntax errors found"; exit 1; }
	@python3 -m py_compile supervisor/*.py 2>/dev/null && echo "OK: All Supervisor modules compile" || { echo "FAIL: Syntax errors found"; exit 1; }
	@python3 -m py_compile ouroboros/tools/*.py 2>/dev/null && echo "OK: All Tools modules compile" || { echo "FAIL: Syntax errors found"; exit 1; }
	@echo "Verifying version sync..."
	@python3 -c "from pathlib import Path; v=Path('VERSION').read().strip(); r=Path('README.md').read_text(); assert v in r, f'Version mismatch: VERSION={v} not in README'; assert v == Path('pyproject.toml').read_text().split('version = ')[1].split('\\n')[0].strip('\"'), f'Version mismatch: VERSION={v} != pyproject.toml'; print(f'OK: Version sync ({v})')"
	@echo "Running tests..."
	@python3 -m pytest tests/ -q --tb=short
	@echo "Verification complete."

# Clean Python cache files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
