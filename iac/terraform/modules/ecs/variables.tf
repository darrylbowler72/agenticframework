variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs"
  type        = list(string)
}
variable "alb_dns_name" {
  description = "ALB DNS name for internal agent communication"
  type        = string
  default     = ""
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
  description = "Docker image version for migration agent"
  type        = string
  default     = "1.0.0"
}

variable "jenkins_image_version" {
  description = "Docker image version for Jenkins"
  type        = string
  default     = "1.0.1"
}
