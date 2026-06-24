@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title RAG-Pro Launcher

:: ============================================
::   RAG-Pro Quick Start
:: ============================================
echo.
echo   RAG-Pro v2.0 - Starting...
echo   Graph + Hybrid Search + Multi-Agent
echo.

:: --- Kill old processes & clean locks ---
echo [0/3] Cleaning up old processes...
taskkill /f /im python.exe /fi "WINDOWTITLE eq Backend*" >nul 2>nul
taskkill /f /im python.exe /fi "WINDOWTITLE eq RAG*" >nul 2>nul
:: Clean Milvus lock file
if exist "backend\data\milvus.db\LOCK" del /f "backend\data\milvus.db\LOCK" >nul 2>nul
echo   Done
echo.

:: --- Check environment ---
if not exist "backend" (
    echo [ERR] backend folder not found
    pause & exit /b 1
)
if not exist "frontend" (
    echo [ERR] frontend folder not found
    pause & exit /b 1
)
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERR] Node.js not found
    pause & exit /b 1
)
if not exist "backend\venv\Scripts\python.exe" (
    echo [ERR] Python venv not found - run install.bat first
    pause & exit /b 1
)
for /f "tokens=2" %%v in ('node --version 2^>^&1') do echo   Node.js %%v
echo   Python (venv) OK
echo.

:: --- Frontend deps ---
echo [1/3] Checking frontend dependencies...
if not exist "frontend\node_modules" (
    echo   Installing...
    cd frontend
    call npm install
    if %errorlevel% neq 0 (
        echo [ERR] npm install failed
        cd .. & pause & exit /b 1
    )
    cd ..
)
echo   Done
echo.

:: --- Neo4j ---
echo [2/3] Knowledge Graph (Neo4j)...
where docker >nul 2>nul
if %errorlevel% equ 0 (
    docker-compose up -d neo4j 2>nul
    if %errorlevel% equ 0 (
        echo   Neo4j started
    ) else (
        echo   Docker not running - skip Neo4j
    )
) else (
    echo   Docker not found - skip Neo4j
)
echo.

:: --- Start backend ---
echo [3/3] Starting services...
cd backend
start "Backend-8000" cmd /c "cd /d "%cd%" && venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
cd ..
timeout /t 3 >nul

:: --- Start frontend ---
cd frontend
start "Frontend-5173" cmd /c "cd /d "%cd%" && npx vite --host 0.0.0.0"
cd ..

:: --- Done ---
echo.
echo   ========================================
echo     Backend   : http://localhost:8000
echo     Frontend  : http://localhost:5173
echo     Graph     : http://localhost:5173/knowledge-graph
echo     API Docs  : http://localhost:8000/docs
echo   ========================================
echo.
echo   Services started. Close this window to keep them running.
pause >nul
