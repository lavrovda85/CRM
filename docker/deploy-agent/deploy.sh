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

_ssh_key_setup() {
  local key_raw="${1:-}"
  local key_file="${2:-/root/.ssh/id_ed25519}"
  if [[ -z "$key_raw" ]]; then
    return 0
  fi
  mkdir -p /root/.ssh
  chmod 700 /root/.ssh
  printf '%s\n' "$key_raw" | sed 's/\\n/\n/g' > "$key_file"
  chmod 600 "$key_file"
}

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

rollback_local() {
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
  _ssh_key_setup "${GITHUB_SSH_KEY:-}" "/root/.ssh/id_ed25519"
  export GIT_SSH_COMMAND='ssh -i /root/.ssh/id_ed25519 -o StrictHostKeyChecking=accept-new'
fi

REMOTE_HOST="${DEPLOY_SSH_HOST:-}"
if [[ -n "$REMOTE_HOST" ]]; then
  REMOTE_USER="${DEPLOY_SSH_USER:-s}"
  REMOTE_PORT="${DEPLOY_SSH_PORT:-22}"
  REMOTE_REPO="${DEPLOY_SSH_REPO_PATH:-/opt/crm}"
  REMOTE_MAIN="${DEPLOY_REMOTE_COMPOSE_FILE_MAIN:-docker-compose.yml}"
  REMOTE_EXTRA="${DEPLOY_REMOTE_COMPOSE_FILE_EXTRA:-deploy/server/docker-compose.ip.yml}"
  REMOTE_HEALTH="${DEPLOY_REMOTE_HEALTH_URL:-http://127.0.0.1:8000/health}"
  SSH_KEY_RAW="${DEPLOY_SSH_KEY:-${GITHUB_SSH_KEY:-}}"
  SSH_KEY_FILE="/root/.ssh/id_deploy_remote"
  if [[ -n "$SSH_KEY_RAW" ]]; then
    _ssh_key_setup "$SSH_KEY_RAW" "$SSH_KEY_FILE"
  fi
  SSH_OPTS=(
    -p "$REMOTE_PORT"
    -o StrictHostKeyChecking=accept-new
  )
  if [[ -f "$SSH_KEY_FILE" ]]; then
    SSH_OPTS+=(-i "$SSH_KEY_FILE")
  fi
  log "Running remote deploy via ssh ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PORT}"
  ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" \
    "BRANCH='${BRANCH}' REPO='${REMOTE_REPO}' MAIN='${REMOTE_MAIN}' EXTRA='${REMOTE_EXTRA}' HEALTH='${REMOTE_HEALTH}' GITHUB_REPO_URL='${GITHUB_REPO_URL:-}' bash -s" <<'REMOTE_EOF'
set -euo pipefail
log() { echo "[$(date -Iseconds)] $*"; }
cd "$REPO"
PREV="$(git rev-parse HEAD 2>/dev/null || echo "")"
log "DEPLOY_PREV_SHA=${PREV}"
if [[ -n "${GITHUB_REPO_URL:-}" ]]; then
  git remote set-url origin "$GITHUB_REPO_URL" || git remote add origin "$GITHUB_REPO_URL"
fi
git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH" || git pull origin "$BRANCH"
NEW="$(git rev-parse HEAD)"
log "DEPLOY_NEW_SHA=${NEW}"
docker compose -f "$MAIN" -f "$EXTRA" build --parallel
docker compose -f "$MAIN" -f "$EXTRA" up -d --remove-orphans
docker compose restart nginx || true
ok=0
for _ in $(seq 1 45); do
  if curl -sf --max-time 8 "$HEALTH" >/dev/null; then ok=1; break; fi
  sleep 2
done
if [[ "$ok" -ne 1 ]]; then
  log "Health check failed: $HEALTH"
  exit 1
fi
log "Deploy success branch=$BRANCH sha=$NEW"
REMOTE_EOF
  exit 0
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
  rollback_local "$PREV"
  exit 1
fi

if ! _dc run --rm -T backend python -m app.cli.apply_schema; then
  log "apply_schema failed"
  rollback_local "$PREV"
  exit 1
fi

if ! _dc up -d; then
  log "docker compose up failed"
  rollback_local "$PREV"
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
  rollback_local "$PREV"
  exit 1
fi

log "Deploy success branch=$BRANCH sha=$NEW"
exit 0
