# OpenAI-only HTTP proxy sidecar: routes matching domains via VLESS+Reality, else direct.
# Build from repository root: docker compose build xray-openai
FROM alpine:3.20

ARG XRAY_VERSION=v26.3.27

RUN apk add --no-cache ca-certificates curl unzip python3 \
    && ARCH="$(uname -m)" \
    && case "$ARCH" in \
         x86_64) XARCH=64 ;; \
         aarch64) XARCH=arm64-v8a ;; \
         *) echo "unsupported arch: $ARCH" >&2; exit 1 ;; \
       esac \
    && curl -fsSL -o /tmp/xray.zip \
         "https://github.com/XTLS/Xray-core/releases/download/${XRAY_VERSION}/Xray-linux-${XARCH}.zip" \
    && unzip -q /tmp/xray.zip -d /tmp/xray \
    && install -m0755 /tmp/xray/xray /usr/local/bin/xray \
    && rm -rf /tmp/xray /tmp/xray.zip \
    && mkdir -p /usr/local/share/xray \
    && curl -fsSL -o /usr/local/share/xray/geosite.dat \
         "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat"

ENV XRAY_LOCATION_ASSET=/usr/local/share/xray

COPY docker/xray/render_openai_xray_config.py /opt/xray/
COPY backend/app/services/vless_uri.py /opt/xray/
COPY docker/xray/entrypoint.sh /entrypoint.sh
# Strip Windows CRLF so /bin/sh can run the script (BusyBox-safe; avoids "no such file or directory").
RUN tr -d '\015' < /entrypoint.sh > /tmp/entrypoint.sh && mv /tmp/entrypoint.sh /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 10808

ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
