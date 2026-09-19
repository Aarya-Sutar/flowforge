output "alb_dns_name" {
  description = "Public URL for the deployed application (http://<this value>)."
  value       = aws_lb.main.dns_name
}

output "ecr_backend_repository_url" {
  description = "Push backend/celery-worker images here (docker tag/push target)."
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_repository_url" {
  description = "Push the frontend image here — build it with --build-arg NEXT_PUBLIC_API_URL=http://<alb_dns_name> AFTER the ALB exists (see the deployment runbook)."
  value       = aws_ecr_repository.frontend.repository_url
}

output "rds_endpoint" {
  description = "RDS connection endpoint (host:port) — private, only reachable from inside the VPC."
  value       = aws_db_instance.main.endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint — private, only reachable from inside the VPC."
  value       = aws_elasticache_cluster.main.cache_nodes[0].address
  sensitive   = true
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}
