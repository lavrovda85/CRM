#!/bin/sh
set -e
export XRAY_CONFIG_PATH="${XRAY_CONFIG_PATH:-/etc/xray/config.json}"
python3 /opt/xray/render_openai_xray_config.py
exec /usr/local/bin/xray run -config "${XRAY_CONFIG_PATH}"
