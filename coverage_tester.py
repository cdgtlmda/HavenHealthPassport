#!/usr/bin/env python3
"""
Medical Compliance Coverage Testing System

This module provides comprehensive coverage testing capabilities for the
medical compliance project. It implements the mandatory coverage verification
requirements from COVERAGE_STRATEGY_MEDICAL_COMPLIANT.md.

Coverage Requirements:
- Encryption/Auth/Audit files: 100% statement coverage (HIPAA critical)
- Medical/Patient files: 95% statement coverage
- All other files: ≥90% statement coverage

Author: HavenHealthPassport Coverage Team
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
import argparse
from dataclasses import dataclass
from enum import Enum


class CoverageLevel(Enum):
    """Coverage level requirements based on file type."""

    CRITICAL = 100  # Encryption, Auth, Audit files
    MEDICAL = 95  # Medical, Patient files
    STANDARD = 90  # All other files


@dataclass
class CoverageResult:
    """Coverage result for a single file or module."""

    file_path: str
    statements: int
    missing: int
    coverage_percent: float
    required_percent: float
    meets_requirement: bool
    missing_lines: List[str]


@dataclass
class CoverageReport:
    """Complete coverage report with summary."""

    total_statements: int
    total_missing: int
    overall_coverage: float
    files_tested: int
    files_passing: int
    files_failing: int
    results: List[CoverageResult]
    critical_files: List[CoverageResult]
    medical_files: List[CoverageResult]
    standard_files: List[CoverageResult]


class CoverageTester:
    """Main coverage testing system."""

    def __init__(self, base_path: str = "."):
        """Initialize the coverage tester with base path."""
        self.base_path = Path(base_path)
        self.critical_patterns = [
            "**/encryption*",
            "**/auth*",
            "**/audit*",
            "**/security/*",
            "**/key_management/*",
        ]
        self.medical_patterns = [
            "**/medical*",
            "**/patient*",
            "**/healthcare/*",
            "**/fhir*",
            "**/hl7*",
        ]

    def classify_file(self, file_path: str) -> CoverageLevel:
        """Classify file by coverage requirement level."""
        path_lower = file_path.lower()

        # Check critical patterns first (highest priority)
        for pattern in ["encryption", "auth", "audit", "security", "key_management"]:
            if pattern in path_lower:
                return CoverageLevel.CRITICAL

        # Check medical patterns
        for pattern in ["medical", "patient", "healthcare", "fhir", "hl7"]:
            if pattern in path_lower:
                return CoverageLevel.MEDICAL

        return CoverageLevel.STANDARD

    def run_coverage_command(
        self, test_path: str = "", module_path: str = ""
    ) -> Tuple[bool, str, dict]:
        """
        Run pytest with coverage for specified test/module.

        Args:
            test_path: Specific test file or directory to run
            module_path: Specific module to measure coverage for

        Returns:
            Tuple of (success, output, coverage_data)
        """
        cmd = ["python", "-m", "pytest"]

        if test_path:
            cmd.append(test_path)

        # Coverage options
        if module_path:
            cmd.extend([f"--cov={module_path}"])
        else:
            cmd.extend(["--cov=src"])

        cmd.extend(
            [
                "--cov-report=json:coverage.json",
                "--cov-report=term-missing",
                "--cov-fail-under=0",  # Don't fail on coverage, we'll handle that
                "-v",
            ]
        )

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.base_path
            )

            # Load coverage data
            coverage_data = {}
            coverage_file = self.base_path / "coverage.json"
            if coverage_file.exists():
                with open(coverage_file) as f:
                    coverage_data = json.load(f)

            return (
                result.returncode == 0,
                result.stdout + "\n" + result.stderr,
                coverage_data,
            )

        except Exception as e:
            return False, f"Error running coverage: {str(e)}", {}

    def parse_coverage_data(self, coverage_data: dict) -> List[CoverageResult]:
        """Parse coverage.json data into CoverageResult objects."""
        results = []

        if not coverage_data or "files" not in coverage_data:
            return results

        for file_path, file_data in coverage_data["files"].items():
            statements = len(file_data.get("executed_lines", []))
            missing_lines = file_data.get("missing_lines", [])
            missing = len(missing_lines)

            if statements > 0:
                coverage_percent = ((statements - missing) / statements) * 100
            else:
                coverage_percent = 0.0

            # Classify file and get requirement
            level = self.classify_file(file_path)
            required_percent = level.value

            meets_requirement = coverage_percent >= required_percent

            results.append(
                CoverageResult(
                    file_path=file_path,
                    statements=statements,
                    missing=missing,
                    coverage_percent=coverage_percent,
                    required_percent=required_percent,
                    meets_requirement=meets_requirement,
                    missing_lines=[str(line) for line in missing_lines],
                )
            )

        return results

    def test_individual_file(
        self, test_file: str, source_module: str = ""
    ) -> CoverageReport:
        """
        Test coverage for a single test file.

        Args:
            test_file: Path to test file
            source_module: Optional specific source module to measure

        Returns:
            CoverageReport for the individual test
        """
        print(f"\n🔍 Testing individual file: {test_file}")
        if source_module:
            print(f"   Measuring coverage for: {source_module}")

        success, output, coverage_data = self.run_coverage_command(
            test_file, source_module
        )

        if not success:
            print(f"❌ Test execution failed!")
            print(output)
            return self._empty_report()

        results = self.parse_coverage_data(coverage_data)
        return self._create_report(results, output)

    def test_batch(self, test_pattern: str, source_pattern: str = "") -> CoverageReport:
        """
        Test coverage for a batch of tests matching a pattern.

        Args:
            test_pattern: Pattern for test files (e.g., "tests/unit/services/")
            source_pattern: Pattern for source files to measure

        Returns:
            CoverageReport for the batch
        """
        print(f"\n📦 Testing batch: {test_pattern}")
        if source_pattern:
            print(f"   Measuring coverage for: {source_pattern}")

        success, output, coverage_data = self.run_coverage_command(
            test_pattern, source_pattern
        )

        if not success:
            print(f"❌ Batch test execution failed!")
            print(output)
            return self._empty_report()

        results = self.parse_coverage_data(coverage_data)
        return self._create_report(results, output)

    def test_full_suite(self) -> CoverageReport:
        """
        Test coverage for the entire test suite.

        Returns:
            CoverageReport for the full suite
        """
        print(f"\n🎯 Testing full suite coverage...")

        success, output, coverage_data = self.run_coverage_command()

        if not success:
            print(f"❌ Full suite execution failed!")
            print(output)
            return self._empty_report()

        results = self.parse_coverage_data(coverage_data)
        return self._create_report(results, output)

    def _create_report(
        self, results: List[CoverageResult], output: str = ""
    ) -> CoverageReport:
        """Create a comprehensive coverage report."""
        if not results:
            return self._empty_report()

        # Categorize results
        critical_files = [
            r
            for r in results
            if self.classify_file(r.file_path) == CoverageLevel.CRITICAL
        ]
        medical_files = [
            r
            for r in results
            if self.classify_file(r.file_path) == CoverageLevel.MEDICAL
        ]
        standard_files = [
            r
            for r in results
            if self.classify_file(r.file_path) == CoverageLevel.STANDARD
        ]

        # Calculate totals
        total_statements = sum(r.statements for r in results)
        total_missing = sum(r.missing for r in results)
        overall_coverage = (
            ((total_statements - total_missing) / total_statements * 100)
            if total_statements > 0
            else 0.0
        )

        files_passing = len([r for r in results if r.meets_requirement])
        files_failing = len(results) - files_passing

        return CoverageReport(
            total_statements=total_statements,
            total_missing=total_missing,
            overall_coverage=overall_coverage,
            files_tested=len(results),
            files_passing=files_passing,
            files_failing=files_failing,
            results=results,
            critical_files=critical_files,
            medical_files=medical_files,
            standard_files=standard_files,
        )

    def _empty_report(self) -> CoverageReport:
        """Create an empty report for failed tests."""
        return CoverageReport(
            total_statements=0,
            total_missing=0,
            overall_coverage=0.0,
            files_tested=0,
            files_passing=0,
            files_failing=0,
            results=[],
            critical_files=[],
            medical_files=[],
            standard_files=[],
        )

    def print_report(self, report: CoverageReport, detailed: bool = True):
        """Print a formatted coverage report."""
        print("\n" + "=" * 80)
        print("📊 MEDICAL COMPLIANCE COVERAGE REPORT")
        print("=" * 80)

        # Overall stats
        print(f"📈 Overall Coverage: {report.overall_coverage:.2f}%")
        print(f"📁 Files Tested: {report.files_tested}")
        print(f"✅ Files Passing: {report.files_passing}")
        print(f"❌ Files Failing: {report.files_failing}")
        print(f"📋 Total Statements: {report.total_statements}")
        print(f"🔍 Missing Coverage: {report.total_missing}")

        # Critical files analysis
        if report.critical_files:
            print(f"\n🔐 CRITICAL FILES (100% Required): {len(report.critical_files)}")
            critical_passing = len(
                [f for f in report.critical_files if f.meets_requirement]
            )
            print(f"   ✅ Passing: {critical_passing}/{len(report.critical_files)}")

            if detailed:
                for file_result in report.critical_files:
                    status = "✅" if file_result.meets_requirement else "❌"
                    print(
                        f"   {status} {file_result.file_path}: {file_result.coverage_percent:.1f}%"
                    )

        # Medical files analysis
        if report.medical_files:
            print(f"\n🏥 MEDICAL FILES (95% Required): {len(report.medical_files)}")
            medical_passing = len(
                [f for f in report.medical_files if f.meets_requirement]
            )
            print(f"   ✅ Passing: {medical_passing}/{len(report.medical_files)}")

            if detailed:
                for file_result in report.medical_files:
                    status = "✅" if file_result.meets_requirement else "❌"
                    print(
                        f"   {status} {file_result.file_path}: {file_result.coverage_percent:.1f}%"
                    )

        # Standard files analysis
        if report.standard_files:
            print(f"\n📄 STANDARD FILES (90% Required): {len(report.standard_files)}")
            standard_passing = len(
                [f for f in report.standard_files if f.meets_requirement]
            )
            print(f"   ✅ Passing: {standard_passing}/{len(report.standard_files)}")

        # Compliance status
        print(f"\n🏆 COMPLIANCE STATUS:")
        overall_min_required = 80.0  # From documentation
        if report.overall_coverage >= overall_min_required:
            print(
                f"   ✅ COMPLIANT - Coverage {report.overall_coverage:.2f}% ≥ {overall_min_required}%"
            )
        else:
            print(
                f"   ❌ NON-COMPLIANT - Coverage {report.overall_coverage:.2f}% < {overall_min_required}%"
            )

        # Show failing files
        if detailed and report.files_failing > 0:
            print(f"\n🚨 FAILING FILES ({report.files_failing}):")
            failing_files = [r for r in report.results if not r.meets_requirement]
            for file_result in failing_files[:10]:  # Show top 10
                print(
                    f"   ❌ {file_result.file_path}: {file_result.coverage_percent:.1f}% (need {file_result.required_percent}%)"
                )
                if file_result.missing_lines:
                    lines_preview = ", ".join(file_result.missing_lines[:5])
                    if len(file_result.missing_lines) > 5:
                        lines_preview += (
                            f" ... +{len(file_result.missing_lines)-5} more"
                        )
                    print(f"      Missing lines: {lines_preview}")

            if len(failing_files) > 10:
                print(f"   ... and {len(failing_files)-10} more failing files")

        print("=" * 80)


def main():
    """Command line interface for coverage testing."""
    parser = argparse.ArgumentParser(description="Medical Compliance Coverage Tester")
    parser.add_argument("--individual", "-i", help="Test individual file")
    parser.add_argument(
        "--module", "-m", help="Specific module to measure coverage for"
    )
    parser.add_argument("--batch", "-b", help="Test batch of files matching pattern")
    parser.add_argument("--full", "-f", action="store_true", help="Test full suite")
    parser.add_argument(
        "--detailed", "-d", action="store_true", help="Show detailed results"
    )

    args = parser.parse_args()

    tester = CoverageTester()

    if args.individual:
        report = tester.test_individual_file(args.individual, args.module or "")
        tester.print_report(report, args.detailed)

    elif args.batch:
        report = tester.test_batch(args.batch, args.module or "")
        tester.print_report(report, args.detailed)

    elif args.full:
        report = tester.test_full_suite()
        tester.print_report(report, args.detailed)

    else:
        print("Usage examples:")
        print(
            "  Individual: python coverage_tester.py -i tests/unit/services/test_encryption_service_real.py -m src/services/encryption_service"
        )
        print(
            "  Batch:      python coverage_tester.py -b tests/unit/services/ -m src/services"
        )
        print("  Full:       python coverage_tester.py -f")
        print("  Detailed:   python coverage_tester.py -f -d")


if __name__ == "__main__":
    main()
