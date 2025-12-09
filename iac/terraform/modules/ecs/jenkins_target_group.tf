# Jenkins Target Group and Listener Rules

resource "aws_lb_target_group" "jenkins" {
  name        = "${var.environment}-jenkins-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/login"
    protocol            = "HTTP"
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = {
    Name = "${var.environment}-jenkins-tg"
  }
}

# ALB Listener Rule for Jenkins root
resource "aws_lb_listener_rule" "jenkins_root" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.jenkins.arn
  }

  condition {
    path_pattern {
      values = ["/jenkins", "/jenkins/", "/dev/jenkins", "/dev/jenkins/"]
    }
  }
}

# ALB Listener Rule for Jenkins paths (wildcard)
resource "aws_lb_listener_rule" "jenkins_proxy" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 11

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.jenkins.arn
  }

  condition {
    path_pattern {
      values = ["/jenkins/*", "/dev/jenkins/*"]
    }
  }
}
