@echo off
SETLOCAL EnableDelayedExpansion

echo.
echo ==========================================
echo    Nanobot AI - Windows Starter
echo ==========================================
echo.

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.11 or higher.
    echo Visit: https://www.python.org/
    pause
    exit /b 1
)

:: Create Virtual Environment if it doesn't exist
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

:: Activate Virtual Environment and Install
echo [INFO] Activating virtual environment and installing dependencies...
call venv\Scripts\activate
pip install -e .

:: Check for config.json
if not exist "%USERPROFILE%\.nanobot\config.json" (
    echo [WARNING] config.json not found in %USERPROFILE%\.nanobot\
    echo [INFO] Creating directory and basic config structure...
    if not exist "%USERPROFILE%\.nanobot" mkdir "%USERPROFILE%\.nanobot"
    
    echo { "providers": { "openrouter": { "apiKey": "sk-or-v1-YOUR_KEY" } }, "agents": { "defaults": { "model": "anthropic/claude-3-5-sonnet-latest" } } } > "%USERPROFILE%\.nanobot\config.json"
    
    echo.
    echo [IMPORTANT] Please edit your API keys in: %USERPROFILE%\.nanobot\config.json
    pause
)

echo.
echo [SUCCESS] Everything is ready.
echo [INFO] Opening Web Dashboard at http://localhost:8080
echo.

:: Start the core which includes the Web Dashboard and Configuration Panel
python nanobot_core.py

pause
