/critic-loop — Run the autonomous code quality loop with Arch-Neo critique

The critic-loop sends your code through quality gates (ruff, mypy, tsc, eslint, prettier)
and then to Arch-Neo for human-level code review. If anything fails, it auto-fixes and
loops until everything is clean.

Usage:
  /critic-loop                Review unstaged changes (default)
  /critic-loop --staged       Review staged changes  
  /critic-loop --install-tools  Install missing quality tools
  /critic-loop --goal         Quick check: pass/fail for /goal automation
  /critic-loop 5              Run up to 5 iterations before giving up

Flow:
  1. Auto-fix formatting/lint issues
  2. Run all detected quality gates in parallel
  3. If gates pass → send to Arch-Neo for critique
  4. If Arch-Neo requests changes → fix and loop back to step 2
  5. If Arch-Neo approves → auto-commit and done

Integration:
  Use with /goal for fully autonomous gating:
    /goal critic-loop.sh --goal    # Continuous quality monitoring
    /critic-loop                    # One-shot review cycle
