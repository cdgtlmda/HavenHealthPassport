# Certification Test Environment Configuration

## Overview
This directory contains the configuration for the Haven Health Passport certification test environment, designed specifically for healthcare standards compliance testing.

## Environment Components

### Core Services
- **FHIR Server**: HAPI FHIR R4 server with full validation enabled
- **PostgreSQL Database**: Primary data store with audit logging
- **HL7 Interface Engine**: For v2.x message processing
- **Terminology Service**: LOINC, SNOMED CT, ICD-10, RxNorm validation

### Supporting Services
- **Test Data Generator**: Creates synthetic test data
- **Prometheus**: Performance and availability monitoring

## Setup Instructions

### Prerequisites
- Docker and Docker Compose installed
- Available ports: 8080, 5433, 2575, 8090, 9091
- Minimum 8GB RAM available
- 50GB free disk space

### Quick Start
```bash
# Run the setup script
./scripts/setup-cert-environment.sh

# Validate the environment
./scripts/validate-cert-environment.sh
```

### Manual Setup
1. Create environment file:
   ```bash
   cp .env.example .env.cert
   # Edit .env.cert with your values
   ```

2. Start services:
   ```bash
   docker-compose -f docker-compose.cert.yml up -d
   ```

3. Verify services:
   ```bash
   docker-compose -f docker-compose.cert.yml ps
   ```

## Service Endpoints

| Service | URL | Purpose |
|---------|-----|---------|
| FHIR Server | http://localhost:8080/fhir | Main FHIR API endpoint |
| FHIR Metadata | http://localhost:8080/fhir/metadata | Capability statement |
| PostgreSQL | localhost:5433 | Database connection |
| HL7 Interface | localhost:2575 | HL7 v2.x message receiver |
| Terminology Service | http://localhost:8090 | Code validation service |
| Prometheus | http://localhost:9091 | Metrics and monitoring |

## Configuration Files

- `docker-compose.cert.yml` - Service definitions
- `fhir-config/application.yaml` - FHIR server configuration
- `monitoring/prometheus-cert.yml` - Monitoring configuration
- `.env.cert` - Environment variables (not in version control)

## Security Features

- TLS encryption enabled for all services
- RBAC access control configured
- Audit logging enabled
- HIPAA compliance mode active
- Data encryption at rest

## Testing Features

- Full FHIR validation enabled
- Terminology validation active
- Performance monitoring
- Audit trail generation
- Synthetic test data available

## Troubleshooting

### Service won't start
- Check port availability
- Verify Docker daemon is running
- Review logs: `docker-compose -f docker-compose.cert.yml logs [service]`

### Database connection issues
- Verify PostgreSQL is running
- Check credentials in .env.cert
- Test connection: `psql -h localhost -p 5433 -U haven_cert_user`

### FHIR validation errors
- Check terminology service is running
- Verify code systems are loaded
- Review FHIR server logs

## Maintenance

### Backup database
```bash
docker exec haven-postgres-cert pg_dump -U haven_cert_user haven_cert > backup.sql
```

### View logs
```bash
docker-compose -f docker-compose.cert.yml logs -f [service-name]
```

### Reset environment
```bash
docker-compose -f docker-compose.cert.yml down -v
./scripts/setup-cert-environment.sh
```
