# Certification Test Environment Configuration

# Environment Identifier
environment = "certification"
region      = "us-east-1"

# Networking Configuration
vpc_cidr = "10.4.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b"]
public_subnet_cidrs = ["10.4.1.0/24", "10.4.2.0/24"]
private_subnet_cidrs = ["10.4.10.0/24", "10.4.11.0/24"]

# FHIR Server Configuration
fhir_server_instance_type = "t3.large"
fhir_server_instance_count = 2
fhir_server_port = 8080
fhir_server_healthcheck_path = "/fhir/metadata"

# Database Configuration
rds_instance_class = "db.t3.medium"
rds_allocated_storage = 100
rds_engine = "postgres"
rds_engine_version = "14.7"
rds_backup_retention_period = 7
rds_multi_az = true

# Security Configuration
enable_encryption_at_rest = true
enable_audit_logging = true
enable_compliance_mode = true
ssl_certificate_arn = ""  # To be configured

# Monitoring and Logging
enable_cloudwatch_logs = true
log_retention_days = 90
enable_performance_insights = true
enable_enhanced_monitoring = true

# Compliance Features
enable_hipaa_compliance = true
enable_gdpr_compliance = true
enable_audit_trail = true
enable_access_logging = true

# Test-Specific Configuration
enable_test_data_generation = true
enable_synthetic_monitoring = true
enable_load_testing_endpoints = true
max_test_users = 1000

# Tags
tags = {
  Environment = "certification"
  Purpose     = "Healthcare Standards Certification Testing"
  Compliance  = "HIPAA,GDPR,ISO27001"
  ManagedBy   = "Terraform"
}
