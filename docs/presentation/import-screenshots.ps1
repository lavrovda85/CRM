<#
.SYNOPSIS
  Copies up to 8 PNG screenshots from a folder into assets/slide-01.png … slide-08.png
  (sorted by file name). Then open index.html and print to PDF from the browser.

.PARAMETER SourceFolder
  Folder containing your PNG files (e.g. Desktop or Downloads).

.EXAMPLE
  .\import-screenshots.ps1 -SourceFolder "$env:USERPROFILE\Desktop\spec-screens"
#>
param(
    [Parameter(Mandatory = $true)]
    [string] $SourceFolder
)

$destDir = Join-Path $PSScriptRoot "assets"
if (-not (Test-Path $destDir)) {
    New-Item -ItemType Directory -Path $destDir | Out-Null
}

$files = Get-ChildItem -LiteralPath $SourceFolder -File -Filter "*.png" | Sort-Object Name
if ($files.Count -eq 0) {
    Write-Error "No PNG files in: $SourceFolder"
    exit 1
}

$n = [Math]::Min(8, $files.Count)
for ($i = 0; $i -lt $n; $i++) {
    $num = "{0:D2}" -f ($i + 1)
    $target = Join-Path $destDir "slide-$num.png"
    Copy-Item -LiteralPath $files[$i].FullName -Destination $target -Force
    Write-Host "OK: $($files[$i].Name) -> slide-$num.png"
}

if ($files.Count -gt 8) {
    Write-Warning "Only first 8 PNG files were used ($($files.Count) found)."
}

$html = Join-Path $PSScriptRoot "index.html"
Start-Process $html
Write-Host "Done. In the browser: Print -> Save as PDF -> Background graphics ON."
