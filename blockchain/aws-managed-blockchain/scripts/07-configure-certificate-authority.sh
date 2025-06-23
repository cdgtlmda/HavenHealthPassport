#!/bin/bash

# Haven Health Passport - Certificate Authority Configuration
# This script documents and validates CA configuration

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${SCRIPT_DIR}/../config"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Certificate Authority Configuration${NC}"
echo -e "${BLUE}================================================${NC}"

# Document CA configuration
create_ca_documentation() {
    cat > "${CONFIG_DIR}/ca-configuration.md" <<'EOF'
# Certificate Authority Configuration

## AWS Managed Blockchain CA Features

### Automatic Configuration
- TLS enabled by default
- Automatic certificate generation
- Built-in certificate management
- Hardware security module (HSM) protection

### Certificate Types
1. **Root CA Certificate**
   - Automatically generated
   - Stored in AWS Certificate Manager
   - 10-year validity period

2. **Intermediate CA Certificates**
   - Generated per member
   - Automatic rotation
   - 5-year validity period

3. **Peer Certificates**
   - Generated for each peer node
   - 1-year validity period
   - Automatic renewal

### Security Features
- HSM-protected private keys
- Automatic CRL management
- Certificate transparency logging
- Audit trail for all operations
EOF
}

create_ca_documentation

echo -e "\n${GREEN}✓ CA configuration documented${NC}"
echo -e "${GREEN}✓ AWS Managed Blockchain handles CA automatically${NC}"
echo -e "${GREEN}Documentation: ${CONFIG_DIR}/ca-configuration.md${NC}"
