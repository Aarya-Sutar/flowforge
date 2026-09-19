# Lets GitHub Actions assume an AWS role directly, per-workflow-run, with no
# long-lived AWS access keys stored as GitHub secrets at all — the modern
# alternative to the old pattern of pasting an IAM user's static key/secret
# into repo secrets (which never expire and leak permanently if a workflow
# log or a compromised action ever exposes them). GitHub issues a short-lived
# OIDC token proving "this specific run, on this specific repo/branch, is
# real"; AWS trusts that token via the identity provider below and hands
# back temporary credentials, valid only for the run's duration.

variable "github_repository" {
  description = "owner/repo — restricts which GitHub repo is allowed to assume the deploy role."
  type        = string
  default     = "Aarya-Sutar/flowforge"
}

data "tls_certificate" "github_actions" {
  url = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
}

resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github_actions.certificates[0].sha1_fingerprint]
}

data "aws_iam_policy_document" "github_actions_assume_role" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Restricts this role to workflow runs triggered from this exact repo's
    # main branch — a pull request from a fork, or any other branch, cannot
    # assume this role. This is the actual access-control mechanism, not
    # just the OIDC trust relationship existing.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_actions_deploy" {
  name               = "${var.project_name}-github-actions-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role.json
}

data "aws_iam_policy_document" "github_actions_deploy_permissions" {
  statement {
    sid = "PushImages"
    actions = [
      "ecr:GetAuthorizationToken",
    ]
    resources = ["*"] # GetAuthorizationToken is account-wide by AWS's own design — it doesn't accept a resource scope
  }

  statement {
    sid = "PushImagesToFlowForgeRepos"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:PutImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
    ]
    resources = [aws_ecr_repository.backend.arn, aws_ecr_repository.frontend.arn]
  }

  statement {
    sid = "DeployToEcs"
    actions = [
      "ecs:DescribeServices",
      "ecs:DescribeTaskDefinition",
      "ecs:RegisterTaskDefinition",
      "ecs:UpdateService",
    ]
    resources = ["*"] # ECS's own resource-level permissions for these actions are limited; scoped instead by which cluster/service the workflow targets
  }

  statement {
    sid       = "PassEcsRoles"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.ecs_execution.arn, aws_iam_role.ecs_task.arn]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "github_actions_deploy" {
  name   = "${var.project_name}-github-actions-deploy"
  role   = aws_iam_role.github_actions_deploy.id
  policy = data.aws_iam_policy_document.github_actions_deploy_permissions.json
}

output "github_actions_deploy_role_arn" {
  description = "Set this as the AWS_DEPLOY_ROLE_ARN GitHub Actions secret (and set the AWS_DEPLOY_ENABLED repo variable to \"true\") once this infrastructure has actually been applied to a real account."
  value       = aws_iam_role.github_actions_deploy.arn
}
