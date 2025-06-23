# Incident Response Module

This Terraform module implements comprehensive incident response capabilities for the Haven Health Passport application.

## Features

- **Incident Response Plan**: Structured incident management with severity levels
- **On-Call Rotation**: Automated on-call scheduling and notifications
- **Forensics Tools**: Evidence collection and chain of custody
- **Communication Templates**: Pre-defined templates for stakeholder communication
- **Status Page**: Public status page for service updates
- **Post-Mortem Process**: Structured lessons learned and improvement tracking

## Components

1. **Incident Management**
   - Severity level definitions
   - Escalation procedures
   - Response playbooks

2. **On-Call System**
   - Rotation scheduling
   - Multi-channel notifications
   - Escalation paths

3. **Forensics Capabilities**
   - Evidence collection automation
   - Immutable storage with Object Lock
   - Chain of custody tracking

4. **Communication**
   - Template management
   - Stakeholder notifications
   - Status page updates

5. **Post-Mortem Process**
   - Structured documentation
   - Action item tracking
   - Knowledge sharing

## Usage

```hcl
module "incident_response" {
  source = "./modules/incident-response"

  project_name = "haven-health-passport"
  kms_key_arn  = module.kms.key_arn
}
```
