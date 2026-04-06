#Requires -Version 5.1
<#
.SYNOPSIS
    Развёртывание SPEC CRM в Яндекс Облако.

.DESCRIPTION
    Первый запуск : создаёт всю инфраструктуру (VPC, SG, VM) и разворачивает приложение.
    Повторный запуск : синхронизирует файлы, пересобирает образы, перезапускает контейнеры,
                       выполняет миграции — обновление без простоя.

.PARAMETER Update
    Принудительно режим обновления (не создавать VM, только деплоить).

.PARAMETER MigrateOnly
    Только выполнить миграции БД на уже запущенной VM.

.PARAMETER Destroy
    ОПАСНО: удалить ВСЕ облачные ресурсы (VM, сеть, IP). Данные будут потеряны.

.EXAMPLE
    # Первый деплой:
    .\deploy.ps1

    # Обновление после изменения кода:
    .\deploy.ps1 -Update

    # Только миграции:
    .\deploy.ps1 -MigrateOnly
#>
[CmdletBinding()]
param(
    [switch]$Update,
    [switch]$MigrateOnly,
    [switch]$Destroy
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ─── Пути ──────────────────────────────────────────────────────────────────
$ROOT = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$DEPLOY_DIR   = $PSScriptRoot
$CONFIG_FILE  = Join-Path $DEPLOY_DIR ".deploy-config.json"
$SSH_KEY_NAME = "yc-crm-key"
$SSH_DIR      = Join-Path $env:USERPROFILE ".ssh"
$SSH_PRIV     = Join-Path $SSH_DIR $SSH_KEY_NAME
$SSH_PUB      = "$SSH_PRIV.pub"
$REMOTE_DIR   = "/opt/crm"
$REMOTE_USER  = "ubuntu"

# ─── Цвета ─────────────────────────────────────────────────────────────────
function hdr  { Write-Host "`n══════════════════════════════════════" -ForegroundColor DarkCyan
                Write-Host "  $args" -ForegroundColor Cyan
                Write-Host "══════════════════════════════════════" -ForegroundColor DarkCyan }
function ok   { Write-Host "  [OK]  $args" -ForegroundColor Green }
function warn { Write-Host "  [!]   $args" -ForegroundColor Yellow }
function info { Write-Host "  [>>]  $args" -ForegroundColor DarkGray }
function err  { Write-Host "  [ERR] $args" -ForegroundColor Red; exit 1 }
function ask  { param([string]$prompt,[string]$default="")
                $val = Read-Host "$prompt$(if($default){" [$default]"})"
                if ([string]::IsNullOrWhiteSpace($val)) { $default } else { $val } }
function askSecret { param([string]$prompt)
                $s = Read-Host -AsSecureString $prompt
                [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)) }

