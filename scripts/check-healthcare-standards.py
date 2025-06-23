#!/usr/bin/env python3
"""
Healthcare Standards Compliance Checker
Validates code against medical software development standards
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Set


class HealthcareStandardsChecker:
    """Enforces healthcare-specific coding standards"""
    
    # PHI fields that must always be handled with care
    PHI_FIELDS = {
        'ssn', 'social_security_number', 'dateOfBirth', 'date_of_birth',
        'medical_record_number', 'mrn', 'patient_name', 'patient_address',
        'phone_number', 'email_address', 'diagnosis', 'treatment',
        'medication', 'allergy', 'insurance_id', 'policy_number'
    }
    
    # Required security patterns
    SECURITY_PATTERNS = {
        'encryption': ['encrypt', 'decrypt', 'hash', 'crypto'],
        'authentication': ['authenticate', 'verify_token', 'check_permission'],
        'audit': ['audit_log', 'log_access', 'record_action'],
        'validation': ['validate', 'sanitize', 'verify']
    }
    
    # Healthcare-specific code issues
    HEALTHCARE_VIOLATIONS = {
        'unencrypted_phi': "PHI field '{field}' used without encryption",
        'missing_audit': "PHI access without audit logging in {function}",
        'insecure_storage': "Storing sensitive data without encryption",
        'missing_validation': "User input not validated before processing",
        'insufficient_auth': "Missing authentication check for PHI access",
        'exposed_error': "Error message may expose sensitive information",
        'unsafe_logging': "Logging potentially contains PHI",
        'missing_timeout': "Session without timeout for medical data access",
        'weak_encryption': "Using deprecated or weak encryption method",
        'missing_rbac': "Missing role-based access control"
    }
    
    def __init__(self, report_file: str):
        self.report_file = report_file
        self.violations = []
        
    def check_pylint_report(self) -> bool:
        """Check PyLint report for healthcare violations"""
        try:
            with open(self.report_file, 'r') as f:
                report = json.load(f)
                
            for issue in report:
                self._check_healthcare_issue(issue)
                
            return len(self.violations) == 0
            
        except Exception as e:
            print(f"Error reading report: {e}")
            return False
            
    def _check_healthcare_issue(self, issue: Dict):
        """Check individual issue for healthcare compliance"""
        message = issue.get('message', '').lower()
        symbol = issue.get('symbol', '')
        path = issue.get('path', '')
        
        # Check for PHI exposure
        for phi_field in self.PHI_FIELDS:
            if phi_field in message and 'encrypt' not in message:
                self.violations.append({
                    'type': 'unencrypted_phi',
                    'message': self.HEALTHCARE_VIOLATIONS['unencrypted_phi'].format(field=phi_field),
                    'location': f"{path}:{issue.get('line', 0)}"
                })
                
        # Check for audit requirements
        if any(field in message for field in ['patient', 'medical', 'health']):
            if 'audit' not in message and 'log' not in message:
                self.violations.append({
                    'type': 'missing_audit',
                    'message': self.HEALTHCARE_VIOLATIONS['missing_audit'].format(
                        function=issue.get('obj', 'unknown')
                    ),
                    'location': f"{path}:{issue.get('line', 0)}"
                })
                
        # Check for security issues
        if symbol in ['hardcoded-password', 'eval-used', 'exec-used']:
            self.violations.append({
                'type': 'security_violation',
                'message': f"Security violation: {symbol}",
                'location': f"{path}:{issue.get('line', 0)}"
            })
            
    def generate_report(self):
        """Generate compliance report"""
        if self.violations:
            print("\n❌ Healthcare Standards Violations Found:\n")
            
            for violation in self.violations:
                print(f"  - {violation['type']}: {violation['message']}")
                print(f"    Location: {violation['location']}\n")
                
            print(f"\nTotal violations: {len(self.violations)}")
            print("\n🚨 This code does not meet healthcare software standards!")
        else:
            print("\n✅ Code meets healthcare standards!")
            
    def check_source_patterns(self, source_dir: str = "src"):
        """Additional pattern-based checks on source code"""
        source_path = Path(source_dir)
        
        for py_file in source_path.rglob("*.py"):
            self._check_file_patterns(py_file)
            
    def _check_file_patterns(self, file_path: Path):
        """Check individual file for healthcare patterns"""
        try:
            content = file_path.read_text()
            lines = content.split('\n')
            
            for i, line in enumerate(lines, 1):
                # Check for hardcoded PHI
                for phi_field in self.PHI_FIELDS:
                    if phi_field in line.lower() and '=' in line:
                        if not any(secure in line.lower() for secure in ['encrypt', 'hash', 'env', 'config']):
                            self.violations.append({
                                'type': 'hardcoded_phi',
                                'message': f"Potential hardcoded PHI: {phi_field}",
                                'location': f"{file_path}:{i}"
                            })
                            
                # Check for print statements with PHI
                if 'print(' in line or 'console.log(' in line:
                    if any(phi in line.lower() for phi in ['patient', 'ssn', 'medical']):
                        self.violations.append({
                            'type': 'unsafe_logging',
                            'message': "Potential PHI in print/log statement",
                            'location': f"{file_path}:{i}"
                        })
                        
                # Check for exception handling that might expose PHI
                if 'except' in line and 'pass' in line:
                    self.violations.append({
                        'type': 'suppressed_error',
                        'message': "Suppressed exception might hide critical errors",
                        'location': f"{file_path}:{i}"
                    })
                    
        except Exception as e:
            print(f"Error checking {file_path}: {e}")


def main():
    parser = argparse.ArgumentParser(description='Check healthcare standards compliance')
    parser.add_argument('report_file', help='PyLint JSON report file')
    parser.add_argument('--source-dir', default='src', help='Source directory to scan')
    args = parser.parse_args()
    
    checker = HealthcareStandardsChecker(args.report_file)
    
    # Check PyLint report
    checker.check_pylint_report()
    
    # Additional pattern checks
    checker.check_source_patterns(args.source_dir)
    
    # Generate report
    checker.generate_report()
    
    # Exit with error if violations found
    if checker.violations:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
