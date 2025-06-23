#!/usr/bin/env python3
"""
Code Complexity Validator
Ensures code complexity stays within healthcare software standards
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List


class ComplexityValidator:
    """Validates code complexity metrics"""
    
    # Healthcare software complexity thresholds
    THRESHOLDS = {
        'cyclomatic': 10,      # Max cyclomatic complexity
        'cognitive': 15,       # Max cognitive complexity
        'nesting': 4,          # Max nesting depth
        'parameters': 5,       # Max function parameters
        'lines': 50,          # Max lines per function
        'file_lines': 500,    # Max lines per file
        'class_methods': 20   # Max methods per class
    }
    
    # Critical functions that need stricter limits
    CRITICAL_FUNCTIONS = {
        'encrypt', 'decrypt', 'authenticate', 'authorize',
        'validate_phi', 'audit_log', 'emergency_access',
        'patient_data', 'medical_record', 'prescription'
    }
    
    def __init__(self, max_complexity: int):
        self.max_complexity = max_complexity
        self.violations = []
        
    def validate_javascript_complexity(self, report_file: str = 'web/complexity-report.json'):
        """Validate JavaScript/TypeScript complexity"""
        try:
            with open(report_file, 'r') as f:
                report = json.load(f)
                
            for file_report in report:
                self._check_js_file_complexity(file_report)
                
        except FileNotFoundError:
            print(f"JavaScript complexity report not found: {report_file}")
        except Exception as e:
            print(f"Error reading JavaScript complexity: {e}")
            
    def validate_python_complexity(self, report_file: str = 'python-complexity.json'):
        """Validate Python complexity using radon output"""
        try:
            with open(report_file, 'r') as f:
                report = json.load(f)
                
            for file_path, complexities in report.items():
                self._check_python_file_complexity(file_path, complexities)
                
        except FileNotFoundError:
            print(f"Python complexity report not found: {report_file}")
        except Exception as e:
            print(f"Error reading Python complexity: {e}")
            
    def _check_js_file_complexity(self, file_report: Dict):
        """Check individual JavaScript file complexity"""
        file_path = file_report.get('path', 'unknown')
        
        # Check file-level metrics
        if file_report.get('lines', 0) > self.THRESHOLDS['file_lines']:
            self.violations.append({
                'type': 'file_too_long',
                'file': file_path,
                'metric': 'lines',
                'value': file_report['lines'],
                'threshold': self.THRESHOLDS['file_lines']
            })
            
        # Check function-level metrics
        for func in file_report.get('functions', []):
            func_name = func.get('name', 'anonymous')
            complexity = func.get('cyclomatic', 0)
            
            # Stricter limits for critical functions
            threshold = self.max_complexity
            if any(critical in func_name.lower() for critical in self.CRITICAL_FUNCTIONS):
                threshold = min(5, self.max_complexity)
                
            if complexity > threshold:
                self.violations.append({
                    'type': 'high_complexity',
                    'file': file_path,
                    'function': func_name,
                    'metric': 'cyclomatic',
                    'value': complexity,
                    'threshold': threshold
                })
                
    def _check_python_file_complexity(self, file_path: str, complexities: List[Dict]):
        """Check individual Python file complexity"""
        for item in complexities:
            if item['type'] == 'function':
                complexity = item['complexity']
                name = item['name']
                
                # Stricter limits for critical functions
                threshold = self.max_complexity
                if any(critical in name.lower() for critical in self.CRITICAL_FUNCTIONS):
                    threshold = min(5, self.max_complexity)
                    
                if complexity > threshold:
                    self.violations.append({
                        'type': 'high_complexity',
                        'file': file_path,
                        'function': name,
                        'metric': 'cyclomatic',
                        'value': complexity,
                        'threshold': threshold
                    })
                    
    def check_nesting_depth(self, source_dir: str = "src"):
        """Additional check for deep nesting in healthcare code"""
        source_path = Path(source_dir)
        
        for py_file in source_path.rglob("*.py"):
            self._check_file_nesting(py_file, 'python')
            
        web_path = Path("web/src")
        if web_path.exists():
            for ts_file in web_path.rglob("*.ts"):
                self._check_file_nesting(ts_file, 'typescript')
            for tsx_file in web_path.rglob("*.tsx"):
                self._check_file_nesting(tsx_file, 'typescript')
                
    def _check_file_nesting(self, file_path: Path, language: str):
        """Check nesting depth in a file"""
        try:
            content = file_path.read_text()
            lines = content.split('\n')
            max_indent = 0
            
            for i, line in enumerate(lines, 1):
                if line.strip():  # Skip empty lines
                    # Count leading spaces/tabs
                    indent = len(line) - len(line.lstrip())
                    
                    # Convert to indent levels (assuming 4 spaces = 1 indent)
                    indent_level = indent // 4
                    
                    if indent_level > self.THRESHOLDS['nesting']:
                        self.violations.append({
                            'type': 'deep_nesting',
                            'file': str(file_path),
                            'line': i,
                            'metric': 'nesting_depth',
                            'value': indent_level,
                            'threshold': self.THRESHOLDS['nesting']
                        })
                        
        except Exception as e:
            print(f"Error checking nesting in {file_path}: {e}")
            
    def generate_report(self):
        """Generate complexity validation report"""
        if self.violations:
            print("\n❌ Code Complexity Violations Found:\n")
            
            # Group by type
            by_type = {}
            for violation in self.violations:
                vtype = violation['type']
                if vtype not in by_type:
                    by_type[vtype] = []
                by_type[vtype].append(violation)
                
            for vtype, violations in by_type.items():
                print(f"\n{vtype.upper().replace('_', ' ')}:")
                for v in violations[:5]:  # Show first 5 of each type
                    if v['type'] == 'high_complexity':
                        print(f"  - {v['file']} - {v['function']}: {v['metric']}={v['value']} (max: {v['threshold']})")
                    elif v['type'] == 'deep_nesting':
                        print(f"  - {v['file']}:{v['line']} - nesting={v['value']} (max: {v['threshold']})")
                    else:
                        print(f"  - {v['file']}: {v['metric']}={v['value']} (max: {v['threshold']})")
                        
                if len(violations) > 5:
                    print(f"  ... and {len(violations) - 5} more")
                    
            print(f"\n\nTotal violations: {len(self.violations)}")
            print("\n🚨 Code complexity exceeds healthcare software standards!")
            print("\nRecommendations:")
            print("- Break down complex functions into smaller, testable units")
            print("- Reduce nesting by using early returns")
            print("- Extract complex conditions into well-named functions")
            print("- Consider using the Strategy pattern for complex business logic")
        else:
            print("\n✅ Code complexity within acceptable limits!")
            
    def write_json_report(self, output_file: str = 'complexity-violations.json'):
        """Write violations to JSON for further processing"""
        with open(output_file, 'w') as f:
            json.dump({
                'violations': self.violations,
                'summary': {
                    'total': len(self.violations),
                    'by_type': {
                        vtype: len([v for v in self.violations if v['type'] == vtype])
                        for vtype in set(v['type'] for v in self.violations)
                    }
                }
            }, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description='Validate code complexity')
    parser.add_argument('--max-complexity', type=int, default=10,
                       help='Maximum allowed cyclomatic complexity')
    parser.add_argument('--source-dir', default='src',
                       help='Source directory to scan')
    parser.add_argument('--output', default='complexity-violations.json',
                       help='Output file for violations')
    args = parser.parse_args()
    
    validator = ComplexityValidator(args.max_complexity)
    
    # Validate complexity reports
    validator.validate_javascript_complexity()
    validator.validate_python_complexity()
    
    # Additional nesting checks
    validator.check_nesting_depth(args.source_dir)
    
    # Generate reports
    validator.generate_report()
    validator.write_json_report(args.output)
    
    # Exit with error if violations found
    if validator.violations:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
