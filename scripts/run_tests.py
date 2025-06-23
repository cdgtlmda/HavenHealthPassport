#!/usr/bin/env python3
"""Test runner configuration for Haven Health Passport.

This script provides various test execution configurations for different
testing scenarios.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


def run_command(cmd: list, env: dict = None) -> int:
    """Run a command with optional environment variables."""
    if env:
        full_env = os.environ.copy()
        full_env.update(env)
    else:
        full_env = os.environ.copy()
    
    print(f"Running: {' '.join(cmd)}")
    return subprocess.call(cmd, env=full_env, cwd=PROJECT_ROOT)


def run_unit_tests(args):
    """Run unit tests only."""
    cmd = [
        "pytest",
        "tests/unit",
        "-v",
        "-m", "unit",
        "--cov=src",
        "--cov-report=term-missing",
    ]
    
    if args.parallel:
        cmd.extend(["-n", str(args.workers)])
    
    if args.verbose:
        cmd.append("-vv")
    
    return run_command(cmd)


def run_integration_tests(args):
    """Run integration tests."""
    # Ensure test containers are running
    if args.with_docker:
        print("Starting test containers...")
        run_command(["docker-compose", "-f", "docker-compose.test.yml", "up", "-d"])
    
    cmd = [
        "pytest",
        "tests/integration",
        "-v",
        "-m", "integration",
        "--cov=src",
        "--cov-report=term-missing",
    ]
    
    if args.parallel:
        cmd.extend(["-n", str(args.workers)])
    
    env = {
        "DATABASE_URL": "postgresql://test:test@localhost:5433/haven_test",
        "REDIS_URL": "redis://localhost:6380/1",
    }
    
    return run_command(cmd, env)


def run_e2e_tests(args):
    """Run end-to-end tests."""
    cmd = [
        "pytest",
        "tests/e2e",
        "-v",
        "-m", "e2e",
        "--cov=src",
        "--cov-report=term-missing",
    ]
    
    if args.headed:
        env = {"HEADLESS": "false"}
    else:
        env = {"HEADLESS": "true"}
    
    return run_command(cmd, env)


def run_all_tests(args):
    """Run all test suites."""
    print("Running all tests...")
    
    # Run unit tests first
    print("\n=== Unit Tests ===")
    unit_result = run_unit_tests(args)
    
    if unit_result != 0 and args.fail_fast:
        return unit_result
    
    # Run integration tests
    print("\n=== Integration Tests ===")
    integration_result = run_integration_tests(args)
    
    if integration_result != 0 and args.fail_fast:
        return integration_result
    
    # Run E2E tests
    print("\n=== E2E Tests ===")
    e2e_result = run_e2e_tests(args)
    
    # Return non-zero if any test suite failed
    return unit_result or integration_result or e2e_result


def run_coverage_report(args):
    """Generate and display coverage report."""
    cmd = ["coverage", "report"]
    
    if args.html:
        run_command(["coverage", "html"])
        print(f"\nHTML coverage report generated at: {PROJECT_ROOT}/htmlcov/index.html")
    
    if args.xml:
        run_command(["coverage", "xml"])
        print(f"\nXML coverage report generated at: {PROJECT_ROOT}/coverage.xml")
    
    return run_command(cmd)


def run_specific_test(args):
    """Run a specific test file or test case."""
    cmd = [
        "pytest",
        args.test_path,
        "-v",
        "--cov=src",
        "--cov-report=term-missing",
    ]
    
    if args.debug:
        cmd.extend(["-s", "--pdb"])
    
    if args.keyword:
        cmd.extend(["-k", args.keyword])
    
    return run_command(cmd)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test runner for Haven Health Passport"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Test commands")
    
    # Unit tests
    unit_parser = subparsers.add_parser("unit", help="Run unit tests")
    unit_parser.add_argument("-p", "--parallel", action="store_true", help="Run tests in parallel")
    unit_parser.add_argument("-w", "--workers", type=int, default=4, help="Number of parallel workers")
    unit_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    # Integration tests
    integration_parser = subparsers.add_parser("integration", help="Run integration tests")
    integration_parser.add_argument("-p", "--parallel", action="store_true", help="Run tests in parallel")
    integration_parser.add_argument("-w", "--workers", type=int, default=2, help="Number of parallel workers")
    integration_parser.add_argument("-d", "--with-docker", action="store_true", help="Start Docker containers")
    
    # E2E tests
    e2e_parser = subparsers.add_parser("e2e", help="Run end-to-end tests")
    e2e_parser.add_argument("--headed", action="store_true", help="Run browser tests in headed mode")
    
    # All tests
    all_parser = subparsers.add_parser("all", help="Run all test suites")
    all_parser.add_argument("-f", "--fail-fast", action="store_true", help="Stop on first failure")
    all_parser.add_argument("-p", "--parallel", action="store_true", help="Run tests in parallel")
    all_parser.add_argument("-w", "--workers", type=int, default=4, help="Number of parallel workers")
    all_parser.add_argument("-d", "--with-docker", action="store_true", help="Start Docker containers")
    
    # Coverage report
    coverage_parser = subparsers.add_parser("coverage", help="Generate coverage report")
    coverage_parser.add_argument("--html", action="store_true", help="Generate HTML report")
    coverage_parser.add_argument("--xml", action="store_true", help="Generate XML report")
    
    # Specific test
    specific_parser = subparsers.add_parser("test", help="Run specific test")
    specific_parser.add_argument("test_path", help="Path to test file or directory")
    specific_parser.add_argument("-k", "--keyword", help="Test keyword expression")
    specific_parser.add_argument("-d", "--debug", action="store_true", help="Enable debugger on failure")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Ensure we're in the virtual environment
    if not os.environ.get("VIRTUAL_ENV"):
        print("Warning: Not running in a virtual environment!")
        print("Consider activating your virtual environment first.")
    
    # Execute the appropriate command
    if args.command == "unit":
        return run_unit_tests(args)
    elif args.command == "integration":
        return run_integration_tests(args)
    elif args.command == "e2e":
        return run_e2e_tests(args)
    elif args.command == "all":
        return run_all_tests(args)
    elif args.command == "coverage":
        return run_coverage_report(args)
    elif args.command == "test":
        return run_specific_test(args)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
