# Network ACL Configuration for Haven Health Passport
# Implements defense-in-depth with stateless network security rules

# Network ACL for Public Subnets
resource "aws_network_acl" "public" {
  vpc_id     = aws_vpc.main.id
  subnet_ids = aws_subnet.public[*].id

  # Inbound Rules

  # Allow HTTPS from anywhere
  ingress {
    protocol   = "tcp"
    rule_no    = 100
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 443
    to_port    = 443
  }

  # Allow HTTP from anywhere (for redirect to HTTPS)
  ingress {
    protocol   = "tcp"
    rule_no    = 110
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 80
    to_port    = 80
  }

  # Allow return traffic for ephemeral ports
  ingress {
    protocol   = "tcp"
    rule_no    = 120
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 1024
    to_port    = 65535
  }

  # Allow ICMP for diagnostics from VPC
  ingress {
    protocol   = "icmp"
    rule_no    = 130
    action     = "allow"
    cidr_block = var.vpc_cidr
    icmp_type  = -1
    icmp_code  = -1
  }
  # Outbound Rules

  # Allow all outbound traffic
  egress {
    protocol   = "-1"
    rule_no    = 100
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 0
    to_port    = 0
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-public-nacl"
      Type = "public"
    }
  )
}

# Network ACL for Private Application Subnets
resource "aws_network_acl" "private_app" {
  vpc_id     = aws_vpc.main.id
  subnet_ids = aws_subnet.private_app[*].id

  # Inbound Rules

  # Allow traffic from public subnets
  ingress {
    protocol   = "-1"
    rule_no    = 100
    action     = "allow"
    cidr_block = cidrsubnet(var.vpc_cidr, 4, 0)
    from_port  = 0
    to_port    = 0
  }

  # Allow traffic from other private app subnets
  ingress {
    protocol   = "-1"
    rule_no    = 110
    action     = "allow"
    cidr_block = cidrsubnet(var.vpc_cidr, 4, length(var.availability_zones))
    from_port  = 0
    to_port    = 0
  }
  # Allow return traffic from internet via NAT
  ingress {
    protocol   = "tcp"
    rule_no    = 120
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 1024
    to_port    = 65535
  }

  # Allow traffic from DB subnets
  ingress {
    protocol   = "-1"
    rule_no    = 130
    action     = "allow"
    cidr_block = cidrsubnet(var.vpc_cidr, 4, 2 * length(var.availability_zones))
    from_port  = 0
    to_port    = 0
  }

  # Outbound Rules

  # Allow all outbound traffic
  egress {
    protocol   = "-1"
    rule_no    = 100
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 0
    to_port    = 0
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-private-app-nacl"
      Type = "private-app"
    }
  )
}
# Network ACL for Private Database Subnets
resource "aws_network_acl" "private_db" {
  vpc_id     = aws_vpc.main.id
  subnet_ids = aws_subnet.private_db[*].id

  # Inbound Rules

  # Allow traffic from private app subnets on database ports
  ingress {
    protocol   = "tcp"
    rule_no    = 100
    action     = "allow"
    cidr_block = cidrsubnet(var.vpc_cidr, 4, length(var.availability_zones))
    from_port  = 3306
    to_port    = 3306
  }

  # Allow PostgreSQL from private app subnets
  ingress {
    protocol   = "tcp"
    rule_no    = 110
    action     = "allow"
    cidr_block = cidrsubnet(var.vpc_cidr, 4, length(var.availability_zones))
    from_port  = 5432
    to_port    = 5432
  }

  # Allow MongoDB from private app subnets
  ingress {
    protocol   = "tcp"
    rule_no    = 120
    action     = "allow"
    cidr_block = cidrsubnet(var.vpc_cidr, 4, length(var.availability_zones))
    from_port  = 27017
    to_port    = 27017
  }

  # Allow Redis from private app subnets
  ingress {
    protocol   = "tcp"
    rule_no    = 130
    action     = "allow"
    cidr_block = cidrsubnet(var.vpc_cidr, 4, length(var.availability_zones))
    from_port  = 6379
    to_port    = 6379
  }
  # Allow return traffic on ephemeral ports
  ingress {
    protocol   = "tcp"
    rule_no    = 140
    action     = "allow"
    cidr_block = cidrsubnet(var.vpc_cidr, 4, length(var.availability_zones))
    from_port  = 1024
    to_port    = 65535
  }

  # Outbound Rules

  # Allow responses to private app subnets
  egress {
    protocol   = "tcp"
    rule_no    = 100
    action     = "allow"
    cidr_block = cidrsubnet(var.vpc_cidr, 4, length(var.availability_zones))
    from_port  = 1024
    to_port    = 65535
  }

  # Deny all other outbound traffic (DB should not initiate connections)
  egress {
    protocol   = "-1"
    rule_no    = 200
    action     = "deny"
    cidr_block = "0.0.0.0/0"
    from_port  = 0
    to_port    = 0
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-private-db-nacl"
      Type = "private-db"
    }
  )
}

# Default Network ACL - Deny all traffic
resource "aws_default_network_acl" "default" {
  default_network_acl_id = aws_vpc.main.default_network_acl_id

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-default-nacl"
      Note = "Deny all - unused"
    }
  )
}
