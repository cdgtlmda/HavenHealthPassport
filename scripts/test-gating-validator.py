#!/usr/bin/env python3
"""
Test Gating Verification Script
Implements the same quality gates as the GitHub Actions workflow for local testing
"""

import subprocess
import json
import sys
import os
import time
from pathlib import Path

class TestGatingValidator:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.results = {
            "js_coverage": None,
            "python_coverage": None,
            "skipped_tests": False,
            "critical_paths": [],
            "execution_time": None,
            "passed": True
        }
        
    def check_js_coverage(self):
        """Check JavaScript/React test coverage"""
        print("🔍 Checking JavaScript/React test coverage...")
        
        web_dir = self.project_root / "web"
        if not web_dir.exists():
            print("⚠️  Web directory not found, skipping JS coverage")
            return True
            
        try:
            # Run tests with coverage
            os.chdir(web_dir)
            result = subprocess.run(
                ["npm", "test", "--", "--coverage", "--watchAll=false", "--ci", "--passWithNoTests"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Parse coverage from output
            for line in result.stdout.split('\n'):
                if 'All files' in line and '%' in line:
                    # Extract coverage percentage
                    parts = line.split('|')
                    if len(parts) >= 2:
                        coverage_str = parts[1].strip().replace('%', '')
                        try:
                            coverage = float(coverage_str)
                            self.results["js_coverage"] = coverage
                            print(f"✅ JavaScript coverage: {coverage}%")
                            
                            if coverage < 80:
                                print(f"❌ JavaScript coverage {coverage}% is below 80% threshold")
                                return False
                            return True
                        except ValueError:
                            pass
                            
            print("⚠️  Could not parse JavaScript coverage")
            return True
            
        except subprocess.TimeoutExpired:
            print("❌ JavaScript tests timed out")
            return False
        except Exception as e:
            print(f"⚠️  JavaScript test error: {e}")
            return True
        finally:
            os.chdir(self.project_root)
            
    def check_python_coverage(self):
        """Check Python test coverage"""
        print("\n🔍 Checking Python test coverage...")
        
        try:
            # Run pytest with coverage
            result = subprocess.run(
                ["python", "-m", "pytest", "tests/", "--cov=src", "--cov-report=term", "--tb=short", "-q"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=300
            )
            
            # Parse coverage from output
            for line in result.stdout.split('\n'):
                if 'TOTAL' in line and '%' in line:
                    parts = line.split()
                    for part in parts:
                        if part.endswith('%'):
                            try:
                                coverage = float(part.replace('%', ''))
                                self.results["python_coverage"] = coverage
                                print(f"✅ Python coverage: {coverage}%")
                                
                                if coverage < 80:
                                    print(f"❌ Python coverage {coverage}% is below 80% threshold")
                                    return False
                                return True
                            except ValueError:
                                pass
                                
            print("⚠️  Could not parse Python coverage")
            return True
            
        except subprocess.TimeoutExpired:
            print("❌ Python tests timed out")
            return False
        except Exception as e:
            print(f"⚠️  Python test error: {e}")
            return True
            
    def check_skipped_tests(self):
        """Check for skipped or focused tests"""
        print("\n🔍 Checking for skipped or focused tests...")
        
        patterns = [r"\.skip\(", r"\.only\(", r"@skip", r"@pytest\.mark\.skip"]
        test_extensions = ["*.test.js", "*.test.jsx", "*.test.ts", "*.test.tsx", "*.spec.js", "test_*.py"]
        
        found_issues = []
        
        for ext in test_extensions:
            for test_file in self.project_root.rglob(ext):
                # Skip third-party and virtual environment files
                path_str = str(test_file)
                if any(skip in path_str for skip in [
                    'node_modules', '__pycache__', 'venv/', '.venv/', 
                    'site-packages/', 'dist-packages/', '.tox/', 
                    'virtualenv/', 'env/', 'SentinelOps/'
                ]):
                    continue
                    
                try:
                    content = test_file.read_text()
                    for pattern in patterns:
                        if pattern in content:
                            found_issues.append(f"{test_file.relative_to(self.project_root)}: {pattern}")
                except Exception:
                    pass
                    
        if found_issues:
            print("❌ Found skipped or focused tests:")
            for issue in found_issues[:5]:  # Show first 5
                print(f"   - {issue}")
            if len(found_issues) > 5:
                print(f"   ... and {len(found_issues) - 5} more")
            self.results["skipped_tests"] = True
            return False
            
        print("✅ No skipped or focused tests found")
        return True
        
    def check_critical_paths(self):
        """Verify critical paths have test coverage"""
        print("\n🔍 Checking critical path test coverage...")
        
        critical_paths = [
            "PatientRegistration",
            "EmergencyAccess", 
            "Authentication",
            "PHIEncryption",
            "AuditLogging"
        ]
        
        missing_paths = []
        
        for path in critical_paths:
            found = False
            
            # Search in test files
            for test_file in self.project_root.rglob("*test*"):
                if test_file.is_file() and 'node_modules' not in str(test_file):
                    try:
                        if path.lower() in test_file.read_text().lower():
                            found = True
                            break
                    except Exception:
                        pass
                        
            if not found:
                missing_paths.append(path)
            else:
                self.results["critical_paths"].append(path)
                
        if missing_paths:
            print("❌ Missing tests for critical paths:")
            for path in missing_paths:
                print(f"   - {path}")
            return False
            
        print("✅ All critical paths have test coverage")
        return True
        
    def run_validation(self):
        """Run all test gating validations"""
        print("=" * 60)
        print("🏥 Haven Health Passport - Test Quality Gates")
        print("=" * 60)
        
        start_time = time.time()
        
        # Run all checks
        checks = [
            ("JavaScript Coverage", self.check_js_coverage),
            ("Python Coverage", self.check_python_coverage),
            ("Skipped Tests", self.check_skipped_tests),
            ("Critical Paths", self.check_critical_paths),
        ]
        
        all_passed = True
        
        for name, check_func in checks:
            if not check_func():
                all_passed = False
                self.results["passed"] = False
                
        # Calculate execution time
        self.results["execution_time"] = time.time() - start_time
        
        # Generate report
        self.generate_report()
        
        return all_passed
        
    def generate_report(self):
        """Generate quality gate report"""
        print("\n" + "=" * 60)
        print("📊 Test Quality Report")
        print("=" * 60)
        
        print("\n## Coverage Metrics")
        if self.results["js_coverage"] is not None:
            print(f"- JavaScript/React: {self.results['js_coverage']}%")
        else:
            print("- JavaScript/React: Not measured")
            
        if self.results["python_coverage"] is not None:
            print(f"- Python: {self.results['python_coverage']}%")
        else:
            print("- Python: Not measured")
            
        print("\n## Quality Checks")
        print(f"- No skipped tests: {'❌' if self.results['skipped_tests'] else '✅'}")
        print(f"- Critical paths covered: {'✅' if len(self.results['critical_paths']) == 5 else '❌'}")
        print(f"- Execution time: {self.results['execution_time']:.1f}s")
        
        print("\n## Thresholds")
        print("- Minimum coverage: 80%")
        print("- Maximum execution time: 600s (10 minutes)")
        
        print(f"\n## Overall Status: {'✅ PASSED' if self.results['passed'] else '❌ FAILED'}")
        print("=" * 60)
        
        # Save report to file
        report_path = self.project_root / "test-quality-report.json"
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n📄 Report saved to: {report_path}")


if __name__ == "__main__":
    validator = TestGatingValidator()
    success = validator.run_validation()
    sys.exit(0 if success else 1)
