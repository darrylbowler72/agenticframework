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

variable "agent_image_version" {
  description = "Version tag for agent container images"
  type        = string
  default     = "latest"
}
