output "api_id" {
  description = "API Gateway ID"
  value       = aws_apigatewayv2_api.main.id
}

output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_stage.main.invoke_url
}

# Commented out since VPC link is not created yet
# output "vpc_link_id" {
#   description = "VPC Link ID"
#   value       = aws_apigatewayv2_vpc_link.main.id
# }
