# DevOps Agentic Framework - Main Terraform Configuration

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # Configure backend in backend-config file:
    # terraform init -backend-config=environments/dev/backend.tfvars
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "devops-agentic-framework"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# VPC and Networking
module "vpc" {
  source = "./modules/vpc"

  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
}

# DynamoDB Tables
module "dynamodb" {
  source = "./modules/dynamodb"

  environment = var.environment
}

# S3 Buckets
module "s3" {
  source = "./modules/s3"

  environment = var.environment
}

# EventBridge
module "eventbridge" {
  source = "./modules/eventbridge"

  environment = var.environment
}

# API Gateway
module "api_gateway" {
  source = "./modules/api_gateway"

  environment            = var.environment
  vpc_id                 = module.vpc.vpc_id
  private_subnet_ids     = module.vpc.private_subnet_ids
  alb_listener_arn       = module.ecs.alb_listener_arn
  alb_dns_name           = module.ecs.alb_dns_name
  alb_security_group_id  = module.ecs.alb_security_group_id

  depends_on = [module.ecs]
}

# Lambda Functions
module "lambda_planner" {
  source = "./modules/lambda"

  function_name = "planner-agent"
  environment   = var.environment
  handler       = "main.lambda_handler"
  runtime       = "python3.11"
  memory_size   = 2048
  timeout       = 300

  source_code_path = "../../backend/agents/planner"
  vpc_subnet_ids   = module.vpc.private_subnet_ids
  vpc_sg_ids       = [module.vpc.lambda_sg_id]

  environment_variables = {
    DYNAMODB_TABLE = module.dynamodb.workflows_table_name
    EVENT_BUS_NAME = module.eventbridge.event_bus_name
  }
}

# ECS Cluster for long-running agents
module "ecs" {
  source = "./modules/ecs"

  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  public_subnet_ids  = module.vpc.public_subnet_ids
}

# Secrets Manager
resource "aws_secretsmanager_secret" "gitlab_credentials" {
  name        = "${var.environment}-gitlab-credentials"
  description = "GitLab API credentials"
}

resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name        = "${var.environment}-anthropic-api-key"
  description = "Anthropic Claude API key"
}

resource "aws_secretsmanager_secret" "slack_credentials" {
  name        = "${var.environment}-slack-credentials"
  description = "Slack bot credentials"
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "agents" {
  name              = "/aws/agentic-framework/${var.environment}"
  retention_in_days = 30
}

# Outputs
output "vpc_id" {
  value = module.vpc.vpc_id
}

output "api_gateway_url" {
  value = module.api_gateway.api_endpoint
}

output "workflows_table_name" {
  value = module.dynamodb.workflows_table_name
}

output "event_bus_name" {
  value = module.eventbridge.event_bus_name
}

output "ecs_cluster_name" {
  value       = module.ecs.cluster_name
  description = "ECS cluster name"
}

output "ecs_service_names" {
  value       = module.ecs.service_names
  description = "ECS service names for each agent"
}
