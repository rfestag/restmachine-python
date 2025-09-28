# Security Guidelines

This project includes comprehensive security scanning tools to help identify vulnerabilities and follow security best practices.

## Security Scanning Tools

### 1. Static Application Security Testing (SAST)

#### Bandit - Python Security Linter
- **Purpose**: Finds common security issues in Python code
- **Run**: `tox -e bandit`
- **Config**: `pyproject.toml` under `[tool.bandit]`
- **Reports**: Console output + `bandit-report.json`

#### Semgrep - Advanced SAST (Optional)
- **Purpose**: Advanced pattern-based security scanning
- **Run**: `tox -e semgrep`
- **Reports**: Console output + `semgrep-report.json`

### 2. Dependency Vulnerability Scanning

#### pip-audit - Dependency Security Scanner
- **Purpose**: Checks dependencies for known vulnerabilities
- **Run**: `tox -e pip-audit`
- **Reports**: Console output + `pip-audit-report.json`
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

Add this to your GitHub Actions workflow:

```yaml
- name: Security Scans
  run: |
    pip install tox
    tox -e security
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
