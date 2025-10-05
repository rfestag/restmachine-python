# Monorepo Versioning for Python Packages

Guide for managing versions and releases in Python monorepos with multiple packages.

## Monorepo Versioning Strategies

### Strategy 1: Independent Versioning (Recommended)

Each package has its own version, released independently.

```
monorepo/
├── packages/
│   ├── restmachine-core/
│   │   └── pyproject.toml  # version = "1.2.3"
│   ├── restmachine-aws/
│   │   └── pyproject.toml  # version = "0.5.1"
│   └── restmachine-django/
│       └── pyproject.toml  # version = "2.0.0"
```

**Pros:**
- Packages can evolve at different rates
- Breaking changes in one don't affect others
- Clear dependency management
- PyPI best practice

**Cons:**
- More complex release coordination
- Need to track which packages changed
- Dependency version management between packages

### Strategy 2: Unified Versioning

All packages share the same version number.

```
monorepo/
├── version.txt              # "1.2.3" - single source
├── packages/
│   ├── restmachine-core/
│   │   └── pyproject.toml  # version = "1.2.3"
│   ├── restmachine-aws/
│   │   └── pyproject.toml  # version = "1.2.3"
│   └── restmachine-django/
│       └── pyproject.toml  # version = "1.2.3"
```

**Pros:**
- Simple to understand
- All packages released together
- Easy version coordination

**Cons:**
- Unnecessary releases (patch to one = release all)
- Confusing for users (why is AWS v2.0 if nothing changed?)
- Not recommended for PyPI

### Strategy 3: Hybrid (Google/Bazel Style)

Core package has main version, plugins reference it.

```
packages/
├── restmachine/
│   └── pyproject.toml      # version = "1.2.3"
├── restmachine-aws/
│   └── pyproject.toml      # version = "1.2.3.post1" (tracks core)
└── restmachine-django/
    └── pyproject.toml      # version = "1.2.3.post2"
```

## Tools for Monorepo Versioning

### 1. setuptools_scm (Git-Based)

**Best for:** Independent versioning with git tags

```toml
# packages/restmachine-core/pyproject.toml
[build-system]
requires = ["setuptools>=61.0", "setuptools_scm[toml]>=6.2"]

[tool.setuptools_scm]
root = "../.."  # Point to monorepo root
tag_regex = "^restmachine-core-(?P<version>.*)$"
write_to = "restmachine/_version.py"
```

**Tag format:**
```bash
# Release core package
git tag restmachine-core-v1.2.3

# Release AWS package
git tag restmachine-aws-v0.5.0
```

**Pros:**
- Uses git tags as source of truth
- Independent package versioning
- Works with standard PyPI

**Cons:**
- Tag naming convention required
- Manual tag coordination

### 2. dunamai (Dynamic Metadata)

**Best for:** Flexible version generation

```toml
[build-system]
requires = ["setuptools>=61.0", "dunamai>=1.7.0"]

[tool.dunamai]
pattern = "^(?P<package>[a-z-]+)-v(?P<base>\\d+\\.\\d+\\.\\d+)"
```

```python
# setup.py or build script
from dunamai import Version, Style
version = Version.from_git().serialize(style=Style.SemVer)
```

### 3. lerna-lite (JavaScript port to Python)

**Best for:** JavaScript developers familiar with Lerna

```bash
# Install
npm install -g lerna-lite

# Initialize
lerna init

# Version packages independently
lerna version --conventional-commits

# Publish changed packages
lerna publish from-git
```

### 4. changesets (Gaining Popularity)

**Best for:** PR-based versioning with changelogs

```bash
# Install
npm install -g @changesets/cli

# Add changeset to PR
changeset add

# Release all changed packages
changeset version
changeset publish
```

### 5. commitizen + standard-version

**Best for:** Conventional commits in monorepos

```bash
pip install commitizen

# Configure per package
cz bump --files-only packages/restmachine-core/pyproject.toml
cz bump --files-only packages/restmachine-aws/pyproject.toml
```

## Detecting Changed Packages

### Method 1: Git Diff (Simple)

```bash
# .github/workflows/detect-changes.yml
- name: Detect changed packages
  id: changes
  run: |
    # Check which packages changed
    if git diff --name-only HEAD~1 | grep -q "^packages/restmachine-core/"; then
      echo "core_changed=true" >> $GITHUB_OUTPUT
    fi
    if git diff --name-only HEAD~1 | grep -q "^packages/restmachine-aws/"; then
      echo "aws_changed=true" >> $GITHUB_OUTPUT
    fi

- name: Release Core
  if: steps.changes.outputs.core_changed == 'true'
  run: |
    cd packages/restmachine-core
    python -m build
```

### Method 2: Turborepo (Advanced)

```bash
# Install Turborepo
npm install -g turbo

# turbo.json
{
  "pipeline": {
    "build": {
      "outputs": ["dist/**"]
    },
    "test": {
      "outputs": []
    },
    "release": {
      "dependsOn": ["build", "test"],
      "outputs": []
    }
  }
}

# Only build/test/release changed packages
turbo run release --filter=[HEAD^1]
```

