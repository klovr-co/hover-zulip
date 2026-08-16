output "instance_public_ip" {
  description = "Static public IPv4 address. Point the DNS A record for domain_name here."
  value       = aws_lightsail_static_ip.hover.ip_address
}

output "backup_bucket_name" {
  description = "Private S3 bucket for encrypted backup archives."
  value       = aws_s3_bucket.backups.bucket
}

output "backup_iam_user_name" {
  description = "IAM user for the server's backup-only S3 credentials. Create its access key manually; do not add it to Terraform state."
  value       = aws_iam_user.backup.name
}

output "github_actions_deploy_role_arn" {
  description = "OIDC role assumed by the app.hover.team GitHub Actions deployment workflow."
  value       = aws_iam_role.github_actions_deploy.arn
}
