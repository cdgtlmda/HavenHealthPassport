# Variables for VPC Security Module

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "haven-health-passport"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones to use"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "haven-health-passport"
    Environment = "production"
    Terraform   = "true"
  }
}

variable "flow_log_retention_days" {
  description = "Number of days to retain VPC flow logs"
  type        = number
  default     = 30
}

variable "kms_key_arn" {
  description = "ARN of the KMS key for encrypting logs"
  type        = string
}

variable "bastion_allowed_cidrs" {
  description = "List of CIDR blocks allowed to connect to bastion host"
  type        = list(string)
  default     = []
}
variable "blocked_countries" {
  description = "List of country codes to block"
  type        = list(string)
  default     = []
}

variable "waf_log_retention_days" {
  description = "Number of days to retain WAF logs"
  type        = number
  default     = 30
}

variable "allowed_ip_addresses" {
  description = "List of IP addresses to allowlist"
  type        = list(string)
  default     = []
}
variable "enable_shield_advanced" {
  description = "Enable AWS Shield Advanced (requires subscription)"
  type        = bool
  default     = false
}

variable "alb_arn" {
  description = "ARN of the Application Load Balancer"
  type        = string
  default     = ""
}

variable "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  type        = string
  default     = ""
}

variable "cloudfront_secret" {
  description = "Secret header value for CloudFront origin verification"
  type        = string
  sensitive   = true
}

variable "cloudfront_geo_restrictions" {
  description = "List of country codes to restrict in CloudFront"
  type        = list(string)
  default     = []
}

variable "sns_alert_topic_arn" {
  description = "ARN of the SNS topic for security alerts"
  type        = string
  default     = ""
}

variable "enable_ddos_auto_scaling" {
  description = "Enable auto-scaling in response to DDoS attacks"
  type        = bool
  default     = true
}

variable "app_autoscaling_group_name" {
  description = "Name of the application auto-scaling group"
  type        = string
  default     = ""
}
variable "vpn_client_cidr" {
  description = "CIDR block for VPN clients"
  type        = string
  default     = "10.100.0.0/16"
}

variable "vpn_server_certificate_arn" {
  description = "ARN of the server certificate for VPN"
  type        = string
  default     = ""
}

variable "vpn_root_certificate_arn" {
  description = "ARN of the root certificate for VPN authentication"
  type        = string
  default     = ""
}

variable "vpn_dns_servers" {
  description = "DNS servers for VPN clients"
  type        = list(string)
  default     = []
}

variable "vpn_split_tunnel" {
  description = "Enable split tunneling for VPN"
  type        = bool
  default     = true
}

variable "vpn_log_retention_days" {
  description = "Number of days to retain VPN logs"
  type        = number
  default     = 30
}

variable "vpn_allowed_cidrs" {
  description = "CIDR blocks allowed to connect to VPN"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "create_vpn_certificates" {
  description = "Create self-signed certificates for VPN (development only)"
  type        = bool
  default     = false
}
variable "site_to_site_vpn_configs" {
  description = "Configuration for site-to-site VPN connections"
  type = list(object({
    name               = string
    bgp_asn            = number
    ip_address         = string
    static_routes_only = bool
  }))
  default = []
}

variable "site_to_site_vpn_static_routes" {
  description = "Static routes for site-to-site VPN connections"
  type = list(object({
    connection_index = number
    cidr            = string
  }))
  default = []
}
variable "bastion_ami_id" {
  description = "AMI ID for bastion host"
  type        = string
  default     = "" # Will use data source to get latest Amazon Linux 2
}

variable "bastion_instance_type" {
  description = "Instance type for bastion host"
  type        = string
  default     = "t3.micro"
}

variable "bastion_key_pair_name" {
  description = "Key pair name for bastion host SSH access"
  type        = string
}

variable "bastion_min_size" {
  description = "Minimum number of bastion hosts"
  type        = number
  default     = 1
}

variable "bastion_max_size" {
  description = "Maximum number of bastion hosts"
  type        = number
  default     = 3
}

variable "bastion_desired_capacity" {
  description = "Desired number of bastion hosts"
  type        = number
  default     = 1
}
variable "bastion_log_retention_days" {
  description = "Number of days to retain bastion logs"
  type        = number
  default     = 30
}
