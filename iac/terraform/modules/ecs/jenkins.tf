# Jenkins ECS Task Definition and Service

# EFS File System for Jenkins persistent storage
resource "aws_efs_file_system" "jenkins" {
  creation_token = "${var.environment}-jenkins-efs"
  encrypted      = true

  tags = {
    Name = "${var.environment}-jenkins-efs"
  }
}

# EFS Access Point for Jenkins with proper permissions
resource "aws_efs_access_point" "jenkins" {
  file_system_id = aws_efs_file_system.jenkins.id

  posix_user {
    uid = 1000
    gid = 1000
  }

  root_directory {
    path = "/jenkins_home"
    creation_info {
      owner_uid   = 1000
      owner_gid   = 1000
      permissions = "755"
    }
  }

  tags = {
    Name = "${var.environment}-jenkins-access-point"
  }
}

# EFS Mount Targets (one per private subnet)
resource "aws_efs_mount_target" "jenkins" {
  count           = length(var.private_subnet_ids)
  file_system_id  = aws_efs_file_system.jenkins.id
  subnet_id       = var.private_subnet_ids[count.index]
  security_groups = [aws_security_group.jenkins_efs.id]
}

# Security Group for EFS
resource "aws_security_group" "jenkins_efs" {
  name        = "${var.environment}-jenkins-efs-sg"
  description = "Security group for Jenkins EFS mount targets"
  vpc_id      = var.vpc_id

  ingress {
    description = "Allow NFS from VPC"
    from_port   = 2049
    to_port     = 2049
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
    Name = "${var.environment}-jenkins-efs-sg"
  }
}

# Jenkins Task Definition
resource "aws_ecs_task_definition" "jenkins" {
  family                   = "${var.environment}-jenkins"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  volume {
    name = "jenkins-home"

    efs_volume_configuration {
      file_system_id          = aws_efs_file_system.jenkins.id
      transit_encryption      = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.jenkins.id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name      = "jenkins"
    image     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${data.aws_region.current.name}.amazonaws.com/jenkins-custom:${var.jenkins_image_version}"
    essential = true

    portMappings = [{
      containerPort = 8080
      hostPort      = 8080
      protocol      = "tcp"
    }]

    mountPoints = [{
      sourceVolume  = "jenkins-home"
      containerPath = "/var/jenkins_home"
      readOnly      = false
    }]

    environment = [
      {
        name  = "JENKINS_OPTS"
        value = "--prefix=/jenkins"
      },
      {
        name  = "JAVA_OPTS"
        value = "-Djenkins.install.runSetupWizard=false"
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "jenkins"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8080/jenkins/login || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 120
    }
  }])

  tags = {
    Name = "${var.environment}-jenkins"
  }
}

# Security Group for Jenkins (allows public access)
resource "aws_security_group" "jenkins" {
  name        = "${var.environment}-jenkins-sg"
  description = "Security group for Jenkins with public access"
  vpc_id      = var.vpc_id

  ingress {
    description = "Allow HTTP from anywhere"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Allow inbound from VPC"
    from_port   = 0
    to_port     = 65535
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
    Name = "${var.environment}-jenkins-sg"
  }
}

# ECS Service for Jenkins (in public subnet with public IP)
resource "aws_ecs_service" "jenkins" {
  name            = "${var.environment}-jenkins"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.jenkins.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [aws_security_group.jenkins.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.jenkins.arn
    container_name   = "jenkins"
    container_port   = 8080
  }

  enable_execute_command = true

  # Ensure ALB is created before the service
  depends_on = [aws_lb_listener.http]

  tags = {
    Name = "${var.environment}-jenkins-service"
  }
}
