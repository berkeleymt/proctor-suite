#!/usr/bin/env bash
# Shared helpers. Sourced by bootstrap.sh and deploy.sh.

INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC2034  # used by deploy.sh
REPO_DIR="$(dirname "$INFRA_DIR")"

# Use sudo for docker only if the current user cannot talk to the daemon
# (right after bootstrap adds the user to the docker group).
if docker info >/dev/null 2>&1; then
  DOCKER=(docker)
else
  DOCKER=(sudo docker)
fi

dc() {
  "${DOCKER[@]}" compose --project-directory "$INFRA_DIR" "$@"
}

load_env() {
  # shellcheck disable=SC1091
  set -a && source "$INFRA_DIR/.env" && set +a
}

wait_healthy() {
  local tries=60
  echo "Waiting for https://${SITE_ADDRESS}/healthz (first start may take a minute while Caddy gets a certificate)..."
  for ((i = 1; i <= tries; i++)); do
    if curl -fsSk --max-time 3 --resolve "${SITE_ADDRESS}:443:127.0.0.1" \
      "https://${SITE_ADDRESS}/healthz" 2>/dev/null | grep -qx ok; then
      echo "healthz: ok"
      return 0
    fi
    sleep 2
  done
  echo "ERROR: /healthz did not answer ok. Check: docker compose -f $INFRA_DIR/docker-compose.yml logs --tail=50" >&2
  return 1
}
