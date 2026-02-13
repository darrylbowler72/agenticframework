# API Gateway Module for DevOps Agentic Framework

resource "aws_apigatewayv2_api" "main" {
  name          = "${var.environment}-agentic-api"
  protocol_type = "HTTP"
  description   = "API Gateway for DevOps Agentic Framework"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["*"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_stage" "main" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = var.environment
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.environment}-agentic-api"
  retention_in_days = 30
}

# VPC Link (for private integrations with ALB)
resource "aws_apigatewayv2_vpc_link" "main" {
  name               = "${var.environment}-vpc-link"
  security_group_ids = [var.alb_security_group_id]
  subnet_ids         = var.private_subnet_ids

  tags = {
    Name = "${var.environment}-vpc-link"
  }
}

# Integration with ALB
resource "aws_apigatewayv2_integration" "alb" {
  api_id             = aws_apigatewayv2_api.main.id
  integration_type   = "HTTP_PROXY"
  integration_method = "ANY"
  integration_uri    = var.alb_listener_arn
  connection_type    = "VPC_LINK"
  connection_id      = aws_apigatewayv2_vpc_link.main.id

  # Preserve the original request path
  payload_format_version = "1.0"
  timeout_milliseconds   = 30000
}

# Routes for Planner Agent
resource "aws_apigatewayv2_route" "create_workflow" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /workflows"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "get_workflow" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /workflows/{workflow_id}"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

# Routes for CodeGen Agent
resource "aws_apigatewayv2_route" "generate" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /generate"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

# Routes for Remediation Agent
resource "aws_apigatewayv2_route" "remediate" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /remediate"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

# Health check routes
resource "aws_apigatewayv2_route" "planner_health" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /planner/health"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "codegen_health" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /codegen/health"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "remediation_health" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /remediation/health"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

# Routes for Chatbot Agent
resource "aws_apigatewayv2_route" "chatbot_root" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "chatbot_static" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /static/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "chatbot_chat_post" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /chat"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "chatbot_session" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /session/{session_id}"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "chatbot_health" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /chatbot/health"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "agents_health" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /api/agents/health"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

# Routes for Migration Agent
resource "aws_apigatewayv2_route" "migration_migrate" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /migrate"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "migration_analyze" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /analyze"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "migration_health" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /migration/health"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

# Jenkins Integration Routes
resource "aws_apigatewayv2_route" "migration_jenkins_test" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /migration/jenkins/test"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "migration_jenkins_jobs" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /migration/jenkins/jobs"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "migration_jenkins_job_details" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /migration/jenkins/jobs/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "migration_jenkins_migrate_job" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /migration/jenkins/migrate-job"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "migration_github_test" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /migration/github/test"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "migration_integration_test" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /migration/integration/test"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "migration_jenkins_create_job" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /migration/jenkins/create-job"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

# Jenkins UI Routes
resource "aws_apigatewayv2_route" "jenkins_root_get" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /jenkins"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "jenkins_proxy_get" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /jenkins/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "jenkins_proxy_post" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /jenkins/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}
