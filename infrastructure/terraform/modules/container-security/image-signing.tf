# Container Image Signing Configuration

# KMS Key for Image Signing
resource "aws_kms_key" "image_signing" {
  description             = "${var.project_name} Container Image Signing Key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-image-signing"
    }
  )
}

# KMS Key Alias
resource "aws_kms_alias" "image_signing" {
  name          = "alias/${var.project_name}-image-signing"
  target_key_id = aws_kms_key.image_signing.key_id
}

# ECR Registry Scanning Configuration
resource "aws_ecr_registry_scanning_configuration" "main" {
  scan_type = "ENHANCED"

  rule {
    scan_frequency = "CONTINUOUS_SCAN"
    repository_filter {
      filter      = "${var.project_name}/*"
      filter_type = "WILDCARD"
    }
  }

  rule {
    scan_frequency = "SCAN_ON_PUSH"
    repository_filter {
      filter      = "*"
      filter_type = "WILDCARD"
    }
  }
}
# Signer Profile for Container Images
resource "aws_signer_signing_profile" "container" {
  platform_id = "AWSLambda-SHA384-ECDSA"
  name        = "${var.project_name}-container-signing"

  signature_validity_period {
    value = 365
    type  = "DAYS"
  }

  tags = var.common_tags
}

# Trust Policy for Signed Images
resource "aws_iam_policy" "image_trust" {
  name        = "${var.project_name}-image-trust-policy"
  description = "Policy requiring signed container images"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Deny"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "ecr:SignatureStatus" = "ACTIVE"
          }
        }
      }
    ]
  })
}
