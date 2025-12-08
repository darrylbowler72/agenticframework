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

# Per-agent container image versions
planner_image_version     = "20251205-174517"
codegen_image_version     = "1.0.4"
remediation_image_version = "20251205-174716"
chatbot_image_version     = "latest"
