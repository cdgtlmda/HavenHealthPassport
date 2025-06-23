# Container Security Module

This Terraform module implements comprehensive container security for the Haven Health Passport application.

## Features

- **Image Scanning**: Automated vulnerability scanning for all container images
- **Base Image Policies**: Enforcement of approved base images
- **Image Signing**: Digital signatures for container images
- **Runtime Protection**: Security controls for running containers
- **Network Policies**: Strict network segmentation for containers
- **Secrets Management**: Secure handling of container secrets

## Security Controls

1. **ECR Scanning**
   - Continuous scanning enabled
   - Scan on push for all repositories
   - Enhanced scanning with Inspector

2. **Image Policies**
   - Only signed images can be pulled
   - Base images must be from approved list
   - Automated vulnerability threshold enforcement

3. **Runtime Security**
   - Read-only root filesystem
   - Non-privileged containers
   - Dropped Linux capabilities
   - Resource limits enforced

4. **Network Security**
   - Strict security group rules
   - Limited egress to required services only
   - No direct internet access

## Usage

```hcl
module "container_security" {
  source = "./modules/container-security"

  project_name          = "haven-health-passport"
  vpc_id               = module.networking.vpc_id
  kms_key_arn          = module.kms.key_arn
  sns_alert_topic_arn  = module.monitoring.sns_topic_arn
}
```
