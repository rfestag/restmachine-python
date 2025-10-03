# Benchmark Output Formatting Options

## Quick Reference

### Group same test across all drivers (RECOMMENDED)
```bash
pytest -m performance --benchmark-only --benchmark-group-by=func --benchmark-columns=min,mean,median
```

**Output example:**
```
----------------------------------- benchmark 'test_get_simple_response': 5 tests -----------------------------------
Name (time in us)                                  Min        Mean      Median
---------------------------------------------------------------------------------------
test_get_simple_response[driver-aws_lambda]     38.86      40.40       39.98
test_get_simple_response[driver-direct]         37.00      44.58       43.30
test_get_simple_response[driver-hypercorn-http1] 1,027     1,241      1,213
test_get_simple_response[driver-hypercorn-http2] 1,020     1,220      1,224
test_get_simple_response[driver-uvicorn-http1]   802       965        930
---------------------------------------------------------------------------------------
```

### Group by driver (all tests for one driver together)
```bash
pytest -m performance --benchmark-only --benchmark-group-by=param --benchmark-columns=min,mean,median
```

Tests will be grouped by the `driver-*` parameter, so all direct tests together, all aws tests together, etc.

### Minimal output (just essential stats)
```bash
pytest -m performance --benchmark-only --benchmark-columns=min,mean,median
```

### Full output (all statistics)
```bash
pytest -m performance --benchmark-only --benchmark-columns=min,max,mean,stddev,median,iqr,outliers,ops,rounds,iterations
```

### Sort options
```bash
# Sort by test name (alphabetically)
--benchmark-sort=name

# Sort by mean execution time (fastest first)
--benchmark-sort=mean

# Sort by minimum time
--benchmark-sort=min
```

## Column Options

Available columns for `--benchmark-columns`:

| Column | Description |
|--------|-------------|
| `min` | Minimum execution time |
| `max` | Maximum execution time |
| `mean` | Average execution time |
| `stddev` | Standard deviation (consistency) |
| `median` | Middle value (less affected by outliers) |
| `iqr` | Interquartile range |
| `outliers` | Number of outlier measurements |
| `ops` | Operations per second |
| `rounds` | Number of measurement rounds |
| `iterations` | Iterations per round |

## Common Use Cases

### 1. Quick comparison across drivers
```bash
tox -e benchmark-all
# Uses: --benchmark-group-by=func --benchmark-columns=min,mean,median
```

### 2. Detailed analysis with all statistics
```bash
pytest -m performance --benchmark-only --benchmark-group-by=func
# Shows all columns by default
```

### 3. Focus on specific driver
```bash
pytest packages/restmachine/tests/performance -m performance --benchmark-only --benchmark-columns=min,mean,median
# Only shows direct driver
```

### 4. Compare specific test across drivers
```bash
pytest -m performance -k "test_get_simple_response" --benchmark-only --benchmark-group-by=func
```

### 5. Generate histogram
```bash
pytest -m performance --benchmark-only --benchmark-histogram --benchmark-group-by=func
# Creates histogram image files in .benchmarks directory
```

## Example Commands

### Clean, focused output for all drivers
```bash
pytest -m performance --benchmark-only \
    --benchmark-group-by=func \
    --benchmark-columns=min,mean,median \
    --benchmark-sort=name
```

### Save baseline and group by function
```bash
pytest -m performance --benchmark-only \
    --benchmark-autosave \
    --benchmark-group-by=func \
    --benchmark-columns=min,mean,median \
    --benchmark-storage=file://packages/restmachine/tests/performance/baselines
```

### Compare against baseline
```bash
pytest -m performance --benchmark-only \
    --benchmark-compare \
    --benchmark-group-by=func \
    --benchmark-columns=min,mean,median \
    --benchmark-storage=file://packages/restmachine/tests/performance/baselines
```

## Tox Command Defaults

All tox benchmark commands now use these optimized defaults:
- `--benchmark-group-by=func` - Group same test across drivers
- `--benchmark-columns=min,mean,median` - Show only essential stats
- `--benchmark-sort=name` - Sort alphabetically (benchmark-all only)

To override, pass extra args to tox:
```bash
tox -e benchmark-all -- --benchmark-columns=min,max,mean,stddev,median
```
