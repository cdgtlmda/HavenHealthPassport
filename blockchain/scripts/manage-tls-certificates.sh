#!/bin/bash

# TLS Certificate Management Script
# Haven Health Passport - Certificate Operations

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CERT_DIR="${SCRIPT_DIR}/../config/tls/certificates"
TLS_CONFIG="${SCRIPT_DIR}/../config/tls/tls-certificate-config.yaml"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Operation modes
OPERATION="${1:-help}"

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

# Show help
show_help() {
    cat <<EOF
TLS Certificate Management for Haven Health Passport Blockchain

Usage: $(basename $0) <operation> [options]

Operations:
    check       Check certificate expiration dates
    renew       Renew expiring certificates
    revoke      Revoke a certificate
    rotate      Rotate all certificates
    backup      Backup certificates
    restore     Restore certificates from backup
    monitor     Start certificate monitoring
    report      Generate certificate report

Options:
    --cert-id   Certificate identifier (for specific operations)
    --reason    Revocation reason (for revoke operation)
    --force     Force operation without confirmation

Examples:
    $(basename $0) check
    $(basename $0) renew --cert-id orderer0
    $(basename $0) revoke --cert-id peer1 --reason keyCompromise
    $(basename $0) rotate --force

EOF
}

# Check certificate expiration
check_expiration() {
    log_info "Checking certificate expiration dates..."

    local report_file="${CERT_DIR}/expiration-report-$(date +%Y%m%d).txt"
    echo "Certificate Expiration Report - $(date)" > "${report_file}"
    echo "==========================================" >> "${report_file}"

    # Function to check single certificate
    check_cert() {
        local cert_file=$1
        local cert_name=$(basename "${cert_file}")

        if [ -f "${cert_file}" ]; then
            local expiry_date=$(openssl x509 -enddate -noout -in "${cert_file}" | cut -d= -f2)
            local expiry_epoch=$(date -d "${expiry_date}" +%s)
            local current_epoch=$(date +%s)
            local days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))

            printf "%-50s %s (%d days)\n" "${cert_name}" "${expiry_date}" "${days_until_expiry}" >> "${report_file}"

            if [ ${days_until_expiry} -lt 0 ]; then
                log_error "${cert_name} has EXPIRED"
            elif [ ${days_until_expiry} -lt 7 ]; then
                log_error "${cert_name} expires in ${days_until_expiry} days (CRITICAL)"
            elif [ ${days_until_expiry} -lt 30 ]; then
                log_warn "${cert_name} expires in ${days_until_expiry} days"
            else
                log_info "${cert_name} expires in ${days_until_expiry} days"
            fi
        fi
    }

    # Check all certificates
    find "${CERT_DIR}" -name "*.pem" -type f | grep -E "(cert|crt)" | while read cert; do
        check_cert "${cert}"
    done

    log_info "Expiration report saved to: ${report_file}"
}

