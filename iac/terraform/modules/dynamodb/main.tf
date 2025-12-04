# DynamoDB Tables Module

# Workflows Table
resource "aws_dynamodb_table" "workflows" {
  name         = "${var.environment}-workflows"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "workflow_id"
  range_key    = "task_id"

  attribute {
    name = "workflow_id"
    type = "S"
  }

  attribute {
    name = "task_id"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = "${var.environment}-workflows"
  }
}

# Remediation Playbooks Table
resource "aws_dynamodb_table" "remediation_playbooks" {
  name         = "${var.environment}-remediation-playbooks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "playbook_id"

  attribute {
    name = "playbook_id"
    type = "S"
  }

  attribute {
    name = "category"
    type = "S"
  }

  global_secondary_index {
    name            = "category-index"
    hash_key        = "category"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = "${var.environment}-remediation-playbooks"
  }
}

# Remediation Actions Table
resource "aws_dynamodb_table" "remediation_actions" {
  name         = "${var.environment}-remediation-actions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "action_id"

  attribute {
    name = "action_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  global_secondary_index {
    name            = "timestamp-index"
    hash_key        = "timestamp"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = "${var.environment}-remediation-actions"
  }
}

# Chatbot Sessions Table
resource "aws_dynamodb_table" "chatbot_sessions" {
  name         = "${var.environment}-chatbot-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = "${var.environment}-chatbot-sessions"
  }
}

# Outputs
output "workflows_table_name" {
  value = aws_dynamodb_table.workflows.name
}

output "workflows_table_arn" {
  value = aws_dynamodb_table.workflows.arn
}

output "remediation_playbooks_table_name" {
  value = aws_dynamodb_table.remediation_playbooks.name
}

output "remediation_actions_table_name" {
  value = aws_dynamodb_table.remediation_actions.name
}

output "chatbot_sessions_table_name" {
  value = aws_dynamodb_table.chatbot_sessions.name
}