function NewPassword {
    $chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#%^&*'
    -join ((1..32) | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
}

# ─── Утилиты SSH/SCP ───────────────────────────────────────────────────────
function Ssh-Run {
    param([string]$host, [string]$cmd, [switch]$Silent)
    $args_ = @("-o","StrictHostKeyChecking=no","-o","ConnectTimeout=15",
               "-i",$SSH_PRIV, "$REMOTE_USER@$host", $cmd)
    if ($Silent) {
        & ssh @args_ 2>&1 | Out-Null
    } else {
        & ssh @args_
    }
    return $LASTEXITCODE
}

function Ssh-RunCheck {
    param([string]$host, [string]$cmd)
    $rc = Ssh-Run -host $host -cmd $cmd
    if ($rc -ne 0) { err "Команда на удалённом сервере завершилась с кодом $rc: $cmd" }
}

function Scp-Dir {
    param([string]$localPath, [string]$host, [string]$remotePath)
    info "Загрузка: $localPath → $remotePath"
    & scp -o "StrictHostKeyChecking=no" -o "ConnectTimeout=15" `
          -i $SSH_PRIV -r $localPath "$REMOTE_USER@${host}:$remotePath"
    if ($LASTEXITCODE -ne 0) { err "SCP завершился с ошибкой" }
}

function Scp-File {
    param([string]$localPath, [string]$host, [string]$remotePath)
    info "Загрузка файла: $localPath → $remotePath"
    & scp -o "StrictHostKeyChecking=no" -o "ConnectTimeout=15" `
          -i $SSH_PRIV $localPath "$REMOTE_USER@${host}:$remotePath"
    if ($LASTEXITCODE -ne 0) { err "SCP файла завершился с ошибкой" }
}

# ─── Генерация архива проекта (исключая dev-мусор) ─────────────────────────
function Create-ProjectArchive {
    $tmpDir = [System.IO.Path]::GetTempPath()
    $archive = Join-Path $tmpDir "crm-deploy.tar.gz"

    $exclude = @("node_modules",".next","__pycache__",".venv","venv","*.pyc",
                 ".git",".gitignore","*.log","dist","build",".pytest_cache",
                 ".mypy_cache",".ruff_cache","htmlcov",".coverage")

    # Собираем список файлов через robocopy во временную папку
    $stagingDir = Join-Path $tmpDir "crm-staging"
    if (Test-Path $stagingDir) { Remove-Item -Recurse -Force $stagingDir }
    New-Item -ItemType Directory -Force $stagingDir | Out-Null

    # Список папок для копирования
    $dirs = @("backend","frontend","docker","deploy")
    foreach ($d in $dirs) {
        $src = Join-Path $ROOT $d
        if (-not (Test-Path $src)) { continue }
        $dst = Join-Path $stagingDir $d
        $excludeArgs = $exclude | ForEach-Object { "/XD"; $_ } | Where-Object { $_ -notmatch '\.' }
        $excludeFileArgs = $exclude | Where-Object { $_ -match '\.' } | ForEach-Object { "/XF"; $_ }
        & robocopy $src $dst /E /NFL /NDL /NJH /NJS /nc /ns /np `
            /XD node_modules .next __pycache__ .venv venv .git .pytest_cache .mypy_cache .ruff_cache htmlcov dist build `
            /XF "*.pyc" "*.log" ".coverage" | Out-Null
    }

    # Корневые файлы
    foreach ($f in @("docker-compose.yml",".env.example","README.md")) {
        $src = Join-Path $ROOT $f
        if (Test-Path $src) { Copy-Item $src $stagingDir }
    }

    # Создаём tar.gz
    Push-Location $stagingDir
    try {
        & tar -czf $archive .
    } finally {
        Pop-Location
    }

    Remove-Item -Recurse -Force $stagingDir -ErrorAction SilentlyContinue
    return $archive
}

# ─── Конфигурация ─────────────────────────────────────────────────────────
function Load-Config {
    if (Test-Path $CONFIG_FILE) {
        return Get-Content $CONFIG_FILE -Raw | ConvertFrom-Json
    }
    return $null
}

function Save-Config([hashtable]$cfg) {
    $cfg | ConvertTo-Json -Depth 5 | Set-Content $CONFIG_FILE -Encoding UTF8
    ok "Конфигурация сохранена: $CONFIG_FILE"
}

function Get-Or-Create-Config {
    $existing = Load-Config
    if ($existing -and -not $Update -and -not $MigrateOnly) {
        $reuse = ask "Найдена существующая конфигурация. Использовать? (y/n)" "y"
        if ($reuse -eq "y") { return $existing }
    }

    hdr "НАСТРОЙКА ДЕПЛОЯ"
    Write-Host @"

Вам понадобится:
  1. Аккаунт Яндекс Облако: https://cloud.yandex.ru
  2. Установленный yc CLI: https://cloud.yandex.ru/docs/cli/quickstart
  3. Запущенный домен (DNS A-запись, направленная на IP сервера)

"@ -ForegroundColor Yellow

    $folderIdHint = ""
    try {
        $folderIdHint = (& yc config get folder-id 2>$null).Trim()
    } catch {}

    $cfg = [ordered]@{
        domain          = ask "Домен (например: crm.mycompany.ru)"
        yc_folder_id    = ask "Folder ID в Яндекс Облако" $folderIdHint
        yc_zone         = ask "Зона" "ru-central1-a"
        vm_name         = ask "Имя VM" "crm-prod"
        vm_cores        = ask "vCPU" "4"
        vm_memory_gb    = ask "ОЗУ (GB)" "8"
        vm_disk_gb      = ask "Диск (GB)" "80"
        vm_platform     = ask "Платформа" "standard-v3"
        email           = ask "Email для Let's Encrypt SSL"
        openai_api_key  = ask "OpenAI API Key (или Enter пропустить)" ""
        yandex_geo_key  = ask "Yandex Geocoder API Key (или Enter пропустить)" ""
        telegram_token  = ask "Telegram Bot Token (или Enter пропустить)" ""

        # Пароли — генерируются автоматически
        pg_password         = $(if ($existing.pg_password)     { $existing.pg_password }     else { NewPassword })
        minio_secret        = $(if ($existing.minio_secret)    { $existing.minio_secret }    else { NewPassword })
        kc_admin_password   = $(if ($existing.kc_admin_password){ $existing.kc_admin_password} else { NewPassword })
        kc_client_secret    = $(if ($existing.kc_client_secret){ $existing.kc_client_secret } else { NewPassword })
        secret_key          = $(if ($existing.secret_key)      { $existing.secret_key }      else { NewPassword })
        nextauth_secret     = $(if ($existing.nextauth_secret) { $existing.nextauth_secret }  else { NewPassword })

        vm_public_ip    = $(if ($existing.vm_public_ip) { $existing.vm_public_ip } else { "" })
        deployed        = $false
    }

    Save-Config $cfg
    return $cfg
}

# ─── Проверка зависимостей ─────────────────────────────────────────────────
function Check-Prerequisites {
    hdr "ПРОВЕРКА ЗАВИСИМОСТЕЙ"

    foreach ($tool in @("ssh","scp","tar","robocopy")) {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
            err "Не найдена утилита: $tool. Установите OpenSSH (Параметры → Приложения → Дополнительные компоненты → OpenSSH Client)"
        }
        ok $tool
    }

    if (-not (Get-Command "yc" -ErrorAction SilentlyContinue)) {
        Write-Host @"

  Установите Яндекс CLI:
    1. Откройте PowerShell от администратора
    2. Выполните: iex (New-Object System.Net.WebClient).DownloadString('https://storage.yandexcloud.net/yandexcloud-yc/install.ps1')
    3. Перезапустите PowerShell
    4. Выполните: yc init

"@ -ForegroundColor Yellow
        err "yc CLI не установлен"
    }
    ok "yc CLI"

    # Проверяем аутентификацию
    try {
        $null = & yc config get token 2>$null
        $profile = (& yc config profile get 2>$null)
        ok "YC авторизован: $profile"
    } catch {
        Write-Host "  Выполните: yc init" -ForegroundColor Yellow
        err "YC не авторизован. Выполните: yc init"
    }
}

