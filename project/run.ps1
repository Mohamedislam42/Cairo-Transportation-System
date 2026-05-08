# Always run the app from this folder so Flask loads templates/static here.
Set-Location $PSScriptRoot
# Override if needed: $env:TRANSPORT_LAB_PORT = "8742"; $env:TRANSPORT_LAB_HOST = "127.0.0.1"
if (-not $env:TRANSPORT_LAB_PORT) { $env:TRANSPORT_LAB_PORT = "5000" }
Write-Host "Serving Cairo Transport Lab from: $PSScriptRoot" -ForegroundColor Cyan
Write-Host "URL: http://127.0.0.1:$($env:TRANSPORT_LAB_PORT)/  (set TRANSPORT_LAB_PORT if port is busy)" -ForegroundColor DarkGray
py -3 app.py
