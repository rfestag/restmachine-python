#!/usr/bin/env python3
"""
Multi-Server Comparison Example

This example demonstrates how to run the same RestMachine application
with different HTTP servers and configurations to compare their behavior.

This is useful for testing and benchmarking different server setups.
"""

import multiprocessing
import socket
import sys
import time
from typing import Dict

import requests
from restmachine import RestApplication


def create_benchmark_app() -> RestApplication:
    """Create a simple application for benchmarking."""
    app = RestApplication()

    @app.get("/")
    def home():
        return {"message": "Hello from RestMachine!", "timestamp": time.time()}

    @app.get("/fast")
    def fast_endpoint():
        return {"result": "fast", "data": list(range(10))}

    @app.get("/slow")
    def slow_endpoint():
        # Simulate some processing time
        time.sleep(0.1)
        return {"result": "slow", "processing_time": 0.1}

    @app.post("/echo")
    def echo_endpoint(json_body):
        return {"echoed": json_body, "length": len(str(json_body))}

    @app.get("/error")
    def error_endpoint():
        raise Exception("Test error for error handling benchmark")

    return app


def run_server_process(server_type: str, http_version: str, port: int):
    """Run a server in a separate process."""
    try:
        # Create a new application in the subprocess
        app = create_benchmark_app()

        if server_type == "uvicorn":
            from restmachine.servers import UvicornDriver
            driver = UvicornDriver(
                app,
                host="127.0.0.1",
                port=port,
                http_version=http_version
            )
            if driver.is_available():
                driver.run(log_level="error", workers=1)
        elif server_type == "hypercorn":
            from restmachine.servers import HypercornDriver
            driver = HypercornDriver(
                app,
                host="127.0.0.1",
                port=port,
                http_version=http_version
            )
            if driver.is_available():
                driver.run(log_level="ERROR", workers=1)
    except Exception as e:
        print(f"Server error in {server_type}: {e}")


class ServerRunner:
    """Helper class to run servers in background processes."""

    def __init__(self, server_type: str, http_version: str = "http1", port: int = 8000):
        self.server_type = server_type
        self.http_version = http_version
        self.port = port
        self.process = None

    def start(self):
        """Start the server in a background process."""
        self.process = multiprocessing.Process(
            target=run_server_process,
            args=(self.server_type, self.http_version, self.port)
        )
        self.process.start()

        # Wait for server to start and test connectivity
        max_attempts = 20
        for attempt in range(max_attempts):
            try:
                response = requests.get(f"http://127.0.0.1:{self.port}/", timeout=1)
                if response.status_code == 200:
                    return True
            except (requests.exceptions.RequestException, ConnectionError):
                time.sleep(0.5)

        return False

    def stop(self):
        """Stop the server."""
        if self.process and self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join()


def benchmark_endpoint(base_url: str, endpoint: str, num_requests: int = 10) -> Dict:
    """Benchmark a specific endpoint."""
    url = f"{base_url}{endpoint}"
    times = []
    errors = 0

    print(f"  Benchmarking {endpoint}...")

    for _ in range(num_requests):
        start_time = time.time()
        try:
            response = requests.get(url, timeout=5)
            end_time = time.time()
            times.append(end_time - start_time)
            if response.status_code >= 400:
                errors += 1
        except Exception:
            end_time = time.time()
            times.append(end_time - start_time)
            errors += 1

    if times:
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
    else:
        avg_time = min_time = max_time = 0

    return {
        "endpoint": endpoint,
        "requests": num_requests,
        "errors": errors,
        "avg_time": avg_time,
        "min_time": min_time,
        "max_time": max_time,
        "success_rate": ((num_requests - errors) / num_requests) * 100
    }


def find_available_port(start_port: int = 8000) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    raise RuntimeError("No available ports found")


