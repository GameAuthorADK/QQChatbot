# Build a portable folder: .\dist\QQChatbot\
#
# Usage:
#   .\build.ps1              # keep config/data/logs in dist (safe upgrade)
#   .\build.ps1 -Fresh       # clean build, drop everything
#   .\build.ps1 -SkipTests
#
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads UTF-8
# without BOM as ANSI, and non-ASCII characters break the parser.

param(
    [switch]$SkipTests,
    [switch]$Fresh
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 0) refuse to rebuild while the app is running
$running = Get-Process -Name QQChatbot -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "QQChatbot is running (PID $($running.Id -join ',')). Close it first." -ForegroundColor Red
    exit 1
}

$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Missing venv. Run these first:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt"
    exit 1
}

# 1) tests
if (-not $SkipTests) {
    Write-Host "== tests ==" -ForegroundColor Cyan
    & $py -m unittest discover -s tests
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Tests failed." -ForegroundColor Red
        exit 1
    }
}

$dist = Join-Path $PSScriptRoot "dist\QQChatbot"
$preserve = @("config", "data", "logs", "runtime", "profiles", "plugins")

# 2) stash user data before PyInstaller wipes dist
$stash = Join-Path $env:TEMP ("qqbot_stash_" + [guid]::NewGuid().ToString("N").Substring(0, 8))
$hadStash = $false
if (-not $Fresh -and (Test-Path $dist)) {
    New-Item -ItemType Directory -Force -Path $stash | Out-Null
    foreach ($d in $preserve) {
        $src = Join-Path $dist $d
        if (Test-Path $src) {
            try {
                Move-Item $src (Join-Path $stash $d) -Force -ErrorAction Stop
                $hadStash = $true
            } catch {
                Write-Host ""
                Write-Host "Cannot move $d : a QQChatbot instance is probably running." -ForegroundColor Red
                Write-Host "Close it and run build again." -ForegroundColor Yellow
                # put back whatever was already moved
                if (Test-Path $stash) {
                    Get-ChildItem $stash | ForEach-Object {
                        Move-Item $_.FullName (Join-Path $dist $_.Name) -Force -ErrorAction SilentlyContinue
                    }
                    Remove-Item $stash -Recurse -Force -ErrorAction SilentlyContinue
                }
                exit 1
            }
        }
    }
    if ($hadStash) { Write-Host "Stashed user data -> $stash" -ForegroundColor DarkGray }
}

# 3) build
Write-Host "== pyinstaller ==" -ForegroundColor Cyan
& ".\.venv\Scripts\pyinstaller.exe" --noconfirm --clean --onedir --noconsole --name QQChatbot --hidden-import pystray --hidden-import pystray._win32 --hidden-import six --hidden-import six.moves --collect-submodules pystray entry.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed. User data is still at: $stash" -ForegroundColor Red
    exit 1
}

$root = (Resolve-Path $dist).Path

# 4) path budget
$max = 0
Get-ChildItem $root -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($root.Length)
    if ($rel.Length -gt $max) { $max = $rel.Length }
}
New-Item -ItemType Directory -Force -Path (Join-Path $dist "app") | Out-Null
@{
    max_rel_len = $max
    checked_at  = (Get-Date -Format "yyyy-MM-dd")
} | ConvertTo-Json | Set-Content (Join-Path $dist "app\path-budget.json") -Encoding UTF8

# 5) restore user data
foreach ($d in $preserve) {
    New-Item -ItemType Directory -Force -Path (Join-Path $dist $d) | Out-Null
}
if ($hadStash) {
    foreach ($d in $preserve) {
        $stashed = Join-Path $stash $d
        if (Test-Path $stashed) {
            $target = Join-Path $dist $d
            Remove-Item $target -Recurse -Force -ErrorAction SilentlyContinue
            Move-Item $stashed $target -Force
        }
    }
    Remove-Item $stash -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "User data restored." -ForegroundColor DarkGray
}

