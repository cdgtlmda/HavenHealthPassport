# DDoS Protection Configuration for Haven Health Passport
# Implements AWS Shield Advanced and CloudFront protection

# Enable AWS Shield Advanced (requires manual subscription)
resource "aws_shield_protection" "alb" {
  count        = var.enable_shield_advanced ? 1 : 0
  name         = "${var.project_name}-alb-shield"
  resource_arn = var.alb_arn

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-alb-shield"
    }
  )
}

# CloudFront Distribution for DDoS Protection
resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.project_name} CloudFront Distribution"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"

  origin {
    domain_name = var.alb_dns_name
    origin_id   = "${var.project_name}-alb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    custom_header {
      name  = "X-CloudFront-Secret"
      value = var.cloudfront_secret
    }
  }

  default_cache_behavior {
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "${var.project_name}-alb"
    forwarded_values {
      query_string = true
      headers      = ["*"]

      cookies {
        forward = "all"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0

    compress = true
  }

  restrictions {
    geo_restriction {
      restriction_type = length(var.cloudfront_geo_restrictions) > 0 ? "blacklist" : "none"
      locations        = var.cloudfront_geo_restrictions
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  web_acl_id = aws_wafv2_web_acl.main.arn

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-cloudfront"
    }
  )
}

# Route 53 Health Check for DDoS Monitoring
resource "aws_route53_health_check" "main" {
  fqdn              = var.alb_dns_name
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = "3"
  request_interval  = "30"
  measure_latency = true

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-health-check"
    }
  )
}

# CloudWatch Alarms for DDoS Detection
resource "aws_cloudwatch_metric_alarm" "ddos_detected" {
  alarm_name          = "${var.project_name}-ddos-detected"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DDoSDetected"
  namespace           = "AWS/DDoSProtection"
  period              = "60"
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "This metric monitors DDoS detection"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ResourceArn = var.alb_arn
  }

  alarm_actions = [var.sns_alert_topic_arn]

  tags = var.common_tags
}

resource "aws_cloudwatch_metric_alarm" "waf_blocked_requests" {
  alarm_name          = "${var.project_name}-waf-blocked-requests-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "BlockedRequests"
  namespace           = "AWS/WAFV2"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1000"
  alarm_description   = "Alert when WAF blocks too many requests"
  treat_missing_data  = "notBreaching"
  dimensions = {
    WebACL = aws_wafv2_web_acl.main.name
    Region = var.aws_region
    Rule   = "ALL"
  }

  alarm_actions = [var.sns_alert_topic_arn]

  tags = var.common_tags
}

# Auto Scaling Policy for DDoS Response
resource "aws_autoscaling_policy" "ddos_response" {
  count                  = var.enable_ddos_auto_scaling ? 1 : 0
  name                   = "${var.project_name}-ddos-response"
  scaling_adjustment     = 10
  adjustment_type        = "PercentChangeInCapacity"
  cooldown               = 300
  autoscaling_group_name = var.app_autoscaling_group_name

  alarm_actions = [
    aws_cloudwatch_metric_alarm.ddos_detected.arn,
    aws_cloudwatch_metric_alarm.waf_blocked_requests.arn
  ]
}
