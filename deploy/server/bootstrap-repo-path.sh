#!/usr/bin/env bash
# First-time: clone repo into /opt/crm when the path is missing or empty.
#
# Do NOT use plain "sudo bash" with git@ URLs: root uses /root/.ssh (no key) → Permission denied.
# Either:
#   A) Public repo — HTTPS (works even as root):
#        sudo mkdir -p /opt/crm && sudo chown "$USER:$USER" /opt/crm
#        git clone https://github.com/lavrovda85/CRM.git /opt/crm
#   B) SSH URL — clone as your user (keys in ~/.ssh), directory must be yours:
#        sudo mkdir -p /opt && sudo chown "$USER:$USER" /opt
#        bash deploy/server/bootstrap-repo-path.sh /opt/crm git@github.com:lavrovda85/CRM.git
#
# This script: if run as root via sudo and URL is git@, re-runs git clone as SUDO_USER.
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
  echo "Error: ${DEST} exists and is not empty. Remove it first, e.g.: sudo rm -rf ${DEST}" >&2
  exit 1
fi

PARENT="$(dirname "$DEST")"
if [[ ! -d "$PARENT" ]]; then
  mkdir -p "$PARENT" 2>/dev/null || sudo mkdir -p "$PARENT"
fi

run_clone() {
  git clone "$REPO_URL" "$DEST"
}

if [[ "$(id -u)" -eq 0 ]]; then
  # Root: HTTPS needs no key; git@ needs keys under /root/.ssh OR clone as the sudo caller.
  if [[ "$REPO_URL" == git@* ]] || [[ "$REPO_URL" == ssh://* ]]; then
    if [[ -n "${SUDO_USER:-}" ]]; then
      echo "Cloning as user ${SUDO_USER} (uses ~${SUDO_USER}/.ssh for GitHub)."
      mkdir -p "$DEST"
      chown "${SUDO_USER}:${SUDO_USER}" "$DEST"
      sudo -u "$SUDO_USER" -H git clone "$REPO_URL" "$DEST"
    else
      echo "Error: SSH URL with root but no SUDO_USER." >&2
      echo "Add a key to /root/.ssh for GitHub, or use HTTPS:" >&2
      echo "  $0 $DEST https://github.com/lavrovda85/CRM.git" >&2
      exit 1
    fi
  else
    run_clone
    if [[ -n "${SUDO_USER:-}" ]] && [[ -d "$DEST" ]]; then
      chown -R "${SUDO_USER}:${SUDO_USER}" "$DEST"
    fi
  fi
else
  if [[ ! -w "$PARENT" ]]; then
    echo "Error: cannot write to ${PARENT}. Use: sudo chown -R $(id -un):$(id -gn) ${PARENT}" >&2
    exit 1
  fi
  mkdir -p "$DEST" 2>/dev/null || true
  rmdir "$DEST" 2>/dev/null || true
  run_clone
fi

if [[ ! -d "${DEST}/.git" ]]; then
  echo "Clone failed (check URL, repo visibility, and SSH deploy key on GitHub)." >&2
  exit 1
fi

echo "Cloned into ${DEST}"
echo "Next: cp ${DEST}/deploy/server/env.template.ip ${DEST}/.env && edit secrets"
echo "Then: bash ${DEST}/deploy/server/first-time-stack.sh ${DEST}"
