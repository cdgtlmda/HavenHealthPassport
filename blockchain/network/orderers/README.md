# Orderer Node Setup for Haven Health Passport

## Overview

This directory contains the configuration and setup scripts for the 5 orderer nodes that form the Raft consensus cluster for the Haven Health Passport blockchain network. Each orderer node is configured for high availability and fault tolerance.

## Directory Structure

```
orderers/
├── setup-orderer-nodes.sh      # Main setup script
├── crypto-config-orderer.yaml  # Crypto material configuration
├── check-orderer-health.sh     # Health check script
├── start-all-orderers.sh       # Start all orderers
├── stop-all-orderers.sh        # Stop all orderers
├── verify-orderer-setup.sh     # Verify setup
├── orderer1/                   # Orderer 1 configuration
│   ├── orderer.yaml           # Orderer configuration
│   ├── orderer1.service       # Systemd service file
│   ├── start-orderer1.sh      # Start script
│   ├── .env                   # Environment variables
│   ├── config/               # Configuration directory
│   ├── data/                 # Data directory
│   └── logs/                 # Log directory
├── orderer2/                   # Orderer 2 configuration
├── orderer3/                   # Orderer 3 configuration
├── orderer4/                   # Orderer 4 configuration
└── orderer5/                   # Orderer 5 configuration
```

## Orderer Node Configuration

| Orderer | Listen Port | Admin Port | Operations Port | Health Check |
|---------|------------|------------|-----------------|--------------|
| orderer1 | 7050 | 7053 | 9443 | https://localhost:9443/healthz |
| orderer2 | 8050 | 8053 | 9444 | https://localhost:9444/healthz |
| orderer3 | 9050 | 9053 | 9445 | https://localhost:9445/healthz |
| orderer4 | 10050 | 10053 | 9446 | https://localhost:9446/healthz |
| orderer5 | 11050 | 11053 | 9447 | https://localhost:9447/healthz |

## Setup Instructions

### 1. Initial Setup

Run the setup script to create all orderer configurations:

```bash
./setup-orderer-nodes.sh
```

This script will:
- Create directory structure for 5 orderer nodes
- Generate crypto configuration
- Create individual orderer configurations
- Generate systemd service files
- Create startup and management scripts

### 2. Verify Setup

Verify that all components are properly configured:

```bash
./verify-orderer-setup.sh
```

### 3. Start Orderer Nodes

#### Option A: Start All Orderers (Development)

```bash
./start-all-orderers.sh
```

#### Option B: Systemd Services (Production)

```bash
# Copy service files
sudo cp orderer*/orderer*.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Start orderer services
sudo systemctl start orderer1
sudo systemctl start orderer2
sudo systemctl start orderer3
sudo systemctl start orderer4
sudo systemctl start orderer5

# Enable auto-start on boot
sudo systemctl enable orderer{1..5}
```

#### Option C: Docker Compose

Use the docker-compose file from the config directory:

```bash
cd ../config/orderer
docker-compose -f docker-compose-orderer-raft.yaml up -d
```

### 4. Health Monitoring

Check the health status of all orderer nodes:

```bash
./check-orderer-health.sh
```

## Configuration Details

### TLS Configuration

Each orderer is configured with TLS enabled for:
- Client connections (port 7050, 8050, etc.)
- Intra-cluster communication
- Admin API endpoints
- Operations/metrics endpoints

TLS certificates are expected in:
- `/var/hyperledger/orderer/tls/server.crt` - Server certificate
- `/var/hyperledger/orderer/tls/server.key` - Server private key
- `/var/hyperledger/orderer/tls/ca.crt` - CA certificate

### Raft Consensus Settings

- **Election Timeout**: 10 ticks (5 seconds)
- **Heartbeat Interval**: 1 tick (500ms)
- **Snapshot Interval**: 100 MB
- **Max Inflight Blocks**: 5

### Data Persistence

Each orderer stores data in:
- **Ledger**: `/var/hyperledger/production/orderer`
- **WAL**: `/var/hyperledger/production/orderer/etcdraft/wal`
- **Snapshots**: `/var/hyperledger/production/orderer/etcdraft/snapshot`

## Monitoring and Metrics

### Prometheus Metrics

Each orderer exposes Prometheus metrics on its operations port:
- orderer1: http://localhost:9443/metrics
- orderer2: http://localhost:9444/metrics
- orderer3: http://localhost:9445/metrics
- orderer4: http://localhost:9446/metrics
- orderer5: http://localhost:9447/metrics

### Log Files

Logs are stored in each orderer's logs directory:
```bash
tail -f orderer1/logs/orderer1.log
tail -f orderer2/logs/orderer2.log
# etc...
```

## Troubleshooting

### Common Issues

1. **Orderer fails to start**
   - Check crypto material is properly generated
   - Verify ports are not in use
   - Check TLS certificates are in correct locations

2. **Raft leader election issues**
   - Ensure all orderers can communicate
   - Check firewall rules for ports 7050-11050
   - Verify TLS certificates are valid

3. **High memory usage**
   - Adjust snapshot interval size
   - Monitor WAL directory size
   - Consider increasing system resources

### Debug Commands

```bash
# Check orderer status
docker ps | grep orderer

# View orderer logs
docker logs orderer1.havenhealthpassport.org

# Check port availability
netstat -tlnp | grep -E '(7050|8050|9050|10050|11050)'

# Test TLS connection
openssl s_client -connect localhost:7050 -showcerts
```

## Maintenance

### Backup

Regular backups should include:
- Crypto material (`../crypto-config/ordererOrganizations/`)
- Ledger data (`/var/hyperledger/production/orderer`)
- Configuration files (`orderer*/orderer.yaml`)

### Updates

To update orderer configuration:
1. Stop the orderer
2. Update configuration file
3. Restart the orderer
4. Verify health status

## Security Considerations

- Keep private keys secure and encrypted
- Regularly rotate TLS certificates
- Monitor access to admin endpoints
- Use firewall rules to restrict access
- Enable audit logging for compliance

## Next Steps

After setting up orderer nodes:
1. Configure peer nodes
2. Create channels
3. Deploy chaincode
4. Set up monitoring infrastructure
