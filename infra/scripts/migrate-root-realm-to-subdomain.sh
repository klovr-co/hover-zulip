#!/usr/bin/env bash
# Move the Zulip realm hosted at the root hostname to a subdomain, while
# retaining Zulip's deactivated redirect from the old realm URL.
set -euo pipefail

aws_profile="${AWS_PROFILE:-klovr}"
aws_region="${AWS_REGION:-ap-southeast-1}"
instance_name="${LIGHTSAIL_INSTANCE_NAME:-hover-production}"
instance_ip="${LIGHTSAIL_INSTANCE_IP:-46.137.250.101}"
new_subdomain="${1:?usage: $0 <new-subdomain>}"
work_dir="$(mktemp -d)"

cleanup() {
    aws lightsail close-instance-public-ports \
        --instance-name "$instance_name" \
        --port-info fromPort=22,toPort=22,protocol=tcp \
        --region "$aws_region" \
        --profile "$aws_profile" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
}
trap cleanup EXIT

aws lightsail open-instance-public-ports \
    --instance-name "$instance_name" \
    --port-info fromPort=22,toPort=22,protocol=tcp,cidrs=0.0.0.0/0 \
    --region "$aws_region" \
    --profile "$aws_profile" >/dev/null

aws lightsail get-instance-access-details \
    --instance-name "$instance_name" \
    --protocol ssh \
    --region "$aws_region" \
    --profile "$aws_profile" >"$work_dir/access.json"
jq -r '.accessDetails.privateKey' "$work_dir/access.json" >"$work_dir/lightsail-key"
jq -r '.accessDetails.certKey' "$work_dir/access.json" >"$work_dir/lightsail-key-cert.pub"
chmod 600 "$work_dir/lightsail-key" "$work_dir/lightsail-key-cert.pub"

ssh_options=(
    -o BatchMode=yes
    -o ConnectTimeout=30
    -o StrictHostKeyChecking=accept-new
    -o UserKnownHostsFile="$work_dir/known_hosts"
    -i "$work_dir/lightsail-key"
    -o CertificateFile="$work_dir/lightsail-key-cert.pub"
)

# The local subdomain is intentionally passed as the remote script's $1.
# shellcheck disable=SC2029
ssh "${ssh_options[@]}" "ubuntu@$instance_ip" "sudo bash -s -- '$new_subdomain'" <<'REMOTE_SCRIPT'
set -euo pipefail
new_subdomain="$1"
manage=/home/zulip/deployments/current/manage.py

echo 'Current realms:'
sudo -u zulip "$manage" list_realms

backup_path="/home/zulip/realm-url-migration-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
sudo -u zulip "$manage" backup --output="$backup_path"
test -s "$backup_path"
echo "Backup written to $backup_path"

sudo -u zulip "$manage" change_realm_subdomain --realm '' "$new_subdomain"

echo 'Realms after migration:'
sudo -u zulip "$manage" list_realms
sudo -u zulip "$manage" check
REMOTE_SCRIPT

echo "Root realm migrated to $new_subdomain.app.hover.team"
