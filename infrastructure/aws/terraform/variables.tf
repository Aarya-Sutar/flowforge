variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix used for naming every resource this configuration creates."
  type        = string
  default     = "flowforge"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zone_count" {
  description = "How many AZs to spread subnets across. 2 is the minimum for an ALB and for RDS/ElastiCache subnet groups, which both require at least two."
  type        = number
  default     = 2
}

variable "backend_image" {
  description = "Full ECR image URI (including tag) for the backend/celery-worker image — they share the same image, same as docker-compose.yml. Set by CI after building and pushing (Phase 9), not committed here."
  type        = string
  default     = ""
}

variable "frontend_image" {
  description = "Full ECR image URI (including tag) for the frontend image."
  type        = string
  default     = ""
}

variable "backend_cpu" {
  description = "Fargate task CPU units for the backend service (1024 = 1 vCPU). Kept small deliberately — see cost notes in docs/learning/PHASE_8_CLOUD_AWS.md."
  type        = number
  default     = 256
}

variable "backend_memory" {
  description = "Fargate task memory (MiB) for the backend service."
  type        = number
  default     = 512
}

variable "worker_cpu" {
  description = "Fargate task CPU units for the celery-worker service."
  type        = number
  default     = 256
}

variable "worker_memory" {
  description = "Fargate task memory (MiB) for the celery-worker service."
  type        = number
  default     = 512
}

variable "frontend_cpu" {
  description = "Fargate task CPU units for the frontend service."
  type        = number
  default     = 256
}

variable "frontend_memory" {
  description = "Fargate task memory (MiB) for the frontend service."
  type        = number
  default     = 512
}

variable "backend_desired_count" {
  description = "Number of backend API tasks to run. 1 by default — this is a demo/portfolio deployment, not a scaled production one; see the learning doc for how this would change under real load."
  type        = number
  default     = 1
}

variable "worker_desired_count" {
  description = "Number of celery-worker tasks to run."
  type        = number
  default     = 1
}

variable "frontend_desired_count" {
  description = "Number of frontend tasks to run."
  type        = number
  default     = 1
}

variable "db_instance_class" {
  description = "RDS instance class. db.t4g.micro is the smallest ARM-based Postgres-compatible class — appropriate for a demo, not for real production load."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage_gb" {
  description = "RDS allocated storage in GB."
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Postgres database name."
  type        = string
  default     = "flowforge"
}

variable "db_username" {
  description = "Postgres master username."
  type        = string
  default     = "flowforge"
}

variable "redis_node_type" {
  description = "ElastiCache node type. cache.t4g.micro is the smallest — same demo-scale reasoning as the RDS instance class."
  type        = string
  default     = "cache.t4g.micro"
}

variable "ai_provider" {
  description = "Which AI provider the celery-worker uses (mock/ollama/openai) — see backend/app/ai/factory.py. Defaults to mock so a deployment never accidentally incurs LLM API costs without an explicit choice."
  type        = string
  default     = "mock"
}

variable "openai_api_key" {
  description = "Only used if ai_provider = \"openai\". Left empty by default; pass via -var or a .tfvars file that is never committed (see .gitignore)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "cors_origins" {
  description = "JSON array string of allowed CORS origins for the backend, e.g. the ALB's or a real domain's URL once known."
  type        = string
  default     = "[]"
}
