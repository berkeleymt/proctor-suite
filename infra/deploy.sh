#!/usr/bin/env bash
# Usage: infra/deploy.sh [--rollback | --restart]
# Pulls main, builds on this machine, restarts, checks health.
# Nothing deploys automatically; a human runs this.
# Schema changes (invariant 10): Alembic runs below, from here and never on app startup.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_env

HISTORY="$INFRA_DIR/.deploy-history"
cd "$REPO_DIR"

case "${1:-}" in
  --restart)
    dc restart
    wait_healthy
    exit 0
    ;;
  --rollback)
    if [ ! -f "$HISTORY" ] || [ "$(wc -l <"$HISTORY")" -lt 2 ]; then
      echo "ERROR: no previous deploy recorded." >&2
      exit 1
    fi
    TARGET="$(tail -n 2 "$HISTORY" | head -n 1)"
    echo "Rolling back to $TARGET"
    git checkout --detach "$TARGET"
    ;;
  "")
    git fetch origin main
    git checkout --detach origin/main
    ;;
  *)
    echo "Unknown option: $1" >&2
    exit 2
    ;;
esac

COMMIT="$(git rev-parse HEAD)"
echo "Deploying commit $COMMIT"

# Invariant 10: schema changes run here, once, before the new app starts. Never on app startup.
# Migrations are additive and forward-only, so --rollback to older code is safe.
dc build app
dc run --rm migrate

dc up -d --build --remove-orphans
wait_healthy
echo "$COMMIT" >>"$HISTORY"
echo "Deployed $COMMIT"