def test_server_configuration(server_type: str, http_version: str, base_port: int):
    """Test a specific server configuration."""
    print(f"\n{'='*60}")
    print(f"Testing {server_type.upper()} with {http_version.upper()}")
    print(f"{'='*60}")

    try:
        # Check if server is available first
        if server_type == "uvicorn":
            from restmachine.servers import UvicornDriver
            dummy_app = create_benchmark_app()
            driver = UvicornDriver(dummy_app)
            if not driver.is_available():
                print(f"❌ {server_type} not available")
                return None
        elif server_type == "hypercorn":
            from restmachine.servers import HypercornDriver
            dummy_app = create_benchmark_app()
            driver = HypercornDriver(dummy_app)
            if not driver.is_available():
                print(f"❌ {server_type} not available")
                return None

        # Find an available port
        port = find_available_port(base_port)
        server = ServerRunner(server_type, http_version, port)

        print(f"✅ Starting {server_type} on port {port}...")

        # Start server and wait for it to be ready
        if server.start():
            print(f"✅ Server responding on http://127.0.0.1:{port}")
        else:
            print("❌ Server failed to start or become ready")
            return None

        base_url = f"http://127.0.0.1:{port}"

        # Run benchmarks
        endpoints = ["/", "/fast", "/slow"]
        results = []

        for endpoint in endpoints:
            result = benchmark_endpoint(base_url, endpoint)
            results.append(result)

        # Test POST endpoint
        try:
            post_response = requests.post(
                f"{base_url}/echo",
                json={"test": "data", "numbers": [1, 2, 3]},
                timeout=5
            )
            post_success = post_response.status_code == 200
        except Exception:
            post_success = False

        # Test error handling
        try:
            error_response = requests.get(f"{base_url}/error", timeout=5)
            error_handled = error_response.status_code == 500
        except Exception:
            error_handled = False

        print(f"\nResults for {server_type} ({http_version}):")
        print("-" * 50)
        for result in results:
            print(f"{result['endpoint']:10} | "
                  f"Avg: {result['avg_time']*1000:6.2f}ms | "
                  f"Min: {result['min_time']*1000:6.2f}ms | "
                  f"Max: {result['max_time']*1000:6.2f}ms | "
                  f"Success: {result['success_rate']:5.1f}%")

        print("\nAdditional Tests:")
        print(f"POST /echo:  {'✅ Working' if post_success else '❌ Failed'}")
        print(f"Error handling: {'✅ Working' if error_handled else '❌ Failed'}")

        return {
            "server": server_type,
            "http_version": http_version,
            "port": port,
            "benchmarks": results,
            "post_test": post_success,
            "error_test": error_handled
        }

    except Exception as e:
        print(f"❌ Error testing {server_type}: {e}")
        return None
    finally:
        server.stop()
        time.sleep(1)  # Give server time to shut down


def main():
    """Main function to run server comparisons."""
    # Ensure multiprocessing works correctly
    multiprocessing.set_start_method('spawn', force=True)

    print("RestMachine Multi-Server Comparison")
    print("=" * 60)

    configurations = [
        ("uvicorn", "http1", 8001),
        ("uvicorn", "http2", 8002),
        ("hypercorn", "http1", 8003),
        ("hypercorn", "http2", 8004),
    ]

    results = []

    for server_type, http_version, base_port in configurations:
        result = test_server_configuration(server_type, http_version, base_port)
        if result:
            results.append(result)

    # Summary
    if results:
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"{'Server':<15} {'HTTP':<6} {'Avg Time':<10} {'Success Rate':<12}")
        print("-" * 50)

        for result in results:
            # Calculate overall average time
            avg_times = [b['avg_time'] for b in result['benchmarks']]
            overall_avg = sum(avg_times) / len(avg_times) if avg_times else 0

            # Calculate overall success rate
            success_rates = [b['success_rate'] for b in result['benchmarks']]
            overall_success = sum(success_rates) / len(success_rates) if success_rates else 0

            print(f"{result['server']:<15} "
                  f"{result['http_version']:<6} "
                  f"{overall_avg*1000:8.2f}ms "
                  f"{overall_success:10.1f}%")

    else:
        print("\n❌ No servers were successfully tested.")
        print("Make sure you have the required dependencies installed:")
        print("  pip install 'restmachine[server]'")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError running benchmark: {e}")
        sys.exit(1)