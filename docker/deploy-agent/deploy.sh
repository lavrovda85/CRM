#!/usr/bin/env bash
# Run on the host repo: build, apply schema, up, health check; rollback on failure.
set -euo pipefail

BRANCH="${1:?branch required}"
REPO="${DEPLOY_REPO_PATH:-/deploy/repo}"
LOG_DIR="${REPO}/.deploy"
mkdir -p "$LOG_DIR"
LOGFILE="${LOG_DIR}/last.log"
exec > >(tee -a "$LOGFILE") 2>&1

log() { echo "[$(date -Iseconds)] $*"; }

_dc() {
  local args=()
  if [[ -n "${COMPOSE_PROJECT_NAME:-}" ]]; then
    args+=(-p "$COMPOSE_PROJECT_NAME")
  fi
  args+=(-f "${DEPLOY_COMPOSE_FILE_MAIN:-docker-compose.yml}")
  if [[ -n "${DEPLOY_COMPOSE_FILE_EXTRA:-}" ]]; then
    args+=(-f "$DEPLOY_COMPOSE_FILE_EXTRA")
  fi
  docker-compose "${args[@]}" "$@"
}

rollback() {
  local prev="${1:-}"
  log "ROLLBACK requested, restoring ${prev:-unknown}"
  if [[ -z "$prev" ]]; then
    log "No previous SHA — cannot rollback automatically"
    return 1
  fi
  cd "$REPO"
  git checkout "$prev" || true
  _dc build || true
  _dc run --rm -T backend python -m app.cli.apply_schema || true
  _dc up -d || true
  log "Rollback deploy finished (verify health manually)"
}

if [[ -n "${GITHUB_SSH_KEY:-}" ]]; then
  mkdir -p /root/.ssh
  chmod 700 /root/.ssh
  printf '%s\n' "$GITHUB_SSH_KEY" | sed 's/\\n/\n/g' > /root/.ssh/id_ed25519
  chmod 600 /root/.ssh/id_ed25519
  export GIT_SSH_COMMAND='ssh -i /root/.ssh/id_ed25519 -o StrictHostKeyChecking=accept-new'
fi

cd "$REPO"

if [[ -n "${GITHUB_REPO_URL:-}" ]]; then
  git remote set-url origin "$GITHUB_REPO_URL" || git remote add origin "$GITHUB_REPO_URL"
fi

PREV="$(git rev-parse HEAD 2>/dev/null || echo "")"
log "DEPLOY_PREV_SHA=${PREV}"

git fetch origin
git checkout "$BRANCH"
git pull --ff-only "origin" "$BRANCH" || git pull "origin" "$BRANCH"

NEW="$(git rev-parse HEAD)"
log "DEPLOY_NEW_SHA=${NEW}"

HEALTH_URL="${DEPLOY_HEALTH_URL:-http://backend:8000/health}"

if ! _dc build; then
  log "docker compose build failed"
  rollback "$PREV"
  exit 1
fi

if ! _dc run --rm -T backend python -m app.cli.apply_schema; then
  log "apply_schema failed"
  rollback "$PREV"
  exit 1
fi

if ! _dc up -d; then
  log "docker compose up failed"
  rollback "$PREV"
  exit 1
fi

ok=0
for _ in $(seq 1 45); do
  if curl -sf --max-time 8 "$HEALTH_URL" >/dev/null; then
    ok=1
    break
  fi
  sleep 2
done

if [[ "$ok" -ne 1 ]]; then
  log "Health check failed: $HEALTH_URL"
  rollback "$PREV"
  exit 1
fi

log "Deploy success branch=$BRANCH sha=$NEW"
exit 0
