# GitHub Actions Workflows

This project uses a hybrid workflow approach that separates concerns by trigger and purpose.

## Workflow Files

### `ci.yml` - Continuous Integration
**Triggers:**
- Push to `main` and `develop` branches
- Pull requests to `main`
- Weekly schedule (Monday 9am UTC)

**Jobs:**
- `test` - Matrix testing across Python 3.9-3.13
  - Generates coverage badge (Python 3.13 on main)
  - Generates complexity badge (Python 3.13 on main)
  - Commits badges to repository (Python 3.13 on main)
- `lint` - Code style checks with ruff
- `type-check` - Type safety with mypy
- `security` - Security scanning
  - Runs bandit (SARIF format)
  - Runs pip-audit (Markdown format)
  - Uploads SARIF to GitHub Security tab
  - Uploads reports as artifacts
- `build` - Package building and validation
  - Only runs on `main` branch or tags
  - Uploads build artifacts (30-day retention)

**Dependencies:** Build requires test, lint, type-check, and security to pass

### `publish.yml` - PyPI Publishing
**Triggers:**
- Push to version tags (`v*`)

**Jobs:**
- `build` - Build the package
- `publish` - Publish to PyPI
  - Uses official PyPA publish action
  - Supports trusted publishing (OIDC)
  - Requires `PYPI_API_TOKEN` secret

**Dependencies:** Publish requires build to complete

### `codeql.yml` - Advanced Security Analysis
**Triggers:**
- Push to `main` and `develop` branches
- Pull requests to `main`
- Weekly schedule (Monday 10am UTC)

**Jobs:**
- `analyze` - CodeQL security analysis
  - Scans for security vulnerabilities
  - Detects code quality issues
  - Uses `security-and-quality` query suite
  - Uploads results to GitHub Security tab

**Language:** Python

## Automated Dependency Management

### Dependabot Configuration (`.github/dependabot.yml`)

Dependabot automatically creates pull requests for dependency updates:

**Python Dependencies:**
- Checks weekly (Monday 9am UTC)
- Groups minor/patch updates together
- Separate groups for development vs production dependencies
- Max 10 open PRs

**GitHub Actions Dependencies:**
- Checks weekly (Monday 9am UTC)
- Keeps workflow actions up to date
- Max 5 open PRs

All Dependabot PRs are automatically labeled and assigned for review.

## Workflow Design

### Why This Structure?

1. **Separation of Concerns**
   - CI validates code quality (testing, linting, security)
   - Publishing is isolated with different triggers and permissions

2. **Tox Integration**
   - All quality checks use tox environments
   - Consistent behavior between local and CI
   - Easy to add new checks

3. **Security Integration**
   - Security runs on every PR for early feedback
   - Weekly scheduled scans for dependency updates
   - SARIF upload requires same-workflow execution

4. **Build Validation**
   - Build runs on main to catch packaging issues early
   - Artifacts retained for 30 days
   - Separate from publishing for safety

## Badge URLs

- **Build Status:** `https://github.com/rfestag/restmachine-python/workflows/CI/badge.svg`
- **Coverage:** `https://raw.githubusercontent.com/rfestag/restmachine-python/main/coverage-badge.svg`
- **Code Quality:** `https://raw.githubusercontent.com/rfestag/restmachine-python/main/complexity-badge.svg`

## Security Findings

View security scan results:
- **GitHub Security Tab** → **Code scanning**
  - **bandit** - SAST security issues
  - **CodeQL** - Advanced security and quality analysis
- **CI Artifacts** → `security-reports` or `pip-audit-report`
- **Dependabot** → **Pull requests** tab (dependency vulnerabilities)

## Running Workflows Locally

All CI checks can be run locally using tox:

```bash
# Run all tests (matches CI matrix)
tox

# Individual checks
tox -e lint          # Code style
tox -e type-check    # Type safety
tox -e security      # Security scans
tox -e build         # Build package

# Build for publishing
python -m build
twine check dist/*
```

## Workflow Dependencies

```
ci.yml:
  ├── test (matrix: py3.9-3.13)
  ├── lint
  ├── type-check
  ├── security ──→ SARIF upload to Security tab
  └── build (depends on all above)

publish.yml (on tags):
  ├── build
  └── publish (depends on build)

codeql.yml (parallel to CI):
  └── analyze ──→ SARIF upload to Security tab

Automated:
  ├── dependabot ──→ Creates PRs for dependency updates
  └── scheduled scans (weekly)
      ├── ci.yml security job (Monday 9am UTC)
      └── codeql.yml (Monday 10am UTC)
```
