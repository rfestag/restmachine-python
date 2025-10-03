"""
Performance benchmarks for RestMachine framework.

This package contains performance tests that run across all drivers
to measure and track performance metrics for common operations.

Test files:
- test_basic_operations.py: Benchmarks for GET, POST, PUT, DELETE
- test_routing.py: Benchmarks for routing with path/query params
- test_json_handling.py: Benchmarks for JSON serialization/deserialization

Usage:
    # Run all benchmarks and save baselines
    pytest packages/restmachine/tests/performance --benchmark-autosave

    # Compare against baseline
    pytest packages/restmachine/tests/performance --benchmark-compare

    # Fail if performance degrades more than 5%
    pytest packages/restmachine/tests/performance --benchmark-compare-fail=min:5%
"""
