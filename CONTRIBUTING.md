# Contributing to RestMachine

Thank you for your interest in contributing to RestMachine! This document provides guidelines and workflows for contributing to the project.

## Development Setup

### Prerequisites

- Python 3.9 or 3.13 (for testing both versions)
- Git
- Virtual environment tools

### Initial Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/restmachine-python.git
   cd restmachine-python
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install development dependencies:**
   ```bash
   pip install -e ".[dev]"
   # Or install tox for running full test suite
   pip install tox
   ```

## Development Workflow

### Test-Driven Development (TDD)

We follow a strict TDD workflow for all feature development:

1. **Activate virtual environment** (do this at the start of every session):
   ```bash
   source .venv/bin/activate
   ```

2. **Write tests FIRST** - Before writing any implementation code
3. **Watch tests fail** - Confirm they fail for the right reasons
4. **Implement minimal code** to make tests pass
5. **Refactor** while keeping tests green
6. **Run full test suite** - Ensure nothing broke

### Running Tests

**Quick test run** (specific package):
```bash
pytest packages/restmachine/tests -v
```

**Full test suite with quality checks** (always run before completing work):
```bash
tox
```

This runs:
- **Linting** (ruff) - Code style and quality checks
- **Type checking** (mypy) - Static type verification
- **Tests** on Python 3.9 and 3.13
- **All package tests** - Ensures nothing broke

**Important:** Do not consider work complete until `tox` passes successfully.

### Package Coverage Requirements

Each package must maintain at least **85% test coverage**:
- restmachine: 91%+
- restmachine-aws: 91%+
- restmachine-orm: 86%+
- restmachine-orm-dynamodb: 87%+
- restmachine-web: 87%+

## Feature Development Process

### 1. Determine Change Type

**New Feature** - Net-new capability:
- Something users can leverage that didn't exist before
- No existing documentation for this capability
- Example: Adding CORS support, new query syntax

**Enhancement** - Improvement to existing feature:
- New parameter to existing function
- Performance improvement
- Better error messages
- Example: Adding timeout parameter to existing client

**Bug Fix** - Correcting issues:
- Security vulnerabilities
- Correctness issues
- Example: Fixing race condition, correcting type hints

### 2. Write Tests (TDD)

Create test file in appropriate package's `tests/` directory:

```python
# packages/{package}/tests/test_new_feature.py
import pytest
from restmachine import YourFeature

def test_basic_functionality():
    """Test that the feature works in the happy path."""
    result = YourFeature.do_something()
    assert result == expected_value

def test_edge_cases():
    """Test boundary conditions."""
    # Test edge cases

def test_error_handling():
    """Test that errors are handled properly."""
    with pytest.raises(ValueError):
        YourFeature.do_invalid_thing()
```

**Run tests to see them fail:**
```bash
pytest packages/{package}/tests/test_new_feature.py -v
```

### 3. Implement Feature

Write minimal code to make tests pass:

```python
# packages/{package}/src/restmachine/new_feature.py
from typing import Optional

class YourFeature:
    """
    Brief description of what this does.

    Args:
        param: Description

    Returns:
        Description of return value

    Example:
        >>> feature = YourFeature()
        >>> feature.do_something()
        'result'
    """

    def do_something(self) -> str:
        # Implementation
        return "result"
```

### 4. Run Full Test Suite

**Always run before completing:**
```bash
tox
```

Fix any linting, type checking, or test failures.

### 5. Update Documentation

#### Package-Specific Documentation

For features specific to one package:
- `packages/{package}/docs/api/` - API reference
- `packages/{package}/docs/guides/` - Usage guides

Example:
```markdown
# packages/restmachine/docs/api/new-feature.md

# YourFeature

Brief description.

## Basic Usage

\`\`\`python
from restmachine import YourFeature

feature = YourFeature()
result = feature.do_something()
\`\`\`

## API Reference

### `YourFeature.do_something()`

Description of method...
```

#### Cross-Package Documentation

For features involving multiple packages:
- `docs/quick-start.md` - Getting started examples
- `docs/usage/` - Usage patterns
- `docs/guides/` - Integration guides

### 6. Update CHANGELOG.md

Add entry under `## [Unreleased]` in appropriate section:

#### New Features → `### Added`
```markdown
- **Feature Name**: Brief description
  - Key capability 1
  - Key capability 2
```

#### Enhancements → `### Changed`
```markdown
- **Component**: Enhancement description
```

#### Bug Fixes → `### Fixed`
```markdown
- **Component**: Issue fixed
```

#### Deprecations → `### Deprecated`
```markdown
- **Feature**: Deprecated feature and migration path
```

#### Removals → `### Removed`
```markdown
- **Feature**: What was removed and why
```

**Skip changelog for:**
- Test coverage improvements
- CI/CD changes
- Code cleanup/refactoring
- Documentation typo fixes

## Pull Request Guidelines

### Before Submitting

- [ ] Tests written BEFORE implementation (TDD)
- [ ] All tests pass (`tox` succeeds)
- [ ] Code coverage meets 85% minimum
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if applicable)
- [ ] Commits are focused and atomic
- [ ] No unintended files in git status

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] New feature (Added)
- [ ] Enhancement (Changed)
- [ ] Bug fix (Fixed)
- [ ] Deprecation (Deprecated)
- [ ] Breaking change (Removed)
- [ ] Documentation only
- [ ] Test/CI improvements

## Checklist
- [ ] Tests written using TDD approach
- [ ] `tox` passes completely
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Coverage target met (85%+)

## Testing
Describe testing approach and results
```

## Code Style

### Python Conventions

- Follow PEP 8 (enforced by ruff)
- Use type hints (checked by mypy)
- Write docstrings for public APIs
- Prefer explicit over implicit
- Keep functions focused and small

### Example

```python
from typing import Optional, List

def process_items(
    items: List[str],
    filter_prefix: Optional[str] = None
) -> List[str]:
    """
    Process a list of items with optional filtering.

    Args:
        items: List of items to process
        filter_prefix: If provided, only include items with this prefix

    Returns:
        Processed list of items

    Example:
        >>> process_items(['apple', 'banana', 'apricot'], filter_prefix='ap')
        ['apple', 'apricot']
    """
    if filter_prefix:
        items = [i for i in items if i.startswith(filter_prefix)]
    return [item.upper() for item in items]
```

## Project Structure

```
restmachine-python/
├── packages/                    # Monorepo packages
│   ├── restmachine/            # Core framework
│   ├── restmachine-aws/        # AWS integrations
│   ├── restmachine-orm/        # ORM layer
│   ├── restmachine-orm-dynamodb/
│   └── restmachine-web/        # Web utilities
├── docs/                        # Top-level documentation
├── examples/                    # Example projects
├── CHANGELOG.md                 # Project changelog
├── CONTRIBUTING.md             # This file
└── tox.ini                     # Test configuration
```

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/yourusername/restmachine-python/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/restmachine-python/discussions)
- **Documentation**: [docs.restmachine.io](https://docs.restmachine.io)

## License

By contributing, you agree that your contributions will be licensed under the project's license.

---

**Remember:** Always source `.venv/bin/activate` and run `tox` before submitting!
