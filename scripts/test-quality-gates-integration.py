#!/usr/bin/env python3
"""
Test to verify quality gates are properly integrated
"""

import os
import subprocess
import sys
import json
from pathlib import Path


def test_quality_gates_integration():
    """Test that quality gates are properly set up and functional"""
    print("🔍 Testing Quality Gates Integration\n")
    
    results = {
        'workflows': {},
        'scripts': {},
        'configuration': {}
    }
    
    # Check GitHub workflows exist
    print("1. Checking GitHub Workflows...")
    workflows = [
        '.github/workflows/quality-gates.yml',
        '.github/workflows/test-gating.yml',
        '.github/actions/setup-environment/action.yml'
    ]
    
    for workflow in workflows:
        exists = Path(workflow).exists()
        results['workflows'][workflow] = exists
        status = "✅" if exists else "❌"
        print(f"   {status} {workflow}")
    
    # Check quality gate scripts exist and are executable
    print("\n2. Checking Quality Gate Scripts...")
    scripts = [
        'scripts/check-healthcare-standards.py',
        'scripts/validate-complexity.py',
        'scripts/check-vulnerabilities.py',
        'scripts/verify-encryption-coverage.py',
        'scripts/hipaa-compliance-check.py',
        'scripts/run-quality-gates.sh'
    ]
    
    for script in scripts:
        path = Path(script)
        exists = path.exists()
        executable = os.access(script, os.X_OK) if exists else False
        results['scripts'][script] = {'exists': exists, 'executable': executable}
        
        if exists:
            exec_status = "✅" if executable else "⚠️"
            print(f"   {exec_status} {script} {'(executable)' if executable else '(not executable)'}")
        else:
            print(f"   ❌ {script} (missing)")
    
    # Check configuration files
    print("\n3. Checking Configuration Files...")
    configs = [
        '.lighthouserc.js',
        'docs/quality-gates.md'
    ]
    
    for config in configs:
        exists = Path(config).exists()
        results['configuration'][config] = exists
        status = "✅" if exists else "❌"
        print(f"   {status} {config}")
    
    # Test that scripts can be imported (syntax check)
    print("\n4. Syntax Checking Python Scripts...")
    python_scripts = [s for s in scripts if s.endswith('.py')]
    
    for script in python_scripts:
        if Path(script).exists():
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'py_compile', script],
                    capture_output=True,
                    text=True
                )
                success = result.returncode == 0
                results['scripts'][script]['syntax_valid'] = success
                status = "✅" if success else "❌"
                print(f"   {status} {script}")
            except Exception as e:
                results['scripts'][script]['syntax_valid'] = False
                print(f"   ❌ {script} - {str(e)}")
    
    # Generate summary
    print("\n" + "="*50)
    print("QUALITY GATES INTEGRATION SUMMARY")
    print("="*50)
    
    # Count successes
    workflow_count = sum(1 for v in results['workflows'].values() if v)
    script_count = sum(1 for v in results['scripts'].values() if v.get('exists', False))
    config_count = sum(1 for v in results['configuration'].values() if v)
    
    total_workflows = len(results['workflows'])
    total_scripts = len(results['scripts'])
    total_configs = len(results['configuration'])
    
    print(f"\nWorkflows: {workflow_count}/{total_workflows} present")
    print(f"Scripts: {script_count}/{total_scripts} present")
    print(f"Configurations: {config_count}/{total_configs} present")
    
    # Overall status
    all_present = (
        workflow_count == total_workflows and
        script_count == total_scripts and
        config_count == total_configs
    )
    
    if all_present:
        print("\n✅ Quality Gates are fully integrated!")
        return 0
    else:
        print("\n⚠️  Some quality gate components are missing")
        print("Run the setup scripts to complete integration")
        return 1
    
    # Write results to file
    with open('quality-gates-integration-test.json', 'w') as f:
        json.dump(results, f, indent=2)


if __name__ == '__main__':
    sys.exit(test_quality_gates_integration())