# ─── SSH ключ ─────────────────────────────────────────────────────────────
function Ensure-SshKey {
    hdr "SSH КЛЮЧ"
    if (-not (Test-Path $SSH_PRIV)) {
        info "Генерация SSH ключа: $SSH_PRIV"
        New-Item -ItemType Directory -Force $SSH_DIR | Out-Null
        & ssh-keygen -t ed25519 -f $SSH_PRIV -N '""' -C "yc-crm-deploy"
        if ($LASTEXITCODE -ne 0) { err "Не удалось сгенерировать SSH ключ" }
        ok "SSH ключ создан"
    } else {
        ok "SSH ключ существует: $SSH_PRIV"
    }
    return Get-Content $SSH_PUB
}

# ─── Инфраструктура ────────────────────────────────────────────────────────
function Ensure-Network {
    param($cfg)
    hdr "СЕТЬ (VPC)"

    $netName  = "$($cfg.vm_name)-net"
    $subName  = "$($cfg.vm_name)-subnet"
    $zone     = $cfg.yc_zone
    $folderId = $cfg.yc_folder_id

    # Сеть
    $net = (& yc vpc network list --folder-id $folderId --format json | ConvertFrom-Json) |
           Where-Object { $_.name -eq $netName }
    if (-not $net) {
        info "Создание VPC сети: $netName"
        & yc vpc network create --name $netName --folder-id $folderId | Out-Null
        ok "Сеть создана: $netName"
    } else {
        ok "Сеть существует: $netName"
    }

    # Подсеть
    $sub = (& yc vpc subnet list --folder-id $folderId --format json | ConvertFrom-Json) |
           Where-Object { $_.name -eq $subName }
    if (-not $sub) {
        info "Создание подсети: $subName (10.10.0.0/24)"
        & yc vpc subnet create `
            --name $subName `
            --folder-id $folderId `
            --zone $zone `
            --range "10.10.0.0/24" `
            --network-name $netName | Out-Null
        ok "Подсеть создана"
    } else {
        ok "Подсеть существует: $subName"
    }

    return @{ netName=$netName; subName=$subName }
}

function Ensure-SecurityGroup {
    param($cfg, $netName)
    hdr "ГРУППА БЕЗОПАСНОСТИ"

    $sgName   = "$($cfg.vm_name)-sg"
    $folderId = $cfg.yc_folder_id

    $sg = (& yc vpc security-group list --folder-id $folderId --format json | ConvertFrom-Json) |
          Where-Object { $_.name -eq $sgName }
    if (-not $sg) {
        info "Создание группы безопасности: $sgName"
        & yc vpc security-group create `
            --name $sgName `
            --folder-id $folderId `
            --network-name $netName `
            --rule "direction=ingress,port=22,protocol=tcp,cidr=0.0.0.0/0" `
            --rule "direction=ingress,port=80,protocol=tcp,cidr=0.0.0.0/0" `
            --rule "direction=ingress,port=443,protocol=tcp,cidr=0.0.0.0/0" `
            --rule "direction=egress,port=any,protocol=any,cidr=0.0.0.0/0" | Out-Null
        ok "Группа безопасности создана"
    } else {
        ok "Группа безопасности существует: $sgName"
    }
    return $sgName
}

