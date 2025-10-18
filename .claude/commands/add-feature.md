---
description: Implement a new feature using TDD workflow with tests, documentation, and changelog updates
---

You are implementing a new feature for RestMachine. Follow this Test-Driven Development (TDD) workflow:

## 1. Setup Environment

First, activate the virtual environment:
```bash
. .venv/bin/activate
```

## 2. Understand the Feature

- Ask clarifying questions about the feature requirements
- Identify which package(s) will be affected
- Determine if this is truly a new feature (net-new capability) vs enhancement/bug fix
- Confirm scope and acceptance criteria

## 3. Write Tests First (TDD)

**Before writing any implementation code:**

- Create test file(s) in appropriate `tests/` directory
- Write failing tests that describe the desired behavior. Where possible, use the existing DSL and drivers for the package. If additions or modifications are needed in DSLs/drivers, prefer adding to them instead of working around them.
- Run tests to confirm they fail for the right reasons
- Tests should cover:
  - Happy path scenarios
  - Edge cases
  - Error conditions
  - Integration points (if applicable)

## 4. Implement the Feature

- Write minimal code to make tests pass
- Follow existing code patterns and conventions
- Add type hints and docstrings
- Keep commits focused and atomic
- Do not commit or add any files to the commit automatically. The developer is responsible for reviewing before committing.
- If you add a new file that belongs in the repo, run `git add -N filename` to add it in an unstaged state (intent to add), so that a git diff shows the new file.

## 5. Run Type Checking

**Before running the full test suite**, verify your new code has no type errors:

```bash
mypy packages/{package_name}/src/{package_name}/**/*.py --config-file=pyproject.toml
```

Common type issues to avoid:
- Use `Tuple` instead of `tuple` for Python 3.9 compatibility (import from `typing`)
- Use `List` instead of `list` for Python 3.9 compatibility (import from `typing`)
- Add `# type: ignore[import-untyped]` for third-party imports without type stubs
- Add `# type: ignore[no-untyped-def]` for functions with dynamic parameters
- Ensure all function return types are annotated

**Fix all type errors before proceeding.**

## 6. Run Full Test Suite

Ensure all tests pass and code meets quality standards:

```bash
tox
```

This runs:
- Linting (ruff)
- Type checking (mypy)
- Tests on Python 3.9 and 3.13
- All package tests

**Do not proceed until tox passes completely.**

## 7. Update Documentation

### Package-Specific Documentation

For features specific to one package, update documentation in:
- `packages/{package_name}/docs/`

Examples:
- API reference: `packages/restmachine-orm/docs/api/models.md`
- Usage guides: `packages/restmachine-aws/docs/guides/lambda-deployment.md`

### Cross-Package Documentation

For features involving multiple packages or integration, update:
- `docs/` (top-level documentation)
- Quick start guides
- Usage examples
- Integration patterns

### Documentation Should Include:

- Clear description of what the feature does
- Code examples showing usage
- Parameters/options with type information
- Return values
- Common use cases
- Related features/concepts

## 8. Update CHANGELOG.md

Add entry to `CHANGELOG.md` under `## [Unreleased]` section:

### For New Features:

Add under `### Added`:
```markdown
- **Feature Name**: Brief description
  - Key capability 1
  - Key capability 2
  - Additional details as needed
```

### For Enhancements:

Add under `### Changed`:
```markdown
- **Component Name**: Enhancement description
  - What changed
  - Why it's better
```

### For Bug Fixes:

Add under `### Fixed`:
```markdown
- **Component**: Issue description and fix
```

### For Deprecations:

Add under `### Deprecated`:
```markdown
- **API/Feature**: What's deprecated and migration path
```

### For Removals:

Add under `### Removed`:
```markdown
- **Feature**: What was removed and why
```

**Note:** Changelog updates are NOT needed for:
- Test coverage improvements
- CI/CD changes
- Code cleanup/refactoring (without behavior changes)
- Documentation fixes

## 9. Final Verification

Before completing:

- [ ] All tests pass (`tox` succeeds)
- [ ] Type checking passes (no mypy errors in new code)
- [ ] Tests were written BEFORE implementation
- [ ] Documentation updated (package-specific and/or top-level)
- [ ] CHANGELOG.md updated (if applicable)
- [ ] Code follows project conventions
- [ ] Type hints added (using `Tuple`, `List` from `typing` for Python 3.9)
- [ ] No unintended files created (check git status)

## 10. Summary

Provide a summary of:
- What was implemented
- Test coverage added
- Documentation updated
- Changelog entry made

## Feature vs Enhancement vs Bug Fix

**New Feature** (changelog: Added):
- Net-new capability users can leverage
- Something there is no documentation for yet
- Fundamentally new functionality
- Example: "Add CORS support", "New ORM query syntax"

**Enhancement** (changelog: Changed):
- Minor changes to existing features
- New parameter to existing function
- Performance improvement
- Better error messages
- Example: "Add timeout parameter to HTTP client"

**Bug Fix** (changelog: Fixed):
- Fixes to known issues
- Security vulnerabilities
- Correctness issues
- Example: "Fix race condition in cache", "Correct type hints"

---

**Remember:** Source the venv at the start of each session and run `tox` before claiming completion!
