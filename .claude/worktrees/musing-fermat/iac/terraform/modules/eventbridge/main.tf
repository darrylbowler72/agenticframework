# EventBridge Module

# Custom Event Bus
resource "aws_cloudwatch_event_bus" "agentic_framework" {
  name = "${var.environment}-agentic-framework"

  tags = {
    Name = "${var.environment}-agentic-framework"
  }
}

# Event Rule: Task Created
resource "aws_cloudwatch_event_rule" "task_created" {
  name           = "${var.environment}-task-created"
  description    = "Route task.created events to appropriate agents"
  event_bus_name = aws_cloudwatch_event_bus.agentic_framework.name

  event_pattern = jsonencode({
    source      = ["agentic-framework.planner"]
    detail-type = ["task.created"]
  })
}

# Event Rule: Pipeline Failed
resource "aws_cloudwatch_event_rule" "pipeline_failed" {
  name           = "${var.environment}-pipeline-failed"
  description    = "Route pipeline.failed events to remediation agent"
  event_bus_name = aws_cloudwatch_event_bus.agentic_framework.name

  event_pattern = jsonencode({
    source      = ["gitlab.webhook"]
    detail-type = ["pipeline.failed"]
  })
}

# Dead Letter Queue for failed events
resource "aws_sqs_queue" "event_dlq" {
  name                       = "${var.environment}-event-dlq"
  message_retention_seconds  = 1209600 # 14 days
  visibility_timeout_seconds = 300

  tags = {
    Name = "${var.environment}-event-dlq"
  }
}

# Outputs
output "event_bus_name" {
  value = aws_cloudwatch_event_bus.agentic_framework.name
}

output "event_bus_arn" {
  value = aws_cloudwatch_event_bus.agentic_framework.arn
}

output "task_created_rule_arn" {
  value = aws_cloudwatch_event_rule.task_created.arn
}

output "pipeline_failed_rule_arn" {
  value = aws_cloudwatch_event_rule.pipeline_failed.arn
}
