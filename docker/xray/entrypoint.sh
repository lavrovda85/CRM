#!/bin/sh
set -e

export XRAY_CONFIG_PATH="${XRAY_CONFIG_PATH:-/etc/xray/config.json}"
export XRAY_GATEWAY_ENV_PATH="${XRAY_GATEWAY_ENV_PATH:-/tmp/xray-gateway.env}"

python3 /opt/xray/render_openai_xray_config.py

_gateway_only=false
case "${XRAY_GATEWAY_ONLY}" in
  1|true|TRUE|yes|YES|on|ON) _gateway_only=true ;;
esac

if [ -f "${XRAY_GATEWAY_ENV_PATH}" ] && [ "${_gateway_only}" = "true" ]; then
  # shellcheck disable=SC1090
  . "${XRAY_GATEWAY_ENV_PATH}"
  if [ "${XRAY_GATEWAY_RELAY}" = "socat" ]; then
    export XRAY_GATEWAY_LISTEN_PORT
    python3 /opt/xray/check_gateway_port.py
    _socat_listen="TCP-LISTEN:${XRAY_GATEWAY_LISTEN_PORT},fork,reuseaddr,keepalive,keepidle=30,keepintvl=10,keepcnt=3,bind=0.0.0.0"
    _socat_target="TCP4:${XRAY_GATEWAY_DOWNSTREAM_ADDRESS}:${XRAY_GATEWAY_DOWNSTREAM_PORT},keepalive,keepidle=30,keepintvl=10,keepcnt=3"
    echo "Starting socat TCP relay ${XRAY_GATEWAY_LISTEN_PORT} -> ${XRAY_GATEWAY_DOWNSTREAM_ADDRESS}:${XRAY_GATEWAY_DOWNSTREAM_PORT}"
    exec socat "${_socat_listen}" "${_socat_target}"
  fi
  exec /usr/local/bin/xray run -config "${XRAY_CONFIG_PATH}"
fi

exec /usr/local/bin/xray run -config "${XRAY_CONFIG_PATH}"