function Ensure-Vm {
    param($cfg, $subName, $sgName, $pubKey)
    hdr "ВИРТУАЛЬНАЯ МАШИНА"

    $vmName   = $cfg.vm_name
    $folderId = $cfg.yc_folder_id
    $zone     = $cfg.yc_zone

    $vm = (& yc compute instance list --folder-id $folderId --format json | ConvertFrom-Json) |
          Where-Object { $_.name -eq $vmName }

    if (-not $vm) {
        info "Создание VM: $vmName ($($cfg.vm_cores) vCPU / $($cfg.vm_memory_gb) GB / $($cfg.vm_disk_gb) GB SSD)"
        info "Это займёт 2-3 минуты..."

        # Cloud-init: устанавливаем Docker при первом запуске
        $cloudInit = @"
#cloud-config
users:
  - name: ubuntu
    groups: docker, sudo
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    shell: /bin/bash
    ssh_authorized_keys:
      - $pubKey

package_update: true
package_upgrade: false

packages:
  - curl
  - git
  - unzip
  - ca-certificates
  - gnupg
  - lsb-release

runcmd:
  - install -m 0755 -d /etc/apt/keyrings
  - curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  - chmod a+r /etc/apt/keyrings/docker.gpg
  - echo "deb [arch=`$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu `$(. /etc/os-release && echo `$VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
  - apt-get update -qq
  - apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  - systemctl enable docker
  - systemctl start docker
  - usermod -aG docker ubuntu
  - mkdir -p /opt/crm
  - chown ubuntu:ubuntu /opt/crm
  - touch /opt/crm/.cloud-init-done
"@
        $tmpCloudInit = [System.IO.Path]::GetTempFileName()
        $cloudInit | Set-Content $tmpCloudInit -Encoding UTF8

        $memBytes = [int]$cfg.vm_memory_gb * 1073741824

        & yc compute instance create `
            --name $vmName `
            --folder-id $folderId `
            --zone $zone `
            --platform-id $cfg.vm_platform `
            --cores $cfg.vm_cores `
            --memory $memBytes `
            --create-boot-disk "type=network-ssd,size=$($cfg.vm_disk_gb),image-family=ubuntu-2204-lts,image-folder-id=standard-images,auto-delete=true" `
            --network-interface "subnet-name=$subName,nat-ip-version=ipv4,security-group-ids=$(& yc vpc security-group list --folder-id $folderId --format json | ConvertFrom-Json | Where-Object { $_.name -eq $sgName } | Select-Object -ExpandProperty id)" `
            --metadata-from-file "user-data=$tmpCloudInit" `
            --preemptible | Out-Null

        Remove-Item $tmpCloudInit -Force

        ok "VM создана: $vmName"

        # Ждём NAT IP
        info "Получение публичного IP..."
        $retries = 0
        do {
            Start-Sleep 5
            $vm = (& yc compute instance list --folder-id $folderId --format json | ConvertFrom-Json) |
                  Where-Object { $_.name -eq $vmName }
            $ip = $vm.network_interfaces[0].primary_v4_address.one_to_one_nat.address
            $retries++
        } while ((-not $ip) -and $retries -lt 30)

        if (-not $ip) { err "Не удалось получить публичный IP за 150 секунд" }
        ok "Публичный IP: $ip"
        return $ip
    } else {
        $ip = $vm.network_interfaces[0].primary_v4_address.one_to_one_nat.address
        ok "VM уже существует: $vmName, IP: $ip"
        return $ip
    }
}

# ─── Ожидание готовности VM ────────────────────────────────────────────────
function Wait-VmReady {
    param([string]$ip)
    hdr "ОЖИДАНИЕ ГОТОВНОСТИ VM"
    info "Ждём SSH ($ip)..."
    $retries = 0
    while ($retries -lt 60) {
        $rc = Ssh-Run -host $ip -cmd "test -f /opt/crm/.cloud-init-done && echo ok" -Silent
        if ($rc -eq 0) { break }
        Write-Host "." -NoNewline
        Start-Sleep 5
        $retries++
    }
    Write-Host ""
    if ($retries -ge 60) { err "VM не отвечает за 5 минут" }
    ok "VM доступна"
}

