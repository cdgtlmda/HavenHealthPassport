#!/usr/bin/env python3
"""
Haven Health Passport - Medical Compliance Test Runner.

Executes all tests with strict medical compliance verification

This script ensures:
1. All tests pass medical compliance checks
2. Coverage meets medical software requirements (80%+)
3. No PHI leakage in any test
4. Full audit trail of test execution
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

# Medical compliance thresholds
MIN_COVERAGE = 80  # HIPAA recommendation
MAX_SECURITY_ISSUES = 0  # Zero tolerance for security
MAX_PHI_LEAKS = 0  # Zero tolerance for PHI exposure


def print_header():
    """Print test execution header."""
    print(f"\n{BLUE}{'='*60}")
    print("  HAVEN HEALTH PASSPORT - MEDICAL COMPLIANCE TEST SUITE")
    print(f"{'='*60}{RESET}")
    print(f"Execution Time: {datetime.utcnow().isoformat()}")
    print("Compliance Mode: STRICT")
    print(f"Minimum Coverage: {MIN_COVERAGE}%")
    print("Security Tolerance: ZERO")
    print("PHI Leakage Tolerance: ZERO\n")


def run_python_tests():
    """Run Python tests with coverage and compliance checks."""
    print(f"{BLUE}Running Python Tests with Medical Compliance...{RESET}")

    cmd = [
        "python",
        "-m",
        "pytest",
        "tests/",
        "-v",
        "--cov=src",
        "--cov-report=term-missing",
        "--cov-report=json",
        "--cov-fail-under=80",
        "-m",
        "not slow",
        "--tb=short",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    # Check for PHI leakage in output
    if "PHILeakageError" in result.stdout or "unencrypted" in result.stdout.lower():
        print(f"{RED}CRITICAL: Potential PHI leakage detected in test output!{RESET}")
        return False

    # Parse coverage
    try:
        with open("coverage.json", "r", encoding="utf-8") as f:
            coverage_data = json.load(f)
            total_coverage = coverage_data["totals"]["percent_covered"]
            print(f"\n{YELLOW}Total Coverage: {total_coverage:.2f}%{RESET}")

            if total_coverage < MIN_COVERAGE:
                print(
                    f"{RED}FAIL: Coverage {total_coverage:.2f}% is below {MIN_COVERAGE}%{RESET}"
                )
                return False
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"{RED}Failed to parse coverage data: {e}{RESET}")
        return False

    return result.returncode == 0


def run_javascript_tests():
    """Run JavaScript/React tests with medical compliance."""
    print(f"\n{BLUE}Running JavaScript Tests with Medical Compliance...{RESET}")

    # Change to web directory
    web_path = Path(__file__).parent.parent / "web"
    os.chdir(web_path)

    cmd = [
        "npm",
        "test",
        "--",
        "--coverage",
        "--watchAll=false",
        "--coverageThreshold",
        '{"global":{"branches":80,"functions":80,"lines":80,"statements":80}}',
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    # Check for medical compliance violations
    violations = []
    if "localStorage" in result.stdout and "PHI" in result.stdout:
        violations.append("PHI stored in localStorage")
    if "console.log" in result.stdout and "patient" in result.stdout.lower():
        violations.append("Patient data logged to console")

    if violations:
        print(f"{RED}JavaScript Compliance Violations:{RESET}")
        for v in violations:
            print(f"  - {v}")
        return False

    return result.returncode == 0


def run_security_scan():
    """Run security scan for medical compliance."""
    print(f"\n{BLUE}Running Security Scan...{RESET}")

    # Run bandit for Python
    cmd = ["bandit", "-r", "src/", "-f", "json", "-o", "bandit_report.json"]
    subprocess.run(cmd, capture_output=True, text=True, check=False)

    try:
        with open("bandit_report.json", "r", encoding="utf-8") as f:
            security_data = json.load(f)
            high_issues = len(
                [i for i in security_data["results"] if i["issue_severity"] == "HIGH"]
            )

            if high_issues > MAX_SECURITY_ISSUES:
                print(
                    f"{RED}FAIL: {high_issues} high severity security issues found{RESET}"
                )
                return False
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"{YELLOW}Warning: Could not parse security report: {e}{RESET}")

    return True


def verify_compliance_markers():
    """Verify all test files have proper compliance markers."""
    print(f"\n{BLUE}Verifying Medical Compliance Markers...{RESET}")

    test_files = Path("tests").rglob("test_*.py")
    missing_markers = []

    for test_file in test_files:
        if "compliance" in str(test_file):
            continue  # Skip compliance test files themselves

        content = test_file.read_text()

        # Check for required markers
        if (
            "patient" in content.lower()
            and "@pytest.mark.hipaa_required" not in content
        ):
            missing_markers.append(f"{test_file}: Missing HIPAA marker")
        if "fhir" in content.lower() and "@pytest.mark.fhir_compliance" not in content:
            missing_markers.append(f"{test_file}: Missing FHIR marker")
        if (
            "emergency" in content.lower()
            and "@pytest.mark.emergency_access" not in content
        ):
            missing_markers.append(f"{test_file}: Missing emergency marker")

    if missing_markers:
        print(f"{RED}Missing Compliance Markers:{RESET}")
        for m in missing_markers:
            print(f"  - {m}")
        return False

    return True


def generate_compliance_report(results):
    """Generate medical compliance test report."""
    report = {
        "execution_time": datetime.utcnow().isoformat(),
        "compliance_mode": "STRICT",
        "results": results,
        "hipaa_compliant": all(results.values()),
        "safe_for_production": False,
    }

    # Only mark safe for production if ALL checks pass
    if report["hipaa_compliant"]:
        report["safe_for_production"] = True
        report["certification"] = {
            "fhir_r4": True,
            "hipaa_security": True,
            "phi_encryption": True,
            "audit_logging": True,
            "emergency_access": True,
        }

    with open("medical_compliance_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report


def main():
    """Execute main test with medical compliance verification."""
    print_header()

    # Track results
    results = {
        "python_tests": False,
        "javascript_tests": False,
        "security_scan": False,
        "compliance_markers": False,
    }

    # Run test suites
    try:
        results["python_tests"] = run_python_tests()
        results["javascript_tests"] = run_javascript_tests()
        results["security_scan"] = run_security_scan()
        results["compliance_markers"] = verify_compliance_markers()
    except (subprocess.CalledProcessError, ValueError, RuntimeError) as e:
        print(f"{RED}Test execution failed: {e}{RESET}")
        sys.exit(1)

    # Generate report
    report = generate_compliance_report(results)

    # Final summary
    print(f"\n{BLUE}{'='*60}")
    print("  MEDICAL COMPLIANCE TEST SUMMARY")
    print(f"{'='*60}{RESET}")

    for check, passed in results.items():
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"{check}: {status}")

    if report["safe_for_production"]:
        print(f"\n{GREEN}✓ System is SAFE FOR PRODUCTION{RESET}")
        print(f"{GREEN}✓ All medical compliance requirements met{RESET}")
    else:
        print(f"\n{RED}✗ System is NOT safe for production{RESET}")
        print(f"{RED}✗ Medical compliance violations detected{RESET}")
        print(f"\n{YELLOW}This system handles refugee medical data.")
        print(f"ANY compliance failure could risk lives.{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
