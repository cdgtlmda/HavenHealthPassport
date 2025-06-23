# Security Monitoring Module

This Terraform module implements comprehensive security monitoring for the Haven Health Passport application.

## Features

- **CloudTrail**: Multi-region audit logging with log validation
- **GuardDuty**: Threat detection with automated response
- **SIEM Integration**: Log aggregation and correlation
- **Alert Automation**: Automated incident response
- **Log Analysis**: Real-time log processing and correlation

## Components

1. **CloudTrail Configuration**
   - Multi-region trail
   - Log file validation
   - Event data store
   - Management and data events

2. **GuardDuty Setup**
   - Threat detection
   - Custom threat intelligence
   - Malware protection
   - Automated remediation

3. **SIEM Integration**
   - Kinesis Firehose for log streaming
   - S3 data lake for long-term storage
   - Glue catalog for querying
   - Log correlation rules

4. **Alert Automation**
   - EventBridge rules
   - Lambda response functions
   - SNS notifications
   - Quarantine procedures

## Usage

```hcl
module "security_monitoring" {
  source = "./modules/security-monitoring"

  project_name        = "haven-health-passport"
  vpc_id             = module.networking.vpc_id
  kms_key_arn        = module.kms.key_arn
  sns_alert_topic_arn = module.alerting.sns_topic_arn
}
```
