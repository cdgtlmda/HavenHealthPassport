# Bastion Host Configuration for Haven Health Passport
# Provides secure SSH access to private instances

# Bastion Host Launch Template
resource "aws_launch_template" "bastion" {
  name_prefix   = "${var.project_name}-bastion-"
  image_id      = coalesce(var.bastion_ami_id, data.aws_ami.amazon_linux_2.id)
  instance_type = var.bastion_instance_type
  key_name      = var.bastion_key_pair_name

  vpc_security_group_ids = [aws_security_group.bastion.id]

  iam_instance_profile {
    arn = aws_iam_instance_profile.bastion.arn
  }

  user_data = base64encode(templatefile("${path.module}/templates/bastion-userdata.sh", {
    project_name = var.project_name
    aws_region   = var.aws_region
  }))

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = 20
      volume_type           = "gp3"
      encrypted             = true
      kms_key_id            = var.kms_key_arn
      delete_on_termination = true
    }
  }

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  tag_specifications {
    resource_type = "instance"

    tags = merge(
      var.common_tags,
      {
        Name = "${var.project_name}-bastion"
        Type = "bastion"
      }
    )
  }
}
# Bastion Host Auto Scaling Group
resource "aws_autoscaling_group" "bastion" {
  name                = "${var.project_name}-bastion-asg"
  vpc_zone_identifier = aws_subnet.public[*].id
  min_size            = var.bastion_min_size
  max_size            = var.bastion_max_size
  desired_capacity    = var.bastion_desired_capacity

  launch_template {
    id      = aws_launch_template.bastion.id
    version = "$Latest"
  }

  health_check_type         = "EC2"
  health_check_grace_period = 300

  tag {
    key                 = "Name"
    value               = "${var.project_name}-bastion"
    propagate_at_launch = true
  }

  dynamic "tag" {
    for_each = var.common_tags

    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }
}

# Elastic IP for Bastion Host
resource "aws_eip" "bastion" {
  count  = var.bastion_desired_capacity
  domain = "vpc"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-bastion-eip-${count.index}"
    }
  )
}
# Data source for latest Amazon Linux 2 AMI
data "aws_ami" "amazon_linux_2" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# CloudWatch Log Groups for Bastion
resource "aws_cloudwatch_log_group" "bastion_secure" {
  name              = "/aws/bastion/${var.project_name}/secure"
  retention_in_days = var.bastion_log_retention_days
  kms_key_id        = var.kms_key_arn

  tags = var.common_tags
}

# IAM Role for Bastion Host
resource "aws_iam_role" "bastion" {
  name = "${var.project_name}-bastion-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = var.common_tags
}
# IAM Policy for Bastion Host
resource "aws_iam_role_policy" "bastion" {
  name = "${var.project_name}-bastion-policy"
  role = aws_iam_role.bastion.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:AssociateAddress",
          "ec2:DescribeAddresses"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Instance Profile for Bastion
resource "aws_iam_instance_profile" "bastion" {
  name = "${var.project_name}-bastion-profile"
  role = aws_iam_role.bastion.name
}
