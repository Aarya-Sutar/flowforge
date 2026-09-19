resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "disabled" # Container Insights bills per metric; left off for a demo deployment. Real production monitoring would enable it.
  }
}

locals {
  db_url_prefix = "postgresql+psycopg2://${var.db_username}"

  backend_environment = [
    { name = "CORS_ORIGINS", value = var.cors_origins },
  ]

  backend_secrets = [
    { name = "JWT_SECRET_KEY", valueFrom = aws_secretsmanager_secret.jwt_secret.arn },
  ]
}

# --- Backend API ---

resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project_name}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "backend"
      image = var.backend_image
      # Runs migrations before starting the server, same as docker-compose.yml.
      # With backend_desired_count > 1 this races across replicas — Alembic's
      # own locking mostly protects against corruption, but a real
      # multi-replica production setup should run migrations as a separate
      # one-off ECS task instead (see docs/learning/PHASE_8_CLOUD_AWS.md).
      command      = ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]

      environment = concat(local.backend_environment, [
        { name = "DATABASE_URL", value = "${local.db_url_prefix}:${random_password.db_password.result}@${aws_db_instance.main.address}:5432/${var.db_name}" },
        { name = "CELERY_BROKER_URL", value = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379/0" },
        { name = "CELERY_RESULT_BACKEND", value = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379/0" },
      ])
      secrets = local.backend_secrets

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "backend"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "backend" {
  name            = "${var.project_name}-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.backend_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http]
}

# --- Celery worker ---

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project_name}-celery-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name    = "celery-worker"
      image   = var.backend_image # same image as the backend, different command — matches docker-compose.yml
      command = ["celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info", "--concurrency=2"]

      environment = concat(
        [
          { name = "AI_PROVIDER", value = var.ai_provider },
          { name = "OPENAI_BASE_URL", value = "https://api.openai.com/v1" },
          { name = "OPENAI_MODEL", value = "gpt-4o-mini" },
        ],
        [
          { name = "DATABASE_URL", value = "${local.db_url_prefix}:${random_password.db_password.result}@${aws_db_instance.main.address}:5432/${var.db_name}" },
          { name = "CELERY_BROKER_URL", value = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379/0" },
          { name = "CELERY_RESULT_BACKEND", value = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379/0" },
        ]
      )
      secrets = concat(
        local.backend_secrets,
        length(aws_secretsmanager_secret.openai_api_key) > 0 ? [
          { name = "OPENAI_API_KEY", valueFrom = aws_secretsmanager_secret.openai_api_key[0].arn }
        ] : []
      )

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "worker" {
  name            = "${var.project_name}-celery-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }
  # No load_balancer block: the worker exposes nothing — it only ever pulls
  # from Redis, the same reason it has no ALB target group.
}

# --- Frontend ---

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.project_name}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.frontend_cpu
  memory                   = var.frontend_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name = "frontend"
      # NEXT_PUBLIC_API_URL is baked into this image at BUILD time (Phase 6
      # docs explain why: it's client-side JS, substituted before bundling)
      # — there is no runtime env var here that can change it. The image
      # referenced by var.frontend_image must already have been built with
      # the ALB's real DNS name (or domain). See the deployment runbook in
      # docs/learning/PHASE_8_CLOUD_AWS.md for the exact two-phase sequence
      # this requires (ALB must exist before the frontend image is built).
      image        = var.frontend_image
      portMappings = [{ containerPort = 3000, protocol = "tcp" }]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.frontend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "frontend"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "frontend" {
  name            = "${var.project_name}-frontend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = var.frontend_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 3000
  }

  depends_on = [aws_lb_listener.http]
}
