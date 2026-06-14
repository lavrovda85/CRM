cd /opt/crm   # или ваш DEPLOY_PATH
git pull --ff-only origin master
docker compose -f docker-compose.yml -f deploy/server/docker-compose.ip.yml build --parallel
docker compose -f docker-compose.yml -f deploy/server/docker-compose.ip.yml up -d --remove-orphans
docker compose restart nginx

Если `backend` не стартует: `docker compose logs backend --tail 100` и `docker compose ps`.
Частая причина — MinIO «unhealthy» (цепочка `depends_on`); после правки healthcheck пересоберите: `docker compose up -d --force-recreate minio backend`.

Если `backend` в статусе **unhealthy**, смотрите причину: `docker inspect crm-backend-1 --format '{{json .State.Health}}'`, руками: `docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=10).read())"`. После `git pull` пересоздайте backend: `docker compose -f docker-compose.yml -f deploy/server/docker-compose.ip.yml up -d --force-recreate backend`.

Для деплоя из фронта через удалённый SSH (пример `s@84.22.153.24:2222`) задайте в `.env`:
- `ADMIN_DEPLOY_ENABLED=true`
- `DEPLOY_AGENT_URL=http://deploy-agent:9090`
- `DEPLOY_SSH_HOST=84.22.153.24`
- `DEPLOY_SSH_PORT=2222`
- `DEPLOY_SSH_USER=s`
- `DEPLOY_SSH_REPO_PATH=/opt/crm`
- `DEPLOY_REMOTE_COMPOSE_FILE_MAIN=docker-compose.yml`
- `DEPLOY_REMOTE_COMPOSE_FILE_EXTRA=deploy/server/docker-compose.ip.yml`

Ключ можно перенести с хоста `s@192.168.1.89` и положить в `DEPLOY_SSH_KEY` как одну строку с `\n`:
`ssh -p 2222 s@84.22.153.24 "mkdir -p ~/.ssh && chmod 700 ~/.ssh" && ssh s@192.168.1.89 "cat ~/.ssh/id_ed25519"`.

### VPN gateway (xray-gateway)

Сервис `xray-gateway` слушает **443 на хосте** (`network_mode: host`). Порт должен быть свободен — `xray-openai` его не занимает.

```bash
docker compose -f docker-compose.yml -f deploy/server/docker-compose.ip.yml down xray-openai xray-gateway
sudo ss -tlnp | grep ':443'    # должно быть пусто
docker compose -f docker-compose.yml -f deploy/server/docker-compose.ip.yml up -d --build xray-gateway
docker compose -f docker-compose.yml -f deploy/server/docker-compose.ip.yml up -d xray-openai
docker compose logs xray-gateway --tail 5
```

Если `Address in use` — на 443 висит старый контейнер или другой процесс. Если 443 нужен nginx/другому сервису, в `.env` задайте `XRAY_GATEWAY_LISTEN_PORT=8443` и в клиентских VLESS-ссылках укажите `:8443`.