### Method 3: Pants Build (Python-Native)

```bash
# Install Pants
pip install pantsbuild.pants

# BUILD files define packages
./pants --changed-since=HEAD~1 package ::
```

### Method 4: Nx (Comprehensive)

```bash
# Install Nx
npm install -g nx

# Only affect changed projects
nx affected --target=build
nx affected --target=test
nx affected --target=release
```

## Example: Independent Versioning Setup

### Directory Structure

```
restmachine-monorepo/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── packages/
│   ├── restmachine-core/
│   │   ├── pyproject.toml
│   │   ├── restmachine/
│   │   │   └── __init__.py
│   │   └── tests/
│   ├── restmachine-aws/
│   │   ├── pyproject.toml
│   │   ├── restmachine_aws/
│   │   │   └── __init__.py
│   │   └── tests/
│   └── restmachine-django/
│       ├── pyproject.toml
│       ├── restmachine_django/
│       │   └── __init__.py
│       └── tests/
├── scripts/
│   ├── detect-changes.sh
│   └── release-package.sh
└── pyproject.toml  # Workspace root
```

### Root pyproject.toml (Workspace)

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools_scm]
# This won't be used for packages, just for workspace tools

[tool.pytest.ini_options]
testpaths = ["packages/*/tests"]

[tool.mypy]
packages = ["packages"]
```

### Package Configuration

```toml
# packages/restmachine-core/pyproject.toml
[build-system]
requires = ["setuptools>=61.0", "setuptools_scm[toml]>=6.2"]
build-backend = "setuptools.build_meta"

[project]
name = "restmachine"
dynamic = ["version"]
dependencies = [
    "jinja2>=3.0.0",
]

[tool.setuptools_scm]
root = "../.."
tag_regex = "^restmachine-v(?P<version>.*)$"
write_to = "restmachine/_version.py"
```

```toml
# packages/restmachine-aws/pyproject.toml
[build-system]
requires = ["setuptools>=61.0", "setuptools_scm[toml]>=6.2"]
build-backend = "setuptools.build_meta"

[project]
name = "restmachine-aws"
dynamic = ["version"]
dependencies = [
    "restmachine>=1.0.0",  # Pin to major version
    "boto3>=1.26.0",
]

[tool.setuptools_scm]
root = "../.."
tag_regex = "^restmachine-aws-v(?P<version>.*)$"
write_to = "restmachine_aws/_version.py"
```

### GitHub Actions Workflow

```yaml
# .github/workflows/release.yml
name: Release Packages

on:
  push:
    tags:
      - 'restmachine-v*'      # Core package
      - 'restmachine-aws-v*'  # AWS package
      - 'restmachine-django-v*'  # Django package

jobs:
  detect-package:
    runs-on: ubuntu-latest
    outputs:
      package: ${{ steps.detect.outputs.package }}
      version: ${{ steps.detect.outputs.version }}
    steps:
      - name: Detect package from tag
        id: detect
        run: |
          TAG="${{ github.ref_name }}"
          if [[ $TAG == restmachine-v* ]]; then
            echo "package=core" >> $GITHUB_OUTPUT
            echo "version=${TAG#restmachine-v}" >> $GITHUB_OUTPUT
          elif [[ $TAG == restmachine-aws-v* ]]; then
            echo "package=aws" >> $GITHUB_OUTPUT
            echo "version=${TAG#restmachine-aws-v}" >> $GITHUB_OUTPUT
          elif [[ $TAG == restmachine-django-v* ]]; then
            echo "package=django" >> $GITHUB_OUTPUT
            echo "version=${TAG#restmachine-django-v}" >> $GITHUB_OUTPUT
          fi

  release:
    needs: detect-package
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
          pip install build twine

      - name: Build package
        run: |
          PACKAGE="${{ needs.detect-package.outputs.package }}"
          if [ "$PACKAGE" = "core" ]; then
            cd packages/restmachine-core
          elif [ "$PACKAGE" = "aws" ]; then
            cd packages/restmachine-aws
          elif [ "$PACKAGE" = "django" ]; then
            cd packages/restmachine-django
          fi
          python -m build

      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
        run: |
          PACKAGE="${{ needs.detect-package.outputs.package }}"
          if [ "$PACKAGE" = "core" ]; then
            cd packages/restmachine-core
          elif [ "$PACKAGE" = "aws" ]; then
            cd packages/restmachine-aws
          elif [ "$PACKAGE" = "django" ]; then
            cd packages/restmachine-django
          fi
          twine upload dist/*

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          generate_release_notes: true
```

### Script: Detect Changes

```bash
#!/bin/bash
# scripts/detect-changes.sh

# Get list of changed packages since last release
CHANGED_PACKAGES=()

for pkg in packages/*/; do
    pkg_name=$(basename "$pkg")

    # Get last tag for this package
    last_tag=$(git tag -l "${pkg_name}-v*" | sort -V | tail -1)

    if [ -z "$last_tag" ]; then
        # No previous release, check if package has changes
        if git diff --name-only HEAD~1 | grep -q "^packages/${pkg_name}/"; then
            CHANGED_PACKAGES+=("$pkg_name")
        fi
    else
        # Check changes since last tag
        if git diff --name-only "$last_tag" HEAD | grep -q "^packages/${pkg_name}/"; then
            CHANGED_PACKAGES+=("$pkg_name")
        fi
    fi
