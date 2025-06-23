# Outputs for S3 module

output "patient_documents_bucket_name" {
  description = "Name of the patient documents bucket"
  value       = aws_s3_bucket.patient_documents.id
}

output "patient_documents_bucket_arn" {
  description = "ARN of the patient documents bucket"
  value       = aws_s3_bucket.patient_documents.arn
}

output "patient_documents_bucket_domain_name" {
  description = "Domain name of the patient documents bucket"
  value       = aws_s3_bucket.patient_documents.bucket_domain_name
}

output "logs_bucket_name" {
  description = "Name of the logs bucket"
  value       = aws_s3_bucket.logs.id
}

output "logs_bucket_arn" {
  description = "ARN of the logs bucket"
  value       = aws_s3_bucket.logs.arn
}

output "bucket_kms_key_id" {
  description = "KMS key ID used for bucket encryption"
  value       = var.kms_key_id
}
