@echo off
IF NOT EXIST ".env" (
    echo Error: .env file not found!
    echo Please create a .env file with required configuration.
    pause
    exit /b 1
)

echo Starting AMV Engine...
python run.py
IF %ERRORLEVEL% NEQ 0 (
    echo Error: AMV Engine execution failed!
    pause
    exit /b %ERRORLEVEL%
)
pause
