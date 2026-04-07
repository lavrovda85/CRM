# Runs on the server with docker.sock + repo mount; not used for local dev unless explicitly enabled.
FROM alpine:3.20

RUN apk add --no-cache \
    docker-cli \
    docker-compose \
    git \
    openssh-client \
    bash \
    curl \
    python3

COPY docker/deploy-agent/deploy.sh /deploy.sh
COPY docker/deploy-agent/server.py /server.py
RUN chmod +x /deploy.sh

EXPOSE 9090

CMD ["python3", "/server.py"]
