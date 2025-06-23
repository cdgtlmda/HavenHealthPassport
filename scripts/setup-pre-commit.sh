#!/bin/bash

# Script to set up pre-commit hooks for Haven Health Passport

# Set colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Setting up pre-commit hooks ===${NC}"

PROJECT_ROOT="/Users/cadenceapeiron/Documents/HavenHealthPassport"
cd "$PROJECT_ROOT"

# Install pre-commit if not already installed
if ! command -v pre-commit &> /dev/null; then
    echo -e "${YELLOW}Installing pre-commit...${NC}"
    pip install pre-commit
fi

# Create pre-commit configuration
echo -e "${BLUE}Creating pre-commit configuration...${NC}"
cat > .pre-commit-config.yaml << 'EOF'
# Pre-commit hooks for Haven Health Passport
# Ensures code quality and healthcare compliance

repos:
  # Security checks
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        exclude: .*\.lock

  # Python security
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ['-ll']
        files: \.py$

  # Type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.5.1
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
        args: [--ignore-missing-imports, --strict]

  # Code formatting
  - repo: https://github.com/psf/black
    rev: 23.9.1
    hooks:
      - id: black
        language_version: python3
        args: [--line-length=88]

  # Import sorting
  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: [--profile=black]

  # Linting
  - repo: https://github.com/PyCQA/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
        args: [--max-line-length=88, --extend-ignore=E203]

  # Docstring checking
  - repo: https://github.com/PyCQA/pydocstyle
    rev: 6.3.0
    hooks:
      - id: pydocstyle
        exclude: ^(tests/|migrations/)

  # General file checks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
        args: ['--maxkb=500']
      - id: check-case-conflict
      - id: check-merge-conflict
      - id: debug-statements
      - id: mixed-line-ending

  # Custom healthcare compliance check
  - repo: local
    hooks:
      - id: healthcare-compliance
        name: Healthcare Compliance Check
        entry: bash -c 'python scripts/check_healthcare_compliance.py'
        language: system
        files: \.py$
        pass_filenames: true

      - id: no-patient-data
        name: No Patient Data in Code
        entry: bash -c 'grep -E "(SSN|DOB|MRN)\s*=\s*[\"\'][^\"\']+[\"\']" "$@" && exit 1 || exit 0'
        language: system
        files: \.py$

# Configuration for specific hooks
default_language_version:
  python: python3.11

ci:
  autofix_commit_msg: |
    [pre-commit.ci] auto fixes from pre-commit.com hooks

    for more information, see https://pre-commit.ci
  autofix_prs: false
  autoupdate_branch: ''
  autoupdate_commit_msg: '[pre-commit.ci] pre-commit autoupdate'
  autoupdate_schedule: weekly
  skip: []
  submodules: false
EOF

# Create healthcare compliance checker
echo -e "${BLUE}Creating healthcare compliance checker...${NC}"
mkdir -p scripts
cat > scripts/check_healthcare_compliance.py << 'EOF'
#!/usr/bin/env python3
"""Check for healthcare compliance issues in Python files."""

import sys
import re
from pathlib import Path

# Patterns that indicate PHI handling
PHI_PATTERNS = [
    r'patient.*data',
    r'medical.*record',
    r'health.*information',
    r'\bPHI\b',
    r'\bPII\b',
    r'diagnosis',
    r'treatment',
    r'prescription'
]

# Patterns that indicate proper encryption
ENCRYPTION_PATTERNS = [
    r'encrypt',
    r'field_encryption',
    r'encrypted',
    r'FieldEncryption',
    r'crypto'
]

# Patterns that indicate audit logging
AUDIT_PATTERNS = [
    r'audit',
    r'log.*access',
    r'track.*access',
    r'AccessLog'
]

def check_file(filepath: str) -> bool:
    """Check a single file for compliance issues."""
    content = Path(filepath).read_text()
    lines = content.split('\n')
    
    issues = []
    
    # Check if file handles PHI
    handles_phi = any(re.search(pattern, content, re.IGNORECASE) 
                     for pattern in PHI_PATTERNS)
    
    if handles_phi:
        # Check for encryption
        has_encryption = any(re.search(pattern, content, re.IGNORECASE) 
                           for pattern in ENCRYPTION_PATTERNS)
        
        # Check for audit logging
        has_audit = any(re.search(pattern, content, re.IGNORECASE) 
                       for pattern in AUDIT_PATTERNS)
        
        if not has_encryption:
            issues.append(f"{filepath}: Handles PHI without encryption")
        
        if not has_audit:
            issues.append(f"{filepath}: Handles PHI without audit logging")
    
    # Check for hardcoded sensitive data
    for i, line in enumerate(lines, 1):
        # Check for potential hardcoded SSN
        if re.search(r'\b\d{3}-\d{2}-\d{4}\b', line):
            issues.append(f"{filepath}:{i}: Potential hardcoded SSN")
        
        # Check for potential hardcoded MRN
        if re.search(r'MRN.*=.*["\'][^"\']+["\']', line):
            issues.append(f"{filepath}:{i}: Potential hardcoded MRN")
    
    # Print issues
    for issue in issues:
        print(issue)
    
    return len(issues) == 0

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: check_healthcare_compliance.py <file1> [file2] ...")
        sys.exit(1)
    
    all_passed = True
    for filepath in sys.argv[1:]:
        if not check_file(filepath):
            all_passed = False
    
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()
EOF

chmod +x scripts/check_healthcare_compliance.py

# Create secrets baseline
echo -e "${BLUE}Creating secrets baseline...${NC}"
detect-secrets scan --baseline .secrets.baseline

# Install pre-commit hooks
echo -e "${BLUE}Installing pre-commit hooks...${NC}"
pre-commit install
pre-commit install --hook-type commit-msg

# Run pre-commit on all files (optional)
echo -e "${YELLOW}Running pre-commit on all files (this may take a while)...${NC}"
echo -e "${YELLOW}You can skip this with Ctrl+C${NC}"
sleep 3
pre-commit run --all-files || true

echo -e "\n${GREEN}✅ Pre-commit hooks successfully installed!${NC}"
echo -e "${BLUE}Hooks will now run automatically before each commit.${NC}"
echo -e "${YELLOW}To manually run hooks: pre-commit run --all-files${NC}"
echo -e "${YELLOW}To skip hooks (emergency only): git commit --no-verify${NC}"