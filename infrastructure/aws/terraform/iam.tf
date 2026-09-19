# Two distinct roles, on purpose — this is the actual "least privilege"
# mechanism, not just a policy statement:
#
# - Execution role: used by the ECS *agent* itself, before your code ever
#   runs, to pull the container image and fetch secrets to inject as env
#   vars. The application never sees these credentials.
# - Task role: used by *your running application code*, if it needs to call
#   any AWS API. FlowForge's app code doesn't call AWS APIs directly today
#   (it talks to Postgres/Redis via their normal wire protocols, not AWS
#   SDK calls) — so this role is intentionally near-empty. Giving it broad
#   permissions "just in case" would be exactly the kind of over-privileged
#   default the spec explicitly warns against.

data "aws_iam_policy_document" "ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${var.project_name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume_role.json
}

resource "aws_iam_role_policy_attachment" "ecs_execution_managed" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "ecs_execution_secrets" {
  statement {
    sid     = "ReadFlowForgeSecrets"
    actions = ["secretsmanager:GetSecretValue"]
    resources = compact([
      aws_secretsmanager_secret.db_password.arn,
      aws_secretsmanager_secret.jwt_secret.arn,
      length(aws_secretsmanager_secret.openai_api_key) > 0 ? aws_secretsmanager_secret.openai_api_key[0].arn : "",
    ])
  }
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name   = "${var.project_name}-ecs-execution-secrets"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.ecs_execution_secrets.json
}

resource "aws_iam_role" "ecs_task" {
  name               = "${var.project_name}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume_role.json
  # No policies attached: the running application currently makes zero AWS
  # API calls. Add scoped permissions here (and only here, never on the
  # execution role) if the app ever genuinely needs to call an AWS service.
}
