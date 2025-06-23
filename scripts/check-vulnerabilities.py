#!/usr/bin/env python3
"""
Vulnerability Checker for Healthcare Application
Zero tolerance for critical vulnerabilities in medical software
"""

import json
import sys
import argparse
from typing import Dict, List, Tuple
from pathlib import Path


class VulnerabilityChecker:
    """Check for security vulnerabilities in dependencies"""
    
    # Known vulnerable packages that must never be used in healthcare
    BANNED_PACKAGES = {
        'python': [
            'pycrypto',      # Use cryptography instead
            'md5',           # Weak hashing
            'sha1',          # Weak hashing
            'pickle',        # Insecure serialization
            'eval',          # Code injection risk
        ],
        'javascript': [
            'jsonwebtoken<9.0.0',  # JWT vulnerabilities
            'express<4.17.3',      # Security fixes
            'axios<0.21.2',        # SSRF vulnerability
            'lodash<4.17.21',      # Prototype pollution
            'serialize-javascript<3.1.0',  # Code injection
        ]
    }
    
    # Healthcare-specific vulnerability patterns
    HEALTHCARE_PATTERNS = {
        'weak_crypto': "Weak cryptography for PHI protection",
        'auth_bypass': "Authentication bypass vulnerability",
        'phi_exposure': "Potential PHI exposure through {vector}",
        'audit_bypass': "Audit logging can be bypassed",
        'injection': "{type} injection vulnerability",
        'insecure_comm': "Insecure communication channel for medical data",
        'session_fixation': "Session fixation in medical portal",
        'weak_random': "Weak randomness for medical identifiers"
    }
    
    def __init__(self, max_critical: int = 0, max_high: int = 0):
        self.max_critical = max_critical
        self.max_high = max_high
        self.vulnerabilities = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': []
        }
        
    def check_python_vulnerabilities(self, report_file: str = 'safety-report.json'):
        """Check Python package vulnerabilities from safety check"""
        try:
            with open(report_file, 'r') as f:
                report = json.load(f)
                
            # Safety report format varies, handle both formats
            vulns = report.get('vulnerabilities', report.get('results', []))
            
            for vuln in vulns:
                self._process_python_vulnerability(vuln)
                
        except FileNotFoundError:
            print(f"Python vulnerability report not found: {report_file}")
        except Exception as e:
            print(f"Error reading Python vulnerabilities: {e}")
            
    def check_javascript_vulnerabilities(self, report_file: str = 'web/npm-audit.json'):
        """Check JavaScript package vulnerabilities from npm audit"""
        try:
            with open(report_file, 'r') as f:
                report = json.load(f)
                
            # Process npm audit vulnerabilities
            if 'vulnerabilities' in report:
                for pkg_name, vuln_info in report['vulnerabilities'].items():
                    self._process_npm_vulnerability(pkg_name, vuln_info)
                    
        except FileNotFoundError:
            print(f"JavaScript vulnerability report not found: {report_file}")
        except Exception as e:
            print(f"Error reading JavaScript vulnerabilities: {e}")
            
    def _process_python_vulnerability(self, vuln: Dict):
        """Process individual Python vulnerability"""
        severity = vuln.get('severity', 'unknown').lower()
        package = vuln.get('package', vuln.get('package_name', 'unknown'))
        description = vuln.get('description', vuln.get('vulnerability', ''))
        
        # Check if it's healthcare-critical
        is_healthcare_critical = self._is_healthcare_critical(package, description)
        
        # Upgrade severity for healthcare-critical vulnerabilities
        if is_healthcare_critical and severity in ['medium', 'low']:
            severity = 'high'
            
        vuln_info = {
            'package': package,
            'severity': severity,
            'description': description,
            'healthcare_critical': is_healthcare_critical,
            'cve': vuln.get('cve', vuln.get('vulnerability_id', 'N/A')),
            'fixed_in': vuln.get('fixed_in', vuln.get('secure_version', 'N/A'))
        }
        
        if severity in self.vulnerabilities:
            self.vulnerabilities[severity].append(vuln_info)
            
    def _process_npm_vulnerability(self, package: str, vuln_info: Dict):
        """Process individual npm vulnerability"""
        severity = vuln_info.get('severity', 'unknown').lower()
        
        # npm audit provides via array for dependency chain
        via = vuln_info.get('via', [])
        description = via[0] if isinstance(via, list) and via else str(via)
        
        # Check if it's healthcare-critical
        is_healthcare_critical = self._is_healthcare_critical(package, str(description))
        
        # Upgrade severity for healthcare-critical vulnerabilities
        if is_healthcare_critical and severity in ['moderate', 'low']:
            severity = 'high'
            
        vuln_data = {
            'package': package,
            'severity': severity,
            'description': description,
            'healthcare_critical': is_healthcare_critical,
            'range': vuln_info.get('range', 'N/A'),
            'fixed_in': vuln_info.get('fixAvailable', False)
        }
        
        # Map npm severity levels
        if severity == 'moderate':
            severity = 'medium'
            
        if severity in self.vulnerabilities:
            self.vulnerabilities[severity].append(vuln_data)
            
    def _is_healthcare_critical(self, package: str, description: str) -> bool:
        """Determine if vulnerability is critical for healthcare"""
        critical_keywords = [
            'authentication', 'authorization', 'crypto', 'encryption',
            'session', 'token', 'jwt', 'password', 'injection', 'xss',
            'sql', 'command', 'path traversal', 'xxe', 'deserialization'
        ]
        
        description_lower = description.lower()
        package_lower = package.lower()
        
        # Check if package handles critical functionality
        critical_packages = [
            'django', 'flask', 'express', 'jsonwebtoken', 'bcrypt',
            'crypto', 'auth', 'session', 'passport', 'cors'
        ]
        
        return (
            any(keyword in description_lower for keyword in critical_keywords) or
            any(pkg in package_lower for pkg in critical_packages)
        )
        
    def check_banned_packages(self):
        """Check for banned packages in requirements/package.json"""
        # Check Python requirements
        req_files = ['requirements.txt', 'requirements/base.txt', 'requirements/production.txt']
        for req_file in req_files:
            if Path(req_file).exists():
                self._check_python_requirements(req_file)
                
        # Check JavaScript packages
        package_json = Path('web/package.json')
        if package_json.exists():
            self._check_javascript_packages(package_json)
            
    def _check_python_requirements(self, req_file: str):
        """Check Python requirements for banned packages"""
        try:
            with open(req_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        package = line.split('==')[0].split('>=')[0].split('<')[0]
                        if package in self.BANNED_PACKAGES['python']:
                            self.vulnerabilities['critical'].append({
                                'package': package,
                                'severity': 'critical',
                                'description': f"Banned package for healthcare: {package}",
                                'healthcare_critical': True,
                                'banned': True
                            })
        except Exception as e:
            print(f"Error checking {req_file}: {e}")
            
    def _check_javascript_packages(self, package_json: Path):
        """Check JavaScript packages for banned/vulnerable versions"""
        try:
            with open(package_json, 'r') as f:
                data = json.load(f)
                
            all_deps = {}
            all_deps.update(data.get('dependencies', {}))
            all_deps.update(data.get('devDependencies', {}))
            
            for package, version in all_deps.items():
                for banned in self.BANNED_PACKAGES['javascript']:
                    if '<' in banned:
                        pkg_name, min_version = banned.split('<')
                        if package == pkg_name:
                            # Simple version check (would need proper semver in production)
                            self.vulnerabilities['critical'].append({
                                'package': package,
                                'severity': 'critical',
                                'description': f"Vulnerable version: {package}@{version} (need >={min_version})",
                                'healthcare_critical': True,
                                'version': version
                            })
        except Exception as e:
            print(f"Error checking package.json: {e}")
            
    def generate_report(self):
        """Generate vulnerability report"""
        total_critical = len(self.vulnerabilities['critical'])
        total_high = len(self.vulnerabilities['high'])
        
        print("\n🔒 Security Vulnerability Report\n")
        print(f"Critical: {total_critical} | High: {total_high} | Medium: {len(self.vulnerabilities['medium'])} | Low: {len(self.vulnerabilities['low'])}")
        print("=" * 80)
        
        if total_critical > 0:
            print("\n❌ CRITICAL VULNERABILITIES (Must fix immediately):")
            for vuln in self.vulnerabilities['critical']:
                self._print_vulnerability(vuln)
                
        if total_high > 0:
            print("\n⚠️  HIGH VULNERABILITIES:")
            for vuln in self.vulnerabilities['high']:
                self._print_vulnerability(vuln)
                
        # Check thresholds
        if total_critical > self.max_critical:
            print(f"\n🚨 FAILED: {total_critical} critical vulnerabilities exceed limit of {self.max_critical}")
            print("   This application CANNOT be deployed to handle patient data!")
            
        if total_high > self.max_high:
            print(f"\n🚨 FAILED: {total_high} high vulnerabilities exceed limit of {self.max_high}")
            
        if total_critical == 0 and total_high == 0:
            print("\n✅ No critical or high vulnerabilities found!")
            
    def _print_vulnerability(self, vuln: Dict):
        """Print individual vulnerability details"""
        healthcare_marker = "🏥 " if vuln.get('healthcare_critical') else ""
        print(f"\n{healthcare_marker}Package: {vuln['package']}")
        print(f"  Severity: {vuln['severity'].upper()}")
        print(f"  Description: {vuln['description']}")
        if vuln.get('cve'):
            print(f"  CVE: {vuln['cve']}")
        if vuln.get('fixed_in'):
            print(f"  Fixed in: {vuln['fixed_in']}")
            
    def write_json_report(self, output_file: str = 'vulnerability-report.json'):
        """Write detailed vulnerability report"""
        report = {
            'summary': {
                'critical': len(self.vulnerabilities['critical']),
                'high': len(self.vulnerabilities['high']),
                'medium': len(self.vulnerabilities['medium']),
                'low': len(self.vulnerabilities['low']),
                'healthcare_critical': sum(
                    1 for severity in self.vulnerabilities.values()
                    for vuln in severity if vuln.get('healthcare_critical')
                )
            },
            'vulnerabilities': self.vulnerabilities,
            'passed': (
                len(self.vulnerabilities['critical']) <= self.max_critical and
                len(self.vulnerabilities['high']) <= self.max_high
            )
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description='Check for security vulnerabilities')
    parser.add_argument('--max-critical', type=int, default=0,
                       help='Maximum allowed critical vulnerabilities')
    parser.add_argument('--max-high', type=int, default=0,
                       help='Maximum allowed high vulnerabilities')
    parser.add_argument('--output', default='vulnerability-report.json',
                       help='Output file for detailed report')
    args = parser.parse_args()
    
    checker = VulnerabilityChecker(args.max_critical, args.max_high)
    
    # Check vulnerability reports
    checker.check_python_vulnerabilities()
    checker.check_javascript_vulnerabilities()
    
    # Check for banned packages
    checker.check_banned_packages()
    
    # Generate reports
    checker.generate_report()
    checker.write_json_report(args.output)
    
    # Exit with error if thresholds exceeded
    if (len(checker.vulnerabilities['critical']) > args.max_critical or
        len(checker.vulnerabilities['high']) > args.max_high):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
