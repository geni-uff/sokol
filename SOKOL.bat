@echo off
rem SOKOL — no Windows este .bat so encaminha para o Ubuntu do WSL2.
rem Autor: Matheus C. Pestana
setlocal EnableExtensions
chcp 65001 >nul
title SOKOL
cd /d "%~dp0"

echo.
echo   SOKOL
echo   No Windows a stack corre no Ubuntu (WSL2), nao no Docker Desktop.
echo.

where wsl.exe >nul 2>&1
if errorlevel 1 (
    echo ERRO: WSL nao encontrado.
    echo Instale o Ubuntu no WSL2. Passos: INSTRUCOES.md, secao 6.0.
    goto :fail
)

for /f "usebackq delims=" %%i in (`wsl.exe wslpath -a "%CD%"`) do set "WSLDIR=%%i"
if "%WSLDIR%"=="" (
    echo ERRO: nao consegui converter o caminho para o WSL.
    goto :fail
)

echo Pasta no Ubuntu: %WSLDIR%
echo A executar ops/start-sokol.sh no WSL...
echo.

wsl.exe -e bash -lc "cd '%WSLDIR%' && bash ops/start-sokol.sh"
if errorlevel 1 goto :fail

echo.
echo Abrindo http://localhost:3000 no Windows...
start "" "http://localhost:3000"
echo Pode fechar esta janela. Os containers continuam no Ubuntu.
timeout /t 8 /nobreak >nul
exit /b 0

:fail
echo.
pause
exit /b 1
