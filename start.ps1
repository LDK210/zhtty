param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$VenvPip = Join-Path $BackendDir ".venv\Scripts\pip.exe"

function Test-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Start-NamedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Command
    )

    Start-Process powershell.exe -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command",
        "Set-Location '$WorkingDirectory'; `$Host.UI.RawUI.WindowTitle = '$Title'; $Command"
    )
}

if (-not (Test-Command "python")) {
    throw "Python is required but was not found in PATH."
}

if (-not (Test-Command "npm")) {
    throw "Node.js/npm is required but was not found in PATH."
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating backend virtual environment..."
    Push-Location $BackendDir
    python -m venv .venv
    Pop-Location
}

if (-not $SkipInstall) {
    Write-Host "Installing backend dependencies..."
    Push-Location $BackendDir
    & $VenvPip install -r requirements.txt
    Pop-Location

    if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
        Write-Host "Installing frontend dependencies..."
        Push-Location $FrontendDir
        npm install
        Pop-Location
    }
}

$env:VITE_API_BASE_URL = "http://localhost:8000"

Write-Host "Applying backend database migrations..."
Push-Location $BackendDir
& $VenvPython -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    throw "Database migration failed with exit code $LASTEXITCODE. Backend startup was cancelled."
}
Pop-Location

Write-Host "Starting HirePilot backend at http://localhost:8000"
Start-NamedProcess `
    -Title "HirePilot Backend" `
    -WorkingDirectory $BackendDir `
    -Command ".\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

Write-Host "Starting HirePilot frontend at http://localhost:5173"
Start-NamedProcess `
    -Title "HirePilot Frontend" `
    -WorkingDirectory $FrontendDir `
    -Command "`$env:VITE_API_BASE_URL='http://localhost:8000'; npm run dev"

Write-Host ""
Write-Host "HirePilot is starting."
Write-Host "Backend:  http://localhost:8000"
Write-Host "Frontend: http://localhost:5173"
Write-Host "Close the opened PowerShell windows to stop the services."
