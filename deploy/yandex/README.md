# Деплой SPEC CRM в Яндекс Облако

## Примерная стоимость

### Минимальная конфигурация (1 VM, все сервисы)

| Ресурс | Конфигурация | Цена/мес |
|--------|-------------|----------|
| VM compute.standard-v3 | 4 vCPU / 8 GB RAM / 80 GB SSD | ~4 200 ₽ |
| Статический внешний IP | - | ~130 ₽ |
| Исходящий трафик ~50 GB | - | ~150 ₽ |
| **ИТОГО** | | **~4 480 ₽/мес (~$47)** |

### Рекомендуемая продакшн-конфигурация (отдельные managed-сервисы)

| Ресурс | Конфигурация | Цена/мес |
|--------|-------------|----------|
| VM для приложения | 4 vCPU / 8 GB / 80 GB SSD | ~4 200 ₽ |
| Managed PostgreSQL | s2.micro: 2 vCPU / 8 GB / 40 GB | ~3 800 ₽ |
| Managed Redis | hm1.nano: 2 vCPU / 8 GB | ~2 400 ₽ |
| Object Storage (MinIO → YOS) | 50 GB | ~200 ₽ |
| Статический IP | - | ~130 ₽ |
| **ИТОГО** | | **~10 730 ₽/мес (~$115)** |

> Точная стоимость: https://cloud.yandex.ru/prices  
> Можно сэкономить ~30% используя прерываемые (preemptible) VM.

---

## Быстрый старт

### 1. Установите yc CLI (один раз)

```powershell
# От имени администратора PowerShell:
iex (New-Object System.Net.WebClient).DownloadString('https://storage.yandexcloud.net/yandexcloud-yc/install.ps1')
# Перезапустите PowerShell, затем:
yc init
```

### 2. Настройте DNS

Перед запуском скрипта убедитесь что у вас есть домен.  
Добавьте A-запись: `crm.example.ru → <IP сервера>` (IP будет известен после создания VM).

Либо сначала запустите скрипт без SSL — он создаст самоподписанный сертификат,  
а после настройки DNS запустите `.\deploy.ps1 -Update` для получения настоящего.

### 3. Первый деплой

```powershell
cd c:\projects\CRM\deploy\yandex
.\deploy.ps1
```

Скрипт спросит:
- Домен (например `crm.mycompany.ru`)
- Folder ID (найдёте в консоли Яндекс Облако)
- Email для Let's Encrypt
- API ключи (OpenAI, Telegram — опционально)
- Все пароли сгенерируются автоматически

Первый деплой занимает **15-20 минут**.

### 4. Обновление после изменения кода

```powershell
.\deploy.ps1 -Update
```

Синхронизирует файлы, пересобирает только изменившиеся образы, перезапускает контейнеры, выполняет миграции.

### 5. Только миграции

```powershell
.\deploy.ps1 -MigrateOnly
```

### 6. Удаление всех ресурсов

```powershell
.\deploy.ps1 -Destroy
```

---

## Структура файлов деплоя

```
deploy/yandex/
├── deploy.ps1              ← главный скрипт
├── docker-compose.prod.yml ← продакшн overrides
├── nginx-prod.conf         ← nginx с SSL
├── .deploy-config.json     ← сохранённая конфигурация и пароли (в .gitignore!)
└── README.md               ← эта документация
```

## Что происходит при деплое

```
1. Проверка зависимостей (yc CLI, ssh, scp)
2. Генерация SSH-ключа (~/.ssh/yc-crm-key)
3. Создание VPC-сети и подсети
4. Создание группы безопасности (порты 22, 80, 443)
5. Создание VM Ubuntu 22.04 с cloud-init (устанавливает Docker)
6. Архивирование проекта (без node_modules, __pycache__)
7. Загрузка архива на VM (SCP)
8. Генерация продакшн .env с уникальными паролями
9. Получение SSL-сертификата Let's Encrypt
10. docker compose up --build (сборка ~10-15 мин при первом запуске)
11. Миграции БД (alembic upgrade head)
12. Настройка автообновления SSL (cron)
```

## После деплоя

| Сервис | URL |
|--------|-----|
| CRM | `https://crm.example.ru` |
| Keycloak Admin | `https://crm.example.ru/keycloak/admin` |
| MinIO Console | `https://crm.example.ru/minio-console` |
| API Docs | `https://crm.example.ru/api/docs` |

**Пароли** хранятся в `deploy/yandex/.deploy-config.json` — добавьте этот файл в `.gitignore`!

## Мониторинг на сервере

```bash
ssh -i ~/.ssh/yc-crm-key ubuntu@<IP>

# Статус контейнеров
cd /opt/crm && docker compose ps

# Логи
docker compose logs -f backend
docker compose logs -f frontend

# Перезапуск одного сервиса
docker compose restart backend

# Полный перезапуск
docker compose -f docker-compose.yml -f deploy/yandex/docker-compose.prod.yml up -d
```

## Резервное копирование

```bash
# На сервере — бэкап PostgreSQL:
docker compose exec postgres pg_dump -U hvac_admin hvac_crm > backup_$(date +%Y%m%d).sql

# Скачать на Windows:
scp -i ~/.ssh/yc-crm-key ubuntu@<IP>:/opt/crm/backup_*.sql .
```
