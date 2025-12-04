variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for VPC link"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for VPC link"
  type        = list(string)
}

variable "alb_listener_arn" {
  description = "ALB listener ARN for integration"
  type        = string
}

variable "alb_security_group_id" {
  description = "ALB security group ID"
  type        = string
}