# ─── Создание production .env ──────────────────────────────────────────────
function Build-ProdEnv {
    param($cfg)

    $domain  = $cfg.domain
    $kc_url  = "https://$domain/keycloak"

    return @"
# === АВТОСГЕНЕРИРОВАНО deploy.ps1 ===
# Не редактируйте вручную — используйте .deploy-config.json

OPENAI_API_KEY=$($cfg.openai_api_key)
OPENAI_MODEL=gpt-4o-mini
AI_ASSISTANT_MAX_TOOL_ROUNDS=24
YANDEX_GEOCODER_API_KEY=$($cfg.yandex_geo_key)
NEXT_PUBLIC_YANDEX_MAPS_API_KEY=$($cfg.yandex_geo_key)

# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=hvac_crm
POSTGRES_USER=hvac_admin
POSTGRES_PASSWORD=$($cfg.pg_password)
DATABASE_URL=postgresql+asyncpg://hvac_admin:$($cfg.pg_password)@postgres:5432/hvac_crm
DATABASE_URL_SYNC=postgresql://hvac_admin:$($cfg.pg_password)@postgres:5432/hvac_crm

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=$($cfg.minio_secret)
MINIO_HOST=minio
MINIO_PORT=9000
MINIO_CONSOLE_PORT=9001
MINIO_BUCKET=hvac-documents
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=$($cfg.minio_secret)

# Keycloak
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=$($cfg.kc_admin_password)
KEYCLOAK_HOST=keycloak
KEYCLOAK_PORT=8080
KEYCLOAK_REALM=hvac
KEYCLOAK_CLIENT_ID=hvac-backend
KEYCLOAK_CLIENT_SECRET=$($cfg.kc_client_secret)
KEYCLOAK_FRONTEND_CLIENT_ID=hvac-frontend
KEYCLOAK_URL=$kc_url
DOMAIN=$domain

# Backend
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
BACKEND_DEBUG=false
BACKEND_INTERNAL_URL=http://backend:8000
SECRET_KEY=$($cfg.secret_key)
CORS_ORIGINS=["https://$domain","https://$domain/keycloak"]

# MCP
MCP_HOST=0.0.0.0
MCP_PORT=8001

# Frontend
NEXT_PUBLIC_API_URL=
NEXT_PUBLIC_WS_URL=wss://$domain/ws
NEXT_PUBLIC_KEYCLOAK_URL=https://$domain
NEXT_PUBLIC_KEYCLOAK_REALM=hvac
NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=hvac-frontend
NEXT_PUBLIC_AVATAR_SERVICE_BASE_URL=https://api.dicebear.com/9.x/thumbs/svg
NEXT_PUBLIC_TASK_TIMELINE_HOUR_START=8
NEXT_PUBLIC_TASK_TIMELINE_HOUR_END=20
NEXTAUTH_URL=https://$domain
NEXTAUTH_SECRET=$($cfg.nextauth_secret)

# Telegram
TELEGRAM_BOT_TOKEN=$($cfg.telegram_token)
TELEGRAM_WEBHOOK_URL=

# App
APP_NAME=HVAC CRM/ERP Platform
APP_VERSION=0.1.0
LOG_LEVEL=INFO
BACKEND_DEBUG=false

# Scheduler (по умолчанию отключён)
TASK_SCHEDULER_ENABLED=false
TASK_SCHEDULER_CRON_MINUTE=0
TASK_SCHEDULER_CRON_HOUR=9
TASK_SCHEDULER_CRON_DAY_OF_MONTH=*
TASK_SCHEDULER_CRON_MONTH_OF_YEAR=*
TASK_SCHEDULER_CRON_DAY_OF_WEEK=1-5
TASK_SCHEDULER_OBSERVER_IDS=
TASK_SCHEDULER_CO_ASSIGNEE_IDS=
TASK_SCHEDULER_DEDUP_WINDOW_MINUTES=180
"@
}

# ─── Обновление Keycloak realm для продакшена ─────────────────────────────
function Build-ProdRealm {
    param($cfg)
    $domain = $cfg.domain
    $src = Get-Content (Join-Path $ROOT "docker\keycloak\hvac-realm.json") -Raw | ConvertFrom-Json

    # Обновляем redirectUris и webOrigins для продакшн домена
    foreach ($client in $src.clients) {
        if ($client.clientId -eq "hvac-frontend") {
            $client.redirectUris = @("https://$domain/*", "https://$domain/keycloak/*")
            $client.webOrigins   = @("https://$domain")
        }
    }
    # Убираем temporary у паролей
    foreach ($user in $src.users) {
        foreach ($cred in $user.credentials) {
            $cred.temporary = $false
        }
    }
    return $src | ConvertTo-Json -Depth 20
}

# ─── Синхронизация файлов ─────────────────────────────────────────────────
function Sync-ProjectFiles {
    param([string]$ip)
    hdr "СИНХРОНИЗАЦИЯ ФАЙЛОВ ПРОЕКТА"

    info "Создание архива проекта (исключая node_modules, __pycache__, .git)..."
    $archive = Create-ProjectArchive
    $archiveSize = (Get-Item $archive).Length / 1MB
    info "Архив: $([math]::Round($archiveSize, 1)) MB"

    Ssh-RunCheck $ip "mkdir -p $REMOTE_DIR"
    Scp-File $archive $ip "/tmp/crm-deploy.tar.gz"
    Ssh-RunCheck $ip "cd $REMOTE_DIR && tar -xzf /tmp/crm-deploy.tar.gz --strip-components=0 2>&1 && rm /tmp/crm-deploy.tar.gz"

    Remove-Item $archive -Force
    ok "Файлы синхронизированы"
}

