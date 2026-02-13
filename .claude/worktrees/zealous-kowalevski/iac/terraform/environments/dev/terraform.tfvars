# Development Environment Configuration

environment = "dev"
aws_region  = "us-east-1"

vpc_cidr = "10.0.0.0/16"

availability_zones = [
  "us-east-1a",
  "us-east-1b",
  "us-east-1c"
]

project_name = "devops-agentic-framework"

# Per-agent container image versions (semantic versioning)
planner_image_version     = "1.0.5"
codegen_image_version     = "1.0.5"
remediation_image_version = "1.0.5"
chatbot_image_version     = "1.0.12"
migration_image_version   = "1.0.5"
jenkins_image_version     = "1.0.0"
