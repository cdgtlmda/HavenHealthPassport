#!/bin/bash

# TLS Certificate Generation Script
# Haven Health Passport - Blockchain TLS Setup

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
TLS_CONFIG="${SCRIPT_DIR}/../config/tls/tls-certificate-config.yaml"
CERT_OUTPUT_DIR="${SCRIPT_DIR}/../config/tls/certificates"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

# Create directory structure
setup_directories() {
    log_section "Setting up directory structure"

    mkdir -p "${CERT_OUTPUT_DIR}"/{ca,orderer,peer,client,admin}
    mkdir -p "${CERT_OUTPUT_DIR}"/ca/{root,intermediate}

    log_info "Directory structure created"
}

# Generate Root CA certificate
generate_root_ca() {
    log_section "Generating Root CA Certificate"

    local ca_dir="${CERT_OUTPUT_DIR}/ca/root"

    # Generate private key using AWS KMS
    log_info "Creating KMS key for Root CA"
    local kms_key_id=$(aws kms create-key \
        --description "Haven Health Blockchain Root CA Key" \
        --key-usage SIGN_VERIFY \
        --key-spec ECC_NIST_P256 \
        --region "${AWS_REGION}" \
        --query 'KeyMetadata.KeyId' \
        --output text)

    # Create alias
    aws kms create-alias \
        --alias-name "alias/haven-health-blockchain-root-ca" \
        --target-key-id "${kms_key_id}" \
        --region "${AWS_REGION}"

    # Generate CSR using OpenSSL with KMS provider
    cat > "${ca_dir}/root-ca.conf" <<EOF
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_ca
prompt = no

[req_distinguished_name]
C = US
ST = Virginia
L = Arlington
O = Haven Health Passport
OU = Blockchain Infrastructure
CN = Haven Health Blockchain Root CA

[v3_ca]
basicConstraints = critical,CA:TRUE
keyUsage = critical,digitalSignature,keyEncipherment,keyCertSign,cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
EOF

    # For development, generate local key (in production, use KMS)
    openssl ecparam -name prime256v1 -genkey -noout -out "${ca_dir}/root-ca-key.pem"

    # Generate self-signed certificate
    openssl req -new -x509 -days 3650 \
        -config "${ca_dir}/root-ca.conf" \
        -key "${ca_dir}/root-ca-key.pem" \
        -out "${ca_dir}/root-ca-cert.pem"

    # Store in AWS Secrets Manager
    aws secretsmanager create-secret \
        --name "haven-health-blockchain-tls/root-ca-key" \
        --description "Root CA private key" \
        --secret-string file://"${ca_dir}/root-ca-key.pem" \
        --region "${AWS_REGION}" || true

    # Store certificate in Parameter Store
    aws ssm put-parameter \
        --name "/haven-health/blockchain/tls/ca-cert" \
        --value "$(cat ${ca_dir}/root-ca-cert.pem)" \
        --type "String" \
        --description "Root CA certificate" \
        --region "${AWS_REGION}" \
        --overwrite || true

    log_info "Root CA certificate generated"
}

# Generate Intermediate CA certificates
generate_intermediate_ca() {
    local ca_name=$1
    local ca_cn=$2
    local ca_ou=$3

    log_section "Generating Intermediate CA: ${ca_name}"

    local ca_dir="${CERT_OUTPUT_DIR}/ca/intermediate/${ca_name}"
    mkdir -p "${ca_dir}"

    # Generate private key
    openssl ecparam -name prime256v1 -genkey -noout -out "${ca_dir}/${ca_name}-key.pem"

    # Create CSR configuration
    cat > "${ca_dir}/${ca_name}-csr.conf" <<EOF
[req]
distinguished_name = req_distinguished_name
prompt = no

[req_distinguished_name]
C = US
ST = Virginia
L = Arlington
O = Haven Health Passport
OU = ${ca_ou}
CN = ${ca_cn}
EOF

    # Generate CSR
    openssl req -new \
        -config "${ca_dir}/${ca_name}-csr.conf" \
        -key "${ca_dir}/${ca_name}-key.pem" \
        -out "${ca_dir}/${ca_name}-csr.pem"

    # Sign with Root CA
    cat > "${ca_dir}/${ca_name}-extensions.conf" <<EOF
basicConstraints = critical,CA:TRUE,pathlen:0
keyUsage = critical,digitalSignature,keyEncipherment,keyCertSign,cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer
EOF

    openssl x509 -req -days 1825 \
        -in "${ca_dir}/${ca_name}-csr.pem" \
        -CA "${CERT_OUTPUT_DIR}/ca/root/root-ca-cert.pem" \
        -CAkey "${CERT_OUTPUT_DIR}/ca/root/root-ca-key.pem" \
        -CAcreateserial \
        -out "${ca_dir}/${ca_name}-cert.pem" \
        -extfile "${ca_dir}/${ca_name}-extensions.conf"

    # Create certificate chain
    cat "${ca_dir}/${ca_name}-cert.pem" \
        "${CERT_OUTPUT_DIR}/ca/root/root-ca-cert.pem" \
        > "${ca_dir}/${ca_name}-chain.pem"

    log_info "Intermediate CA ${ca_name} generated"
}

