# Post-Mortem Process Configuration

# DynamoDB Table for Post-Mortem Records
resource "aws_dynamodb_table" "postmortems" {
  name           = "${var.project_name}-postmortems"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "incident_id"
  range_key      = "version"

  attribute {
    name = "incident_id"
    type = "S"
  }
  attribute {
    name = "version"
    type = "N"
  }
  attribute {
    name = "created_date"
    type = "S"
  }

  global_secondary_index {
    name            = "created_date_index"
    hash_key        = "created_date"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  tags = var.common_tags
}

# Lambda for Post-Mortem Processing
resource "aws_lambda_function" "postmortem_processor" {
  filename      = "${path.module}/lambda/postmortem-processor.zip"
  function_name = "${var.project_name}-postmortem-processor"
  role          = aws_iam_role.postmortem_processor.arn
  handler       = "index.handler"
  runtime       = "python3.9"

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.postmortems.name
    }
  }
}
