# Run in dev mode (no packaging).
# Usage: .\run-dev.ps1
#        $env:QQBOT_NO_WINDOW=1; .\run-dev.ps1

Set-Location $PSScriptRoot
& ".\.venv\Scripts\python.exe" -m qqbot
