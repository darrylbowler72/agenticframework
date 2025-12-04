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

# VPC Link (for private integrations) - Commented out for now, will add later
# resource "aws_apigatewayv2_vpc_link" "main" {
#   name               = "${var.environment}-vpc-link"
#   security_group_ids = []
#   subnet_ids         = []
#
#   tags = {
#     Name = "${var.environment}-vpc-link"
#   }
# }
