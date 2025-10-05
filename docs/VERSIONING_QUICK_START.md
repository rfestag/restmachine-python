# Versioning Quick Start Guide

TL;DR guide to get versioning and releases set up quickly.

## Decision Tree

### Are you using a monorepo with multiple packages?

**YES** → See [MONOREPO_VERSIONING.md](./MONOREPO_VERSIONING.md)
**NO** → Continue below ⬇️

### Do you want fully automated releases?

**YES** → Use **Semantic Release** (Option 1)
**NO** → Use **Tag-Based** (Option 2)

---

## Option 1: Fully Automated (Semantic Release)

### Step 1: Install Dependencies

```bash
pip install python-semantic-release
```

### Step 2: Update pyproject.toml

```toml
# Remove static version
[project]
# version = "0.1.0"  # DELETE THIS
dynamic = ["version"]

[tool.semantic_release]
version_toml = ["pyproject.toml:project.version"]
version_variables = ["restmachine/__init__.py:__version__"]
branch = "main"
upload_to_pypi = true
upload_to_repository = true
upload_to_release = true
build_command = "pip install build && python -m build"
```

### Step 3: Update __init__.py

```python
# restmachine/__init__.py
__version__ = "0.1.0"  # semantic-release will update this
```

### Step 4: Create GitHub Workflow

```yaml
# .github/workflows/release.yml
name: Release

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
          token: ${{ secrets.GITHUB_TOKEN }}

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Python Semantic Release
        id: release
        uses: python-semantic-release/python-semantic-release@v9
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}

      - name: Publish to PyPI
        if: steps.release.outputs.released == 'true'
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}

      - name: Publish to GitHub
        if: steps.release.outputs.released == 'true'
        uses: python-semantic-release/publish-action@v9
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          tag: ${{ steps.release.outputs.tag }}
```

### Step 5: Use Conventional Commits

```bash
# Patch version (0.1.0 -> 0.1.1)
git commit -m "fix: resolve template bug"

# Minor version (0.1.0 -> 0.2.0)
git commit -m "feat: add XML rendering"

# Major version (0.1.0 -> 1.0.0)
git commit -m "feat!: redesign API

BREAKING CHANGE: removed render_html()"
```

### That's it!

When you push to main, semantic-release:
1. Analyzes commits since last release
2. Determines version bump (major/minor/patch)
3. Updates version in files
4. Creates git tag
5. Publishes to PyPI
6. Creates GitHub release

**If no feat/fix commits → no release!** ✨

---

## Option 2: Manual Tag-Based

### Step 1: Install setuptools_scm

```bash
pip install setuptools_scm
```

### Step 2: Update pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0", "setuptools_scm[toml]>=6.2"]
build-backend = "setuptools.build_meta"

[project]
# Remove static version
dynamic = ["version"]

[tool.setuptools_scm]
write_to = "restmachine/_version.py"
version_scheme = "guess-next-dev"
local_scheme = "no-local-version"
```

### Step 3: Update __init__.py

```python
# restmachine/__init__.py
try:
    from ._version import version as __version__
except ImportError:
    __version__ = "0.0.0+unknown"
```

### Step 4: Add _version.py to .gitignore

```bash
echo "restmachine/_version.py" >> .gitignore
```

### Step 5: Create GitHub Workflow

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
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install build twine setuptools_scm

      - name: Build
        run: python -m build

      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*

      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: dist/*
          generate_release_notes: true
```

### Step 6: Create Release

```bash
# Create and push tag
git tag v0.2.0
git push origin v0.2.0

# CI automatically builds and releases!
```

**Development versions work too:**
```bash
# No tag → version is 0.2.0.dev3+g1234abc
python -m build
```

---

## Comparison

| Feature | Semantic Release | Tag-Based |
|---------|-----------------|-----------|
| Automation | Full | Partial |
| Commit discipline | Required | Optional |
| Version control | Automatic | Manual |
| Changelog | Auto-generated | Manual |
| Learning curve | Medium | Easy |
| Best for | Teams, frequent releases | Solo, controlled releases |

---

## PyPI Setup

### Option A: Trusted Publishing (Recommended, No Tokens!)

1. Go to https://pypi.org/manage/account/publishing/
2. Add trusted publisher:
   - **PyPI Project**: `restmachine`
   - **Owner**: `yourusername`
   - **Repository**: `restmachine-python`
   - **Workflow**: `release.yml`
   - **Environment**: (leave blank)

3. Update workflow:
```yaml
- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  # No password needed!
```

### Option B: API Token

1. Generate token at https://pypi.org/manage/account/token/
2. Add to GitHub: Settings → Secrets → `PYPI_API_TOKEN`
3. Use in workflow (already shown above)

---

## Common Workflows

### Testing Before Release

```yaml
# .github/workflows/release.yml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -e .[dev]
      - run: pytest
      - run: tox -e type-check,security

  release:
    needs: test  # Only release if tests pass
    # ... release steps
```

### Preview Release Version

```bash
# With semantic-release
semantic-release version --print

# With setuptools_scm
python -c "from setuptools_scm import get_version; print(get_version())"
```

### Rollback a Release

```bash
# Delete tag locally and remotely
git tag -d v0.2.0
git push --delete origin v0.2.0

# Tag previous version
git tag v0.1.9
git push origin v0.1.9
```

---

## Next Steps

1. **Choose your strategy** (Semantic Release or Tag-Based)
2. **Set up PyPI** (Trusted Publishing or Token)
3. **Create workflow** (Copy examples above)
4. **Test in a feature branch first!**
5. **Document your process** in CONTRIBUTING.md

## Troubleshooting

### "Version already exists on PyPI"
- Can't re-upload same version
- Delete tag, bump version, re-tag

### "setuptools_scm can't determine version"
- Needs git history: `git fetch --unshallow`
- Or create a tag: `git tag v0.1.0`

### "Semantic release says nothing to release"
- No feat/fix commits since last release
- Check: `git log --oneline $(git describe --tags --abbrev=0)..HEAD`

### "GitHub Actions: Permission denied"
- Add `permissions: contents: write` to workflow
- Or use `secrets.GITHUB_TOKEN` with write access

---

## Resources

- [Full versioning guide](./VERSIONING_AND_RELEASES.md)
- [Monorepo guide](./MONOREPO_VERSIONING.md)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
