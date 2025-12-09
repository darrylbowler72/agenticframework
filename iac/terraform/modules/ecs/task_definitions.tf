# ECS Task Definitions for Agents

locals {
  agents = {
    planner = {
      port        = 8000
      cpu         = 512
      memory      = 1024
      environment = "DYNAMODB_TABLE"
    }
    codegen = {
      port        = 8001
      cpu         = 512
      memory      = 1024
      environment = "S3_BUCKET"
    }
    remediation = {
      port        = 8002
      cpu         = 512
      memory      = 1024
      environment = "DYNAMODB_TABLE"
    }
    chatbot = {
      port        = 8003
      cpu         = 512
      memory      = 1024
      environment = "DYNAMODB_TABLE"
    }
    migration = {
      port        = 8004
      cpu         = 512
      memory      = 1024
      environment = "DYNAMODB_TABLE"
    }
  }

  # Map agent names to their version variables
  agent_versions = {
    planner     = var.planner_image_version
    codegen     = var.codegen_image_version
    remediation = var.remediation_image_version
    chatbot     = var.chatbot_image_version
    migration   = var.migration_image_version
  }
}

# Get AWS account ID
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Task Definition for each agent
resource "aws_ecs_task_definition" "agents" {
  for_each = local.agents

  family                   = "${var.environment}-${each.key}-agent"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "${each.key}-agent"
    image     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${data.aws_region.current.name}.amazonaws.com/${each.key}-agent:${local.agent_versions[each.key]}"
    essential = true

    portMappings = [{
      containerPort = each.value.port
      hostPort      = each.value.port
      protocol      = "tcp"
    }]

    environment = concat([
      {
        name  = "AWS_REGION"
        value = data.aws_region.current.name
      },
      {
        name  = "AWS_ACCOUNT_ID"
        value = data.aws_caller_identity.current.account_id
      },
      {
        name  = "ENVIRONMENT"
        value = var.environment
      },
      {
        name  = "AGENT_VERSION"
        value = local.agent_versions[each.key]
      },
      {
        name  = "LOG_LEVEL"
        value = "INFO"
      },
      {
        name  = "MCP_GITHUB_URL"
        value = "http://${var.environment}-mcp-github.${var.environment}-agentic.local:8100"
      }
    ], each.key == "chatbot" ? [{
      name  = "INTERNAL_ALB_URL"
      value = "http://${aws_lb.agents.dns_name}"
    }] : [])

    secrets = [
      {
        name      = "ANTHROPIC_API_KEY"
        valueFrom = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.environment}-anthropic-api-key"
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = each.key
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:${each.value.port}/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])

  tags = {
    Name = "${var.environment}-${each.key}-agent"
  }
}

# Security Group for ECS Tasks
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.environment}-ecs-tasks-sg"
  description = "Security group for ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    description = "Allow inbound from VPC"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.environment}-ecs-tasks-sg"
  }
}

# ECS Services for each agent
resource "aws_ecs_service" "agents" {
  for_each = local.agents

  name            = "${var.environment}-${each.key}-agent"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.agents[each.key].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = lookup({
      planner     = aws_lb_target_group.planner.arn
      codegen     = aws_lb_target_group.codegen.arn
      remediation = aws_lb_target_group.remediation.arn
      chatbot     = aws_lb_target_group.chatbot.arn
      migration   = aws_lb_target_group.migration.arn
    }, each.key)
    container_name = "${each.key}-agent"
    container_port = each.value.port
  }

  enable_execute_command = true

  # Ensure ALB is created before the service
  depends_on = [aws_lb_listener.http]

  tags = {
    Name = "${var.environment}-${each.key}-agent-service"
  }
}

# MCP GitHub Server Task Definition
resource "aws_ecs_task_definition" "mcp_github" {
  family                   = "${var.environment}-mcp-github-agent"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "mcp-github"
    image     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${data.aws_region.current.name}.amazonaws.com/mcp-github:1.0.7"
    essential = true

    portMappings = [{
      containerPort = 8100
      hostPort      = 8100
      protocol      = "tcp"
    }]

    environment = [
      {
        name  = "AWS_REGION"
        value = data.aws_region.current.name
      },
      {
        name  = "ENVIRONMENT"
        value = var.environment
      },
      {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
    ]

    secrets = [
      {
        name      = "GITHUB_TOKEN"
        valueFrom = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.environment}-github-credentials"
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "mcp-github"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8100/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])

  tags = {
    Name = "${var.environment}-mcp-github"
  }
}

# ECS Service for MCP GitHub Server
resource "aws_ecs_service" "mcp_github" {
  name            = "${var.environment}-mcp-github"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.mcp_github.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  # Enable ECS Service Discovery for internal DNS
  service_registries {
    registry_arn = aws_service_discovery_service.mcp_github.arn
  }

  enable_execute_command = true

  tags = {
    Name = "${var.environment}-mcp-github-service"
  }
}

# Service Discovery for MCP GitHub Server
resource "aws_service_discovery_service" "mcp_github" {
  name = "${var.environment}-mcp-github"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }

  tags = {
    Name = "${var.environment}-mcp-github-discovery"
  }
}

# Service Discovery Namespace
resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "${var.environment}-agentic.local"
  vpc  = var.vpc_id

  tags = {
    Name = "${var.environment}-agentic-namespace"
  }
}
