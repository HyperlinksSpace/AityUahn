# AityUahn backend installer — Windows PowerShell 5.1+ / PowerShell 7+
# Usage: irm https://raw.githubusercontent.com/HyperlinksSpace/AityUahn/main/scripts/install.ps1 | iex
# Optional: $env:AITYUAHN_INSTALL_DIR = "C:\AityUahn"; irm ... | iex

$ErrorActionPreference = "Stop"

$Repo = if ($env:AITYUAHN_REPO) { $env:AITYUAHN_REPO } else { "HyperlinksSpace/AityUahn" }
$Branch = if ($env:AITYUAHN_BRANCH) { $env:AITYUAHN_BRANCH } else { "main" }
$InstallDir = if ($env:AITYUAHN_INSTALL_DIR) { $env:AITYUAHN_INSTALL_DIR } else { Join-Path $env:USERPROFILE "AityUahn" }
$ZipUrl = "https://github.com/$Repo/archive/refs/heads/$Branch.zip"

function Write-Info($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "!!> $msg" -ForegroundColor Yellow }

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($ver in @("-3.12", "-3.11", "-3")) {
            & py $ver -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return @{ exe = "py"; args = @($ver) }
            }
        }
    }
    foreach ($name in @("python3", "python")) {
        if (Get-Command $name -ErrorAction SilentlyContinue) {
            & $name -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return @{ exe = $name; args = @() }
            }
        }
    }
    throw "Python 3.11+ is required. Install from https://www.python.org/downloads/ (check 'Add python.exe to PATH')."
}

function Invoke-Python([hashtable]$Py, [string[]]$ScriptArgs) {
    if ($Py.args.Count -gt 0) {
        & $Py.exe @($Py.args) @ScriptArgs
    } else {
        & $Py.exe @ScriptArgs
    }
    if ($LASTEXITCODE -ne 0) { throw "Python command failed (exit $LASTEXITCODE): $($Py.exe) $($Py.args -join ' ') $($ScriptArgs -join ' ')" }
}

function Get-RepoSource {
    if (Test-Path (Join-Path $InstallDir ".git")) {
        Write-Info "Updating existing install at $InstallDir"
        Push-Location $InstallDir
        try {
            git pull --ff-only origin $Branch 2>$null
        } catch {
            Write-Warn "git pull failed — continuing with existing files"
        } finally {
            Pop-Location
        }
        return
    }
    if ((Test-Path $InstallDir) -and (Get-ChildItem $InstallDir -Force | Select-Object -First 1)) {
        throw "Install directory exists and is not empty: $InstallDir (set `$env:AITYUAHN_INSTALL_DIR or remove it)"
    }

    $parent = Split-Path $InstallDir -Parent
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }

    if (Get-Command git -ErrorAction SilentlyContinue) {
        Write-Info "Cloning https://github.com/$Repo.git -> $InstallDir"
        git clone --depth 1 --branch $Branch "https://github.com/$Repo.git" $InstallDir
        return
    }

    Write-Info "Downloading ZIP (git not found) -> $InstallDir"
    $tmp = Join-Path $env:TEMP ("aityuahn-" + [guid]::NewGuid().ToString("n"))
    New-Item -ItemType Directory -Path $tmp -Force | Out-Null
    $zipPath = Join-Path $tmp "aityuahn.zip"
    try {
        Invoke-WebRequest -Uri $ZipUrl -OutFile $zipPath -UseBasicParsing
        Expand-Archive -Path $zipPath -DestinationPath $tmp -Force
        $extracted = Get-ChildItem $tmp -Directory | Where-Object { $_.Name -like "AityUahn*" } | Select-Object -First 1
        if (-not $extracted) { throw "Could not find extracted folder in ZIP" }
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
        Copy-Item -Path (Join-Path $extracted.FullName "*") -Destination $InstallDir -Recurse -Force
    } finally {
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Install-Venv([hashtable]$Py) {
    $venv = Join-Path $InstallDir ".venv"
    Write-Info "Creating virtualenv in $venv"
    Invoke-Python $Py @("-m", "venv", $venv)
    $pip = Join-Path $venv "Scripts\python.exe"
    & $pip -m pip install -U pip wheel
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
    Push-Location $InstallDir
    try {
        & $pip -m pip install -e ".[dev]"
        if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    } finally {
        Pop-Location
    }
}

function Write-ConfigFiles {
    Push-Location $InstallDir
    try {
        if (-not (Test-Path "forge.yaml") -and (Test-Path "config\forge.example.yaml")) {
            Copy-Item "config\forge.example.yaml" "forge.yaml"
            Write-Info "Created forge.yaml from example"
        }
        if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
            Copy-Item ".env.example" ".env"
            Write-Info "Created .env from example — add API keys when ready"
        }
    } finally {
        Pop-Location
    }
}

function Write-Launchers {
    $servePs1 = Join-Path $InstallDir "serve.ps1"
    @'
Set-Location $PSScriptRoot
& "$PSScriptRoot\.venv\Scripts\aityuahn.exe" serve @args
'@ | Set-Content -Path $servePs1 -Encoding UTF8

    $serveBat = Join-Path $InstallDir "serve.bat"
    @"
@echo off
cd /d "%~dp0"
call "%~dp0.venv\Scripts\activate.bat"
aityuahn serve %*
"@ | Set-Content -Path $serveBat -Encoding ASCII
    Write-Info "Launchers: serve.bat and serve.ps1"
}

Write-Info "AityUahn backend installer"
$python = Get-PythonCommand
Write-Info ("Using Python: {0} {1}" -f $python.exe, ($python.args -join " "))
Get-RepoSource
Install-Venv $python
Write-ConfigFiles
Write-Launchers

Write-Host ""
Write-Info "Done. Installed to: $InstallDir"
Write-Host @"

Next steps:
  cd "$InstallDir"
  .\serve.bat
  # or:  .\.venv\Scripts\Activate.ps1  then  aityuahn serve

  Open http://127.0.0.1:8765 and connect the controller.

"@
