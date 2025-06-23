# VPN Configuration for Haven Health Passport
# Provides secure remote access to private resources

# Client VPN Endpoint
resource "aws_ec2_client_vpn_endpoint" "main" {
  description            = "${var.project_name} Client VPN"
  server_certificate_arn = var.vpn_server_certificate_arn
  client_cidr_block      = var.vpn_client_cidr

  authentication_options {
    type                       = "certificate-authentication"
    root_certificate_chain_arn = var.vpn_root_certificate_arn
  }

  connection_log_options {
    enabled               = true
    cloudwatch_log_group  = aws_cloudwatch_log_group.vpn.name
    cloudwatch_log_stream = aws_cloudwatch_log_stream.vpn.name
  }

  dns_servers = var.vpn_dns_servers

  split_tunnel = var.vpn_split_tunnel

  transport_protocol = "tcp"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-client-vpn"
    }
  )
}

# CloudWatch Log Group for VPN Logs
resource "aws_cloudwatch_log_group" "vpn" {
  name              = "/aws/vpn/${var.project_name}"
  retention_in_days = var.vpn_log_retention_days
  kms_key_id        = var.kms_key_arn

  tags = var.common_tags
}

# CloudWatch Log Stream for VPN
resource "aws_cloudwatch_log_stream" "vpn" {
  name           = "vpn-connection-logs"
  log_group_name = aws_cloudwatch_log_group.vpn.name
}
# VPN Network Association
resource "aws_ec2_client_vpn_network_association" "private_app" {
  count                  = length(var.availability_zones)
  client_vpn_endpoint_id = aws_ec2_client_vpn_endpoint.main.id
  subnet_id              = aws_subnet.private_app[count.index].id
}

# VPN Authorization Rules
resource "aws_ec2_client_vpn_authorization_rule" "all_private" {
  client_vpn_endpoint_id = aws_ec2_client_vpn_endpoint.main.id
  target_network_cidr    = var.vpc_cidr
  authorize_all_groups   = true
  description            = "Allow VPN clients to access VPC"
}

# Security Group for VPN Endpoint
resource "aws_security_group" "vpn" {
  name        = "${var.project_name}-vpn-sg"
  description = "Security group for VPN endpoint"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "OpenVPN from allowed IPs"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = var.vpn_allowed_cidrs
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-vpn-sg"
    }
  )
}
# Route for VPN Traffic
resource "aws_ec2_client_vpn_route" "private_app" {
  count                  = length(var.availability_zones)
  client_vpn_endpoint_id = aws_ec2_client_vpn_endpoint.main.id
  destination_cidr_block = cidrsubnet(var.vpc_cidr, 4, count.index + length(var.availability_zones))
  target_vpc_subnet_id   = aws_subnet.private_app[count.index].id
  description            = "Route to private app subnet ${count.index}"
}

# VPN Endpoint Certificate (self-signed for development)
resource "tls_private_key" "vpn_ca" {
  count     = var.create_vpn_certificates ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_self_signed_cert" "vpn_ca" {
  count           = var.create_vpn_certificates ? 1 : 0
  private_key_pem = tls_private_key.vpn_ca[0].private_key_pem

  subject {
    common_name  = "${var.project_name}-vpn-ca"
    organization = var.project_name
  }

  validity_period_hours = 8760 # 1 year

  allowed_uses = [
    "cert_signing",
    "crl_signing",
  ]

  is_ca_certificate = true
}

resource "aws_acm_certificate" "vpn_server" {
  count                     = var.create_vpn_certificates ? 1 : 0
  private_key               = tls_private_key.vpn_ca[0].private_key_pem
  certificate_body          = tls_self_signed_cert.vpn_ca[0].cert_pem
  certificate_chain         = tls_self_signed_cert.vpn_ca[0].cert_pem
  tags                      = var.common_tags
}
