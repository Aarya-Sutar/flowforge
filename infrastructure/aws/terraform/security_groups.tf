# Each security group only allows traffic from the specific thing that
# legitimately needs to reach it — never a broad CIDR — which is what
# actually enforces the "RDS/ElastiCache are private" claim in vpc.tf's
# comment: being in a subnet with no internet route stops inbound traffic
# from outside the VPC, but only the security group rules below stop
# something else *inside* the VPC (a misconfigured resource, a compromised
# task) from reaching the database directly.

resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb"
  description = "Allows inbound HTTP from the internet; the only thing here that should be internet-facing."
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-alb-sg" }
}

resource "aws_security_group" "ecs_tasks" {
  name        = "${var.project_name}-ecs-tasks"
  description = "Backend, celery-worker, and frontend Fargate tasks. Inbound only from the ALB, never directly from the internet."
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Backend API"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description     = "Frontend"
    from_port       = 3000
    to_port         = 3000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    # Needs outbound: pulling images from ECR, reaching RDS/ElastiCache,
    # and (for the worker) calling an AI provider over HTTPS.
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-ecs-tasks-sg" }
}

resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds"
  description = "PostgreSQL. Inbound only from the ECS tasks security group."
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Postgres from backend/worker tasks"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-rds-sg" }
}

resource "aws_security_group" "redis" {
  name        = "${var.project_name}-redis"
  description = "ElastiCache Redis. Inbound only from the ECS tasks security group."
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Redis from backend/worker tasks"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-redis-sg" }
}
