#!/bin/bash

# Haven Health Passport - Admin User Configuration
# This script handles admin user creation and password management

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${SCRIPT_DIR}/../config"
SECURE_DIR="${SCRIPT_DIR}/../.secure"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Admin User Configuration${NC}"
echo -e "${BLUE}================================================${NC}"

# Create secure directory for sensitive data
create_secure_storage() {
    if [ ! -d "${SECURE_DIR}" ]; then
        mkdir -p "${SECURE_DIR}"
        chmod 700 "${SECURE_DIR}"
        echo -e "${GREEN}✓ Created secure storage directory${NC}"
    fi
}

# Generate admin credentials documentation
generate_admin_docs() {
    cat > "${CONFIG_DIR}/admin-user-guide.md" <<'EOF'
# Admin User Configuration Guide

## Admin Username
- Default: `HavenAdmin`
- Purpose: Primary administrator for blockchain network
- Permissions: Full network administration rights

## Password Requirements
- Minimum length: 8 characters
- Must include: uppercase, lowercase, numbers, special characters
- No dictionary words or common patterns
- Regular rotation required (90 days)

## Security Best Practices
1. Never share admin credentials
2. Use MFA when available
3. Rotate passwords regularly
4. Monitor admin activities
5. Use separate accounts for daily operations
EOF
}

# Execute configuration
create_secure_storage
generate_admin_docs

echo -e "\n${GREEN}Admin user configuration completed!${NC}"
echo -e "${YELLOW}Note: Admin password must be set during deployment${NC}"
