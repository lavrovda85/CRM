#!/usr/bin/env bash
# First-time: clone repo into /opt/crm when the path is missing or empty.
#
# On the server:
#   sudo mkdir -p /opt && sudo chown "$USER:$USER" /opt
#   bash deploy/server/bootstrap-repo-path.sh /opt/crm
#
# Or with explicit URL (private repo: ssh URL + deploy key on server):
#   bash deploy/server/bootstrap-repo-path.sh /opt/crm git@github.com:lavrovda85/CRM.git
#
# Then:
#   cp /opt/crm/deploy/server/env.template.ip /opt/crm/.env
#   nano /opt/crm/.env
#   bash /opt/crm/deploy/server/first-time-stack.sh /opt/crm

set -euo pipefail

DEST="${1:-/opt/crm}"
REPO_URL="${2:-https://github.com/lavrovda85/CRM.git}"

if [[ -d "${DEST}/.git" ]]; then
  echo "Already a git repository: ${DEST}"
  exit 0
fi

if [[ -e "$DEST" ]] && [[ -n "$(ls -A "$DEST" 2>/dev/null)" ]]; then
  echo "Error: ${DEST} exists and is not empty. Remove contents or pick another path." >&2
  exit 1
fi

PARENT="$(dirname "$DEST")"
if [[ ! -d "$PARENT" ]]; then
  mkdir -p "$PARENT" 2>/dev/null || sudo mkdir -p "$PARENT"
fi
if [[ ! -w "$PARENT" ]] && command -v sudo >/dev/null 2>&1; then
  sudo mkdir -p "$DEST" 2>/dev/null || true
  sudo chown "$(id -un):$(id -gn)" "$DEST" 2>/dev/null || true
fi

git clone "$REPO_URL" "$DEST"

echo "Cloned into ${DEST}"
echo "Next: cp ${DEST}/deploy/server/env.template.ip ${DEST}/.env && edit secrets"
echo "Then: bash ${DEST}/deploy/server/first-time-stack.sh ${DEST}"
