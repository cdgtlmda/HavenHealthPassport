# Base Image Policies Configuration

# S3 Bucket for Approved Base Images List
resource "aws_s3_bucket" "approved_images" {
  bucket = "${var.project_name}-approved-base-images"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-approved-base-images"
    }
  )
}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "approved_images" {
  bucket = aws_s3_bucket.approved_images.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "approved_images" {
  bucket = aws_s3_bucket.approved_images.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
  }
}

# Upload approved base images list
resource "aws_s3_object" "approved_images_list" {
  bucket = aws_s3_bucket.approved_images.id
  key    = "approved-images.json"

  content = jsonencode({
    approved_images = var.approved_base_images
    updated_at     = timestamp()
  })

  content_type = "application/json"

  tags = var.common_tags
}
# Lambda for Base Image Policy Enforcement
resource "aws_lambda_function" "image_policy_enforcer" {
  filename         = "${path.module}/lambda/image-policy-enforcer.zip"
  function_name    = "${var.project_name}-image-policy-enforcer"
  role            = aws_iam_role.image_policy_enforcer.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 60
  memory_size     = 256

  environment {
    variables = {
      APPROVED_IMAGES_BUCKET = aws_s3_bucket.approved_images.id
      APPROVED_IMAGES_KEY    = aws_s3_object.approved_images_list.key
    }
  }

  tags = var.common_tags
}

# IAM Role for Image Policy Enforcer
resource "aws_iam_role" "image_policy_enforcer" {
  name = "${var.project_name}-image-policy-enforcer-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.common_tags
}
