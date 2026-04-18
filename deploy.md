cd /opt/crm   # или ваш DEPLOY_PATH
git pull --ff-only origin master
docker compose -f docker-compose.yml -f deploy/server/docker-compose.ip.yml build --parallel
docker compose -f docker-compose.yml -f deploy/server/docker-compose.ip.yml up -d --remove-orphans
docker compose restart nginx

Если `backend` не стартует: `docker compose logs backend --tail 100` и `docker compose ps`.
Частая причина — MinIO «unhealthy» (цепочка `depends_on`); после правки healthcheck пересоберите: `docker compose up -d --force-recreate minio backend`.

Если `backend` в статусе **unhealthy**, смотрите причину: `docker inspect crm-backend-1 --format '{{json .State.Health}}'`, руками: `docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=10).read())"`. После `git pull` пересоздайте backend: `docker compose -f docker-compose.yml -f deploy/server/docker-compose.ip.yml up -d --force-recreate backend`.