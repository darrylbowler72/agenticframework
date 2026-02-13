variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "handler" {
  description = "Lambda function handler"
  type        = string
}

variable "runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.11"
}

variable "memory_size" {
  description = "Memory size in MB"
  type        = number
  default     = 1024
}

variable "timeout" {
  description = "Timeout in seconds"
  type        = number
  default     = 60
}

variable "source_code_path" {
  description = "Path to source code directory"
  type        = string
}

variable "vpc_subnet_ids" {
  description = "VPC subnet IDs"
  type        = list(string)
}

variable "vpc_sg_ids" {
  description = "VPC security group IDs"
  type        = list(string)
}

variable "environment_variables" {
  description = "Environment variables for Lambda"
  type        = map(string)
  default     = {}
}
