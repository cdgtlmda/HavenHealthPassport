# SIEM Integration Configuration

# Kinesis Firehose for Log Aggregation
resource "aws_kinesis_firehose_delivery_stream" "security_logs" {
  name        = "${var.project_name}-security-logs"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn           = aws_iam_role.firehose.arn
    bucket_arn         = aws_s3_bucket.siem_logs.arn
    prefix             = "security-logs/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
    error_output_prefix = "error-logs/"
    compression_format = "GZIP"

    processing_configuration {
      enabled = "true"

      processors {
        type = "Lambda"

        parameters {
          parameter_name  = "LambdaArn"
          parameter_value = aws_lambda_function.log_processor.arn
        }
      }
    }

    data_format_conversion_configuration {
      enabled = true

      output_format_configuration {
        serializer {
          parquet_ser_de {}
        }
      }

      schema_configuration {
        database_name = aws_glue_catalog_database.security_logs.name
        table_name    = aws_glue_catalog_table.security_logs.name
      }
    }
  }

  tags = var.common_tags
}
# S3 Bucket for SIEM Logs
resource "aws_s3_bucket" "siem_logs" {
  bucket = "${var.project_name}-siem-logs-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-siem-logs"
    }
  )
}

# Glue Database for Security Logs
resource "aws_glue_catalog_database" "security_logs" {
  name = "${var.project_name}_security_logs"

  description = "Security logs database for SIEM integration"
}

# Glue Table for Security Logs
resource "aws_glue_catalog_table" "security_logs" {
  name          = "security_logs"
  database_name = aws_glue_catalog_database.security_logs.name

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "projection.enabled"              = "true"
    "projection.year.type"            = "integer"
    "projection.year.range"           = "2024,2030"
    "projection.month.type"           = "integer"
    "projection.month.range"          = "1,12"
    "projection.day.type"             = "integer"
    "projection.day.range"            = "1,31"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.siem_logs.bucket}/security-logs/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "timestamp"
      type = "timestamp"
    }
    columns {
      name = "event_type"
      type = "string"
    }
  }
}
