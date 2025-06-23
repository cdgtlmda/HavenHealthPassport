#!/usr/bin/env python3
"""
PHI Encryption Coverage Verifier
Ensures all PHI fields are properly encrypted in the healthcare system
"""

import ast
import json
import re
import sys
from pathlib import Path
from typing import Set, Dict, List, Tuple


class PHIEncryptionVerifier:
    """Verify all PHI fields are properly encrypted"""
    
    # PHI fields that MUST be encrypted
    PHI_FIELDS = {
        # Patient identifiers
        'ssn', 'social_security_number', 'social_security',
        'medical_record_number', 'mrn', 'patient_id',
        'insurance_id', 'insurance_number', 'policy_number',
        'drivers_license', 'passport_number', 'national_id',
        
        # Personal information
        'date_of_birth', 'dateOfBirth', 'dob', 'birth_date',
        'patient_name', 'full_name', 'first_name', 'last_name',
        'middle_name', 'maiden_name', 'patient_address',
        'street_address', 'home_address', 'email', 'email_address',
        'phone', 'phone_number', 'mobile_number', 'fax_number',
        
        # Medical information
        'diagnosis', 'diagnoses', 'medical_history', 'medications',
        'allergies', 'treatment', 'prescription', 'lab_results',
        'test_results', 'procedure', 'surgery', 'condition',
        'symptom', 'vital_signs', 'blood_type', 'genetic_info',
        
        # Financial/Insurance
        'credit_card', 'bank_account', 'billing_info',
        'payment_method', 'insurance_details'
    }
    
    # Acceptable encryption indicators
    ENCRYPTION_PATTERNS = {
        'function_calls': [
            'encrypt', 'decrypt', 'hash', 'encode', 'cipher',
            'encryptField', 'encryptPHI', 'secureField',
            'hashPassword', 'bcrypt', 'argon2', 'scrypt'
        ],
        'decorators': [
            '@encrypted', '@secure', '@protected', '@phi_encrypted',
            '@encrypt_field', '@sensitive_field'
        ],
        'class_names': [
            'EncryptedField', 'SecureField', 'PHIField',
            'EncryptedCharField', 'EncryptedTextField'
        ]
    }
    
    def __init__(self):
        self.violations = []
        self.encrypted_fields = set()
        self.unencrypted_fields = set()
        
    def verify_all_files(self, source_dirs: List[str] = ['src', 'web/src']):
        """Verify encryption in all source files"""
        for source_dir in source_dirs:
            if Path(source_dir).exists():
                self._verify_directory(Path(source_dir))
                
    def _verify_directory(self, directory: Path):
        """Verify all files in a directory"""
        # Python files
        for py_file in directory.rglob("*.py"):
            self._verify_python_file(py_file)
            
        # JavaScript/TypeScript files
        for ext in ['*.js', '*.jsx', '*.ts', '*.tsx']:
            for js_file in directory.rglob(ext):
                self._verify_javascript_file(js_file)
                
    def _verify_python_file(self, file_path: Path):
        """Verify PHI encryption in Python file"""
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
            
            # Check class definitions for model fields
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    self._check_python_class(node, file_path)
                elif isinstance(node, ast.Assign):
                    self._check_python_assignment(node, file_path)
                elif isinstance(node, ast.FunctionDef):
                    self._check_python_function(node, file_path)
                    
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            
    def _check_python_class(self, class_node: ast.ClassDef, file_path: Path):
        """Check Python class for PHI fields"""
        # Check if it's a model class
        is_model = any(
            base.id in ['Model', 'BaseModel', 'Document']
            for base in class_node.bases
            if isinstance(base, ast.Name)
        )
        
        if not is_model:
            return
            
        # Check each field
        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.id.lower()
                        if self._is_phi_field(field_name):
                            # Check if field is encrypted
                            if not self._is_encrypted_field(node.value, content):
                                self.violations.append({
                                    'file': str(file_path),
                                    'line': node.lineno,
                                    'field': field_name,
                                    'type': 'unencrypted_model_field',
                                    'class': class_node.name
                                })
                                self.unencrypted_fields.add(field_name)
                            else:
                                self.encrypted_fields.add(field_name)
                                
    def _check_python_assignment(self, assign_node: ast.Assign, file_path: Path):
        """Check Python assignments for PHI"""
        for target in assign_node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id.lower()
                if self._is_phi_field(var_name):
                    # Check if value is encrypted
                    if not self._is_encrypted_value(assign_node.value):
                        self.violations.append({
                            'file': str(file_path),
                            'line': assign_node.lineno,
                            'field': var_name,
                            'type': 'unencrypted_assignment'
                        })
                        
    def _check_python_function(self, func_node: ast.FunctionDef, file_path: Path):
        """Check Python function for PHI handling"""
        # Check function parameters
        for arg in func_node.args.args:
            if self._is_phi_field(arg.arg.lower()):
                # Check if function has encryption decorator
                has_encryption = any(
                    isinstance(dec, ast.Name) and dec.id in ['encrypt_params', 'secure_function']
                    for dec in func_node.decorator_list
                )
                
                if not has_encryption:
                    # Check if encryption happens in function body
                    if not self._function_encrypts_data(func_node):
                        self.violations.append({
                            'file': str(file_path),
                            'line': func_node.lineno,
                            'field': arg.arg,
                            'type': 'unencrypted_parameter',
                            'function': func_node.name
                        })
                        
    def _verify_javascript_file(self, file_path: Path):
        """Verify PHI encryption in JavaScript/TypeScript file"""
        try:
            content = file_path.read_text()
            lines = content.split('\n')
            
            for i, line in enumerate(lines, 1):
                # Check for PHI field definitions
                for phi_field in self.PHI_FIELDS:
                    if phi_field in line.lower():
                        # Check if line has encryption
                        if not any(pattern in line for pattern in self.ENCRYPTION_PATTERNS['function_calls']):
                            # Check context (previous/next lines)
                            context_encrypted = self._check_js_context(lines, i-1)
                            if not context_encrypted:
                                self.violations.append({
                                    'file': str(file_path),
                                    'line': i,
                                    'field': phi_field,
                                    'type': 'potential_unencrypted_field'
                                })
                                
        except Exception as e:
            print(f"Error checking {file_path}: {e}")
            
    def _is_phi_field(self, field_name: str) -> bool:
        """Check if field name is a PHI field"""
        field_lower = field_name.lower()
        return any(
            phi in field_lower or field_lower in phi
            for phi in self.PHI_FIELDS
        )
        
    def _is_encrypted_field(self, value_node: ast.AST, file_content: str) -> bool:
        """Check if a field value indicates encryption"""
        if isinstance(value_node, ast.Call):
            if isinstance(value_node.func, ast.Name):
                # Check for encrypted field types
                return value_node.func.id in self.ENCRYPTION_PATTERNS['class_names']
                
        return False
        
    def _is_encrypted_value(self, value_node: ast.AST) -> bool:
        """Check if a value is encrypted"""
        if isinstance(value_node, ast.Call):
            if isinstance(value_node.func, ast.Name):
                return value_node.func.id in self.ENCRYPTION_PATTERNS['function_calls']
            elif isinstance(value_node.func, ast.Attribute):
                return value_node.func.attr in self.ENCRYPTION_PATTERNS['function_calls']
                
        return False
        
    def _function_encrypts_data(self, func_node: ast.FunctionDef) -> bool:
        """Check if function body contains encryption calls"""
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.ENCRYPTION_PATTERNS['function_calls']:
                        return True
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in self.ENCRYPTION_PATTERNS['function_calls']:
                        return True
                        
        return False
        
    def _check_js_context(self, lines: List[str], line_num: int) -> bool:
        """Check surrounding lines for encryption in JS/TS files"""
        # Check 2 lines before and after
        start = max(0, line_num - 2)
        end = min(len(lines), line_num + 3)
        
        context = '\n'.join(lines[start:end])
        
        return any(
            pattern in context
            for pattern in self.ENCRYPTION_PATTERNS['function_calls']
        )
        
    def verify_database_schemas(self):
        """Verify database schema files for encryption"""
        schema_files = [
            'alembic/versions/*.py',
            'src/models/*.py',
            'database/migrations/*.sql'
        ]
        
        for pattern in schema_files:
            for schema_file in Path('.').glob(pattern):
                self._verify_schema_file(schema_file)
                
    def _verify_schema_file(self, file_path: Path):
        """Verify schema file for PHI encryption"""
        try:
            content = file_path.read_text()
            
            for phi_field in self.PHI_FIELDS:
                if phi_field in content.lower():
                    # Check if field has encryption indicator
                    pattern = f"{phi_field}.*(?:encrypted|cipher|secure|hash)"
                    if not re.search(pattern, content, re.IGNORECASE):
                        self.violations.append({
                            'file': str(file_path),
                            'field': phi_field,
                            'type': 'unencrypted_schema_field'
                        })
                        
        except Exception as e:
            print(f"Error checking schema {file_path}: {e}")
            
    def generate_report(self):
        """Generate encryption coverage report"""
        print("\n🔐 PHI Encryption Coverage Report\n")
        print("=" * 80)
        
        if self.violations:
            print(f"\n❌ Found {len(self.violations)} potential encryption violations:\n")
            
            # Group by type
            by_type = {}
            for violation in self.violations:
                vtype = violation['type']
                if vtype not in by_type:
                    by_type[vtype] = []
                by_type[vtype].append(violation)
                
            for vtype, violations in by_type.items():
                print(f"\n{vtype.upper().replace('_', ' ')}:")
                for v in violations[:10]:  # Show first 10
                    print(f"  - {v['file']}:{v.get('line', 'N/A')} - Field: {v['field']}")
                    if 'class' in v:
                        print(f"    In class: {v['class']}")
                    if 'function' in v:
                        print(f"    In function: {v['function']}")
                        
                if len(violations) > 10:
                    print(f"  ... and {len(violations) - 10} more")
                    
            print("\n🚨 All PHI fields MUST be encrypted!")
            print("\nRequired actions:")
            print("1. Use EncryptedField for Django models")
            print("2. Call encryptPHI() for all PHI in JavaScript")
            print("3. Use @encrypt_field decorator for sensitive data")
            print("4. Ensure all database columns use encryption")
            
        else:
            print("\n✅ All PHI fields appear to be properly encrypted!")
            
        # Summary
        print(f"\n📊 Summary:")
        print(f"  - Encrypted fields found: {len(self.encrypted_fields)}")
        print(f"  - Potential violations: {len(self.violations)}")
        print(f"  - Unique unencrypted fields: {len(self.unencrypted_fields)}")
        
    def write_json_report(self, output_file: str = 'encryption-coverage.json'):
        """Write detailed report to JSON"""
        report = {
            'summary': {
                'total_violations': len(self.violations),
                'encrypted_fields': list(self.encrypted_fields),
                'unencrypted_fields': list(self.unencrypted_fields),
                'coverage_percentage': (
                    len(self.encrypted_fields) / 
                    (len(self.encrypted_fields) + len(self.unencrypted_fields))
                    * 100 if (self.encrypted_fields or self.unencrypted_fields) else 100
                )
            },
            'violations': self.violations,
            'passed': len(self.violations) == 0
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description='Verify PHI encryption coverage')
    parser.add_argument('--output', default='encryption-coverage.json',
                       help='Output file for detailed report')
    parser.add_argument('--source-dirs', nargs='+', 
                       default=['src', 'web/src'],
                       help='Source directories to scan')
    args = parser.parse_args()
    
    verifier = PHIEncryptionVerifier()
    
    # Verify all source files
    verifier.verify_all_files(args.source_dirs)
    
    # Verify database schemas
    verifier.verify_database_schemas()
    
    # Generate reports
    verifier.generate_report()
    verifier.write_json_report(args.output)
    
    # Exit with error if violations found
    if verifier.violations:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