# Generate node certificate
generate_node_certificate() {
    local node_type=$1  # orderer or peer
    local node_id=$2
    local node_dns=$3
    local node_ip=$4

    log_section "Generating ${node_type} certificate for ${node_id}"

    local cert_dir="${CERT_OUTPUT_DIR}/${node_type}/${node_id}"
    mkdir -p "${cert_dir}"

    # Select appropriate CA
    local ca_name="${node_type}-service-ca"
    if [ "${node_type}" = "orderer" ]; then
        ca_name="ordering-service-ca"
    else
        ca_name="peer-service-ca"
    fi

    # Generate private key
    openssl ecparam -name prime256v1 -genkey -noout -out "${cert_dir}/server-key.pem"

    # Create CSR configuration with SANs
    cat > "${cert_dir}/server-csr.conf" <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = US
ST = Virginia
L = Arlington
O = Haven Health Passport
OU = ${node_type^}
CN = ${node_id}.haven-health.local

[v3_req]
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth,clientAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = ${node_id}.haven-health.local
DNS.3 = ${node_dns}
DNS.4 = *.${node_type}.haven-health.local
IP.1 = 127.0.0.1
IP.2 = ${node_ip}
EOF

    # Generate CSR
    openssl req -new \
        -config "${cert_dir}/server-csr.conf" \
        -key "${cert_dir}/server-key.pem" \
        -out "${cert_dir}/server-csr.pem"

    # Sign with Intermediate CA
    openssl x509 -req -days 365 \
        -in "${cert_dir}/server-csr.pem" \
        -CA "${CERT_OUTPUT_DIR}/ca/intermediate/${ca_name}/${ca_name}-cert.pem" \
        -CAkey "${CERT_OUTPUT_DIR}/ca/intermediate/${ca_name}/${ca_name}-key.pem" \
        -CAcreateserial \
        -out "${cert_dir}/server-cert.pem" \
        -extensions v3_req \
        -extfile "${cert_dir}/server-csr.conf"

    # Create full chain
    cat "${cert_dir}/server-cert.pem" \
        "${CERT_OUTPUT_DIR}/ca/intermediate/${ca_name}/${ca_name}-cert.pem" \
        "${CERT_OUTPUT_DIR}/ca/root/root-ca-cert.pem" \
        > "${cert_dir}/server-chain.pem"

    # Generate client certificate for mutual TLS
    openssl ecparam -name prime256v1 -genkey -noout -out "${cert_dir}/client-key.pem"

    cat > "${cert_dir}/client-csr.conf" <<EOF
[req]
distinguished_name = req_distinguished_name
prompt = no

[req_distinguished_name]
C = US
ST = Virginia
L = Arlington
O = Haven Health Passport
OU = ${node_type^}
CN = ${node_id}-client.haven-health.local
EOF

    openssl req -new \
        -config "${cert_dir}/client-csr.conf" \
        -key "${cert_dir}/client-key.pem" \
        -out "${cert_dir}/client-csr.pem"

    openssl x509 -req -days 365 \
        -in "${cert_dir}/client-csr.pem" \
        -CA "${CERT_OUTPUT_DIR}/ca/intermediate/${ca_name}/${ca_name}-cert.pem" \
        -CAkey "${CERT_OUTPUT_DIR}/ca/intermediate/${ca_name}/${ca_name}-key.pem" \
        -CAcreateserial \
        -out "${cert_dir}/client-cert.pem"

    log_info "Certificates for ${node_type} ${node_id} generated"
}

