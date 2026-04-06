# Builds SPEC-CRM-presentation.pdf from index.html via Chrome headless.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $chrome)) {
    $chrome = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
}
$pdf = Join-Path $root "SPEC-CRM-presentation.pdf"
$htmlUrl = "file:///" + ($root -replace "\\", "/") + "/index.html"
& $chrome --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$pdf" --virtual-time-budget=15000 $htmlUrl
if (-not (Test-Path $pdf)) { throw "PDF was not created." }
Get-Item $pdf | Format-List FullName, Length, LastWriteTime
