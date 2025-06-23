# Audit Trail Implementation

# DynamoDB Table for Audit Logs
resource "aws_dynamodb_table" "audit_trail" {
  name             = "${var.project_name}-audit-trail"
  billing_mode     = "PAY_PER_REQUEST"
  hash_key         = "audit_id"
  range_key        = "timestamp"
  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  attribute {
    name = "audit_id"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "S"
  }
  attribute {
    name = "user_id"
    type = "S"
  }

  global_secondary_index {
    name            = "user_id_index"
    hash_key        = "user_id"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = var.common_tags
}

# DynamoDB Streams Event Source Mapping
resource "aws_lambda_event_source_mapping" "audit_stream" {
  event_source_arn  = aws_dynamodb_table.audit_trail.stream_arn
  function_name     = aws_lambda_function.audit_processor.arn
  starting_position = "LATEST"
}
