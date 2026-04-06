#!/usr/bin/env bash
# Clone CRM repo into /opt/crm (or set TARGET_DIR).
set -euo pipefail

TARGET_DIR="${TARGET_DIR:-/opt/crm}"
# Set one of: GIT_REPO_URL=git@github.com:org/crm.git  OR  GIT_REPO_URL=https://github.com/org/crm.git
: "${GIT_REPO_URL:?Set GIT_REPO_URL to your git remote}"

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run as normal user with sudo when needed; clone into ${TARGET_DIR} may need sudo mkdir."
fi

sudo mkdir -p "$(dirname "${TARGET_DIR}")"
if [[ -d "${TARGET_DIR}/.git" ]]; then
  echo "Already cloned: ${TARGET_DIR}"
  exit 0
fi

sudo git clone --branch master --depth 1 "${GIT_REPO_URL}" "${TARGET_DIR}"
sudo chown -R "$(whoami):$(whoami)" "${TARGET_DIR}" 2>/dev/null || true
echo "Cloned to ${TARGET_DIR}"
