# RestMachine Performance Benchmarks

This directory contains performance benchmarks for the RestMachine framework. These tests run across all drivers to measure and track performance metrics for common operations.

**Note:** Performance tests are **excluded by default** when running pytest. Use `-m performance` to run them explicitly, or use the `tox -e benchmark` commands.

## Test Files

- **test_basic_operations.py**: Benchmarks for GET, POST, PUT, DELETE operations
- **test_routing.py**: Benchmarks for routing with path and query parameters
- **test_json_handling.py**: Benchmarks for JSON serialization/deserialization with various payload sizes

## Running Benchmarks

### Using Tox (Recommended)

```bash
# Run benchmarks on direct driver only (fastest - for quick iterations)
# Groups results so same test across parameters appears together
tox -e benchmark

# Run benchmarks across ALL drivers (direct, uvicorn, hypercorn, aws)
# Shows same test across all 5 drivers side-by-side for easy comparison
tox -e benchmark-all

# Compare against baselines (fails if performance degrades > 5%)
tox -e benchmark-compare

# Run with detailed statistics and histogram
tox -e benchmark-verbose
```

**Output format:** All commands now use `--benchmark-group-by=func` to group results by test name, making it easy to compare the same test across different drivers side-by-side.

### Using Pytest Directly

**Important:** Performance tests are excluded by default. When running specific performance test files/tests, you must override the marker filter with `-m performance` or `-m ""`.

```bash
# Run all performance tests across ALL drivers (grouped by test name)
pytest -m performance --benchmark-only --benchmark-group-by=func --benchmark-columns=min,mean,median

# Run performance tests on direct driver only
pytest packages/restmachine/tests/performance -m performance --benchmark-only --benchmark-group-by=func

# Run specific performance test across all drivers
pytest -m performance -k "test_get_simple_response" --benchmark-only --benchmark-group-by=func

# Save baselines with grouped output
pytest -m performance --benchmark-only --benchmark-autosave --benchmark-group-by=func --benchmark-storage=file://packages/restmachine/tests/performance/baselines

# Compare against previous run
pytest packages/restmachine/tests/performance -m performance --benchmark-compare --benchmark-group-by=func

# Show only specific columns (cleaner output)
pytest -m performance --benchmark-only --benchmark-group-by=func --benchmark-columns=min,mean,median

# Sort results alphabetically
pytest -m performance --benchmark-only --benchmark-group-by=func --benchmark-sort=name
```

**See [BENCHMARK_OPTIONS.md](./BENCHMARK_OPTIONS.md) for complete formatting options.**


## Baseline Storage

Benchmark baselines are stored in `packages/restmachine/tests/performance/baselines/` directory. Each driver maintains separate baseline files.

**Note:** Add baseline files to `.gitignore` if you don't want to commit them, or commit them to track performance over time.

## Multi-Driver Testing

All performance tests inherit from `MultiDriverTestBase`, which means they automatically run across all configured drivers:

- **direct**: Direct RestMachine driver (no HTTP server) - ~40 μs per request
- **uvicorn-http1**: Uvicorn HTTP/1.1 server (requires restmachine-uvicorn package) - ~550 μs per request
- **hypercorn-http1**: Hypercorn HTTP/1.1 server (requires restmachine-hypercorn package) - ~750 μs per request
- **hypercorn-http2**: Hypercorn HTTP/2 server (requires restmachine-hypercorn package) - ~1200 μs per request
- **aws-lambda**: AWS Lambda driver (requires restmachine-aws package) - varies by deployment

The performance tests are automatically included in each driver package's test suite, so you can measure and compare performance across all deployment environments.

## Understanding Results

pytest-benchmark provides comprehensive statistics for each test:

```
Name (time in us)              Min       Max      Mean    StdDev    Median
---------------------------------------------------------------------------
test_get_simple_response     156.2     289.4     167.8      12.3     165.1
```

- **Min/Max**: Fastest and slowest execution times
- **Mean**: Average execution time across all rounds
- **StdDev**: Standard deviation (lower is more consistent)
- **Median**: Middle value (less affected by outliers)

## CI/CD Integration

To integrate with CI/CD pipelines:

1. **Save baselines** from main branch:
   ```bash
   tox -e benchmark
   git add packages/restmachine/tests/performance/baselines/
   git commit -m "Update performance baselines"
   ```

2. **Compare in PR builds**:
   ```bash
   tox -e benchmark-compare
   ```

3. **Fail builds on regression** (5% threshold):
   ```bash
   pytest packages/restmachine/tests/performance --benchmark-compare-fail=min:5%
   ```

## Writing New Benchmarks

Create new test classes that inherit from `MultiDriverTestBase`:

```python
from restmachine import RestApplication
from tests.framework import MultiDriverTestBase

class TestMyFeaturePerformance(MultiDriverTestBase):
    def create_app(self) -> RestApplication:
        app = RestApplication()

        @app.get("/my-endpoint")
        def my_handler():
            return {"data": "value"}

        return app

    def test_my_feature_performance(self, api, benchmark):
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/my-endpoint")

        data = api_client.expect_successful_retrieval(result)
        assert data["data"] == "value"
```

## Excluding Performance Tests by Default

Performance tests are automatically excluded from normal test runs to keep them fast. This is configured in `pyproject.toml`:

```toml
addopts = "-v --tb=short -m 'not performance'"
```

**To verify exclusion:**
```bash
$ pytest --collect-only -q
============== 1031/1059 tests collected (28 deselected) in 0.28s ==============
                                     ^^^^^^^^^^^^
                              28 performance tests excluded
```

**To run ONLY performance tests:**
```bash
pytest -m performance               # All performance tests
pytest -m performance -v            # With verbose output
tox -e benchmark                    # Using tox (recommended)
```

**To run ALL tests (including performance):**
```bash
pytest -m ""                        # Override marker selection
```

## Tips

- **Focus on common cases**: Don't benchmark every edge case, focus on the most frequently used operations
- **Consistent environment**: Run benchmarks on the same machine/environment for accurate comparisons
- **Warm-up rounds**: pytest-benchmark automatically performs warm-up rounds to ensure stable measurements
- **Statistical significance**: Tests run multiple rounds (min 5) to ensure statistical validity
- **Keep them excluded**: Performance tests slow down test runs, so keep them excluded from regular testing
