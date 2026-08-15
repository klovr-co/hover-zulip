# AWS Singapore starter deployment

This Terraform configuration provisions the low-cost, single-host Hover production deployment at `app.hover.team`:

```text
Internet -> Lightsail Ubuntu 24.04 host -> local PostgreSQL, Redis, RabbitMQ
                                         -> encrypted private S3 backup bucket
```

It deliberately does **not** create Kubernetes, RDS, an ALB, NAT gateways, or
managed Redis/RabbitMQ. The Lightsail `medium_3_0` bundle provides 2 vCPU, 4
GiB RAM, 80 GiB SSD, a static IPv4 address, and included transfer. It is
appropriate for a pilot or small customer, not a high-availability/SLA-backed
deployment.

There is intentionally no always-on preview or staging environment. Until
there are active users and a need to test releases separately, `app.hover.team`
is the only deployed environment.

## Estimated recurring cost

| Item | Expected monthly cost |
| --- | ---: |
| Lightsail 4 GiB bundle | $24 |
| S3 backup storage and requests | $1-5 initially |
| Route 53 hosted zone | ~$0.50 |
| Domain and email | Provider dependent |
| **AWS total** | **~$26-35 before domain/email** |

Do not choose the 2 GiB bundle. The upstream production requirements specify
2 GiB only as a minimum and recommend 4 GiB for an installation with 25 or
more daily active users.

## Provision

1. Configure AWS credentials for an account whose billing alarm is already
   enabled.
2. Copy the example variables file and replace the placeholder SSH CIDR:

   ```sh
   cp terraform.tfvars.example terraform.tfvars
   ```

3. Review the exact changes and apply them:

   ```sh
   terraform init
   terraform plan
   terraform apply
   ```

4. Create an `A` record for `app.hover.team` at the DNS provider that manages
   `hover.team`, using the `instance_public_ip` output. Do this before running
   the Zulip installer: its Certbot step verifies that DNS points to this host.
5. In IAM, create an access key for the emitted `backup_iam_user_name` and
   install it only on the server as the backup user. Do **not** create that key
   in Terraform: Terraform state would contain its secret.

## Install the application

SSH to the generated public IP only after DNS has propagated. Follow the
repository's supported single-server installer using this repository/branch;
it configures PostgreSQL, Redis, RabbitMQ, Django, Tornado and workers on the
same dedicated host. Use Certbot with the hostname from `domain_name`.

After installation, configure a daily `manage.py backup` job to write its
archive under `backups/` in the S3 bucket. The bucket policy permits only that
prefix. Test a restore before inviting users.

## Continuous deployment

`.github/workflows/deploy-app-hover-team.yml` deploys every push to `main`.
It uses GitHub OIDC and the `github_actions_deploy_role_arn` Terraform output,
so no AWS access key is stored in GitHub. The workflow creates a Git bundle for
the exact pushed commit and installs it via Zulip's supported
`upgrade-zulip-from-git --local-ref` workflow.

Lightsail does not offer private runner networking for this small single-host
setup. During a deployment, the workflow opens TCP/22 only long enough to use
an AWS-issued, short-lived Lightsail SSH certificate, and closes the port in
an `always` cleanup step. TCP/80 and TCP/443 remain the only persistent public
ports.

## Upgrade path

1. Upgrade the Lightsail bundle to 8 GiB if memory pressure occurs.
2. Move PostgreSQL to RDS Single-AZ when a failed host must not risk database
   recovery time.
3. Add an ALB and a second app host for application availability.
4. Enable RDS Multi-AZ only when the contract requires database failover.

## State

This starter configuration uses local Terraform state to avoid creating a
second always-on dependency. Keep the state encrypted in a restricted team
password manager or private storage. Before a second operator or production
change workflow is introduced, migrate state to a dedicated encrypted S3
Terraform-state bucket with locking.
