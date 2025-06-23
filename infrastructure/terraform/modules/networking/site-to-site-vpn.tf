# Site-to-Site VPN Configuration for Haven Health Passport
# Connects on-premises networks or partner healthcare systems

# Customer Gateway
resource "aws_customer_gateway" "main" {
  count      = length(var.site_to_site_vpn_configs)
  bgp_asn    = var.site_to_site_vpn_configs[count.index].bgp_asn
  ip_address = var.site_to_site_vpn_configs[count.index].ip_address
  type       = "ipsec.1"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-cgw-${var.site_to_site_vpn_configs[count.index].name}"
    }
  )
}

# Virtual Private Gateway
resource "aws_vpn_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-vgw"
    }
  )
}

# VPN Gateway Attachment
resource "aws_vpn_gateway_attachment" "main" {
  vpc_id         = aws_vpc.main.id
  vpn_gateway_id = aws_vpn_gateway.main.id
}
# VPN Connection
resource "aws_vpn_connection" "main" {
  count               = length(var.site_to_site_vpn_configs)
  customer_gateway_id = aws_customer_gateway.main[count.index].id
  vpn_gateway_id      = aws_vpn_gateway.main.id
  type                = "ipsec.1"
  static_routes_only  = var.site_to_site_vpn_configs[count.index].static_routes_only

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-vpn-${var.site_to_site_vpn_configs[count.index].name}"
    }
  )
}

# VPN Connection Routes (for static routing)
resource "aws_vpn_connection_route" "main" {
  count                  = length(var.site_to_site_vpn_static_routes)
  vpn_connection_id      = aws_vpn_connection.main[var.site_to_site_vpn_static_routes[count.index].connection_index].id
  destination_cidr_block = var.site_to_site_vpn_static_routes[count.index].cidr
}

# Route Propagation (for BGP)
resource "aws_vpn_gateway_route_propagation" "main" {
  count          = length(var.availability_zones)
  vpn_gateway_id = aws_vpn_gateway.main.id
  route_table_id = aws_route_table.private_app[count.index].id
}

# CloudWatch Log Group for VPN Monitoring
resource "aws_cloudwatch_log_group" "site_to_site_vpn" {
  name              = "/aws/vpn/site-to-site/${var.project_name}"
  retention_in_days = var.vpn_log_retention_days
  kms_key_id        = var.kms_key_arn

  tags = var.common_tags
}
# CloudWatch Alarms for VPN Connection
resource "aws_cloudwatch_metric_alarm" "vpn_connection_state" {
  count               = length(var.site_to_site_vpn_configs)
  alarm_name          = "${var.project_name}-vpn-${var.site_to_site_vpn_configs[count.index].name}-down"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "TunnelState"
  namespace           = "AWS/VPN"
  period              = "60"
  statistic           = "Maximum"
  threshold           = "1"
  alarm_description   = "VPN connection is down"
  treat_missing_data  = "breaching"

  dimensions = {
    VpnId = aws_vpn_connection.main[count.index].id
  }

  alarm_actions = [var.sns_alert_topic_arn]

  tags = var.common_tags
}
