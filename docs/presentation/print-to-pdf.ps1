<#
.SYNOPSIS
  Opens the presentation HTML in the default browser for printing to PDF.

  In the browser: Ctrl+P -> Destination "Save as PDF" -> Margins "None" or "Minimum"
  -> enable "Background graphics" for correct colors.

.EXAMPLE
  .\print-to-pdf.ps1
#>
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$html = Join-Path $here "index.html"
if (-not (Test-Path $html)) {
    Write-Error "Missing index.html at $here"
    exit 1
}
Start-Process $html