Copy-Item "README.txt" $dist -Force -ErrorAction SilentlyContinue

# 5b) bundled documentation (read by the in-app Help tab)
$docsDist = Join-Path $dist "docs"
if (Test-Path $docsDist) { Remove-Item $docsDist -Recurse -Force }
Copy-Item "docs" $docsDist -Recurse -Force

# retired built-in example: /lucky is now the fortune minigame
$legacyLucky = Join-Path $dist "plugins\lucky.py"
if (Test-Path $legacyLucky) {
    Remove-Item $legacyLucky -Force
    Write-Host "  removed legacy code plugin: lucky.py" -ForegroundColor DarkGray
}

# 6) sync bundled plugins
#    - YAML rule packs: always overwrite (built-in, versioned)
#    - root *.py code plugins: copy only when missing (keep user edits)
#    - plugins/trpg/*.py rule plugins: copy only when missing
$bundled = Join-Path $PSScriptRoot "plugins"
if (Test-Path $bundled) {
    Get-ChildItem $bundled -Directory | Where-Object { $_.Name -ne "trpg" -and $_.Name -ne "minigame" -and $_.Name -ne "modes" } | ForEach-Object {
        $target = Join-Path $dist ("plugins\" + $_.Name)
        if (Test-Path $target) { Remove-Item $target -Recurse -Force }
        Copy-Item $_.FullName $target -Recurse -Force
        Write-Host "  bundled plugin: $($_.Name)" -ForegroundColor DarkGray
    }

    Get-ChildItem $bundled -File -Filter *.py | ForEach-Object {
        $target = Join-Path $dist ("plugins\" + $_.Name)
        if (-not (Test-Path $target)) {
            Copy-Item $_.FullName $target -Force
            Write-Host "  bundled code plugin: $($_.Name)" -ForegroundColor DarkGray
        }
    }

    $trpgDist = Join-Path $dist "plugins\trpg"
    New-Item -ItemType Directory -Force -Path $trpgDist | Out-Null
    $trpgSrc = Join-Path $bundled "trpg"
    if (Test-Path $trpgSrc) {
        Get-ChildItem $trpgSrc -File -Filter *.py | ForEach-Object {
            $target = Join-Path $trpgDist $_.Name
            if (-not (Test-Path $target)) {
                Copy-Item $_.FullName $target -Force
                Write-Host "  bundled rule plugin: $($_.Name)" -ForegroundColor DarkGray
            }
        }
    }

    $gameDist = Join-Path $dist "plugins\minigame"
    New-Item -ItemType Directory -Force -Path $gameDist | Out-Null
    $gameSrc = Join-Path $bundled "minigame"
    if (Test-Path $gameSrc) {
        Get-ChildItem $gameSrc -File -Filter *.py | ForEach-Object {
            $target = Join-Path $gameDist $_.Name
            if (-not (Test-Path $target)) {
                Copy-Item $_.FullName $target -Force
                Write-Host "  bundled game plugin: $($_.Name)" -ForegroundColor DarkGray
            }
        }
    }

    $modeDist = Join-Path $dist "plugins\modes"
    New-Item -ItemType Directory -Force -Path $modeDist | Out-Null
    $modeSrc = Join-Path $bundled "modes"
    if (Test-Path $modeSrc) {
        Get-ChildItem $modeSrc -File -Filter *.py | ForEach-Object {
            $target = Join-Path $modeDist $_.Name
            if (-not (Test-Path $target)) {
                Copy-Item $_.FullName $target -Force
                Write-Host "  bundled mode plugin: $($_.Name)" -ForegroundColor DarkGray
            }
        }
    }
}

$size = [math]::Round(((Get-ChildItem $dist -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
$budget = 260 - $max - 10

Write-Host ""
Write-Host "Done: $dist" -ForegroundColor Green
Write-Host "  size        : $size MB"
Write-Host "  max_rel_len : $max"
Write-Host "  path budget : $budget chars"
