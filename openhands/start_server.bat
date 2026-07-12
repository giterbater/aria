@echo off
REM ============================================
REM  ARIA - OpenHands Agent Server Launcher
REM  Execution Engine for CTO Architecture
REM ============================================

echo.
echo ============================================
echo   ARIA - OpenHands Agent Server
echo   Execution Engine for CTO Architecture
echo ============================================
echo.

set VENV=%~dp0..\.venv-openhands
set PYTHON=%VENV%\Scripts\python.exe
set PROJECT=%~dp0..

REM Verify Python venv exists
if not exist "%PYTHON%" (
    echo [!] OpenHands venv not found at %VENV%
    echo     Run: uv venv .venv-openhands --python 3.12
    echo     Then: uv pip install --python %VENV%\Scripts\python.exe openhands-ai
    pause
    exit /b 1
)

REM Load environment variables from project .env
echo [*] Loading environment...
for /f "usebackq tokens=1,* delims==" %%a in ("%PROJECT%\.env") do (
    set "%%a=%%b"
)

REM Verify NVIDIA API key
if "%NVIDIA_API_KEY%"=="" (
    echo [!] ERROR: NVIDIA_API_KEY not set. Check %PROJECT%\.env
    pause
    exit /b 1
)
echo [OK] NVIDIA API key loaded

REM Set OpenHands environment
set OPENHANDS_SUPPRESS_BANNER=1
set LLM_MODEL=openai/minimaxai/minimax-m2.7
set LLM_BASE_URL=https://integrate.api.nvidia.com/v1

echo.
echo Configuration:
echo   LLM:       %LLM_MODEL% (NVIDIA API)
echo   Workspace: %PROJECT%
echo   Backend:   agent-server
echo.
echo Starting OpenHands Agent Server...
echo Press Ctrl+C to stop
echo.

"%PYTHON%" -c "from openhands.app_server.app import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8000)"

pause
