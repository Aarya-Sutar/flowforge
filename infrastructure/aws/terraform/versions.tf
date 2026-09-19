terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # No backend block: state defaults to local. For real team use, configure
  # an S3 backend with DynamoDB locking here — deliberately not done in this
  # project (see docs/learning/PHASE_8_CLOUD_AWS.md) since it would require
  # a pre-existing S3 bucket/table this repo has no way to provision safely
  # from a fresh checkout, and this infrastructure has never actually been
  # applied to a real account.
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "flowforge"
      ManagedBy = "terraform"
    }
  }
}
