# Radon Code Quality Quick Start

This guide shows you how to use Radon for code quality checks in this project.

## Quick Commands

```bash
# Run all quality checks (part of standard tox run)
tox -e complexity

# Generate detailed reports with JSON output
tox -e complexity-report

# Run all checks including complexity
tox
```

## What Gets Checked

### 1. Cyclomatic Complexity (CC)

Measures code complexity - the number of independent paths through code.

**Example Output:**
```
packages/restmachine/src/restmachine/adapter.py
    M 210:4 ASGIAdapter._asgi_to_request - B (7)
```

- **Rating:** B (good)
- **Score:** 7 (out of target ≤10)
- **Location:** Line 210, method `_asgi_to_request`

### 2. Maintainability Index (MI)

Composite metric for code maintainability.

**Example Output:**
```
packages/restmachine/src/restmachine/application.py - B (9.34)
```

- **Rating:** B (acceptable)
- **Score:** 9.34 (out of target ≥10)

### 3. Raw Metrics

**Example Output:**
```
** Total **
    LOC: 7,501       # Total lines
    LLOC: 4,091      # Logical lines
    SLOC: 4,313      # Source lines
    Comments: 676    # Comment lines
    Comment %: 9%    # Comment ratio
```

## Interpreting Ratings

### Cyclomatic Complexity Ratings:
- **A (1-5):** ✅ Simple, low risk
- **B (6-10):** ✅ Moderate, acceptable
- **C (11-20):** ⚠️ Complex, needs review
- **D (21-30):** ❌ Very complex, refactor recommended
- **E (31-40):** ❌ Extremely complex, refactor required
- **F (41+):** ❌ Unmaintainable, must refactor

### Maintainability Index Ratings:
- **A (20-100):** ✅ Highly maintainable
- **B (10-19):** ✅ Moderately maintainable
- **C (0-9):** ⚠️ Low maintainability

## Current Project Status

✅ **Overall Average Complexity:** A (3.59)
✅ **Total Lines of Code:** 7,501
✅ **Comment Coverage:** 9% (676 comments)

**Areas for Improvement:**
- `state_machine.py`: C (6.67) MI - inherent to state machine pattern
- Several parsing methods in AWS adapter: D complexity

## Common Scenarios

### Check specific file
```bash
radon cc packages/restmachine/src/restmachine/adapter.py
```

### Check with different threshold
```bash
radon cc packages/restmachine/src/restmachine --min C
```

### Generate JSON report
```bash
radon cc packages/restmachine/src/restmachine --json --output-file=complexity.json
```

## Integration with CI/CD

The complexity check runs automatically as part of tox:

```yaml
# In GitHub Actions, GitLab CI, etc.
- run: tox -e complexity
```

This ensures code quality standards are maintained across all contributions.

## Learn More

- Full documentation: `docs/CODE_QUALITY_STANDARDS.md`
- Radon docs: https://radon.readthedocs.io/
- Cyclomatic Complexity: https://en.wikipedia.org/wiki/Cyclomatic_complexity
