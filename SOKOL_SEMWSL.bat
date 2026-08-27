@echo off
rem SOKOL_SEMWSL — sobe a stack no Docker Desktop do Windows (sem WSL manual).
rem Autor: Matheus C. Pestana
rem Uso:
rem   SOKOL_SEMWSL.bat           → sobe sem rebuild (rapido)
rem   SOKOL_SEMWSL.bat build     → rebuild das imagens
rem   SOKOL_SEMWSL.bat web       → so recria sokol-web (porta / nginx)
rem Requer: Docker Desktop; LM Studio no Windows :1234 (opcional para o Agent).
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title SOKOL (Windows / Docker Desktop)
cd /d "%~dp0"

set "MODE=up"
if /I "%~1"=="build" set "MODE=build"
if /I "%~1"=="web" set "MODE=web"

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

rem Porta da UI no host (default 3000). Se ocupada, mude SOKOL_WEB_PORT no .env.
set "WEB_PORT=3000"
for /f "usebackq tokens=1,* delims==" %%a in (`.env`) do (
    if /I "%%a"=="SOKOL_WEB_PORT" set "WEB_PORT=%%b"
)
set "WEB_PORT=!WEB_PORT: =!"

if not exist "data\media-cache" mkdir "data\media-cache"
if not exist "data\staging" mkdir "data\staging"
if not exist "data\backups" mkdir "data\backups"
if not exist "UFDRsTest" mkdir "UFDRsTest"

pushd deploy
if /I "!MODE!"=="build" (
    echo A reconstruir e subir os containers...
    docker compose -f docker-compose.yml -f docker-compose.windows.yml --env-file ..\.env up --build -d
) else if /I "!MODE!"=="web" (
    echo A recriar so o sokol-web na porta !WEB_PORT! (sem rebuild^)...
    docker compose -f docker-compose.yml -f docker-compose.windows.yml --env-file ..\.env up -d --no-build --force-recreate sokol-web
) else (
    echo A subir os containers sem rebuild (rapido^).
    echo Para rebuild: SOKOL_SEMWSL.bat build
    docker compose -f docker-compose.yml -f docker-compose.windows.yml --env-file ..\.env up -d --no-build
)
set "COMPOSE_ERR=!ERRORLEVEL!"
popd
if not "!COMPOSE_ERR!"=="0" (
    echo.
    echo Compose falhou. Diagnostico rapido:
    echo   docker ps -a --filter name=sokol-api
    echo   docker logs sokol-api --tail 80
    echo   curl http://localhost:8000/health
    echo.
    echo Se a porta da UI !WEB_PORT! estiver ocupada:
    echo   1^) netstat -ano ^| findstr :!WEB_PORT!
    echo   2^) no .env defina SOKOL_WEB_PORT=3001 ^(ou outra livre^)
    echo   3^) SOKOL_SEMWSL.bat web
    echo.
    echo Se a porta 8000 estiver ocupada, mude SOKOL_API_PORT no .env.
    goto :fail
)

if /I "!MODE!"=="web" goto :open_ui

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
if not "!OK!"=="1" (
    echo ERRO: a API nao respondeu. Veja: docker logs sokol-api
    goto :fail
)

echo A aplicar migracoes...
docker exec sokol-api alembic upgrade head
if errorlevel 1 goto :fail

:open_ui
echo.
echo SOKOL no ar: http://localhost:!WEB_PORT!
echo Login de desenvolvimento: admin / admin123
echo LM Studio (Agent^): http://localhost:1234 no Windows.
echo.
echo Abrindo http://localhost:!WEB_PORT! ...
start "" "http://localhost:!WEB_PORT!"
timeout /t 5 /nobreak >nul
exit /b 0

:fail
echo.
pause
exit /b 1
