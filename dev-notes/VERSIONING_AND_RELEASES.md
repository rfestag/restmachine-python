# Versioning and Release Automation

This document covers modern approaches to package versioning and release automation for Python projects.

## Version Management Strategies

### 1. Manual Versioning (Current)

**What we have now:**
```toml
# pyproject.toml
[project]
version = "0.1.0"
```

**Pros:**
- Simple and explicit
- Full control over versions
- Easy to understand

**Cons:**
- Manual updates required
- Risk of forgetting to bump version
- No automation

### 2. Git-Based Versioning (Recommended)

Use `setuptools_scm` to derive version from git tags:

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=61.0", "setuptools_scm[toml]>=6.2"]

[project]
# Remove static version
dynamic = ["version"]

[tool.setuptools_scm]
write_to = "restmachine/_version.py"
version_scheme = "guess-next-dev"
local_scheme = "no-local-version"
```

```python
# restmachine/__init__.py
try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"
```

**Pros:**
- Version derived from git tags (e.g., `v1.2.3`)
- No manual updates needed
- Development versions auto-generated
- Single source of truth (git tags)

**Cons:**
- Requires git tags for releases
- Slightly more complex setup

### 3. Semantic Release Automation (Best for CI/CD)

Use `python-semantic-release` for fully automated versioning:

```toml
# pyproject.toml
[tool.semantic_release]
version_toml = ["pyproject.toml:project.version"]
branch = "main"
upload_to_pypi = false
upload_to_release = true
build_command = "pip install build && python -m build"