done

if [ ${#CHANGED_PACKAGES[@]} -eq 0 ]; then
    echo "No packages changed"
    exit 0
fi

echo "Changed packages:"
printf '%s\n' "${CHANGED_PACKAGES[@]}"
```

## Conventional Commits for Monorepos

### Commit Message Format

```bash
# Scope indicates package
feat(core): add XML rendering support
fix(aws): resolve Lambda timeout issue
docs(django): update integration guide

# Multiple packages
feat(core,aws): add shared logging interface

# Breaking changes
feat(core)!: redesign API interface

BREAKING CHANGE: removed deprecated render_html()
```

### Configuration

```toml
# .commitlintrc.toml
[rules]
  type-enum = [2, "always", [
    "feat", "fix", "docs", "style", "refactor",
    "perf", "test", "build", "ci", "chore", "revert"
  ]]

  scope-enum = [2, "always", [
    "core", "aws", "django", "deps", "release"
  ]]

  scope-empty = [2, "never"]  # Scope required for monorepo
```

## Cross-Package Dependencies

### Internal Dependencies

```toml
# packages/restmachine-aws/pyproject.toml
[project]
dependencies = [
    # Use version specifiers for published packages
    "restmachine>=1.0.0,<2.0.0",
]

[project.optional-dependencies]
dev = [
    # For local development, use editable install
    # pip install -e packages/restmachine-core
]
```

### Development Workflow

```bash
# Install all packages in editable mode
pip install -e packages/restmachine-core
pip install -e packages/restmachine-aws
pip install -e packages/restmachine-django

# Or use a script
for pkg in packages/*/; do
    pip install -e "$pkg"
done
```

### Dependency Version Synchronization

```python
# scripts/sync-versions.py
import tomli
import tomli_w
from pathlib import Path

def sync_core_version():
    """Ensure all packages depend on correct core version."""
    core_version = get_package_version("packages/restmachine-core")

    for pkg in Path("packages").iterdir():
        if pkg.name == "restmachine-core":
            continue

        pyproject = pkg / "pyproject.toml"
        with open(pyproject, "rb") as f:
            data = tomli.load(f)

        # Update dependency on core
        deps = data["project"]["dependencies"]
        for i, dep in enumerate(deps):
            if dep.startswith("restmachine"):
                deps[i] = f"restmachine>={core_version},<{next_major(core_version)}"

        with open(pyproject, "wb") as f:
            tomli_w.dump(data, f)
```

## Testing Strategy for Monorepos

### Test All Packages

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        package:
          - restmachine-core
          - restmachine-aws
          - restmachine-django
        python-version: ['3.9', '3.10', '3.11', '3.12']

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install package
        run: |
          pip install -e packages/${{ matrix.package }}[dev]

      - name: Run tests
        run: |
          cd packages/${{ matrix.package }}
          pytest
```

### Integration Tests

```python
# packages/integration-tests/test_cross_package.py
import pytest

def test_aws_uses_core():
    """Test AWS package integrates with core."""
    from restmachine import RestApplication, render
    from restmachine_aws import LambdaHandler

    app = RestApplication()
    handler = LambdaHandler(app)

    # Test they work together
    assert handler.app is app
```

## Recommended Setup for restmachine

If you plan to split into multiple packages:

```
restmachine-monorepo/
├── packages/
│   ├── restmachine/           # Core package
│   ├── restmachine-aws/       # AWS integrations
│   ├── restmachine-django/    # Django integration
│   ├── restmachine-fastapi/   # FastAPI integration
│   └── restmachine-cli/       # CLI tools
├── .github/workflows/
│   ├── test.yml              # Test all packages
│   ├── release.yml           # Release on tags
│   └── detect-changes.yml    # Detect what changed
└── scripts/
    ├── detect-changes.sh
    └── release-package.sh
```

**Release flow:**
1. Make changes to a package
2. Commit with conventional format: `feat(aws): add new feature`
3. Create PR, tests run for all packages
4. Merge to main
5. Tag release: `git tag restmachine-aws-v1.2.3`
6. CI/CD automatically releases just that package

## Resources

- [Monorepo Tools](https://monorepo.tools/)
- [Turborepo](https://turbo.build/repo)
- [Nx for Python](https://nx.dev/recipes/other/python)
- [Google's Monorepo Approach](https://research.google/pubs/pub45424/)
- [setuptools_scm monorepo support](https://setuptools-scm.readthedocs.io/en/latest/usage/#monorepos)
