terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  # Pin this deployment to the Klovr account rather than relying on the
  # machine's mutable default AWS CLI profile.
  profile = "klovr"
  region  = var.aws_region

  default_tags {
    tags = {
      Application = "hover"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
