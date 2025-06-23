#!/usr/bin/env python
"""Run coverage test to prove we can measure production code coverage."""

import subprocess
import sys
import os

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Set required environment variables
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing"
os.environ["FERNET_KEY"] = "zH8F0WgeF-xyaGdG0XrNwkLq1RwSJHPFanJq3LgQTfY="

print("Starting coverage measurement of production code...")

# Run coverage directly on a Python script that imports production code
test_code = '''
import os
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing"
os.environ["FERNET_KEY"] = "zH8F0WgeF-xyaGdG0XrNwkLq1RwSJHPFanJq3LgQTfY="

# Import and execute production code
from src.services.auth_service import AuthenticationService
from src.auth.password_policy import default_password_policy
from src.core.security import generate_random_password

# Execute code to generate coverage
auth = AuthenticationService(None)
valid, errors = default_password_policy.validate("Test123!@#")
password = generate_random_password(16)

print(f"Auth service created: {auth is not None}")
print(f"Password validation: {valid}")
print(f"Generated password length: {len(password)}")
'''

# Write test script
with open('temp_coverage_test.py', 'w') as f:
    f.write(test_code)

# Run with coverage
result = subprocess.run([
    sys.executable, '-m', 'coverage', 'run',
    '--source=src.services.auth_service,src.auth.password_policy,src.core.security',
    'temp_coverage_test.py'
], capture_output=True, text=True)

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

# Generate coverage report
report_result = subprocess.run([
    sys.executable, '-m', 'coverage', 'report', '-m'
], capture_output=True, text=True)

# Show only relevant lines
for line in report_result.stdout.split('\n'):
    if 'auth_service' in line or 'password_policy' in line or 'security' in line or 'TOTAL' in line:
        print(line)

# Cleanup
os.remove('temp_coverage_test.py')
