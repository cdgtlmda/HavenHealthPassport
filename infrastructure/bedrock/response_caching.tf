# Bedrock Response Caching Configuration
# Implements multi-layer caching for cost optimization and performance

locals {
  # Cache configuration by use case
  cache_configs = {
    medical_analysis = {
      enabled         = true
      ttl_seconds     = 3600      # 1 hour
      max_size_mb     = 100
      similarity_threshold = 0.95
      cache_keys      = ["use_case", "messages_hash", "model_key"]
    }

    medical_translation = {
      enabled         = true
      ttl_seconds     = 86400     # 24 hours
      max_size_mb     = 500
      similarity_threshold = 0.98  # Higher threshold for translations
      cache_keys      = ["source_lang", "target_lang", "text_hash", "model_key"]
    }

    document_analysis = {
      enabled         = true
      ttl_seconds     = 7200      # 2 hours
      max_size_mb     = 200
      similarity_threshold = 0.90
      cache_keys      = ["document_hash", "analysis_type", "model_key"]
    }

    embeddings = {
      enabled         = true
      ttl_seconds     = 604800    # 7 days
      max_size_mb     = 1000
      similarity_threshold = 1.0   # Exact match only
      cache_keys      = ["text_hash", "model_key", "dimensions"]
    }

    general_chat = {
      enabled         = false     # No caching for conversations
      ttl_seconds     = 0
      max_size_mb     = 0
      similarity_threshold = 0
      cache_keys      = []
    }
  }
  # Cache storage tiers
  cache_tiers = {
    hot = {
      storage_type    = "elasticache"
      max_items       = 10000
      eviction_policy = "lru"
    }

    warm = {
      storage_type    = "s3"
      max_items       = 100000
      eviction_policy = "ttl"
    }

    cold = {
      storage_type    = "s3_glacier"
      max_items       = 1000000
      eviction_policy = "ttl"
    }
  }
}

# ElastiCache Redis cluster for hot cache
resource "aws_elasticache_replication_group" "bedrock_cache" {
  replication_group_id       = "${var.project_name}-bedrock-cache"
  description               = "Redis cache for Bedrock responses"
  engine                    = "redis"
  engine_version           = "7.0"
  node_type                = var.cache_node_type
  port                     = 6379
  parameter_group_name     = aws_elasticache_parameter_group.bedrock_cache.name
  subnet_group_name        = aws_elasticache_subnet_group.bedrock_cache.name
  security_group_ids       = [aws_security_group.cache_sg.id]

  # High availability
  automatic_failover_enabled = true
  multi_az_enabled          = true
  num_cache_clusters        = 2

  # Encryption
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token_enabled        = true
  auth_token                = random_password.cache_auth_token.result

  # Backup
  snapshot_retention_limit   = 7
  snapshot_window           = "03:00-05:00"
  maintenance_window        = "sun:05:00-sun:07:00"
  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-bedrock-cache"
      Component   = "AI-ML"
      CacheType   = "hot"
    }
  )
}

# ElastiCache parameter group
resource "aws_elasticache_parameter_group" "bedrock_cache" {
  family = "redis7"
  name   = "${var.project_name}-bedrock-cache-params"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  parameter {
    name  = "timeout"
    value = "300"
  }

  parameter {
    name  = "tcp-keepalive"
    value = "300"
  }
}

# ElastiCache subnet group
resource "aws_elasticache_subnet_group" "bedrock_cache" {
  name       = "${var.project_name}-bedrock-cache-subnet"
  subnet_ids = var.private_subnet_ids

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-bedrock-cache-subnet"
    }
  )
}

# Security group for cache
resource "aws_security_group" "cache_sg" {
  name        = "${var.project_name}-bedrock-cache-sg"
  description = "Security group for Bedrock cache"
  vpc_id      = var.vpc_id
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda_sg.id]
    description     = "Redis access from Lambda functions"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-bedrock-cache-sg"
    }
  )
}

# Random password for cache auth
resource "random_password" "cache_auth_token" {
  length  = 32
  special = true
}

# Store auth token in Secrets Manager
resource "aws_secretsmanager_secret" "cache_auth_token" {
  name = "${var.project_name}-bedrock-cache-auth-token"

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-cache-auth-token"
      Component = "AI-ML"
    }
  )
}

resource "aws_secretsmanager_secret_version" "cache_auth_token" {
  secret_id     = aws_secretsmanager_secret.cache_auth_token.id
  secret_string = random_password.cache_auth_token.result
}
# S3 bucket for warm/cold cache storage
resource "aws_s3_bucket" "bedrock_cache" {
  bucket = "${var.project_name}-bedrock-response-cache"

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-bedrock-cache"
      Component   = "AI-ML"
      CacheType   = "warm-cold"
    }
  )
}

# S3 bucket versioning
resource "aws_s3_bucket_versioning" "bedrock_cache" {
  bucket = aws_s3_bucket.bedrock_cache.id

  versioning_configuration {
    status = "Enabled"
  }
}

# S3 bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "bedrock_cache" {
  bucket = aws_s3_bucket.bedrock_cache.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.bedrock_config.arn
    }
  }
}

# S3 lifecycle policy for cache tiers
resource "aws_s3_bucket_lifecycle_configuration" "bedrock_cache" {
  bucket = aws_s3_bucket.bedrock_cache.id

  rule {
    id     = "transition-to-cold"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "GLACIER_IR"
    }

    expiration {
      days = 365
    }
  }
}
# Lambda function for cache management
resource "aws_lambda_function" "cache_manager" {
  filename         = data.archive_file.cache_manager.output_path
  function_name    = "${var.project_name}-bedrock-cache-manager"
  role            = aws_iam_role.cache_manager.arn
  handler         = "cache_manager.handler"
  runtime         = "python3.11"
  timeout         = 30
  memory_size     = 512

  environment {
    variables = {
      CACHE_CONFIGS_JSON    = jsonencode(local.cache_configs)
      REDIS_ENDPOINT        = aws_elasticache_replication_group.bedrock_cache.configuration_endpoint_address
      REDIS_PORT           = aws_elasticache_replication_group.bedrock_cache.port
      CACHE_BUCKET         = aws_s3_bucket.bedrock_cache.id
      AUTH_TOKEN_SECRET_ID = aws_secretsmanager_secret.cache_auth_token.id
      ENVIRONMENT          = var.environment
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda_sg.id]
  }

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-cache-manager"
      Component = "AI-ML"
    }
  )
}

# CloudWatch Log Group for cache manager
resource "aws_cloudwatch_log_group" "cache_manager" {
  name              = "/aws/lambda/${aws_lambda_function.cache_manager.function_name}"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.bedrock_config.arn

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-cache-manager-logs"
      Component = "AI-ML"
    }
  )
}
# Outputs
output "cache_configs" {
  description = "Cache configurations by use case"
  value       = local.cache_configs
}

output "redis_endpoint" {
  description = "Redis cache endpoint"
  value       = aws_elasticache_replication_group.bedrock_cache.configuration_endpoint_address
  sensitive   = true
}

output "cache_bucket_name" {
  description = "S3 bucket for cache storage"
  value       = aws_s3_bucket.bedrock_cache.id
}

output "cache_manager_function_arn" {
  description = "ARN of the cache manager Lambda function"
  value       = aws_lambda_function.cache_manager.arn
}

# Variables
variable "cache_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t4g.micro"
}