# Renew certificate
renew_certificate() {
    local cert_id="${2:-all}"

    log_info "Renewing certificate(s): ${cert_id}"

    # Function to renew single certificate
    renew_single() {
        local node_type=$1
        local node_id=$2

        log_info "Renewing certificate for ${node_type} ${node_id}"

        local cert_dir="${CERT_DIR}/${node_type}/${node_id}"
        local old_cert="${cert_dir}/server-cert.pem"

        if [ ! -f "${old_cert}" ]; then
            log_error "Certificate not found: ${old_cert}"
            return 1
        fi

        # Backup old certificate
        local backup_dir="${cert_dir}/backup-$(date +%Y%m%d-%H%M%S)"
        mkdir -p "${backup_dir}"
        cp "${cert_dir}"/*.pem "${backup_dir}/"

        # Generate new certificate (reuse existing key)
        local ca_name="${node_type}-service-ca"
        if [ "${node_type}" = "orderer" ]; then
            ca_name="ordering-service-ca"
        fi

        # Extract subject from old certificate
        local subject=$(openssl x509 -subject -noout -in "${old_cert}" | cut -d= -f2-)

        # Generate new certificate
        openssl x509 -req -days 365 \
            -in "${cert_dir}/server-csr.pem" \
            -CA "${CERT_DIR}/ca/intermediate/${ca_name}/${ca_name}-cert.pem" \
            -CAkey "${CERT_DIR}/ca/intermediate/${ca_name}/${ca_name}-key.pem" \
            -CAcreateserial \
            -out "${cert_dir}/server-cert-new.pem" \
            -extensions v3_req \
            -extfile "${cert_dir}/server-csr.conf"

        # Create grace period (keep both certificates valid)
        mv "${cert_dir}/server-cert.pem" "${cert_dir}/server-cert-old.pem"
        mv "${cert_dir}/server-cert-new.pem" "${cert_dir}/server-cert.pem"

        # Update certificate chain
        cat "${cert_dir}/server-cert.pem" \
            "${CERT_DIR}/ca/intermediate/${ca_name}/${ca_name}-cert.pem" \
            "${CERT_DIR}/ca/root/root-ca-cert.pem" \
            > "${cert_dir}/server-chain.pem"

        # Update in AWS ACM
        aws acm import-certificate \
            --certificate fileb://"${cert_dir}/server-cert.pem" \
            --private-key fileb://"${cert_dir}/server-key.pem" \
            --certificate-chain fileb://"${cert_dir}/server-chain.pem" \
            --certificate-arn "$(aws acm list-certificates --region ${AWS_REGION} \
                --query "CertificateSummaryList[?DomainName=='${node_id}.haven-health.local'].CertificateArn" \
                --output text)" \
            --region "${AWS_REGION}" || true

        log_info "Certificate renewed for ${node_type} ${node_id}"
    }

    if [ "${cert_id}" = "all" ]; then
        # Renew all certificates
        for node_dir in "${CERT_DIR}"/orderer/*/; do
            if [ -d "${node_dir}" ]; then
                node_id=$(basename "${node_dir}")
                renew_single "orderer" "${node_id}"
            fi
        done

        for node_dir in "${CERT_DIR}"/peer/*/; do
            if [ -d "${node_dir}" ]; then
                node_id=$(basename "${node_dir}")
                renew_single "peer" "${node_id}"
            fi
        done
    else
        # Renew specific certificate
        if [[ "${cert_id}" == orderer* ]]; then
            renew_single "orderer" "${cert_id}"
        elif [[ "${cert_id}" == peer* ]]; then
            renew_single "peer" "${cert_id}"
        else
            log_error "Unknown certificate ID: ${cert_id}"
            exit 1
        fi
    fi
}

# Revoke certificate
revoke_certificate() {
    local cert_id="${2}"
    local reason="${3:-unspecified}"

    if [ -z "${cert_id}" ]; then
        log_error "Certificate ID required for revocation"
        exit 1
    fi

    log_warn "Revoking certificate: ${cert_id} (reason: ${reason})"

    # Find certificate
    local cert_file=""
    if [[ "${cert_id}" == orderer* ]]; then
        cert_file="${CERT_DIR}/orderer/${cert_id}/server-cert.pem"
    elif [[ "${cert_id}" == peer* ]]; then
        cert_file="${CERT_DIR}/peer/${cert_id}/server-cert.pem"
    fi

    if [ ! -f "${cert_file}" ]; then
        log_error "Certificate not found: ${cert_file}"
        exit 1
    fi

    # Extract serial number
    local serial=$(openssl x509 -serial -noout -in "${cert_file}" | cut -d= -f2)

    # Add to revocation database
    local crl_dir="${CERT_DIR}/ca/crl"
    echo "${serial} $(date +%y%m%d%H%M%SZ) ${reason}" >> "${crl_dir}/revoked.txt"

    # Regenerate CRL
    openssl ca -config "${crl_dir}/crl.conf" \
        -keyfile "${CERT_DIR}/ca/root/root-ca-key.pem" \
        -cert "${CERT_DIR}/ca/root/root-ca-cert.pem" \
        -gencrl \
        -out "${crl_dir}/root-ca.crl" || true

    # Upload updated CRL
    aws s3 cp "${crl_dir}/root-ca.crl" \
        "s3://haven-health-blockchain-crl/root.crl" \
        --region "${AWS_REGION}" || true

    # Notify OCSP responder
    # (In production, this would update the OCSP database)

    log_info "Certificate ${cert_id} revoked successfully"
}

# Backup certificates
backup_certificates() {
    log_info "Backing up certificates..."

    local backup_name="cert-backup-$(date +%Y%m%d-%H%M%S)"
    local backup_dir="/tmp/${backup_name}"

    # Create backup
    mkdir -p "${backup_dir}"
    cp -r "${CERT_DIR}"/* "${backup_dir}/"

    # Create tarball
    tar -czf "${backup_dir}.tar.gz" -C /tmp "${backup_name}"

    # Upload to S3
    aws s3 cp "${backup_dir}.tar.gz" \
        "s3://haven-health-blockchain-backups/certificates/${backup_name}.tar.gz" \
        --region "${AWS_REGION}"

    # Cleanup
    rm -rf "${backup_dir}" "${backup_dir}.tar.gz"

    log_info "Certificates backed up to S3: ${backup_name}.tar.gz"
}

# Monitor certificates
monitor_certificates() {
    log_info "Starting certificate monitoring..."

    while true; do
        clear
        echo "Haven Health Blockchain - Certificate Monitor"
        echo "============================================"
        echo "Time: $(date)"
        echo ""

        # Check expiration status
        check_expiration | grep -E "(CRITICAL|WARNING|days)"

        # Check CRL status
        if [ -f "${CERT_DIR}/ca/crl/root-ca.crl" ]; then
            echo ""
            echo "CRL Status:"
            openssl crl -in "${CERT_DIR}/ca/crl/root-ca.crl" -noout -lastupdate -nextupdate
        fi

        # Check for alerts
        echo ""
        echo "Recent Alerts:"
        aws cloudwatch describe-alarms \
            --alarm-name-prefix "HavenHealth-Certificate" \
            --state-value ALARM \
            --region "${AWS_REGION}" \
            --query 'MetricAlarms[*].[AlarmName,StateReason]' \
            --output table 2>/dev/null || echo "No active alerts"

        echo ""
        echo "Press Ctrl+C to exit"
        sleep 60
    done
}

# Generate certificate report
generate_report() {
    log_info "Generating certificate report..."

    local report_file="${CERT_DIR}/certificate-report-$(date +%Y%m%d-%H%M%S).html"

    cat > "${report_file}" <<EOF
<!DOCTYPE html>
<html>
<head>
    <title>Haven Health Blockchain - Certificate Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        .expired { color: red; font-weight: bold; }
        .warning { color: orange; font-weight: bold; }
        .good { color: green; }
    </style>
</head>
<body>
    <h1>Haven Health Blockchain - Certificate Report</h1>
    <p>Generated: $(date)</p>

    <h2>Certificate Status</h2>
    <table>
        <tr>
            <th>Certificate</th>
            <th>Type</th>
            <th>Expiration</th>
            <th>Days Until Expiry</th>
            <th>Status</th>
        </tr>
EOF

    # Add certificate data
    find "${CERT_DIR}" -name "*-cert.pem" -type f | while read cert; do
        local cert_name=$(basename "${cert}")
        local cert_type=$(echo "${cert}" | awk -F'/' '{print $(NF-2)}')
        local expiry_date=$(openssl x509 -enddate -noout -in "${cert}" | cut -d= -f2)
        local days_left=$(( ($(date -d "${expiry_date}" +%s) - $(date +%s)) / 86400 ))

        local status_class="good"
        local status_text="Valid"

        if [ ${days_left} -lt 0 ]; then
            status_class="expired"
            status_text="EXPIRED"
        elif [ ${days_left} -lt 7 ]; then
            status_class="expired"
            status_text="CRITICAL"
        elif [ ${days_left} -lt 30 ]; then
            status_class="warning"
            status_text="WARNING"
        fi

        echo "<tr>" >> "${report_file}"
        echo "    <td>${cert_name}</td>" >> "${report_file}"
        echo "    <td>${cert_type}</td>" >> "${report_file}"
        echo "    <td>${expiry_date}</td>" >> "${report_file}"
        echo "    <td class='${status_class}'>${days_left}</td>" >> "${report_file}"
        echo "    <td class='${status_class}'>${status_text}</td>" >> "${report_file}"
        echo "</tr>" >> "${report_file}"
    done

    cat >> "${report_file}" <<EOF
    </table>

    <h2>Certificate Hierarchy</h2>
    <pre>
Root CA
├── Ordering Service CA
│   ├── orderer0
│   ├── orderer1
│   └── ...
└── Peer Service CA
    ├── peer0
    ├── peer1
    └── ...
    </pre>

    <h2>Recent Operations</h2>
    <ul>
        <li>Last CRL Update: $(stat -c %y "${CERT_DIR}/ca/crl/root-ca.crl" 2>/dev/null || echo "N/A")</li>
        <li>Last Backup: $(aws s3 ls s3://haven-health-blockchain-backups/certificates/ --region ${AWS_REGION} | tail -1 | awk '{print $1, $2}' || echo "N/A")</li>
    </ul>
</body>
</html>
EOF

    log_info "Certificate report generated: ${report_file}"

    # Upload to S3 for web access
    aws s3 cp "${report_file}" \
        "s3://haven-health-blockchain-reports/certificates/latest.html" \
        --content-type "text/html" \
        --region "${AWS_REGION}" || true
}

# Main execution
case "${OPERATION}" in
    check)
        check_expiration
        ;;
    renew)
        renew_certificate "$@"
        ;;
    revoke)
        revoke_certificate "$@"
        ;;
    rotate)
        log_warn "Rotating all certificates..."
        renew_certificate "renew" "all"
        ;;
    backup)
        backup_certificates
        ;;
    restore)
        log_error "Restore operation not yet implemented"
        ;;
    monitor)
        monitor_certificates
        ;;
    report)
        generate_report
        ;;
    help|*)
        show_help
        ;;
esac
