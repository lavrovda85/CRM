cd /opt/crm   # или ваш DEPLOY_PATH
git pull --ff-only origin master
docker compose -f docker-compose.yml -f deploy/server/docker-compose.ip.yml build --parallel
docker compose -f docker-compose.yml -f deploy/server/docker-compose.ip.yml up -d --remove-orphans
$ docker compose restart nginx 