# Migration from setup.py to pyproject.toml

This document describes the migration from `setup.py` to modern `pyproject.toml` packaging.

## What Changed

### Before (setup.py)
- All package metadata was in `setup.py`
- Dependencies loaded from `requirements.txt`
- Executed Python code to read files and configure package

### After (pyproject.toml)
- All package metadata in declarative `pyproject.toml` (PEP 621)
- Dependencies declared directly in `[project.dependencies]`
- No code execution required
- `setup.py` reduced to a minimal compatibility shim

## Benefits of pyproject.toml

1. **Declarative**: No code execution, just data
2. **Standard**: PEP 517, 518, 621 compliant
3. **Tool-agnostic**: Works with pip, poetry, pdm, hatch, etc.
4. **Single source**: All project config in one place
5. **Future-proof**: The Python packaging standard going forward

## File Structure

### pyproject.toml Structure

```toml
[build-system]          # Build backend configuration
[project]               # Package metadata
  - dependencies        # Core runtime dependencies
  - optional-dependencies # Extra/optional dependencies
  - urls                # Project URLs
[tool.setuptools]       # Setuptools-specific config
[tool.bandit]          # Tool configurations
[tool.detect-secrets]
```

### Key Sections

#### Core Metadata
```toml
[project]
name = "restmachine"
version = "0.1.0"
description = "..."
readme = "README.md"
requires-python = ">=3.8"
license = "MIT"  # SPDX identifier
authors = [...]
keywords = [...]
classifiers = [...]
```

#### Dependencies
```toml
dependencies = [
    "jinja2>=3.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=6.0", "ruff", "mypy", ...]
server = ["uvicorn[standard]>=0.20.0", ...]
validation = ["pydantic>=2.0.0"]
```

## Installation Commands

### User Installation
```bash
# Install package with core dependencies
pip install -e .

# Install with optional extras
pip install -e .[server]
pip install -e .[validation]
pip install -e .[dev]

# Multiple extras
pip install -e .[dev,server,validation]
```

### Development Setup
```bash
# Use the convenience file
pip install -r requirements-dev.txt

# Or directly
pip install -e .[dev,validation,server]
tox
```

## What Happened to setup.py?

**It's been deleted!** 🎉

Modern pip (>=21.3) and all build tools work perfectly with just `pyproject.toml`. The `setup.py` file is no longer needed.

### Do I need setup.py?

**No!** All package configuration is now in `pyproject.toml`:
- ✅ Metadata, dependencies, URLs
- ✅ Optional extras (dev, server, validation)
- ✅ Tool configurations (bandit, mypy, etc.)

Everything works without it:
- `pip install -e .` ✅
- `pip install -e .[dev]` ✅
- `tox` ✅
- `python -m build` ✅

### For older projects

If you're maintaining an older project that still needs `setup.py` for compatibility, you can use a minimal shim:

```python
from setuptools import setup
setup()  # All config in pyproject.toml
```

But for modern projects: **just delete it!**

## Migrating Your Own Projects

1. **Create pyproject.toml** with `[build-system]` and `[project]` sections
2. **Move metadata** from setup.py to `[project]`
3. **Move dependencies** to `[project.dependencies]`
4. **Move extras** to `[project.optional-dependencies]`
5. **Test installation**: `pip install -e .`
6. **Test build**: `python -m build`
7. **Optionally delete setup.py** or reduce to minimal shim

## Common Issues

### License Format
Modern format uses SPDX identifiers:
```toml
# Modern (correct)
license = "MIT"

# Old (deprecated)
license = {text = "MIT"}
```

### Classifiers
Don't duplicate license in classifiers:
```toml
# Don't include "License :: OSI Approved :: MIT License"
# when using SPDX license identifier
```

### Package Discovery
Explicitly configure package finding:
```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["restmachine*"]
exclude = ["tests*", "examples*"]
```

## References

- [PEP 517](https://peps.python.org/pep-0517/) - Backend interface
- [PEP 518](https://peps.python.org/pep-0518/) - pyproject.toml spec
- [PEP 621](https://peps.python.org/pep-0621/) - Project metadata
- [PyPA Guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
- [SPDX License List](https://spdx.org/licenses/)

## Tools That Work With pyproject.toml

- ✅ pip (>=21.3)
- ✅ build
- ✅ poetry
- ✅ pdm
- ✅ hatch
- ✅ flit
- ✅ setuptools (>=61.0)
- ✅ tox
- ✅ bandit
- ✅ mypy
- ✅ ruff
- ✅ pytest
