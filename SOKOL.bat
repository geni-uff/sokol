@echo off
rem SOKOL — sobe a stack e abre o navegador. Autor: Matheus C. Pestana
setlocal EnableExtensions
chcp 65001 >nul
title SOKOL
cd /d "%~dp0"

echo.
echo   SOKOL
echo   Clique e aguarde. Esta janela sobe os containers e abre o navegador.
echo.

where docker >nul 2>&1
if errorlevel 1 (
    echo ERRO: Docker nao encontrado no PATH.
    echo Instale o Docker Desktop e marque "Use Docker Compose V2".
    goto :fail
)

docker info >nul 2>&1
if errorlevel 1 (
    echo Docker parado. Tentando abrir o Docker Desktop...
    if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
        start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    ) else if exist "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe" (
        start "" "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe"
    )
    echo Aguarde o Docker ficar pronto...
    set /a _n=0
    :wait_docker
    timeout /t 3 /nobreak >nul
    docker info >nul 2>&1
    if not errorlevel 1 goto :docker_ok
    set /a _n+=1
    if %_n% lss 40 goto :wait_docker
    echo ERRO: Docker nao respondeu. Abra o Docker Desktop e clique de novo neste arquivo.
    goto :fail
)

:docker_ok
if not exist ".env" (
    copy /Y "deploy\env.example" ".env" >nul
    echo Aviso: criei o arquivo .env a partir do exemplo.
)

if not exist "data\media-cache" mkdir "data\media-cache"
if not exist "data\staging" mkdir "data\staging"
if not exist "data\backups" mkdir "data\backups"
if not exist "UFDRsTest" mkdir "UFDRsTest"

where lms >nul 2>&1
if not errorlevel 1 (
    echo Ligando o LM Studio, se existir...
    lms server start >nul 2>&1
)

echo.
echo A subir os containers. A primeira vez baixa imagens e pode demorar varios minutos.
echo Nao feche esta janela.
echo.

pushd deploy
docker compose --env-file ..\.env up --build -d
set _rc=%errorlevel%
popd
if not "%_rc%"=="0" (
    echo ERRO: docker compose falhou.
    goto :fail
)

echo.
echo A esperar a API em http://localhost:8000/health ...
set /a _n=0
:wait_api
curl.exe -sf http://localhost:8000/health >nul 2>&1
if not errorlevel 1 goto :api_ok
timeout /t 3 /nobreak >nul
set /a _n+=1
if %_n% lss 60 goto :wait_api
echo ERRO: a API nao respondeu. Veja: docker logs sokol-api
goto :fail

:api_ok
echo A aplicar migracoes...
docker exec sokol-api alembic upgrade head
if errorlevel 1 (
    echo ERRO: alembic falhou.
    goto :fail
)

echo.
echo SOKOL no ar.
echo Login de desenvolvimento: admin / admin123
echo.
echo Abrindo http://localhost:3000
start "" "http://localhost:3000"

echo Pode fechar esta janela. Os containers continuam a correr.
timeout /t 8 /nobreak >nul
exit /b 0

:fail
echo.
pause
exit /b 1