# ─── Первый деплой ────────────────────────────────────────────────────────
function Deploy-App {
    param([string]$ip, $cfg)
    hdr "ДЕПЛОЙ ПРИЛОЖЕНИЯ"

    # Загрузка .env
    $envContent = Build-ProdEnv $cfg
    $tmpEnv = [System.IO.Path]::GetTempFileName()
    $envContent | Set-Content $tmpEnv -Encoding UTF8
    Scp-File $tmpEnv $ip "$REMOTE_DIR/.env"
    Remove-Item $tmpEnv -Force
    ok ".env загружен"

    # Keycloak realm с продакшн-доменом
    $realmJson = Build-ProdRealm $cfg
    $tmpRealm  = [System.IO.Path]::GetTempFileName()
    $realmJson | Set-Content $tmpRealm -Encoding UTF8
    Ssh-RunCheck $ip "mkdir -p $REMOTE_DIR/docker/keycloak"
    Scp-File $tmpRealm $ip "$REMOTE_DIR/docker/keycloak/hvac-realm.json"
    Remove-Item $tmpRealm -Force
    ok "Keycloak realm загружен (с продакшн доменом)"

    # nginx-prod.conf: подставляем домен
    $nginxConf = Get-Content (Join-Path $DEPLOY_DIR "nginx-prod.conf") -Raw
    $nginxConf = $nginxConf -replace '\$\{DOMAIN\}', $cfg.domain
    $tmpNginx  = [System.IO.Path]::GetTempFileName()
    $nginxConf | Set-Content $tmpNginx -Encoding UTF8
    Ssh-RunCheck $ip "mkdir -p $REMOTE_DIR/deploy/yandex"
    Scp-File $tmpNginx $ip "$REMOTE_DIR/deploy/yandex/nginx-prod.conf"
    Remove-Item $tmpNginx -Force
    ok "nginx.conf загружен"

    # Копируем docker-compose.prod.yml
    Scp-File (Join-Path $DEPLOY_DIR "docker-compose.prod.yml") $ip "$REMOTE_DIR/deploy/yandex/docker-compose.prod.yml"

    # Первый запуск: только nginx (HTTP) для получения SSL сертификата
    hdr "ПОЛУЧЕНИЕ SSL СЕРТИФИКАТА (Let's Encrypt)"
    $certbotCmd = @"
set -e
cd $REMOTE_DIR

# Запускаем временный nginx только для ACME challenge
docker run --rm -d --name nginx-tmp \
    -p 80:80 \
    -v /var/www/certbot:/var/www/certbot:rw \
    nginx:alpine sh -c "mkdir -p /var/www/certbot && nginx -g 'daemon off;' &
    printf 'server{listen 80;location /.well-known/acme-challenge/{root /var/www/certbot;}location /{return 200 ok;}}' > /etc/nginx/conf.d/default.conf && nginx -s reload && sleep 3600" 2>/dev/null || true

# Устанавливаем certbot
which certbot || (apt-get install -y certbot 2>/dev/null || (
    curl -sSL https://dl.eff.org/certbot-auto -o /usr/local/bin/certbot-auto
    chmod +x /usr/local/bin/certbot-auto
))

sleep 5
sudo certbot certonly --webroot \
    -w /var/www/certbot \
    -d $($cfg.domain) \
    --email $($cfg.email) \
    --agree-tos \
    --non-interactive \
    --no-eff-email 2>&1

docker stop nginx-tmp 2>/dev/null || true
echo "SSL_CERT_OK"
"@
    $rc = Ssh-Run $ip $certbotCmd
    if ($rc -ne 0) {
        warn "SSL сертификат не получен автоматически."
        warn "Убедитесь, что DNS-запись $($cfg.domain) → $ip настроена."
        warn "После настройки DNS выполните вручную на сервере:"
        warn "  sudo certbot certonly --webroot -w /var/www/certbot -d $($cfg.domain) --email $($cfg.email) --agree-tos --non-interactive"
        warn "Затем повторите: .\deploy.ps1 -Update"
        # Устанавливаем self-signed для первого запуска
        Ssh-RunCheck $ip @"
mkdir -p /etc/letsencrypt/live/$($cfg.domain)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/letsencrypt/live/$($cfg.domain)/privkey.pem \
    -out    /etc/letsencrypt/live/$($cfg.domain)/fullchain.pem \
    -subj "/CN=$($cfg.domain)" 2>/dev/null
echo "Self-signed cert created (temporary)"
"@
        warn "Создан самоподписанный сертификат (временно)"
    } else {
        ok "SSL сертификат получен"
    }

    # Запуск всех сервисов
    hdr "ЗАПУСК КОНТЕЙНЕРОВ"
    $composeCmd = "cd $REMOTE_DIR && docker compose -f docker-compose.yml -f deploy/yandex/docker-compose.prod.yml up -d --build 2>&1"
    info "Сборка и запуск контейнеров (первый запуск 10-15 минут)..."
    Ssh-RunCheck $ip $composeCmd
    ok "Контейнеры запущены"

    # Миграции
    Run-Migrations $ip

    # Cron для автообновления SSL
    Ssh-RunCheck $ip @"
(crontab -l 2>/dev/null | grep -v certbot; echo "0 3 * * * certbot renew --webroot -w /var/www/certbot --quiet && cd $REMOTE_DIR && docker compose -f docker-compose.yml -f deploy/yandex/docker-compose.prod.yml restart nginx") | crontab -
echo "Certbot cron configured"
"@
    ok "Автообновление SSL настроено"
}

