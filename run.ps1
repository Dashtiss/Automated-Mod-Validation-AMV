# AMV Engine Runner
# This script runs the AMV Engine with proper environment checks

Write-Host "AMV Engine Runner" -ForegroundColor Green

# Check for .env file
if (-not (Test-Path ".env")) {
    Write-Host "Error: .env file not found!" -ForegroundColor Red
    Write-Host "Please create a .env file with required configuration." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check for Python installation
try {
    $pythonVersion = python --version
    Write-Host "Using $pythonVersion" -ForegroundColor Cyan
} catch {
    Write-Host "Error: Python not found!" -ForegroundColor Red
    Write-Host "Please install Python and add it to your PATH." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check for required packages
Write-Host "Checking dependencies..." -ForegroundColor Cyan
python -m pip install -r requirements.txt

# Start the AMV Engine
Write-Host "`nStarting AMV Engine..." -ForegroundColor Green
try {
    python run.py
} catch {
    Write-Host "Error running AMV Engine: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Read-Host "Press Enter to exit"
