# Container Runtime Protection Configuration

# Security Policy for ECS Tasks
resource "aws_iam_policy" "ecs_task_security" {
  name        = "${var.project_name}-ecs-task-security"
  description = "Security policy for ECS tasks"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Deny"
        Action = "*"
        Resource = "*"
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "ecr:SignatureStatus" = "ACTIVE"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}
# ECS Task Definition with Security Controls
resource "aws_ecs_task_definition" "secure_template" {
  family                   = "${var.project_name}-secure-task-template"
  network_mode            = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                     = "256"
  memory                  = "512"
  execution_role_arn      = aws_iam_role.ecs_execution.arn
  task_role_arn           = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture       = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name      = "secure-container-template"
      image     = "placeholder"
      essential = true

      # Security configurations
      readonlyRootFilesystem = true
      privileged             = false
      user                   = "1000:1000"

      linuxParameters = {
        initProcessEnabled = true
        capabilities = {
          drop = ["ALL"]
          add  = []
        }
      }

      # Resource limits
      ulimits = [
        {
          name      = "nofile"
          softLimit = 1024
          hardLimit = 4096
        }
      ]

      # Health check
      healthCheck = {
        command     = ["CMD-SHELL", "echo healthy"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])
}
