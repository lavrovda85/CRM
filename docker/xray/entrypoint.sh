#!/bin/sh
set -e

export XRAY_CONFIG_PATH="${XRAY_CONFIG_PATH:-/etc/xray/config.json}"
export XRAY_GATEWAY_ENV_PATH="${XRAY_GATEWAY_ENV_PATH:-/tmp/xray-gateway.env}"

python3 /opt/xray/render_openai_xray_config.py

if [ -f "${XRAY_GATEWAY_ENV_PATH}" ]; then
  # shellcheck disable=SC1090
  . "${XRAY_GATEWAY_ENV_PATH}"
  if [ "${XRAY_GATEWAY_RELAY}" = "socat" ]; then
    echo "Starting socat TCP relay ${XRAY_GATEWAY_LISTEN_PORT} -> ${XRAY_GATEWAY_DOWNSTREAM_ADDRESS}:${XRAY_GATEWAY_DOWNSTREAM_PORT}"
    socat "TCP-LISTEN:${XRAY_GATEWAY_LISTEN_PORT},fork,reuseaddr,bind=0.0.0.0" \
      "TCP4:${XRAY_GATEWAY_DOWNSTREAM_ADDRESS}:${XRAY_GATEWAY_DOWNSTREAM_PORT}" &
  fi
fi

exec /usr/local/bin/xray run -config "${XRAY_CONFIG_PATH}"
