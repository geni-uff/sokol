@echo off
rem SOKOL_SEMWSL — sobe a stack no Docker Desktop do Windows (sem WSL manual).
rem Autor: Matheus C. Pestana
rem Requer: Docker Desktop ligado; LM Studio no Windows na porta 1234 (opcional para o Agent).
setlocal EnableExtensions
chcp 65001 >nul
title SOKOL (Windows / Docker Desktop)
cd /d "%~dp0"

echo.
echo   SOKOL — modo Windows (sem WSL)
echo   Usa Docker Desktop + bridge network (nao network_mode: host).
echo.

where docker.exe >nul 2>&1
if errorlevel 1 (
    echo ERRO: docker nao esta no PATH.
    echo Instale e abra o Docker Desktop, depois tente de novo.
    goto :fail
)

docker info >nul 2>&1
if errorlevel 1 (
    echo ERRO: o Docker Desktop nao responde.
    echo Abra o Docker Desktop e espere ficar "Running".
    goto :fail
)

if not exist ".env" (
    copy /Y "deploy\env.example" ".env" >nul
    echo Aviso: criei .env a partir de deploy\env.example. Defina POSTGRES_PASSWORD.
)

if not exist "data\media-cache" mkdir "data\media-cache"
if not exist "data\staging" mkdir "data\staging"
if not exist "data\backups" mkdir "data\backups"
if not exist "UFDRsTest" mkdir "UFDRsTest"

echo A subir os containers (primeira vez pode demorar varios minutos^)...
echo.
pushd deploy
docker compose -f docker-compose.yml -f docker-compose.windows.yml --env-file ..\.env up --build -d
set "COMPOSE_ERR=%ERRORLEVEL%"
popd
if not "%COMPOSE_ERR%"=="0" goto :fail

echo.
echo A esperar http://localhost:8000/health ...
set "OK=0"
for /L %%i in (1,1,60) do (
    curl.exe -sf http://localhost:8000/health >nul 2>&1
    if not errorlevel 1 (
        set "OK=1"
        goto :health_done
    )
    timeout /t 3 /nobreak >nul
)
:health_done
if not "%OK%"=="1" (
    echo ERRO: a API nao respondeu. Veja: docker logs sokol-api
    goto :fail
)

echo A aplicar migracoes...
docker exec sokol-api alembic upgrade head
if errorlevel 1 goto :fail

echo.
echo SOKOL no ar: http://localhost:3000
echo Login de desenvolvimento: admin / admin123
echo LM Studio (Agent^): http://localhost:1234 no Windows — use host.docker.internal nos containers.
echo.
echo Abrindo http://localhost:3000 ...
start "" "http://localhost:3000"
timeout /t 8 /nobreak >nul
exit /b 0

:fail
echo.
pause
exit /b 1
