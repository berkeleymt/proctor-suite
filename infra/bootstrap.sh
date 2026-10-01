#!/usr/bin/env bash
# One-time setup on a fresh Ubuntu 24.04 EC2 box. Safe to re-run.
# Run as the normal user (ubuntu), not root:  bash ~/proctor-suite/infra/bootstrap.sh
set -euo pipefail
INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(id -u)" -eq 0 ]; then
  echo "Run as the ubuntu user, not root (use: sudo su - ubuntu)." >&2
  exit 1
fi

echo "== Docker =="
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER" || true

echo "== Swap =="
if [ "$(swapon --show --noheadings | wc -l)" -eq 0 ]; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "== infra/.env =="
if [ ! -f "$INFRA_DIR/.env" ]; then
  if [ -z "${SITE_ADDRESS:-}" ]; then
    TOKEN="$(curl -fsS -X PUT http://169.254.169.254/latest/api/token \
      -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')"
    IP="$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" \
      http://169.254.169.254/latest/meta-data/public-ipv4)"
    SITE_ADDRESS="${IP//./-}.sslip.io"
  fi
  umask 077
  {
    echo "SITE_ADDRESS=$SITE_ADDRESS"
    echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)"
  } >"$INFRA_DIR/.env"
  echo "Wrote infra/.env (SITE_ADDRESS=$SITE_ADDRESS)"
else
  echo "infra/.env already exists; leaving it alone."
fi

echo "== Port check =="
# shellcheck source=lib.sh
source "$INFRA_DIR/lib.sh"
if [ -z "$(dc ps -q 2>/dev/null)" ] && ss -ltn | awk '{print $4}' | grep -Eq ':(80|443)$'; then
  echo "ERROR: something else is already listening on port 80 or 443 (the old placeholder page?)." >&2
  echo "Find it:  sudo ss -ltnp | grep -E ':80 |:443 '" >&2
  echo "Stop it, then re-run this script." >&2
  exit 1
fi

echo "== Deploy =="
bash "$INFRA_DIR/deploy.sh"

load_env
echo
echo "Done. Open: https://${SITE_ADDRESS}/healthz"
