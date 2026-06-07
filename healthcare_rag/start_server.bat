@echo off
REM ================================================================
REM START SERVER — Batch script for Windows
REM ================================================================

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo 🚀 Healthcare RAG Server Launcher
echo ==================================
echo.

set LLM_MODE=%1
if "!LLM_MODE!"=="" set LLM_MODE=auto

set PORT=%2
if "!PORT!"=="" set PORT=8000

set RELOAD=%3

echo 📋 Configuration:
echo    LLM Mode: !LLM_MODE!
echo    Port: !PORT!
if "!RELOAD!"=="--reload" (
    echo    Reload: YES
) else (
    echo    Reload: NO
)
echo.

echo Starting server...
python scripts/start_server.py --llm !LLM_MODE! --port !PORT! !RELOAD!

echo.
echo ✅ Server stopped
pause
