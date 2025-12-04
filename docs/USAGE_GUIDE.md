# DevOps Agentic Framework - Usage Guide

## Overview

The DevOps Agentic Framework provides AI-powered agents that automate DevOps workflows. This guide shows you how to use the deployed infrastructure.

## Current Deployment

### Infrastructure Status
- ✅ **3 AI Agents Running** on ECS Fargate
- ✅ **API Gateway** deployed
- ✅ **DynamoDB, S3, EventBridge** configured
- ⚠️ **API Gateway → ECS Integration** needs configuration

### Agent Endpoints (Internal)

The agents run on private IPs in your VPC:

1. **Planner Agent** (port 8000)
   - `POST /workflows` - Create workflow
   - `GET /workflows/{workflow_id}` - Get status
   - `GET /health` - Health check

2. **CodeGen Agent** (port 8001)
   - `POST /generate` - Generate microservice
   - `GET /health` - Health check

3. **Remediation Agent** (port 8002)
   - `POST /remediate` - Auto-fix issues
   - `GET /health` - Health check

## How to Use the Framework

### Method 1: Direct Testing (Development)

Since agents are in private subnets, you can test them using AWS Systems Manager Session Manager:

#### Step 1: Enable ECS Exec (Already Done)

Your services have `enable_execute_command = true` configured.

#### Step 2: Get a Task ID

```bash
# List running tasks
aws ecs list-tasks \
  --cluster dev-agentic-cluster \
  --service-name dev-planner-agent \
  --region us-east-1

# Get task details
aws ecs describe-tasks \
  --cluster dev-agentic-cluster \
  --tasks <task-arn> \
  --region us-east-1
```

#### Step 3: Test Health Endpoint

```bash
# Connect to the Planner Agent container
aws ecs execute-command \
  --cluster dev-agentic-cluster \
  --task <task-id> \
  --container planner-agent \
  --interactive \
  --command "/bin/sh" \
  --region us-east-1

# Inside the container, test:
curl http://localhost:8000/health
```

### Method 2: Connect API Gateway (Production)

To make agents publicly accessible (with authentication), you need to configure API Gateway integration.

#### Option A: Service Discovery with Cloud Map

Create AWS Cloud Map service discovery:

```bash
# Create namespace
aws servicediscovery create-private-dns-namespace \
  --name agentic-framework.local \
  --vpc vpc-0060df8e60cf8c532 \
  --region us-east-1

# Register services (done automatically by ECS with service discovery enabled)
```

#### Option B: Network Load Balancer + VPC Link

1. **Create NLB for each service** (or use Application Load Balancer)
2. **Create VPC Link** in API Gateway
3. **Add routes** to API Gateway

Example Terraform configuration needed:

```hcl
# Add to modules/ecs/main.tf

resource "aws_lb" "planner" {
  name               = "${var.environment}-planner-nlb"
  internal           = true
  load_balancer_type = "network"
  subnets            = var.private_subnet_ids
}

resource "aws_lb_target_group" "planner" {
  name        = "${var.environment}-planner-tg"
  port        = 8000
  protocol    = "TCP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled  = true
    protocol = "HTTP"
    path     = "/health"
  }
}

resource "aws_lb_listener" "planner" {
  load_balancer_arn = aws_lb.planner.arn
  port              = "8000"
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.planner.arn
  }
}

# Update ECS service to register with target group
resource "aws_ecs_service" "agents" {
  # ... existing config ...

  load_balancer {
    target_group_arn = aws_lb_target_group.planner.arn
    container_name   = "planner-agent"
    container_port   = 8000
  }
}
```

Then add VPC Link and routes to API Gateway:

```hcl
# Add to modules/api_gateway/main.tf

resource "aws_apigatewayv2_vpc_link" "main" {
  name               = "${var.environment}-vpc-link"
  security_group_ids = [var.ecs_security_group_id]
  subnet_ids         = var.private_subnet_ids
}

resource "aws_apigatewayv2_integration" "planner" {
  api_id             = aws_apigatewayv2_api.main.id
  integration_type   = "HTTP_PROXY"
  integration_uri    = aws_lb_listener.planner.arn
  integration_method = "POST"
  connection_type    = "VPC_LINK"
  connection_id      = aws_apigatewayv2_vpc_link.main.id
}

resource "aws_apigatewayv2_route" "create_workflow" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /workflows"
  target    = "integrations/${aws_apigatewayv2_integration.planner.id}"
}

resource "aws_apigatewayv2_route" "get_workflow" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /workflows/{workflow_id}"
  target    = "integrations/${aws_apigatewayv2_integration.planner.id}"
}
```

## Usage Examples

Once API Gateway is connected, you can use the framework like this:

### 1. Create a New Microservice