# ─── Обновление ────────────────────────────────────────────────────────────
function Update-App {
    param([string]$ip, $cfg)
    hdr "ОБНОВЛЕНИЕ ПРИЛОЖЕНИЯ"

    # Синхронизируем файлы
    Sync-ProjectFiles $ip

    # Обновляем .env (без смены паролей)
    $envContent = Build-ProdEnv $cfg
    $tmpEnv = [System.IO.Path]::GetTempFileName()
    $envContent | Set-Content $tmpEnv -Encoding UTF8
    Scp-File $tmpEnv $ip "$REMOTE_DIR/.env"
    Remove-Item $tmpEnv -Force
    ok ".env обновлён"

    # Обновляем nginx conf
    $nginxConf = Get-Content (Join-Path $DEPLOY_DIR "nginx-prod.conf") -Raw
    $nginxConf = $nginxConf -replace '\$\{DOMAIN\}', $cfg.domain
    $tmpNginx  = [System.IO.Path]::GetTempFileName()
    $nginxConf | Set-Content $tmpNginx -Encoding UTF8
    Scp-File $tmpNginx $ip "$REMOTE_DIR/deploy/yandex/nginx-prod.conf"
    Remove-Item $tmpNginx -Force

    Scp-File (Join-Path $DEPLOY_DIR "docker-compose.prod.yml") $ip "$REMOTE_DIR/deploy/yandex/docker-compose.prod.yml"

    # Пересборка и перезапуск
    info "Пересборка изменённых образов и перезапуск..."
    Ssh-RunCheck $ip "cd $REMOTE_DIR && docker compose -f docker-compose.yml -f deploy/yandex/docker-compose.prod.yml up -d --build 2>&1"
    ok "Контейнеры обновлены"

    # Миграции
    Run-Migrations $ip
}

# ─── Миграции ──────────────────────────────────────────────────────────────
function Run-Migrations {
    param([string]$ip)
    hdr "МИГРАЦИИ БД"
    info "Ожидание готовности postgres..."
    Start-Sleep 10
    $rc = Ssh-Run $ip "cd $REMOTE_DIR && docker compose -f docker-compose.yml -f deploy/yandex/docker-compose.prod.yml exec -T backend alembic upgrade head 2>&1"
    if ($rc -ne 0) {
        warn "alembic upgrade head вернул код $rc. Это нормально если нет Alembic миграций."
        warn "Схема создаётся автоматически в режиме DEBUG или через CREATE_ALL."
    } else {
        ok "Миграции выполнены"
    }
}

# ─── Удаление ресурсов ─────────────────────────────────────────────────────
function Destroy-Infrastructure {
    param($cfg)
    hdr "УДАЛЕНИЕ ИНФРАСТРУКТУРЫ"
    $confirm = ask "ВЫ УВЕРЕНЫ? Все данные будут потеряны! Введите 'DELETE' для подтверждения"
    if ($confirm -ne "DELETE") { err "Отменено." }

    $folderId = $cfg.yc_folder_id
    $vmName   = $cfg.vm_name

    # Удаляем VM
    $vm = (& yc compute instance list --folder-id $folderId --format json | ConvertFrom-Json) |
          Where-Object { $_.name -eq $vmName }
    if ($vm) {
        info "Удаление VM: $vmName"
        & yc compute instance delete --name $vmName --folder-id $folderId | Out-Null
        ok "VM удалена"
    }

    # Удаляем подсеть
    $subName = "$vmName-subnet"
    $sub = (& yc vpc subnet list --folder-id $folderId --format json | ConvertFrom-Json) |
           Where-Object { $_.name -eq $subName }
    if ($sub) {
        info "Удаление подсети: $subName"
        & yc vpc subnet delete --name $subName --folder-id $folderId | Out-Null
        ok "Подсеть удалена"
    }

    # Удаляем SG
    $sgName = "$vmName-sg"
    $sg = (& yc vpc security-group list --folder-id $folderId --format json | ConvertFrom-Json) |
          Where-Object { $_.name -eq $sgName }
    if ($sg) {
        info "Удаление группы безопасности: $sgName"
        & yc vpc security-group delete --name $sgName --folder-id $folderId | Out-Null
        ok "Группа безопасности удалена"
    }

    # Удаляем сеть
    $netName = "$vmName-net"
    $net = (& yc vpc network list --folder-id $folderId --format json | ConvertFrom-Json) |
           Where-Object { $_.name -eq $netName }
    if ($net) {
        info "Удаление сети: $netName"
        & yc vpc network delete --name $netName --folder-id $folderId | Out-Null
        ok "Сеть удалена"
    }

    # Удаляем конфиг
    if (Test-Path $CONFIG_FILE) { Remove-Item $CONFIG_FILE -Force }
    ok "Все ресурсы удалены"
}

