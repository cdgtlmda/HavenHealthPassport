#!/usr/bin/env python3
"""
Haven Health Passport - Test Coverage Reality Check
Shows the actual state of test coverage vs infrastructure
"""

import os
import json
from pathlib import Path
from collections import defaultdict


def count_source_files():
    """Count source files that need tests"""
    counts = defaultdict(int)
    
    # React/TypeScript files
    web_src = Path('web/src')
    if web_src.exists():
        for ext in ['*.tsx', '*.ts', '*.jsx', '*.js']:
            files = list(web_src.rglob(ext))
            # Exclude test files and type definitions
            source_files = [f for f in files if '.test.' not in str(f) and '.spec.' not in str(f) and '.d.ts' not in str(f)]
            counts[f'React/TS ({ext})'] = len(source_files)
    
    # Python files
    python_src = Path('src')
    if python_src.exists():
        py_files = list(python_src.rglob('*.py'))
        source_files = [f for f in py_files if '__pycache__' not in str(f)]
        counts['Python'] = len(source_files)
    
    return counts


def count_test_files():
    """Count actual test files"""
    counts = defaultdict(int)
    
    # React/TypeScript tests
    web_src = Path('web/src')
    if web_src.exists():
        for pattern in ['*.test.tsx', '*.test.ts', '*.test.jsx', '*.test.js', '*.spec.tsx', '*.spec.ts']:
            test_files = list(web_src.rglob(pattern))
            if test_files:
                counts[f'React/TS tests ({pattern})'] = len(test_files)
    
    # Python tests
    tests_dir = Path('tests')
    if tests_dir.exists():
        test_files = list(tests_dir.rglob('test_*.py'))
        counts['Python tests'] = len(test_files)
    
    # Cypress E2E tests
    cypress_dir = Path('web/cypress/e2e')
    if cypress_dir.exists():
        e2e_files = list(cypress_dir.rglob('*.cy.js'))
        counts['Cypress E2E tests'] = len(e2e_files)
    
    return counts


def check_test_infrastructure():
    """Check what test infrastructure exists"""
    infrastructure = {
        'Jest Config': Path('web/jest.config.js').exists() or Path('web/package.json').exists(),
        'Pytest Config': Path('pytest.ini').exists() or Path('pyproject.toml').exists(),
        'Cypress Config': Path('web/cypress.config.js').exists() or Path('web/cypress.json').exists(),
        'Test Database': Path('docker-compose.test.yml').exists(),
        'CI Pipeline': Path('.github/workflows/ci-cd-pipeline.yml').exists(),
        'Quality Gates': Path('.github/workflows/quality-gates.yml').exists(),
        'Coverage Config': Path('.coveragerc').exists() or Path('web/.nycrc').exists(),
        'Test Fixtures': Path('tests/conftest.py').exists(),
        'Mock Services': Path('tests/mocks').exists() or Path('web/src/__mocks__').exists(),
        'LocalStack Config': any(Path('.').rglob('*localstack*'))
    }
    return infrastructure


def estimate_coverage():
    """Estimate actual test coverage based on file counts"""
    source_counts = count_source_files()
    test_counts = count_test_files()
    
    total_source = sum(source_counts.values())
    total_tests = sum(test_counts.values())
    
    # Rough estimation: assume each test file covers 2-3 source files
    estimated_coverage = min((total_tests * 2.5 / total_source * 100), 100) if total_source > 0 else 0
    
    return {
        'source_files': total_source,
        'test_files': total_tests,
        'estimated_coverage': estimated_coverage,
        'source_breakdown': dict(source_counts),
        'test_breakdown': dict(test_counts)
    }


def main():
    print("🔍 Haven Health Passport - Test Coverage Reality Check")
    print("=" * 60)
    
    # Check infrastructure
    print("\n📦 Test Infrastructure Status:")
    infrastructure = check_test_infrastructure()
    for item, exists in infrastructure.items():
        status = "✅" if exists else "❌"
        print(f"  {status} {item}")
    
    infrastructure_score = sum(infrastructure.values()) / len(infrastructure) * 100
    print(f"\nInfrastructure Completeness: {infrastructure_score:.0f}%")
    
    # Count files
    print("\n📊 File Count Analysis:")
    coverage_data = estimate_coverage()
    
    print(f"\nSource Files: {coverage_data['source_files']}")
    for file_type, count in coverage_data['source_breakdown'].items():
        print(f"  - {file_type}: {count} files")
    
    print(f"\nTest Files: {coverage_data['test_files']}")
    for file_type, count in coverage_data['test_breakdown'].items():
        print(f"  - {file_type}: {count} files")
    
    # Coverage estimation
    print(f"\n📈 Coverage Estimation:")
    print(f"  Estimated Coverage: ~{coverage_data['estimated_coverage']:.1f}%")
    print(f"  Files Without Tests: ~{coverage_data['source_files'] - coverage_data['test_files']} files")
    
    # Reality check
    print("\n⚠️  Reality Check:")
    if coverage_data['estimated_coverage'] < 20:
        print("  ❌ CRITICAL: Test coverage is dangerously low!")
        print("  ❌ This application is NOT ready for production")
        print("  ❌ Handling medical data with this coverage level is irresponsible")
    elif coverage_data['estimated_coverage'] < 50:
        print("  ⚠️  WARNING: Test coverage is below acceptable levels")
        print("  ⚠️  Significant testing effort required before production")
    elif coverage_data['estimated_coverage'] < 80:
        print("  🔶 Test coverage needs improvement for healthcare standards")
        print("  🔶 Target 80% minimum for production deployment")
    else:
        print("  ✅ Test coverage appears adequate")
    
    # Specific warnings
    print("\n🚨 Critical Gaps:")
    if coverage_data['test_breakdown'].get('React/TS tests (*.test.tsx)', 0) < 10:
        print("  - Almost no React component tests")
    if coverage_data['test_breakdown'].get('Python tests', 0) < 20:
        print("  - Insufficient Python/API tests")
    if coverage_data['test_breakdown'].get('Cypress E2E tests', 0) < 5:
        print("  - Minimal E2E test coverage")
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 SUMMARY:")
    print(f"  Infrastructure: {infrastructure_score:.0f}% Ready")
    print(f"  Test Coverage: ~{coverage_data['estimated_coverage']:.1f}% (ESTIMATED)")
    print(f"  Production Ready: {'NO ❌' if coverage_data['estimated_coverage'] < 80 else 'MAYBE ⚠️'}")
    
    # Save report
    report = {
        'infrastructure': infrastructure,
        'infrastructure_score': infrastructure_score,
        'coverage_data': coverage_data,
        'production_ready': coverage_data['estimated_coverage'] >= 80
    }
    
    with open('test-coverage-reality-check.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print("\n💾 Detailed report saved to: test-coverage-reality-check.json")
    
    return 0 if coverage_data['estimated_coverage'] >= 80 else 1


if __name__ == '__main__':
    exit(main())
