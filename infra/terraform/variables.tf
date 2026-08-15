variable "aws_region" {
  description = "AWS Region for this deployment."
  type        = string
  default     = "ap-southeast-1"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "production"
}

variable "instance_name" {
  description = "Lightsail instance and static IP name."
  type        = string
  default     = "hover-production"
}

variable "domain_name" {
  description = "Public hostname for Hover, for example hover.example.com."
  type        = string
}

variable "administrator_email" {
  description = "Operations contact used by the Zulip installer and certificate renewal."
  type        = string
}

variable "release_tarball_url" {
  description = "HTTPS URL of the production Zulip/Hover release tarball installed during first boot."
  type        = string
  default     = "https://download.zulip.com/server/zulip-server-latest.tar.gz"
}

variable "ssh_allowed_cidrs" {
  description = "CIDR ranges permitted to use SSH. Replace the example value before applying."
  type        = list(string)
}

variable "backup_retention_days" {
  description = "Number of days to retain encrypted backup archives in S3."
  type        = number
  default     = 30
}
