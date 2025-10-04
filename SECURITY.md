# Security Guidelines

This project includes comprehensive security scanning tools to help identify vulnerabilities and follow security best practices.

## Security Scanning Tools

### 1. Static Application Security Testing (SAST)

#### Bandit - Python Security Linter
- **Purpose**: Finds common security issues in Python code
- **Run**: `tox -e bandit`
- **Config**: `pyproject.toml` under `[tool.bandit]`
- **Reports**: Console output + `bandit-report.sarif` (SARIF format for GitHub Security tab)

#### Semgrep - Advanced SAST (Optional)
- **Purpose**: Advanced pattern-based security scanning
- **Run**: `tox -e semgrep`
- **Reports**: Console output + `semgrep-report.json`

### 2. Dependency Vulnerability Scanning

#### pip-audit - Dependency Security Scanner
- **Purpose**: Checks dependencies for known vulnerabilities
- **Run**: `tox -e pip-audit`
- **Reports**: Console output + `pip-audit-report.md` (Markdown format)
- **Database**: Uses PyPI vulnerability database

### 3. Secret Detection

#### Detect-Secrets - Secret Scanner
- **Purpose**: Scans for hardcoded secrets, API keys, tokens
- **Run**: `tox -e secrets`
- **Config**: `pyproject.toml` under `[tool.detect-secrets]`
- **Baseline**: `.secrets.baseline` (tracks known false positives)

## Running Security Scans

### Run All Security Scans
```bash
tox -e security
```

### Run Individual Scans
```bash
# SAST scanning
tox -e bandit

# Dependency vulnerabilities
tox -e pip-audit

# Secret detection
tox -e secrets

# Advanced SAST (optional)
tox -e semgrep
```

## Current Security Issues

### High Severity
✅ **Resolved**: All high-severity issues have been fixed.

### Low Severity
6 instances of **Try/Except/Pass** patterns in `restmachine/state_machine.py`
   - **Issue**: Silent exception handling can mask errors
   - **Recommendation**: Add logging or more specific exception handling

## Security Best Practices

1. **Regular Scanning**: Run security scans before each release
2. **Dependency Updates**: Keep dependencies updated to latest secure versions
3. **Code Review**: Review security scan results during code review process
4. **CI Integration**: Add security scans to your CI/CD pipeline

## CI/CD Integration

### GitHub Actions

This project includes automated security scanning as part of the CI workflow. The security job:
- Runs on every push to `main` and `develop` branches
- Runs on all pull requests to `main`
- Runs weekly on Monday at 9am UTC (scheduled scan)
- Uploads Bandit results to GitHub Security tab (SARIF format)
- Uploads pip-audit markdown reports as artifacts

**View security findings**: Navigate to the **Security** tab → **Code scanning** in GitHub to see Bandit findings.

The security scans run in parallel with unit tests, linting, and type checking as part of the CI pipeline.

Manual workflow example:

```yaml
security:
  runs-on: ubuntu-latest
  permissions:
    security-events: write
    contents: read

  steps:
  - uses: actions/checkout@v4

  - name: Set up Python
    uses: actions/setup-python@v4
    with:
      python-version: "3.11"

  - name: Run security scans
    run: |
      pip install tox
      tox -e security

  - name: Upload Bandit SARIF to Security tab
    uses: github/codeql-action/upload-sarif@v3
    if: always()
    with:
      sarif_file: bandit-report.sarif
      category: bandit

  - name: Upload pip-audit report
    uses: actions/upload-artifact@v4
    if: always()
    with:
      name: pip-audit-report
      path: pip-audit-report.md
```

## Suppressing False Positives

### Bandit
Add `# nosec` comment to suppress specific warnings:
```python
import hashlib
password_hash = hashlib.md5(password.encode()).hexdigest()  # nosec B324
```

### Detect-Secrets
Add false positives to `.secrets.baseline`:
```bash
detect-secrets scan --baseline .secrets.baseline --update
```

## Security Contact

For security vulnerabilities, please follow responsible disclosure:
1. Do not open public issues for security vulnerabilities
2. Email security concerns to: [your-security-email]
3. Include detailed reproduction steps and impact assessment

## Compliance

This security setup helps maintain compliance with:
- OWASP Top 10 security risks
- Common security vulnerabilities (CWE)
- Python security best practices
- Open source security standards
