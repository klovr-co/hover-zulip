locals {
  backup_bucket_name = "${var.instance_name}-backups-${data.aws_caller_identity.current.account_id}"
}

data "aws_caller_identity" "current" {}

# GitHub Actions exchanges its short-lived OIDC token for this role.  The
# trust policy intentionally permits only deployments from this repository's
# main branch; no long-lived AWS credentials are stored in GitHub.
resource "aws_iam_openid_connect_provider" "github_actions" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_policy_document" "github_actions_deploy_assume_role" {
  statement {
    effect  = "Allow"
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

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:klovr-co/hover-zulip:*"]
    }
  }
}

resource "aws_iam_role" "github_actions_deploy" {
  name               = "${var.instance_name}-github-actions-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_actions_deploy_assume_role.json
}

resource "aws_iam_role_policy" "github_actions_deploy" {
  name = "${var.instance_name}-deploy-lightsail"
  role = aws_iam_role.github_actions_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DeployToThisLightsailInstance"
        Effect = "Allow"
        Action = [
          "lightsail:CloseInstancePublicPorts",
          "lightsail:GetInstance",
          "lightsail:GetInstanceAccessDetails",
          "lightsail:OpenInstancePublicPorts",
        ]
        Resource = "*"
      },
    ]
  })
}

resource "aws_lightsail_instance" "hover" {
  name              = var.instance_name
  availability_zone = "${var.aws_region}a"
  blueprint_id      = "ubuntu_24_04"
  bundle_id         = "medium_3_0" # 2 vCPU, 4 GiB RAM, 80 GiB SSD.
  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    administrator_email = var.administrator_email
    domain_name         = var.domain_name
    release_tarball_url = var.release_tarball_url
  })
}

resource "aws_lightsail_static_ip" "hover" {
  # Lightsail instances and static IPs share a single name namespace.
  name = "${var.instance_name}-ip"
}

resource "aws_lightsail_static_ip_attachment" "hover" {
  static_ip_name = aws_lightsail_static_ip.hover.name
  instance_name  = aws_lightsail_instance.hover.name
}

resource "aws_lightsail_instance_public_ports" "hover" {
  instance_name = aws_lightsail_instance.hover.name

  dynamic "port_info" {
    for_each = length(var.ssh_allowed_cidrs) == 0 ? [] : [true]

    content {
      protocol  = "tcp"
      from_port = 22
      to_port   = 22
      cidrs     = var.ssh_allowed_cidrs
    }
  }

  port_info {
    protocol  = "tcp"
    from_port = 80
    to_port   = 80
    cidrs     = ["0.0.0.0/0"]
  }

  port_info {
    protocol  = "tcp"
    from_port = 443
    to_port   = 443
    cidrs     = ["0.0.0.0/0"]
  }
}

resource "aws_s3_bucket" "backups" {
  bucket        = local.backup_bucket_name
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "backups" {
  bucket                  = aws_s3_bucket.backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "expire-old-backups"
    status = "Enabled"

    filter {
      prefix = "backups/"
    }

    expiration {
      days = var.backup_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}

resource "aws_iam_user" "backup" {
  name = "${var.instance_name}-backup"
}

resource "aws_iam_user_policy" "backup" {
  name = "${var.instance_name}-write-backups"
  user = aws_iam_user.backup.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListBackupBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.backups.arn
      },
      {
        Sid    = "WriteOnlyBackupPrefix"
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:DeleteObject",
          "s3:GetObject",
          "s3:PutObject",
        ]
        Resource = "${aws_s3_bucket.backups.arn}/backups/*"
      },
    ]
  })
}
