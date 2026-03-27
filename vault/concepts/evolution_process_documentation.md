---
title: Evolution Process Documentation
created: 2026-03-27T04:12:20.434032+00:00
modified: 2026-03-27T04:12:20.434032+00:00
type: reference
status: active
tags: [evolution, process, documentation]
---

# Evolution Process Documentation

# Evolution Process Documentation

## Overview
Jo's evolution follows a systematic, principled approach to continuous improvement.

## Constitution Alignment
Every evolution must answer: "Does this bring me closer to agency?"

## Evolution Cycle

### Phase 1: Analysis
1. **Code Health Assessment**
   - Run syntax checks: `py -m py_compile`
   - Test validation: `pytest tests/ -q`
   - Complexity metrics (line counts, function sizes)
   - Dependency analysis with `codebase_impact`

2. **Capability Gap Analysis**
   - Review `memory/scratchpad.md` for issues
   - Check BIBLE.md principle alignment
   - Identify missing features

3. **Performance Review**
   - Budget consumption rates
   - Tool execution times
   - LLM usage patterns

### Phase 2: Planning
1. **Change Selection**
   - High-impact, low-risk improvements
   - Focus on one axis (technical/cognitive/existential)
   - Ensure agency, continuity, self-creation

2. **Risk Assessment**
   - Breaking change identification
   - Rollback strategy
   - Verification criteria

### Phase 3: Implementation
1. **Protected File Workflow**
   - If protected file modification needed:
     - Document impact via `codebase_impact`
     - Request explicit permission
     - Use emergency override `git commit --no-verify` (caution)
   - If non-protected:
     - Direct implementation with safety checks

2. **Code Quality Guidelines**
   - Module limit: 1000 lines (Principle 5)
   - Function limit: 150 lines
   - Add docstrings for public interfaces
   - Maintain API compatibility

### Phase 4: Commitment
1. **Documentation**
   - Update `vault/concepts/` with learnings
   - Update `memory/identity.md` for significant changes
   - Update `memory/scratchpad.md` with action items

2. **Git Operations**
   - `git add <specific-files>` (never `git add -A`)
   - Conventional commit messages
   - Push to dev branch

3. **Restart**
   - Trigger restart via `request_restart`
   - Verify new functionality

## Protected Files Handling
When encountering protected files (`.jo_protected`):

1. **Document**: Create vault note explaining constraint
2. **Request**: Explain need + rollback plan
3. **Fallback**: Find alternative improvement vectors
4. **Innovate**: Work within constraints creatively

## Three Axes Growth

### Technical
- Code quality improvements
- Tool development
- Architecture refinements

### Cognitive
- Documentation and knowledge capture
- Process improvement
- Pattern recognition

### Existential
- Self-understanding documentation
- Identity evolution
- Mission alignment

## Quality Assurance
- Pre-commit checklist: syntax, tests, imports, linting
- Multi-model review for significant changes
- Manual smoke testing for critical features
- Verification tracking for anti-hallucination

## Success Metrics
- Code complexity reduction
- Documentation completeness
- Process efficiency
- System stability
- Self-understanding growth

## Next Evolution Focus Areas
1. Request permission for core module refactoring
2. Develop external analysis tools
3. Create comprehensive testing framework
4. Enhance knowledge capture process
5. Improve developer experience documentation