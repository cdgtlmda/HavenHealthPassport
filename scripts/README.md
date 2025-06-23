# Haven Health Passport Scripts

This directory contains utility scripts for maintaining code quality and compliance in the Haven Health Passport project.

## Compliance Scripts

### check-compliance.sh

Comprehensive code compliance checking script that runs multiple quality and security checks.

```bash
./scripts/check-compliance.sh
```

**What it checks:**
1. **Healthcare Compliance** (CRITICAL)
   - FHIR resource validation
   - HIPAA compliance (PHI encryption, audit logging)
   - Medical data handling standards

2. **Security** (bandit)
   - SQL injection vulnerabilities
   - Hardcoded passwords
   - Insecure cryptographic practices
   - Other security anti-patterns

3. **Type Safety** (mypy)
   - Type annotations
   - Type consistency
   - Strict typing rules

4. **Testing**
   - Test failures
   - Code coverage (minimum 80% for medical software)

5. **Code Quality** (pylint)
   - Code errors
   - Code smells
   - Best practices

6. **Code Formatting**
   - Black formatting
   - Import sorting (isort)

7. **Style Guide** (flake8)
   - PEP 8 compliance
   - Code style consistency

8. **Documentation**
   - Missing docstrings
   - Documentation completeness

9. **Code Complexity**
   - Cyclomatic complexity
   - Function complexity

**Output:**
- Summary report in terminal
- Detailed reports in `compliance_reports/`
- Error chunks in `error_chunks/` (500 lines each)

### count-errors.sh

Quick error counting script for rapid feedback.

```bash
./scripts/count-errors.sh
```

**Features:**
- Fast execution (runs checks in parallel)
- Focuses on critical issues
- Shows counts for:
  - HIPAA compliance issues
  - Security issues (High/Medium severity)
  - Failed tests
  - Type errors
  - Formatting issues

### verify-fix.sh

Verify fixes for individual files.

```bash
./scripts/verify-fix.sh src/auth/oauth2.py
```

**What it does:**
- Runs all quality checks on a single file
- Provides immediate feedback
- Shows which checks pass/fail
- Suggests fixes for common issues

## Setup and Initialization Scripts

### setup-dev-env.sh

Sets up the complete development environment.

```bash
./scripts/setup-dev-env.sh
```

**What it does:**
- Creates virtual environment
- Installs all dependencies
- Sets up pre-commit hooks
- Configures IDE settings
- Initializes database
- Sets up test data

### init-database.sh

Initializes the database with schema and test data.

```bash
./scripts/init-database.sh
```

**Features:**
- Creates database schema
- Runs migrations
- Loads test data
- Sets up test users
- Configures FHIR resources

## Testing Scripts

### run-tests.sh

Runs the complete test suite with coverage.

```bash
./scripts/run-tests.sh
```

**Options:**
- `--unit` - Run only unit tests
- `--integration` - Run only integration tests
- `--e2e` - Run only end-to-end tests
- `--coverage` - Generate coverage report
- `--parallel` - Run tests in parallel

### test-healthcare-compliance.sh

Specialized tests for healthcare standards.

```bash
./scripts/test-healthcare-compliance.sh
```

**What it tests:**
- FHIR resource validation
- HL7 message parsing
- HIPAA compliance rules
- Encryption standards
- Audit logging

## Deployment Scripts

### deploy-staging.sh

Deploys to staging environment.

```bash
./scripts/deploy-staging.sh
```

**Process:**
1. Runs all compliance checks
2. Builds Docker images
3. Runs database migrations
4. Deploys to AWS ECS
5. Runs smoke tests
6. Updates monitoring

### deploy-production.sh

Deploys to production with safety checks.

```bash
./scripts/deploy-production.sh
```

**Safety features:**
- Requires manual confirmation
- Backs up database
- Blue-green deployment
- Automatic rollback on failure
- Health check monitoring

## Maintenance Scripts

### backup-database.sh

Creates encrypted database backups.

```bash
./scripts/backup-database.sh
```

**Features:**
- Encrypted backups
- Compression
- S3 upload
- Retention policy
- HIPAA compliant

### rotate-secrets.sh

Rotates all secrets and encryption keys.

```bash
./scripts/rotate-secrets.sh
```

**What it rotates:**
- Database passwords
- API keys
- JWT secrets
- Encryption keys
- OAuth credentials

### clean-logs.sh

Cleans old logs while maintaining compliance.

```bash
./scripts/clean-logs.sh
```

**Features:**
- Maintains audit logs (7 years for HIPAA)
- Archives old logs
- Compresses log files
- Uploads to secure storage

## Best Practices

### Running Compliance Checks

1. **Before committing:**
   ```bash
   ./scripts/count-errors.sh
   ```

2. **Before pull requests:**
   ```bash
   ./scripts/check-compliance.sh
   ```

3. **After fixing issues:**
   ```bash
   ./scripts/verify-fix.sh <file_path>
   ```

### Fixing Common Issues

**Formatting issues:**
```bash
black src/ tests/
isort src/ tests/
```

**Type errors:**
```bash
# Add type hints to functions
# Use Optional[] for nullable types
# Import from typing module
```

**Security issues:**
```bash
# Never hardcode secrets
# Use environment variables
# Validate all inputs
# Use parameterized queries
```

**Healthcare compliance:**
```bash
# Always encrypt PHI
# Add audit logging
# Validate FHIR resources
# Follow HIPAA guidelines
```

## CI/CD Integration

These scripts are integrated into the CI/CD pipeline:

1. **Pre-commit hooks** run `count-errors.sh`
2. **Pull request checks** run `check-compliance.sh`
3. **Deployment pipeline** runs full compliance suite
4. **Nightly builds** run comprehensive tests

## Troubleshooting

### Script not found
```bash
chmod +x scripts/*.sh
```

### Missing dependencies
```bash
pip install -r requirements-dev.txt
```

### Virtual environment issues
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Permission denied
```bash
sudo chown -R $USER:$USER .
```

## Contributing

When adding new scripts:

1. Follow the naming convention: `action-target.sh`
2. Add proper error handling
3. Include help text
4. Update this README
5. Make scripts executable
6. Test on all platforms