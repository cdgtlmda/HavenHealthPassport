# Subnet Configuration for Haven Health Passport VPC
# Implements secure network segmentation with public, private app, and private DB tiers

# Public Subnets (for NAT Gateways and Load Balancers)
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-public-subnet-${var.availability_zones[count.index]}"
      Type = "public"
    }
  )
}

# Private Subnets for Application Tier
resource "aws_subnet" "private_app" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + length(var.availability_zones))
  availability_zone = var.availability_zones[count.index]

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-private-app-subnet-${var.availability_zones[count.index]}"
      Type = "private-app"
    }
  )
}
# Private Subnets for Database Tier
resource "aws_subnet" "private_db" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + (2 * length(var.availability_zones)))
  availability_zone = var.availability_zones[count.index]

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-private-db-subnet-${var.availability_zones[count.index]}"
      Type = "private-db"
    }
  )
}
