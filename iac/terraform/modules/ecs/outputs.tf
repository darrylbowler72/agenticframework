output "cluster_id" {
  description = "ECS cluster ID"
  value       = aws_ecs_cluster.main.id
}

output "cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "cluster_arn" {
  description = "ECS cluster ARN"
  value       = aws_ecs_cluster.main.arn
}

output "task_execution_role_arn" {
  description = "ECS task execution role ARN"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "task_role_arn" {
  description = "ECS task role ARN"
  value       = aws_iam_role.ecs_task.arn
}

output "service_names" {
  description = "ECS service names"
  value       = { for k, v in aws_ecs_service.agents : k => v.name }
}

output "task_definition_arns" {
  description = "ECS task definition ARNs"
  value       = { for k, v in aws_ecs_task_definition.agents : k => v.arn }
}
