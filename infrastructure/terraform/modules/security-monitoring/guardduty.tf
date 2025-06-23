# GuardDuty Configuration for Threat Detection

# Enable GuardDuty
resource "aws_guardduty_detector" "main" {
  enable                       = true
  finding_publishing_frequency = var.guardduty_finding_frequency

  datasources {
    s3_logs {
      enable = true
    }
    kubernetes {
      audit_logs {
        enable = var.enable_eks_audit_logs
      }
    }
    malware_protection {
      scan_ec2_instance_with_findings {
        ebs_volumes {
          enable = true
        }
      }
    }
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-guardduty"
    }
  )
}

# GuardDuty ThreatIntelSet for Custom Threat Intelligence
resource "aws_guardduty_threatintelset" "main" {
  count       = var.threat_intel_set_url != "" ? 1 : 0
  activate    = true
  detector_id = aws_guardduty_detector.main.id
  format      = "TXT"
  location    = var.threat_intel_set_url
  name        = "${var.project_name}-threat-intel"

  tags = var.common_tags
}
# S3 bucket for GuardDuty custom IP lists
resource "aws_s3_bucket" "guardduty_lists" {
  count  = length(var.trusted_ip_list) > 0 ? 1 : 0
  bucket = "${var.project_name}-guardduty-lists-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-guardduty-lists"
    }
  )
}

# Upload trusted IPs list
resource "aws_s3_object" "trusted_ips" {
  count   = length(var.trusted_ip_list) > 0 ? 1 : 0
  bucket  = aws_s3_bucket.guardduty_lists[0].id
  key     = "trusted-ips.txt"
  content = join("\n", var.trusted_ip_list)

  tags = var.common_tags
}

# GuardDuty IPSet for Trusted IPs
resource "aws_guardduty_ipset" "trusted" {
  count       = length(var.trusted_ip_list) > 0 ? 1 : 0
  activate    = true
  detector_id = aws_guardduty_detector.main.id
  format      = "TXT"
  location    = "s3://${aws_s3_bucket.guardduty_lists[0].id}/${aws_s3_object.trusted_ips[0].key}"
  name        = "${var.project_name}-trusted-ips"

  tags = var.common_tags
}

# EventBridge Rule for GuardDuty Findings
resource "aws_cloudwatch_event_rule" "guardduty_findings" {
  name        = "${var.project_name}-guardduty-findings"
  description = "Capture GuardDuty findings"

  event_pattern = jsonencode({
    source      = ["aws.guardduty"]
    detail-type = ["GuardDuty Finding"]
    detail = {
      severity = [{ numeric = [">=", var.guardduty_severity_threshold] }]
    }
  })

  tags = var.common_tags
}
