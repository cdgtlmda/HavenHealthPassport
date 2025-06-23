# PostgreSQL RDS Infrastructure

This directory contains the Terraform configuration and database schema for the Haven Health Passport PostgreSQL RDS infrastructure.

## Architecture Overview

- **Multi-AZ Deployment**: Primary database with automatic failover
- **Read Replicas**: 2 read replicas for load distribution
- **Connection Pooling**: RDS Proxy for efficient connection management
- **Encryption**: KMS encryption at rest, SSL/TLS in transit
- **Backup**: 35-day retention with point-in-time recovery
- **Monitoring**: CloudWatch alarms and enhanced monitoring

## Directory Structure

```
rds/
├── variables.tf          # Input variables
├── parameter_group.tf    # RDS parameter configuration
├── security_group.tf     # Security group rules
├── rds_instance.tf       # Main RDS instance
├── read_replicas.tf      # Read replica configuration
├── monitoring.tf         # CloudWatch alarms
├── iam_kms.tf           # IAM roles and KMS keys
├── backup.tf            # Backup configuration
├── rds_proxy.tf         # Connection pooling
├── secrets.tf           # Secrets Manager
├── lambda_rotation.tf   # Password rotation
├── outputs.tf           # Output values
└── schema/              # Database schema
    ├── 01_initial_schema.sql
    ├── 02_patients_table.sql
    ├── 03_health_records_table.sql
    ├── 04_verifications_table.sql
    ├── 05_access_logs_table.sql
    └── 06_sync_queue_table.sql
```

## Deployment Instructions

1. **Prerequisites**:
   - Terraform >= 1.0
   - AWS CLI configured
   - VPC with at least 2 subnets in different AZs

2. **Initialize Terraform**:
   ```bash
   terraform init
   ```

3. **Plan the deployment**:
   ```bash
   terraform plan -var="database_password=YourSecurePassword"
   ```

4. **Apply the configuration**:
   ```bash
   terraform apply -var="database_password=YourSecurePassword"
   ```

5. **Run database migrations**:
   ```bash
   psql -h $(terraform output -raw rds_proxy_endpoint) \
        -U haven_admin -d haven_health_db \
        -f schema/*.sql
   ```

## Connection Details

### Using RDS Proxy (Recommended)
```
Host: $(terraform output -raw rds_proxy_endpoint)
Port: 5432
Database: haven_health_db
SSL Mode: require
```

### Direct Connection (Master)
```
Host: $(terraform output -raw rds_master_address)
Port: 5432
Database: haven_health_db
SSL Mode: require
```

### Read Replicas
```bash
terraform output -json rds_replica_endpoints
```

## Security Considerations

1. **Encryption**: All data encrypted at rest using KMS
2. **Network**: Isolated in private subnets
3. **Access**: Security group restricts access to application servers
4. **SSL/TLS**: Enforced for all connections
5. **Password Rotation**: Automated every 30 days

## Monitoring

CloudWatch alarms are configured for:
- CPU utilization > 80%
- Connection count > 800
- Free storage < 50GB
- Read replica lag > 60 seconds

Alerts are sent to: devops@havenhealthpassport.org

## Backup and Recovery

- **Automated Backups**: Daily snapshots with 35-day retention
- **Point-in-Time Recovery**: Available for the retention period
- **Manual Snapshots**: Create before major changes
- **S3 Export**: Automated weekly exports to S3

## Maintenance

- **Maintenance Window**: Sunday 04:00-05:00 UTC
- **Backup Window**: Daily 03:00-04:00 UTC
- **Auto Minor Version Upgrade**: Enabled
- **Major Version Upgrades**: Manual process

## Cost Optimization

- Read replicas use smaller instance types
- Automated archival of old backups to Glacier
- RDS Proxy reduces connection overhead
- Performance Insights retention limited to 7 days

## Disaster Recovery

1. **Multi-AZ**: Automatic failover in case of AZ failure
2. **Read Replicas**: Can be promoted to master if needed
3. **Backups**: Stored in S3 with cross-region replication
4. **Point-in-Time Recovery**: RPO of 5 minutes

## Troubleshooting

### High Connection Count
- Check RDS Proxy metrics
- Review application connection pooling
- Consider scaling read replicas

### Performance Issues
- Review Performance Insights
- Check slow query log
- Analyze pg_stat_statements

### Storage Issues
- Monitor free storage alarm
- Enable storage autoscaling if needed
- Archive old data

## Support

For issues or questions:
- Slack: #haven-health-infrastructure
- Email: devops@havenhealthpassport.org
