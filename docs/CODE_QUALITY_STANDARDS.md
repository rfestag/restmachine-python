# Code Quality and Complexity Standards

This project uses [Radon](https://radon.readthedocs.io/) to ensure code maintainability and manageable complexity.

## Running Quality Checks

```bash
# Run standard quality checks (enforces standards)
tox -e complexity

# Generate detailed reports with JSON output
tox -e complexity-report
```

## Metrics and Standards

### Cyclomatic Complexity (CC)

Cyclomatic Complexity measures the number of linearly independent paths through a program's source code.

**Rating Scale:**
- **A**: 1-5 (simple, low risk)
- **B**: 6-10 (moderate complexity, medium risk)
- **C**: 11-20 (complex, high risk)
- **D**: 21-30 (very complex, very high risk)
- **E**: 31-40 (extremely complex, extremely high risk)
- **F**: 41+ (unmaintainable, needs refactoring)

**Our Standard:** Functions should be **B or better** (CC ≤ 10)

**Current Average:** A (3.59) ✅

### Maintainability Index (MI)

The Maintainability Index is a composite metric combining:
- Halstead Volume
- Cyclomatic Complexity
- Lines of Code
- Percent of Comments

**Rating Scale:**
- **A**: 20-100 (highly maintainable)
- **B**: 10-19 (moderately maintainable)
- **C**: 0-9 (low maintainability, needs attention)

**Our Standard:** Files should be **B or better** (MI ≥ 10)

**Current Status:**
- Most files: A or B ✅
- `state_machine.py`: C (6.67) ⚠️  (needs refactoring)

### Raw Metrics

**Total Project Stats:**
- **LOC (Lines of Code):** 7,501
- **LLOC (Logical Lines of Code):** 4,091
- **SLOC (Source Lines of Code):** 4,313
- **Comments:** 676
- **Comment Percentage:** 9% of total lines, 16% of source lines

## Interpreting Results

### High Complexity Areas

Functions with complexity ratings of C or higher indicate areas that may benefit from refactoring:

**Current High-Complexity Functions:**

1. **`RequestStateMachine.state_execute_and_render`** - F (49)
   - Location: `packages/restmachine/src/restmachine/state_machine.py:851`
   - This is the main state machine execution function
   - High complexity is inherent to the state machine pattern

2. **`RequestStateMachine.process_request`** - E (35)
   - Location: `packages/restmachine/src/restmachine/state_machine.py:171`
   - Entry point for request processing
   - Complexity from coordinating multiple state transitions

3. **`AwsApiGatewayAdapter._parse_alb_event`** - D (23)
   - Location: `packages/restmachine-aws/src/restmachine_aws/adapter.py:270`
   - Handles multiple ALB event formats and edge cases
   - Consider extracting helper methods

4. **`AwsApiGatewayAdapter._parse_apigw_v2_event`** - D (21)
   - Location: `packages/restmachine-aws/src/restmachine_aws/adapter.py:188`
   - Parses v2 API Gateway events
   - Could benefit from extraction of parsing logic

5. **`AwsApiGatewayAdapter._parse_apigw_v1_event`** - C (19)
   - Location: `packages/restmachine-aws/src/restmachine_aws/adapter.py:113`
   - Parses v1 API Gateway events
   - Similar structure to v2, extraction opportunity

## Refactoring Guidelines

When a function exceeds the complexity threshold:

1. **Extract Methods:** Break down complex functions into smaller, focused methods
2. **Reduce Conditionals:** Use lookup tables, polymorphism, or strategy pattern
3. **Simplify Logic:** Flatten nested conditions, use early returns
4. **Add Comments:** Explain complex business logic
5. **Consider Patterns:** State machines, strategy, or command patterns for complex flows

## Example: Reducing Complexity

**Before (High Complexity):**
```python
def process_data(data):
    if data:
        if data.type == 'A':
            if data.valid:
                return process_type_a(data)
            else:
                return error_response()
        elif data.type == 'B':
            if data.valid:
                return process_type_b(data)
            else:
                return error_response()
        else:
            return unknown_type()
    else:
        return no_data()
```

**After (Lower Complexity):**
```python
def process_data(data):
    if not data:
        return no_data()

    if not data.valid:
        return error_response()

    processors = {
        'A': process_type_a,
        'B': process_type_b,
    }

    processor = processors.get(data.type)
    if processor:
        return processor(data)

    return unknown_type()
```

## CI/CD Integration

The complexity checks are part of the standard tox run:

```bash
tox  # Runs all checks including complexity
```

This ensures:
- New code meets quality standards
- Complexity doesn't creep up over time
- Team maintains consistent code quality

## Tools

- **Radon:** https://radon.readthedocs.io/
- **Cyclomatic Complexity:** https://en.wikipedia.org/wiki/Cyclomatic_complexity
- **Maintainability Index:** https://docs.microsoft.com/en-us/visualstudio/code-quality/code-metrics-values

## Exceptions

The state machine implementation (`state_machine.py`) is allowed to have lower maintainability due to:
- Inherent complexity of the webmachine-style state machine pattern
- Sequential state transitions require coordinated logic
- Performance requirements (state machine is hot path)

However, we should:
- Add comprehensive comments
- Keep individual state methods simple (mostly B or better ✅)
- Consider refactoring the main execution loop in future versions
