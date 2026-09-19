# One repo per distinct image. Backend and celery-worker share the same
# image (same as docker-compose.yml's build context) — they're pushed to
# the same repo with different tags/uses if desired, matching how the
# local setup already treats them as "the same image, two commands."

resource "aws_ecr_repository" "backend" {
  name                 = "${var.project_name}-backend"
  image_tag_mutability = "IMMUTABLE" # a given tag (e.g. a git SHA) should never silently change what it points to

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "frontend" {
  name                 = "${var.project_name}-frontend"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name
  policy     = local.ecr_expire_untagged_policy
}

resource "aws_ecr_lifecycle_policy" "frontend" {
  repository = aws_ecr_repository.frontend.name
  policy     = local.ecr_expire_untagged_policy
}

locals {
  # Expires untagged images after 7 days — keeps storage cost from growing
  # unbounded from build cache layers/failed pushes, without touching
  # anything actually deployed (which is always tagged).
  ecr_expire_untagged_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
