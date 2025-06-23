#!/usr/bin/env python3
"""
HIPAA Compliance Checker
Validates that the application meets HIPAA security requirements
"""

import os
import re
import sys
import json
from pathlib import Path
from typing import Dict, List, Set


class HIPAAComplianceChecker:
    """Check HIPAA compliance requirements"""
    
    # HIPAA Security Rule Requirements (45 CFR §164.308-316)
    REQUIREMENTS = {
        'access_control': {
            'unique_user_identification': 'Each user must have unique identifier',
            'automatic_logoff': 'Sessions must timeout after inactivity',
            'encryption_decryption': 'PHI must be encrypted at rest and in transit'
        },
        'audit_controls': {
            'audit_logs': 'System must log all PHI access',
            'audit_review': 'Regular review mechanisms must exist',
            'audit_retention': 'Logs must be retained for 7 years'
        },
        'integrity': {
            'phi_alteration': 'PHI must be protected from improper alteration',
            'phi_destruction': 'PHI must be protected from destruction',
            'backup_procedures': 'Regular backups must be implemented'
        },
        'transmission_security': {
            'integrity_controls': 'Data integrity during transmission',
            'encryption': 'Encryption for data in transit'
        },
        'administrative': {
            'security_officer': 'Designated security officer required',
            'workforce_training': 'Security awareness training',
            'access_management': 'Procedures for granting access',
            'incident_procedures': 'Security incident procedures'
        }
    }
    
    def __init__(self):
        self.violations = []
        self.compliant_items = []
        
    def check_access_control(self):
        """Check access control implementations"""
        print("Checking Access Control Requirements...")
        
        # Check for unique user identification
        if self._check_pattern_exists('User.*id|user_id|username', ['src', 'web/src']):
            self.compliant_items.append('unique_user_identification')
        else:
            self.violations.append({
                'requirement': 'unique_user_identification',
                'message': 'No unique user identification system found'
            })
            
        # Check for session timeout
        timeout_patterns = [
            'session.*timeout|SESSION_TIMEOUT',
            'idle.*timeout|IDLE_TIMEOUT',
            'auto.*logout|automatic.*logoff'
        ]
        
        if any(self._check_pattern_exists(pattern, ['src', 'web/src']) for pattern in timeout_patterns):
            self.compliant_items.append('automatic_logoff')
        else:
            self.violations.append({
                'requirement': 'automatic_logoff',
                'message': 'No automatic session timeout implementation found'
            })
            
        # Check for encryption
        if self._check_encryption_implementation():
            self.compliant_items.append('encryption_decryption')
        else:
            self.violations.append({
                'requirement': 'encryption_decryption',
                'message': 'Inadequate PHI encryption implementation'
            })
            
    def check_audit_controls(self):
        """Check audit logging requirements"""
        print("Checking Audit Control Requirements...")
        
        # Check for audit logging
        audit_patterns = [
            'AuditLog|audit_log',
            'log.*access|access.*log',
            'audit.*trail|audit_trail'
        ]
        
        if any(self._check_pattern_exists(pattern, ['src', 'web/src']) for pattern in audit_patterns):
            self.compliant_items.append('audit_logs')
            
            # Check for 7-year retention
            if self._check_pattern_exists('retention.*7|seven.*year|2555.*days', ['src', 'config']):
                self.compliant_items.append('audit_retention')
            else:
                self.violations.append({
                    'requirement': 'audit_retention',
                    'message': 'No 7-year audit retention policy found'
                })
        else:
            self.violations.append({
                'requirement': 'audit_logs',
                'message': 'No audit logging implementation found'
            })
            
    def check_integrity_controls(self):
        """Check data integrity requirements"""
        print("Checking Integrity Control Requirements...")
        
        # Check for backup procedures
        backup_patterns = [
            'backup|Backup',
            'disaster.*recovery',
            'data.*recovery'
        ]
        
        if any(self._check_pattern_exists(pattern, ['src', 'scripts', 'docs']) for pattern in backup_patterns):
            self.compliant_items.append('backup_procedures')
        else:
            self.violations.append({
                'requirement': 'backup_procedures',
                'message': 'No backup procedures found'
            })
            
        # Check for data integrity validation
        if self._check_pattern_exists('checksum|hash.*verify|integrity.*check', ['src']):
            self.compliant_items.append('phi_alteration')
        else:
            self.violations.append({
                'requirement': 'phi_alteration',
                'message': 'No data integrity validation found'
            })
            
    def check_transmission_security(self):
        """Check transmission security requirements"""
        print("Checking Transmission Security Requirements...")
        
        # Check for TLS/HTTPS
        tls_patterns = [
            'https|HTTPS',
            'tls|TLS|ssl|SSL',
            'secure.*connection'
        ]
        
        if any(self._check_pattern_exists(pattern, ['src', 'config', 'docker-compose.yml']) for pattern in tls_patterns):
            self.compliant_items.append('encryption_transmission')
        else:
            self.violations.append({
                'requirement': 'encryption_transmission',
                'message': 'No secure transmission configuration found'
            })
            
    def check_administrative_safeguards(self):
        """Check administrative safeguard requirements"""
        print("Checking Administrative Safeguards...")
        
        # Check for security documentation
        doc_files = [
            'SECURITY.md',
            'docs/security.md',
            'docs/hipaa-compliance.md',
            'docs/incident-response.md'
        ]
        
        found_docs = sum(1 for doc in doc_files if Path(doc).exists())
        
        if found_docs >= 2:
            self.compliant_items.append('administrative_procedures')
        else:
            self.violations.append({
                'requirement': 'administrative_procedures',
                'message': f'Insufficient security documentation (found {found_docs}/4 required docs)'
            })
            
    def _check_pattern_exists(self, pattern: str, directories: List[str]) -> bool:
        """Check if a pattern exists in specified directories"""
        for directory in directories:
            if Path(directory).exists():
                for file_path in Path(directory).rglob("*"):
                    if file_path.is_file() and file_path.suffix in ['.py', '.js', '.ts', '.tsx', '.yml', '.yaml', '.md']:
                        try:
                            content = file_path.read_text()
                            if re.search(pattern, content, re.IGNORECASE):
                                return True
                        except:
                            continue
        return False
        
    def _check_encryption_implementation(self) -> bool:
        """Check for proper encryption implementation"""
        encryption_indicators = [
            'AES.*256|aes256',
            'encrypt.*field|EncryptedField',
            'fernet|Fernet',
            'KMS|kms.*encrypt'
        ]
        
        found_encryption = sum(
            1 for pattern in encryption_indicators
            if self._check_pattern_exists(pattern, ['src'])
        )
        
        return found_encryption >= 2
        
    def check_configuration_security(self):
        """Check security configuration"""
        print("Checking Security Configuration...")
        
        # Check environment variables for security settings
        env_files = ['.env.example', '.env.production', 'docker-compose.yml']
        
        required_configs = [
            'ENCRYPTION_KEY|SECRET_KEY',
            'DATABASE.*ENCRYPT|DB.*SSL',
            'SESSION.*SECURE|SECURE.*COOKIE'
        ]
        
        for config in required_configs:
            if not any(self._check_pattern_exists(config, [f]) for f in env_files if Path(f).exists()):
                self.violations.append({
                    'requirement': 'security_configuration',
                    'message': f'Missing security configuration: {config}'
                })
                
    def generate_report(self):
        """Generate HIPAA compliance report"""
        total_requirements = sum(len(cat) for cat in self.REQUIREMENTS.values())
        compliant_count = len(self.compliant_items)
        
        print("\n" + "="*80)
        print("🏥 HIPAA Compliance Report")
        print("="*80)
        
        print(f"\nCompliance Score: {compliant_count}/{total_requirements} requirements met")
        print(f"Compliance Percentage: {(compliant_count/total_requirements)*100:.1f}%")
        
        if self.violations:
            print(f"\n❌ Violations Found ({len(self.violations)}):\n")
            for violation in self.violations:
                print(f"  - {violation['requirement']}: {violation['message']}")
        else:
            print("\n✅ All checked requirements are compliant!")
            
        print("\n✅ Compliant Requirements:")
        for item in self.compliant_items:
            print(f"  - {item}")
            
        # HIPAA requires 100% compliance
        if self.violations:
            print("\n🚨 CRITICAL: Application is NOT HIPAA compliant!")
            print("   All violations must be resolved before handling PHI.")
        else:
            print("\n✅ Application meets checked HIPAA requirements!")
            
    def write_json_report(self, output_file: str = 'hipaa-compliance.json'):
        """Write detailed compliance report"""
        total_requirements = sum(len(cat) for cat in self.REQUIREMENTS.values())
        compliant_count = len(self.compliant_items)
        
        report = {
            'compliant': len(self.violations) == 0,
            'score': f"{compliant_count}/{total_requirements}",
            'percentage': (compliant_count/total_requirements)*100,
            'compliant_items': self.compliant_items,
            'violations': self.violations,
            'requirements': self.REQUIREMENTS
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)


def main():
    checker = HIPAAComplianceChecker()
    
    # Run all compliance checks
    checker.check_access_control()
    checker.check_audit_controls()
    checker.check_integrity_controls()
    checker.check_transmission_security()
    checker.check_administrative_safeguards()
    checker.check_configuration_security()
    
    # Generate report
    checker.generate_report()
    checker.write_json_report()
    
    # Exit with error if not compliant
    if checker.violations:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
