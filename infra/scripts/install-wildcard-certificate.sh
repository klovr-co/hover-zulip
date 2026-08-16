#!/usr/bin/env bash
# Install and automatically renew a Let's Encrypt wildcard certificate for the
# multi-realm Zulip host. Run from an operator workstation with AWS profile
# access and CLOUDFLARE_CERTBOT_API_TOKEN set; it never writes the token to git.
set -euo pipefail

: "${CLOUDFLARE_CERTBOT_API_TOKEN:?source ~/.config/zsh/cloudflare-certbot.env first}"

aws_profile="${AWS_PROFILE:-klovr}"
aws_region="${AWS_REGION:-ap-southeast-1}"
instance_name="${LIGHTSAIL_INSTANCE_NAME:-hover-production}"
instance_ip="${LIGHTSAIL_INSTANCE_IP:-46.137.250.101}"
domain_name="${ZULIP_DOMAIN_NAME:-app.hover.team}"
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
  --profile "$aws_profile" > "$work_dir/access.json"
jq -r '.accessDetails.privateKey' "$work_dir/access.json" > "$work_dir/lightsail-key"
jq -r '.accessDetails.certKey' "$work_dir/access.json" > "$work_dir/lightsail-key-cert.pub"
chmod 600 "$work_dir/lightsail-key" "$work_dir/lightsail-key-cert.pub"

ssh_options=(
  -o BatchMode=yes
  -o ConnectTimeout=30
  -o StrictHostKeyChecking=accept-new
  -o UserKnownHostsFile="$work_dir/known_hosts"
  -i "$work_dir/lightsail-key"
  -o CertificateFile="$work_dir/lightsail-key-cert.pub"
)

# A DNS-01 credential must be available for every renewal. The Cloudflare token
# has only DNS edit/read access for hover.team and is readable solely by root.
printf 'dns_cloudflare_api_token = %s\n' "$CLOUDFLARE_CERTBOT_API_TOKEN" \
  | ssh "${ssh_options[@]}" "ubuntu@$instance_ip" \
      'sudo install -d -m 700 /etc/letsencrypt && sudo tee /etc/letsencrypt/cloudflare-dns.ini >/dev/null && sudo chmod 600 /etc/letsencrypt/cloudflare-dns.ini'

ssh "${ssh_options[@]}" "ubuntu@$instance_ip" "sudo bash -s -- '$domain_name'" <<'REMOTE_SCRIPT'
set -euo pipefail
domain_name="$1"

apt-get update
apt-get install --yes certbot python3-certbot-dns-cloudflare

certificate_path="$(nginx -T 2>/dev/null | sed -n -E 's/^[[:space:]]*ssl_certificate[[:space:]]+([^;]+);/\1/p' | head -n 1)"
private_key_path="$(nginx -T 2>/dev/null | sed -n -E 's/^[[:space:]]*ssl_certificate_key[[:space:]]+([^;]+);/\1/p' | head -n 1)"
test -n "$certificate_path"
test -n "$private_key_path"

certbot certonly \
  --non-interactive \
  --agree-tos \
  --register-unsafely-without-email \
  --dns-cloudflare \
  --dns-cloudflare-credentials /etc/letsencrypt/cloudflare-dns.ini \
  --cert-name zulip-app-hover-team \
  --keep-until-expiring \
  -d "$domain_name" \
  -d "*.$domain_name"

install -d -m 755 /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/zulip-wildcard-certificate <<EOF
#!/bin/sh
set -eu
install -D -m 0644 "\$RENEWED_LINEAGE/fullchain.pem" "$certificate_path"
install -D -m 0600 "\$RENEWED_LINEAGE/privkey.pem" "$private_key_path"
nginx -t
systemctl reload nginx
EOF
chmod 700 /etc/letsencrypt/renewal-hooks/deploy/zulip-wildcard-certificate

RENEWED_LINEAGE="/etc/letsencrypt/live/zulip-app-hover-team" \
  /etc/letsencrypt/renewal-hooks/deploy/zulip-wildcard-certificate
REMOTE_SCRIPT

echo "Wildcard certificate installed for $domain_name and *.$domain_name."
