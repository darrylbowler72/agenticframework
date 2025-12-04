# Application Load Balancer for ECS Services

# Security Group for ALB
resource "aws_security_group" "alb" {
  name        = "${var.environment}-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = var.vpc_id

  ingress {
    description = "Allow HTTP from VPC"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  ingress {
    description = "Allow HTTPS from VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  ingress {
    description = "Allow health checks from VPC"
    from_port   = 8000
    to_port     = 8002
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.environment}-alb-sg"
  }
}

# Application Load Balancer (internal, for VPC Link)
resource "aws_lb" "agents" {
  name               = "${var.environment}-agents-alb"
  internal           = true
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.private_subnet_ids

  enable_deletion_protection = false
  enable_http2              = true

  tags = {
    Name = "${var.environment}-agents-alb"
  }
}

# Target Groups for each agent
resource "aws_lb_target_group" "planner" {
  name        = "${var.environment}-planner-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = {
    Name = "${var.environment}-planner-tg"
  }
}

resource "aws_lb_target_group" "codegen" {
  name        = "${var.environment}-codegen-tg"
  port        = 8001
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = {
    Name = "${var.environment}-codegen-tg"
  }
}

resource "aws_lb_target_group" "remediation" {
  name        = "${var.environment}-remediation-tg"
  port        = 8002
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = {
    Name = "${var.environment}-remediation-tg"
  }
}

# ALB Listener - Default action (port 80)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.agents.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "fixed-response"

    fixed_response {
      content_type = "application/json"
      message_body = jsonencode({
        message = "DevOps Agentic Framework"
        version = "1.0.0"
      })
      status_code = "200"
    }
  }
}

# Listener Rules for routing to agents
resource "aws_lb_listener_rule" "planner_workflows" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.planner.arn
  }

  condition {
    path_pattern {
      values = ["/workflows", "/workflows/*", "/dev/workflows", "/dev/workflows/*"]
    }
  }
}

resource "aws_lb_listener_rule" "codegen" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 200

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.codegen.arn
  }

  condition {
    path_pattern {
      values = ["/generate", "/generate/*", "/dev/generate", "/dev/generate/*"]
    }
  }
}

resource "aws_lb_listener_rule" "remediation" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 300

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.remediation.arn
  }

  condition {
    path_pattern {
      values = ["/remediate", "/remediate/*", "/dev/remediate", "/dev/remediate/*"]
    }
  }
}

# Health check endpoints for each agent
resource "aws_lb_listener_rule" "planner_health" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 101

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.planner.arn
  }

  condition {
    path_pattern {
      values = ["/planner/health", "/dev/planner/health"]
    }
  }
}

resource "aws_lb_listener_rule" "codegen_health" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 201

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.codegen.arn
  }

  condition {
    path_pattern {
      values = ["/codegen/health", "/dev/codegen/health"]
    }
  }
}

resource "aws_lb_listener_rule" "remediation_health" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 301

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.remediation.arn
  }

  condition {
    path_pattern {
      values = ["/remediation/health", "/dev/remediation/health"]
    }
  }
}

# Update ECS task security group to allow traffic from ALB
resource "aws_security_group_rule" "ecs_from_alb" {
  type                     = "ingress"
  from_port                = 8000
  to_port                  = 8002
  protocol                 = "tcp"
  security_group_id        = aws_security_group.ecs_tasks.id
  source_security_group_id = aws_security_group.alb.id
  description              = "Allow traffic from ALB"
}

# Outputs
output "alb_arn" {
  description = "ARN of the Application Load Balancer"
  value       = aws_lb.agents.arn
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.agents.dns_name
}

output "alb_listener_arn" {
  description = "ARN of the ALB HTTP listener"
  value       = aws_lb_listener.http.arn
}

output "target_group_arns" {
  description = "ARNs of target groups"
  value = {
    planner     = aws_lb_target_group.planner.arn
    codegen     = aws_lb_target_group.codegen.arn
    remediation = aws_lb_target_group.remediation.arn
  }
}

output "alb_security_group_id" {
  description = "ALB security group ID"
  value       = aws_security_group.alb.id
}