# ─── Итоговая информация ──────────────────────────────────────────────────
function Show-Summary {
    param([string]$ip, $cfg)

    $kc_pass = $cfg.kc_admin_password

    Write-Host @"

╔══════════════════════════════════════════════════════════════════╗
║                  ДЕПЛОЙ УСПЕШНО ЗАВЕРШЁН                         ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Приложение:     https://$($cfg.domain.PadRight(37))║
║  VM (SSH):       ssh -i ~/.ssh/$SSH_KEY_NAME ubuntu@$($ip.PadRight(16))║
║  IP сервера:     $($ip.PadRight(49))║
║                                                                  ║
║  KEYCLOAK ADMIN:                                                 ║
║    URL:          https://$($cfg.domain)/keycloak/admin          ║
║    Логин:        admin                                           ║
║    Пароль:       $($kc_pass.Substring(0, [Math]::Min(20,$kc_pass.Length)) + '...') ║
║                                                                  ║
║  MinIO Console:  https://$($cfg.domain)/minio-console           ║
║                                                                  ║
║  Конфиг сохранён: deploy/yandex/.deploy-config.json             ║
║  Пароли БД см. там же (держите в безопасности!)                 ║
║                                                                  ║
║  ОБНОВЛЕНИЕ: запустите .\deploy.ps1 -Update                     ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Green

    # Стоимость
    Write-Host @"

  ПРИМЕРНАЯ СТОИМОСТЬ (compute.standard-v3):
  ┌────────────────────────────────────────────────┐
  │  VM $($cfg.vm_cores) vCPU / $($cfg.vm_memory_gb) GB / $($cfg.vm_disk_gb) GB SSD  ≈  4 200 руб/мес   │
  │  Статический IP                     ≈    130 руб/мес   │
  │  Трафик ~50 GB исходящий            ≈    150 руб/мес   │
  │  ─────────────────────────────────────────────  │
  │  ИТОГО                              ≈  4 480 руб/мес   │
  │  (~`$47/мес по курсу)                           │
  └────────────────────────────────────────────────┘
  Точная стоимость: https://cloud.yandex.ru/prices

"@ -ForegroundColor DarkYellow
}

# ─── ТОЧКА ВХОДА ──────────────────────────────────────────────────────────
Write-Host @"

  ╔══════════════════════════════════════════╗
  ║      SPEC CRM — Деплой в Яндекс Облако   ║
  ╚══════════════════════════════════════════╝
"@ -ForegroundColor Cyan

try {
    if ($Destroy) {
        $cfg = Load-Config
        if (-not $cfg) { err "Конфигурация не найдена. Нечего удалять." }
        Destroy-Infrastructure $cfg
        exit 0
    }

    Check-Prerequisites
    $pubKey = Ensure-SshKey
    $cfg = Get-Or-Create-Config

    if ($MigrateOnly) {
        $ip = $cfg.vm_public_ip
        if (-not $ip) { err "IP сервера не найден в конфиге. Запустите полный деплой." }
        Run-Migrations $ip
        exit 0
    }

    $isUpdate = $Update -or ($cfg.deployed -eq $true)

    if (-not $isUpdate) {
        # Первый деплой: создаём инфраструктуру
        $net = Ensure-Network $cfg
        $sg  = Ensure-SecurityGroup $cfg $net.netName
        $ip  = Ensure-Vm $cfg $net.subName $sg $pubKey
        $cfg.vm_public_ip = $ip
        $cfg.deployed = $true
        Save-Config $cfg
    } else {
        $ip = $cfg.vm_public_ip
        if (-not $ip) { err "IP не найден в конфиге. Удалите .deploy-config.json и запустите заново." }
        ok "Режим обновления, IP: $ip"
    }

    Wait-VmReady $ip
    Sync-ProjectFiles $ip

    if (-not $isUpdate) {
        Deploy-App $ip $cfg
    } else {
        Update-App $ip $cfg
    }

    Show-Summary $ip $cfg

} catch {
    Write-Host "`n  [ОШИБКА] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "  $($_.ScriptStackTrace)" -ForegroundColor DarkRed
    exit 1
}
