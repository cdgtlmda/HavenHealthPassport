# AWS Config Rules for Compliance

# Config Rules for Compliance Checks
resource "aws_config_config_rule" "encrypted_volumes" {
  name = "${var.project_name}-encrypted-volumes"

  source {
    owner             = "AWS"
    source_identifier = "ENCRYPTED_VOLUMES"
  }
}

resource "aws_config_config_rule" "s3_bucket_encryption" {
  name = "${var.project_name}-s3-bucket-encryption"

  source {
    owner             = "AWS"
    source_identifier = "S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED"
  }
}

resource "aws_config_config_rule" "rds_encryption" {
  name = "${var.project_name}-rds-encryption"

  source {
    owner             = "AWS"
    source_identifier = "RDS_STORAGE_ENCRYPTED"
  }
}

resource "aws_config_config_rule" "mfa_enabled" {
  name = "${var.project_name}-mfa-enabled"

  source {
    owner             = "AWS"
    source_identifier = "MFA_ENABLED_FOR_IAM_CONSOLE_ACCESS"
  }
}

resource "aws_config_config_rule" "root_account_mfa" {
  name = "${var.project_name}-root-account-mfa"

  source {
    owner             = "AWS"
    source_identifier = "ROOT_ACCOUNT_MFA_ENABLED"
  }
}

# Custom Config Rule for HIPAA Compliance
resource "aws_config_config_rule" "hipaa_compliance" {  name = "${var.project_name}-hipaa-compliance"

  source {
    owner             = "AWS"
    source_identifier = "HIPAA_CONTROLS_BASELINE"
  }
}

# Lambda Function for Drift Detection
resource "aws_lambda_function" "drift_detector" {
  filename         = "${path.module}/lambda/drift-detector.zip"
  function_name    = "${var.project_name}-drift-detector"
  role            = aws_iam_role.drift_detector.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 300
  memory_size     = 512

  environment {
    variables = {
      CONFIG_RULES  = jsonencode(var.compliance_rules)
      SNS_TOPIC_ARN = var.sns_alert_topic_arn
    }
  }

  tags = var.common_tags
}

# EventBridge Rule for Config Compliance Changes
resource "aws_cloudwatch_event_rule" "config_compliance" {
  name        = "${var.project_name}-config-compliance"
  description = "Trigger on config compliance changes"

  event_pattern = jsonencode({
    source      = ["aws.config"]
    detail-type = ["Config Rules Compliance Change"]
    detail = {
      messageType = ["ComplianceChangeNotification"]
      newEvaluationResult = {
        complianceType = ["NON_COMPLIANT"]
      }
    }
  })

  tags = var.common_tags
}

# EventBridge Target for Lambda
resource "aws_cloudwatch_event_target" "drift_lambda" {
  rule      = aws_cloudwatch_event_rule.config_compliance.name
  target_id = "DriftDetectorLambda"
  arn       = aws_lambda_function.drift_detector.arn
}
