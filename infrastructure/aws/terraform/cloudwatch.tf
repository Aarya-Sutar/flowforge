# One log group per service — the ECS agent ships each container's stdout
# here automatically (configured on each task definition in ecs.tf), which
# is exactly what carries the structured JSON logs from
# backend/app/core/logging.py (Phase 7) into CloudWatch: no separate log
# shipping agent needed, since the app already logs to stdout and ECS's
# awslogs driver does the rest.

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.project_name}/backend"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.project_name}/celery-worker"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${var.project_name}/frontend"
  retention_in_days = 14
}
