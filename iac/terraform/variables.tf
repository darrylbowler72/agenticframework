# Terraform Variables

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "devops-agentic-framework"
}

variable "planner_image_version" {
  description = "Version tag for planner agent container image"
  type        = string
  default     = "latest"
}

variable "codegen_image_version" {
  description = "Version tag for codegen agent container image"
  type        = string
  default     = "latest"
}

variable "remediation_image_version" {
  description = "Version tag for remediation agent container image"
  type        = string
  default     = "latest"
}

variable "chatbot_image_version" {
  description = "Version tag for chatbot agent container image"
  type        = string
  default     = "latest"
}

variable "migration_image_version" {
  description = "Version tag for migration agent container image"
  type        = string
  default     = "latest"
}
