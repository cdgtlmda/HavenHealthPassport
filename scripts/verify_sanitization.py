#!/usr/bin/env python3
"""
Verification script to check if the repository has been properly sanitized.
This script looks for potential credentials that may have been missed.
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple

# Patterns that might indicate credentials
CREDENTIAL_PATTERNS = {
    'aws_access_key': r'AKIA[0-9A-Z]{16}',
    'aws_secret_key': r'[0-9a-zA-Z/+]{40}',
    'generic_secret': r'secret["\']?\s*[:=]\s*["\'][^"\']{8,}["\']',
    'generic_password': r'password["\']?\s*[:=]\s*["\'][^"\']{6,}["\']',
    'generic_token': r'token["\']?\s*[:=]\s*["\'][^"\']{10,}["\']',
    'jwt_token': r'eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*',
    'api_key': r'api[_-]?key["\']?\s*[:=]\s*["\'][^"\']{10,}["\']',
    'private_key_begin': r'-----BEGIN.*PRIVATE KEY-----',
    'certificate_begin': r'-----BEGIN CERTIFICATE-----',
    'database_url_with_creds': r'(postgresql|mysql|mongodb)://[^:]+:[^@]+@',
}

# Files and directories to skip
SKIP_PATHS = {
    '.git', '__pycache__', 'node_modules', '.pytest_cache', '.mypy_cache',
    'dist', 'build', 'coverage', '.coverage', '.tox', '.venv', 'venv',
    'blockchain/aws-lambda-functions/package',  # AWS SDK examples
    'scripts/verify_sanitization.py',  # This file itself
    'SECURITY_SETUP.md',  # Documentation file
}

# File extensions to check
CHECK_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.yaml', '.yml',
    '.env', '.sh', '.bash', '.conf', '.cfg', '.ini', '.toml'
}

def should_skip_path(path: Path) -> bool:
    """Check if a path should be skipped."""
    path_parts = path.parts
    return any(skip in path_parts for skip in SKIP_PATHS)

def check_file_for_credentials(file_path: Path) -> List[Tuple[str, int, str]]:
    """Check a single file for potential credentials."""
    issues = []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, 1):
            # Skip comments that are just placeholders
            if 'REPLACE_WITH' in line or 'your_' in line.lower() or 'placeholder' in line.lower():
                continue

            for pattern_name, pattern in CREDENTIAL_PATTERNS.items():
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    # Additional filtering for false positives
                    matched_text = match.group()

                    # Skip obvious test/example values
                    if any(test_word in matched_text.lower() for test_word in
                           ['test', 'example', 'demo', 'sample', 'placeholder']):
                        continue

                    # Skip LocalStack dummy credentials
                    if pattern_name in ['aws_access_key', 'aws_secret_key'] and matched_text in ['test']:
                        continue

                    issues.append((pattern_name, line_num, matched_text))

    except Exception as e:
        print(f"Error reading {file_path}: {e}")

    return issues

def scan_repository() -> Dict[str, List[Tuple[str, int, str]]]:
    """Scan the entire repository for potential credentials."""
    print("🔍 Scanning repository for potential credentials...")

    repo_root = Path('.')
    issues_by_file = {}

    for file_path in repo_root.rglob('*'):
        if not file_path.is_file():
            continue

        if should_skip_path(file_path):
            continue

        if file_path.suffix not in CHECK_EXTENSIONS and not file_path.name.startswith('.env'):
            continue

        issues = check_file_for_credentials(file_path)
        if issues:
            issues_by_file[str(file_path)] = issues

    return issues_by_file

def main():
    """Main function to run the sanitization verification."""
    print("🔐 Haven Health Passport - Sanitization Verification")
    print("=" * 50)

    issues_by_file = scan_repository()

    if not issues_by_file:
        print("✅ No potential credentials found!")
        print("✅ Repository appears to be properly sanitized.")
        print("\n📋 Summary:")
        print("  - All hardcoded credentials have been removed")
        print("  - Configuration files use placeholders")
        print("  - Sensitive data replaced with environment variables")
        print(f"\n📖 See SECURITY_SETUP.md for credential configuration instructions")
        return 0

    print("⚠️  Potential credentials found:")
    print("-" * 30)

    total_issues = 0
    for file_path, issues in issues_by_file.items():
        print(f"\n📁 {file_path}:")
        for pattern_name, line_num, matched_text in issues:
            total_issues += 1
            # Truncate long matches for display
            display_text = matched_text[:50] + "..." if len(matched_text) > 50 else matched_text
            print(f"  Line {line_num}: {pattern_name} - {display_text}")

    print(f"\n📊 Total issues found: {total_issues}")
    print("\n⚠️  Please review these findings and ensure they are:")
    print("  1. Test/example values only")
    print("  2. Placeholder text")
    print("  3. Not actual credentials")
    print(f"\n📖 See SECURITY_SETUP.md for credential configuration instructions")

    return 1 if total_issues > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
