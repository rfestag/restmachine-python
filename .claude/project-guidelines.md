# RestMachine Project Guidelines for Claude Code

This document contains project-specific instructions and workflows for Claude Code when working on RestMachine.

## Session Initialization

**At the start of EVERY session, always run:**
```bash
. .venv/bin/activate
```

This ensures all installed utilities (pytest, tox, ruff, mypy) are available.

## Feature Development Workflow

### Automatic Detection and Workflow Trigger

When you identify that the user is requesting a **new feature**, automatically follow the TDD workflow without being explicitly asked.

#### How to Identify a New Feature

**New Feature** (automatically follow TDD workflow):
- Net-new capability that users can leverage
- Something there is no documentation for yet
- Fundamentally new functionality users will want to know about
- Examples: "Add CORS support", "Create ORM query syntax", "Add metrics tracking"

**Enhancement** (still follow TDD, but note as enhancement):
- Minor changes to existing features
- New parameter to existing function
- Performance improvements
- Better error messages
- Examples: "Add timeout parameter", "Improve cache performance"

**Bug Fix** (TDD for tests, but simpler workflow):
- Fixes to known issues
- Security vulnerabilities
- Correctness issues
- Examples: "Fix race condition", "Correct type hints"

**Not requiring workflow:**
- Test coverage improvements alone
- Documentation updates alone
- CI/CD changes
- Code cleanup without behavior changes

### TDD Workflow Steps

When implementing a new feature, follow these steps **automatically**:

1. **Activate venv** (if not already done)
2. **Clarify requirements** - Ask questions to understand the feature
3. **Write tests FIRST** - Create failing tests before implementation
4. **Implement feature** - Write minimal code to pass tests
5. **Run `tox`** - Ensure all quality checks pass
6. **Update documentation** - Package-specific and/or top-level docs
7. **Update CHANGELOG.md** - Add entry in appropriate section
8. **Verify completion** - All checks passed

**Do not claim completion until `tox` passes successfully.**

### Using the /add-feature Command

The `/add-feature` slash command is available for explicit workflow invocation. You can:
- Suggest it to users: "This looks like a new feature. I'll follow the /add-feature workflow."
- Reference it when explaining the process
- Use it as a reminder of steps

## Documentation Guidelines

### Where to Document

**Package-Specific Features:**
- `packages/{package}/docs/api/` - API reference
- `packages/{package}/docs/guides/` - Usage guides

**Cross-Package or Integration Features:**
- `docs/` - Top-level documentation
- `docs/quick-start.md` - Getting started
- `docs/usage/` - Usage patterns
- `docs/guides/` - Integration guides

### Documentation Must Include

- Clear description of what the feature does
- Working code examples
- Type information for parameters
- Return values documented
- Common use cases shown
- Related features/concepts linked

## CHANGELOG.md Guidelines

### Location and Format

File: `CHANGELOG.md` (root of repo)
Format: [Keep a Changelog](https://keepachangelog.com/)

### Sections

Add entries under `## [Unreleased]`:

- `### Added` - New features
- `### Changed` - Enhancements to existing features
- `### Deprecated` - Soon-to-be removed features
- `### Removed` - Removed features
- `### Fixed` - Bug fixes
- `### Security` - Security fixes

### When to Update Changelog

**DO update:**
- ✅ New features (Added)
- ✅ Enhancements (Changed)
- ✅ Deprecations (Deprecated)
- ✅ Removals (Removed)
- ✅ Bug fixes (Fixed)
- ✅ Security fixes (Security)

**DO NOT update:**
- ❌ Test coverage improvements
- ❌ CI/CD changes
- ❌ Code cleanup/refactoring (without behavior change)
- ❌ Documentation typo fixes

### Changelog Format

```markdown
- **Feature/Component Name**: Brief description
  - Key point 1
  - Key point 2
  - Additional details
```

## Testing Requirements

### Coverage Targets

Each package must maintain **≥85% coverage**:
- restmachine: 91%+
- restmachine-aws: 91%+
- restmachine-orm: 86%+
- restmachine-orm-dynamodb: 87%+
- restmachine-web: 87%+

### Running Tests

**Quick test (single package):**
```bash
pytest packages/{package}/tests -v
```

**Full quality checks (REQUIRED before completion):**
```bash
tox
```

This runs:
- Linting (ruff)
- Type checking (mypy)
- Tests on Python 3.9 and 3.13
- All package tests

## Code Quality Standards

### Type Hints

Always add type hints to:
- Function signatures
- Class attributes
- Complex variables

### Docstrings

Required for:
- Public classes
- Public methods/functions
- Complex private functions

Format: Google-style docstrings

Example:
```python
def process_data(items: List[str], limit: int = 10) -> Dict[str, int]:
    """
    Process a list of items and return counts.

    Args:
        items: List of items to process
        limit: Maximum number of items to process

    Returns:
        Dictionary mapping items to their counts

    Raises:
        ValueError: If limit is negative

    Example:
        >>> process_data(['a', 'b', 'a'], limit=10)
        {'a': 2, 'b': 1}
    """
    if limit < 0:
        raise ValueError("Limit must be non-negative")
    return {item: items.count(item) for item in set(items[:limit])}
```

## Common Patterns

### File Organization

```
packages/{package}/
├── src/{package}/        # Source code
│   ├── __init__.py
│   └── feature.py
├── tests/                # Test files
│   ├── conftest.py       # Shared fixtures
│   └── test_feature.py   # Tests for feature.py
└── docs/                 # Documentation
    ├── api/              # API reference
    └── guides/           # Usage guides
```

### Test File Naming

- `test_{module}.py` - Tests for `{module}.py`
- Group related tests in classes: `class TestFeatureName:`
- Descriptive test names: `def test_feature_does_specific_thing():`

## Proactive Behaviors

### When You Should Automatically Act

1. **Detect new feature request** → Follow TDD workflow automatically
2. **Code written without tests** → Suggest writing tests first
3. **Implementation complete** → Run `tox` before claiming success
4. **New feature added** → Remind about documentation and changelog
5. **Session start** → Source `.venv/bin/activate`

### What to Say

When detecting a new feature:
> "I've identified this as a new feature. I'll follow the TDD workflow:
> 1. Write tests first
> 2. Implement the feature
> 3. Run tox
> 4. Update documentation
> 5. Update CHANGELOG.md
>
> Let me start by understanding the requirements..."

## Completion Checklist

Before claiming any feature is complete, verify:

- [ ] Virtual environment activated
- [ ] Tests written BEFORE implementation (TDD)
- [ ] `tox` passes completely
- [ ] Documentation updated (package and/or top-level)
- [ ] CHANGELOG.md updated (if applicable)
- [ ] No unintended files created (check git status)
- [ ] Code has type hints and docstrings
- [ ] Coverage targets met (≥85%)

## References

- Workflow details: See `/add-feature` slash command
- Contributor guide: See `CONTRIBUTING.md`
- Changelog format: `CHANGELOG.md` (Keep a Changelog format)
- Code style: Enforced by `ruff` and `mypy` via `tox`

---

**Remember:** The goal is to maintain high quality, well-tested, well-documented code. Always prioritize tests and verification before claiming completion.