```bash
curl -X POST https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "template": "microservice-rest-api",
    "requested_by": "user@example.com",
    "parameters": {
      "service_name": "user-service",
      "language": "python",
      "database": "postgresql",
      "environment": "dev"
    }
  }'
```

Response:
```json
{
  "workflow_id": "wf-abc123def456",
  "status": "in_progress",
  "tasks": [
    {
      "task_id": "t-12345678",
      "agent": "codegen",
      "status": "pending",
      "description": "Generate user-service microservice code"
    }
  ],
  "created_at": "2024-12-03T10:00:00Z"
}
```

### 2. Check Workflow Status

```bash
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/workflows/wf-abc123def456
```

Response:
```json
{
  "workflow_id": "wf-abc123def456",
  "status": "completed",
  "template": "microservice-rest-api",
  "tasks": [
    {
      "task_id": "t-12345678",
      "agent": "codegen",
      "status": "completed",
      "description": "Generate user-service microservice code",
      "result": {
        "repository_url": "https://gitlab.com/your-org/user-service",
        "files_generated": 15
      }
    }
  ]
}
```

### 3. Generate Code Directly

```bash
curl -X POST https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/generate \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "payment-service",
    "language": "python",
    "database": "postgresql",
    "api_type": "rest",
    "environment": "dev"
  }'
```

### 4. Check Agent Health

```bash
# Check if agents are running
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/health

# Individual agent health (once routes are configured)
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/planner/health
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/codegen/health
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/remediation/health
```

## What Happens Behind the Scenes

### Workflow Execution Flow

1. **Request arrives** at API Gateway
2. **Planner Agent** receives request:
   - Analyzes the request using Claude AI
   - Breaks it into tasks
   - Stores workflow in DynamoDB
   - Publishes events to EventBridge
3. **EventBridge** routes events to appropriate agents
4. **CodeGen Agent** generates code:
   - Creates microservice structure
   - Generates Dockerfile, CI/CD configs
   - Stores artifacts in S3
   - Creates GitLab repository
5. **Status updates** stored in DynamoDB
6. **Results** available via GET /workflows/{id}

### Event-Driven Architecture

```
Request → API Gateway → Planner Agent → EventBridge
                                              ↓
                        ┌──────────────────────┼──────────────────────┐
                        ↓                      ↓                      ↓
                  CodeGen Agent        Policy Agent         Remediation Agent
                        ↓                      ↓                      ↓
                     S3/GitLab              Reports                DynamoDB
```

## Next Steps

To make the framework fully functional:

1. **Configure API Gateway Routes** (see Method 2 above)
2. **Add Authentication** (AWS IAM or JWT)
3. **Set up GitLab Integration** (store credentials in Secrets Manager)
4. **Deploy ArgoCD** for GitOps workflows
5. **Add Policy Agent** with OPA rules
6. **Set up Backstage** for developer UI

## Monitoring and Debugging

### View Agent Logs

```bash
# Planner Agent logs
aws logs tail /aws/ecs/dev-agentic-cluster --follow --filter-pattern planner

# CodeGen Agent logs
aws logs tail /aws/ecs/dev-agentic-cluster --follow --filter-pattern codegen

# All agents
aws logs tail /aws/ecs/dev-agentic-cluster --follow
```

### Check DynamoDB

```bash
# List workflows
aws dynamodb scan --table-name dev-workflows --region us-east-1

# Get specific workflow
aws dynamodb query \
  --table-name dev-workflows \
  --key-condition-expression "workflow_id = :wf_id" \
  --expression-attribute-values '{":wf_id":{"S":"wf-abc123def456"}}' \
  --region us-east-1
```

### Check S3 Artifacts

```bash
# List generated code
aws s3 ls s3://dev-agent-artifacts-773550624765/codegen/ --recursive

# Download artifact
aws s3 cp s3://dev-agent-artifacts-773550624765/codegen/user-service/... ./
```

## Troubleshooting

### Issue: Can't reach API Gateway endpoints
**Solution**: API Gateway routes need to be configured (see Method 2 above)

### Issue: Agents not processing events
**Solution**: Check EventBridge rules are enabled and targeting correct services

### Issue: Claude API errors
**Solution**: Verify Anthropic API key in Secrets Manager:
```bash
aws secretsmanager get-secret-value --secret-id dev-anthropic-api-key --region us-east-1
```

### Issue: GitLab repository not created
**Solution**: Add GitLab credentials to Secrets Manager:
```bash
aws secretsmanager put-secret-value \
  --secret-id dev-gitlab-credentials \
  --secret-string '{"url":"https://gitlab.com","token":"your-token"}' \
  --region us-east-1
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/darrylbowler72/agenticframework/issues
- Documentation: See README.md and architecture.md