# Commit message parsing
commit_parser = "angular"  # feat:, fix:, BREAKING CHANGE:
```

**Pros:**
- Fully automated based on commit messages
- Follows semantic versioning automatically
- Generates changelogs
- Integrates with CI/CD

**Cons:**
- Requires conventional commit messages
- Team discipline needed

## Release Triggering Strategies

### Option 1: Tag-Based Releases (Simple & Reliable)

**How it works:**
1. Developer creates git tag: `git tag v1.2.3`
2. Push tag: `git push origin v1.2.3`
3. CI/CD detects tag and triggers release

**GitHub Actions Example:**
```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install build tools
        run: pip install build twine

      - name: Build package
        run: python -m build

      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
        run: twine upload dist/*

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          generate_release_notes: true
```

### Option 2: Conventional Commits + Automation

**How it works:**
1. Developers use conventional commit messages
2. CI/CD analyzes commits to determine version bump
3. Automatic release on merge to main (if changes warrant)

**Conventional Commit Format:**
```bash
# Patch version bump (0.1.0 -> 0.1.1)
git commit -m "fix: resolve template rendering bug"

# Minor version bump (0.1.0 -> 0.2.0)
git commit -m "feat: add XML rendering support"

# Major version bump (0.1.0 -> 1.0.0)
git commit -m "feat!: redesign API interface

BREAKING CHANGE: removed deprecated render_html function"
```

**GitHub Actions Example:**
```yaml
# .github/workflows/semantic-release.yml
name: Semantic Release

on:
  push:
    branches:
      - main

jobs:
  release:
    runs-on: ubuntu-latest
    concurrency: release

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Python Semantic Release
        uses: python-semantic-release/python-semantic-release@v9
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          pypi_token: ${{ secrets.PYPI_TOKEN }}
```

### Option 3: Label-Based Releases (PR-Driven)

**How it works:**
1. Add label to PR: `release:minor`, `release:patch`, `release:major`
2. When PR merges, CI/CD bumps version accordingly
3. Release created automatically

**GitHub Actions Example:**
```yaml
# .github/workflows/release-on-label.yml
name: Release on Label

on:
  pull_request:
    types: [closed]

jobs:
  release:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Determine version bump
        id: bump
        run: |
          if [[ "${{ contains(github.event.pull_request.labels.*.name, 'release:major') }}" == "true" ]]; then
            echo "bump=major" >> $GITHUB_OUTPUT
          elif [[ "${{ contains(github.event.pull_request.labels.*.name, 'release:minor') }}" == "true" ]]; then
            echo "bump=minor" >> $GITHUB_OUTPUT
          elif [[ "${{ contains(github.event.pull_request.labels.*.name, 'release:patch') }}" == "true" ]]; then
            echo "bump=patch" >> $GITHUB_OUTPUT
          else
            echo "bump=none" >> $GITHUB_OUTPUT
          fi

      - name: Bump version
        if: steps.bump.outputs.bump != 'none'
        run: |
          pip install bump2version
          bump2version ${{ steps.bump.outputs.bump }}

      # ... build and release steps
```

### Option 4: Manual Workflow Dispatch

**How it works:**
1. Tests pass on main branch
2. Maintainer manually triggers release workflow
3. Choose version bump type in UI

**GitHub Actions Example:**
```yaml
# .github/workflows/manual-release.yml
name: Manual Release

on:
  workflow_dispatch:
    inputs:
      version_bump:
        description: 'Version bump type'
        required: true
        default: 'patch'
        type: choice
        options:
          - major
          - minor
          - patch

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Bump version
        run: |
          pip install bump2version
          bump2version ${{ inputs.version_bump }}

      # ... rest of release steps
```

## Recommended Setup for restmachine

### Phase 1: Simple Tag-Based (Start Here)

**Best for:**
- Small teams
- Starting out with automation
- Clear, explicit control

**Setup:**
```bash
# Install tools
pip install build twine

# Create release
git tag v0.2.0
git push origin v0.2.0

# CI/CD automatically builds and publishes
```

### Phase 2: Conventional Commits (Scale Up)

**Best for:**
- Growing teams
- Frequent releases
- Clear commit history

**Setup:**
1. Add `python-semantic-release` to dev dependencies
2. Configure commit message format
3. Automate on merge to main

### Phase 3: Full Automation (Advanced)

**Best for:**
- Mature projects
- Multiple contributors
- Continuous delivery

**Includes:**
- Automatic version bumping
- Changelog generation
- PyPI publishing
- GitHub releases
- Docker image publishing

## Tools Comparison

| Tool | Type | Best For | Complexity |
|------|------|----------|------------|
| Manual editing | Static | Simple projects | Low |
| `setuptools_scm` | Git-based | Git-centric workflow | Low |
| `bump2version` | CLI tool | Controlled automation | Medium |
| `python-semantic-release` | Full automation | CI/CD pipeline | Medium |
| `poetry version` | Poetry-specific | Poetry users | Low |
| `tbump` | Git + version files | Multiple files | Medium |

## Example: setuptools_scm Setup

**1. Install:**
```bash
pip install setuptools_scm
```

**2. Update pyproject.toml:**
```toml
[build-system]
requires = ["setuptools>=61.0", "setuptools_scm[toml]>=6.2"]
build-backend = "setuptools.build_meta"

[project]
# Remove: version = "0.1.0"
dynamic = ["version"]

[tool.setuptools_scm]
write_to = "restmachine/_version.py"
```

**3. Update __init__.py:**
```python
try:
    from ._version import version as __version__
except ImportError:
    __version__ = "0.0.0+unknown"
```

**4. Create releases:**
```bash
# Tag a release
git tag v0.2.0
git push origin v0.2.0

# Build uses tag for version
python -m build
```

## Example: GitHub Actions Release Workflow

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      id-token: write  # For trusted publishing to PyPI

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine

      - name: Run tests
        run: |
          pip install -e .[dev]
          pytest tests/

      - name: Build package
        run: python -m build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          generate_release_notes: true
          files: dist/*
```

## Best Practices

### 1. Semantic Versioning (SemVer)

Follow the format: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes (1.0.0 -> 2.0.0)
- **MINOR**: New features, backward compatible (1.0.0 -> 1.1.0)
- **PATCH**: Bug fixes, backward compatible (1.0.0 -> 1.0.1)

### 2. Pre-release Versions

```
0.1.0a1     # Alpha 1
0.1.0b1     # Beta 1
0.1.0rc1    # Release candidate 1
0.1.0       # Final release
```

### 3. Development Versions

With `setuptools_scm`:
```
0.1.0.dev3+g1234abc  # 3 commits after v0.1.0
```

### 4. Release Checklist

- [ ] All tests pass
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped (manual or auto)
- [ ] Git tag created
- [ ] Package built successfully
- [ ] Published to PyPI
- [ ] GitHub release created

## Security: PyPI Publishing

### Trusted Publishing (Recommended)

No API tokens needed! Configure on PyPI:

1. Go to PyPI project settings
2. Add trusted publisher (GitHub Actions)
3. Use in workflow:

```yaml
- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  # No token needed with trusted publishing!
```

### API Token Method

1. Generate token on PyPI
2. Add to GitHub secrets as `PYPI_API_TOKEN`
3. Use in workflow:

```yaml
- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  with:
    password: ${{ secrets.PYPI_API_TOKEN }}
```

## Migration Path for restmachine

### Week 1: Basic Automation
```bash
# Add setuptools_scm
pip install setuptools_scm

# Update pyproject.toml
# Create .github/workflows/release.yml
# Test with: git tag v0.2.0
```

### Week 2: Conventional Commits
```bash
# Team adopts: feat:, fix:, BREAKING CHANGE:
# Add commit message linting (optional)
# Monitor commit quality
```

### Week 3: Full Automation
```bash
# Add python-semantic-release
# Enable automatic releases on main
# Setup changelog generation
```

## Resources

- [Semantic Versioning](https://semver.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [setuptools_scm docs](https://setuptools-scm.readthedocs.io/)
- [python-semantic-release](https://python-semantic-release.readthedocs.io/)
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
- [GitHub Actions for Python](https://docs.github.com/en/actions/automating-builds-and-tests/building-and-testing-python)
