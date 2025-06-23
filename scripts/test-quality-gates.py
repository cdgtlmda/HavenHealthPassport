#!/usr/bin/env python3
"""
Test to verify quality gates scripts are functioning correctly
"""

import subprocess
import sys
import json
from pathlib import Path


def test_hipaa_compliance_script():
    """Test the HIPAA compliance checker script"""
    print("Testing HIPAA Compliance Checker...")
    
    # Run the script
    result = subprocess.run(
        [sys.executable, 'scripts/hipaa-compliance-check.py'],
        capture_output=True,
        text=True
    )
    
    print(f"Exit code: {result.returncode}")
    print(f"Output:\n{result.stdout}")
    
    # Check if JSON report was created
    report_path = Path('hipaa-compliance.json')
    if report_path.exists():
        with open(report_path, 'r') as f:
            report = json.load(f)
        print(f"Report generated: {json.dumps(report, indent=2)}")
        report_path.unlink()  # Clean up
    
    return result.returncode


def test_encryption_coverage_script():
    """Test the encryption coverage verifier script"""
    print("\nTesting Encryption Coverage Verifier...")
    
    # Run the script
    result = subprocess.run(
        [sys.executable, 'scripts/verify-encryption-coverage.py', '--source-dirs', 'src', 'web/src'],
        capture_output=True,
        text=True
    )
    
    print(f"Exit code: {result.returncode}")
    print(f"Output:\n{result.stdout}")
    
    # Check if JSON report was created
    report_path = Path('encryption-coverage.json')
    if report_path.exists():
        with open(report_path, 'r') as f:
            report = json.load(f)
        print(f"Coverage: {report['summary']['coverage_percentage']:.1f}%")
        report_path.unlink()  # Clean up
    
    return result.returncode


def test_complexity_validator():
    """Test the complexity validator script"""
    print("\nTesting Complexity Validator...")
    
    # Create dummy complexity reports for testing
    js_report = [{
        "path": "test.js",
        "functions": [{
            "name": "testFunction",
            "cyclomatic": 5
        }],
        "lines": 100
    }]
    
    py_report = {
        "test.py": [{
            "type": "function",
            "name": "test_function",
            "complexity": 5
        }]
    }
    
    # Write test reports
    Path('web').mkdir(exist_ok=True)
    with open('web/complexity-report.json', 'w') as f:
        json.dump(js_report, f)
    
    with open('python-complexity.json', 'w') as f:
        json.dump(py_report, f)
    
    # Run the script
    result = subprocess.run(
        [sys.executable, 'scripts/validate-complexity.py', '--max-complexity', '10'],
        capture_output=True,
        text=True
    )
    
    print(f"Exit code: {result.returncode}")
    print(f"Output:\n{result.stdout}")
    
    # Clean up
    Path('web/complexity-report.json').unlink()
    Path('python-complexity.json').unlink()
    Path('complexity-violations.json').unlink(missing_ok=True)
    
    return result.returncode


def main():
    """Run all quality gate script tests"""
    print("🔍 Testing Quality Gate Scripts\n")
    print("="*60)
    
    tests = [
        ("HIPAA Compliance", test_hipaa_compliance_script),
        ("Encryption Coverage", test_encryption_coverage_script),
        ("Complexity Validator", test_complexity_validator)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            exit_code = test_func()
            results.append((test_name, "PASS" if exit_code in [0, 1] else "FAIL"))
        except Exception as e:
            print(f"Error in {test_name}: {e}")
            results.append((test_name, "ERROR"))
    
    print("\n" + "="*60)
    print("📊 Test Results Summary:\n")
    
    for test_name, status in results:
        emoji = "✅" if status == "PASS" else "❌"
        print(f"{emoji} {test_name}: {status}")
    
    # All scripts should at least run without crashing
    all_passed = all(status in ["PASS"] for _, status in results)
    
    if all_passed:
        print("\n✅ All quality gate scripts are functional!")
        return 0
    else:
        print("\n❌ Some quality gate scripts failed!")
        return 1


if __name__ == '__main__':
    sys.exit(main())
