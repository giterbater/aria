@echo off
REM ============================================
REM  ARIA - OpenHands One-Click Launcher
REM ============================================

echo.
echo   ARIA - OpenHands Agent Server
echo   http://localhost:8000
echo.

set VENV=%~dp0..\.venv-openhands
set PYTHON=%VENV%\Scripts\python.exe
set SERVER=%~dp0server.py

if not exist "%PYTHON%" (
    echo [!] OpenHands venv not found. Run setup first.
    pause
    exit /b 1
)

set OPENHANDS_SUPPRESS_BANNER=1
"%PYTHON%" "%SERVER%" %*