# Store certificates in AWS
store_certificates_aws() {
    log_section "Storing certificates in AWS"

    # Function to import certificate to ACM
    import_to_acm() {
        local cert_name=$1
        local cert_path=$2
        local key_path=$3
        local chain_path=$4

        log_info "Importing ${cert_name} to ACM"

        aws acm import-certificate \
            --certificate fileb://"${cert_path}" \
            --private-key fileb://"${key_path}" \
            --certificate-chain fileb://"${chain_path}" \
            --tags Key=Name,Value="${cert_name}" Key=Environment,Value=production \
            --region "${AWS_REGION}"
    }

    # Import orderer certificates
    for cert_dir in "${CERT_OUTPUT_DIR}"/orderer/*/; do
        if [ -d "${cert_dir}" ]; then
            node_id=$(basename "${cert_dir}")
            import_to_acm \
                "haven-health-orderer-${node_id}" \
                "${cert_dir}/server-cert.pem" \
                "${cert_dir}/server-key.pem" \
                "${cert_dir}/server-chain.pem" || true
        fi
    done

    log_info "Certificates stored in AWS"
}

# Generate CRL (Certificate Revocation List)
generate_crl() {
    log_section "Generating Certificate Revocation List"

    local crl_dir="${CERT_OUTPUT_DIR}/ca/crl"
    mkdir -p "${crl_dir}"

    # Initialize CRL database
    touch "${crl_dir}/index.txt"
    echo "01" > "${crl_dir}/crlnumber"

    # Generate CRL
    cat > "${crl_dir}/crl.conf" <<EOF
[ca]
default_ca = CA_default

[CA_default]
database = ${crl_dir}/index.txt
crlnumber = ${crl_dir}/crlnumber
default_crl_days = 7
default_md = sha256
EOF

    openssl ca -config "${crl_dir}/crl.conf" \
        -keyfile "${CERT_OUTPUT_DIR}/ca/root/root-ca-key.pem" \
        -cert "${CERT_OUTPUT_DIR}/ca/root/root-ca-cert.pem" \
        -gencrl \
        -out "${crl_dir}/root-ca.crl" || true

    # Upload to S3
    aws s3 cp "${crl_dir}/root-ca.crl" \
        "s3://haven-health-blockchain-crl/root.crl" \
        --region "${AWS_REGION}" || true

    log_info "CRL generated and uploaded"
}

# Validate certificates
validate_certificates() {
    log_section "Validating certificates"

    # Validate Root CA
    openssl x509 -in "${CERT_OUTPUT_DIR}/ca/root/root-ca-cert.pem" \
        -text -noout > "${CERT_OUTPUT_DIR}/validation-root-ca.txt"

    # Validate certificate chains
    for cert_dir in "${CERT_OUTPUT_DIR}"/orderer/*/; do
        if [ -d "${cert_dir}" ]; then
            node_id=$(basename "${cert_dir}")
            log_info "Validating orderer ${node_id} certificate chain"

            openssl verify -CAfile "${CERT_OUTPUT_DIR}/ca/root/root-ca-cert.pem" \
                -untrusted "${CERT_OUTPUT_DIR}/ca/intermediate/ordering-service-ca/ordering-service-ca-cert.pem" \
                "${cert_dir}/server-cert.pem"
        fi
    done

    log_info "Certificate validation complete"
}

# Main execution
main() {
    log_info "Starting TLS certificate generation"

    # Check prerequisites
    if ! command -v openssl &> /dev/null; then
        log_error "OpenSSL not found. Please install OpenSSL."
        exit 1
    fi

    # Setup
    setup_directories

    # Generate certificates
    generate_root_ca
    generate_intermediate_ca "ordering-service-ca" "Haven Health Ordering Service CA" "Ordering Service"
    generate_intermediate_ca "peer-service-ca" "Haven Health Peer Service CA" "Peer Service"

    # Generate node certificates (example nodes)
    generate_node_certificate "orderer" "orderer0" "orderer0.haven-health.com" "10.0.1.10"
    generate_node_certificate "orderer" "orderer1" "orderer1.haven-health.com" "10.0.2.10"
    generate_node_certificate "peer" "peer0" "peer0.haven-health.com" "10.0.1.20"
    generate_node_certificate "peer" "peer1" "peer1.haven-health.com" "10.0.2.20"

    # Store and validate
    store_certificates_aws
    generate_crl
    validate_certificates

    log_info "TLS certificate generation completed successfully!"
    log_info "Certificates are stored in: ${CERT_OUTPUT_DIR}"
}

# Run main function
main "$@"
