<#
.SYNOPSIS
  Publishes a local HTTP service through Cloudflare Tunnel (quick URL or named tunnel).

.DESCRIPTION
  - Quick mode (default): no Cloudflare account config; prints a random *.trycloudflare.com URL.
  - Token mode: set CLOUDFLARE_TUNNEL_TOKEN (Zero Trust tunnel token) for a stable hostname.

  Typical CRM stack: nginx on port 80 (see repo docker-compose) so API + frontend + Keycloak paths work.

.PARAMETER Port
  Local port to expose (default 80).

.PARAMETER Quick
  Force quick tunnel even if CLOUDFLARE_TUNNEL_TOKEN is set.

.PARAMETER Config
  Path to cloudflared config YAML for `tunnel run` (optional).

.EXAMPLE
  .\start-tunnel.ps1
  # Quick tunnel to http://127.0.0.1:80

.EXAMPLE
  $env:CLOUDFLARE_TUNNEL_TOKEN = '<paste-from-dashboard>'
  .\start-tunnel.ps1 -Quick:$false
#>
[CmdletBinding()]
param(
    [int] $Port = 80,
    [switch] $Quick,
    [string] $Config = ""
)

$ErrorActionPreference = "Stop"

function Get-CloudflaredPath {
    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $local = Join-Path $PSScriptRoot "cloudflared.exe"
    if (Test-Path $local) { return $local }
    return $null
}

$exe = Get-CloudflaredPath
if (-not $exe) {
    Write-Host "cloudflared not found. Install, then re-run:" -ForegroundColor Yellow
    Write-Host "  winget install --id Cloudflare.cloudflared" -ForegroundColor Cyan
    Write-Host "Or download: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/" -ForegroundColor Cyan
    exit 1
}

$target = "http://127.0.0.1:$Port"
$token = [Environment]::GetEnvironmentVariable("CLOUDFLARE_TUNNEL_TOKEN", "Process")
if (-not $token) { $token = [Environment]::GetEnvironmentVariable("CLOUDFLARE_TUNNEL_TOKEN", "User") }

if ($Config -and (Test-Path $Config)) {
    Write-Host "Using config: $Config" -ForegroundColor Green
    & $exe tunnel --config $Config run
    exit $LASTEXITCODE
}

if (-not $Quick -and $token) {
    Write-Host "Named tunnel (token from CLOUDFLARE_TUNNEL_TOKEN) -> $target" -ForegroundColor Green
    & $exe tunnel run --token $token
    exit $LASTEXITCODE
}

Write-Host "Quick tunnel -> $target (share the https URL printed below; no stable hostname)." -ForegroundColor Green
Write-Host "For a fixed URL, create a tunnel in Cloudflare Zero Trust and set CLOUDFLARE_TUNNEL_TOKEN." -ForegroundColor DarkGray
& $exe tunnel --url $target
exit $LASTEXITCODE
