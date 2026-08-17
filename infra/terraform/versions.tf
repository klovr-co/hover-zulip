terraform {
  required_version = ">= 1.5.0"

  # This bucket and lock table are bootstrapped outside Terraform so this
  # configuration can safely store and lock the state that manages them.
  backend "s3" {
    bucket         = "hover-production-terraform-state-991265479958"
    key            = "production/terraform.tfstate"
    region         = "ap-southeast-1"
    profile        = "klovr"
    encrypt        = true
    dynamodb_table = "hover-production-terraform-locks"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"
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

# Configure authentication using CLOUDFLARE_API_TOKEN rather than a Terraform
# variable so the token is never written to configuration or state.
provider "cloudflare" {}
