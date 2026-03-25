@echo off
setlocal enabledelayedexpansion
title SOC IP Analyzer v5.5
cd /d "%~dp0"
color 0B

:: CONFIG PYTHON AUTO INSTALL
set "PYTHON_INSTALLER=python_installer.exe"
set "PYTHON_URL=https://www.python.org/ftp/python/3.12.2/python-3.12.2-amd64.exe"

echo.
echo  ==========================================
echo       SOC IP Analyzer v5.6 - Check Point
echo  ==========================================
echo.

:: ══════════════════════════════════════════
:: [1/5] PYTHON
:: ══════════════════════════════════════════
echo  [1/5] Verificando Python...
python --version >nul 2>&1

if errorlevel 1 (
    echo  [AVISO] Python nao encontrado.
    echo  Baixando Python...

    powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%'" >nul 2>&1

    if exist "%PYTHON_INSTALLER%" (
        echo  Instalando Python...

        start /wait "" "%PYTHON_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0

        echo  Python instalado! Reiniciando script...
        timeout /t 2 >nul

        :: Reabre o próprio script já com Python instalado
        start "" "%~f0"
        exit /b
    ) else (
        echo  [ERRO] Falha ao baixar Python!
        echo  Instale manualmente em: https://python.org
        pause
        exit /b 1
    )
)

echo  [OK] Python encontrado.
echo.

:: ══════════════════════════════════════════
:: [2/5] API KEY
:: ══════════════════════════════════════════
echo  [2/5] Verificando API Key...

if exist "config.txt" (
    echo  [OK] config.txt encontrado.
) else (
    echo.
    echo  ----------------------------------------
    echo   PRIMEIRA EXECUCAO
    echo  ----------------------------------------
    echo.
    echo  Acesse https://www.abuseipdb.com/account/api
    echo  e copie sua API Key.
    echo.
    set /p APIKEY="  Cole sua API Key e pressione ENTER: "

    if "!APIKEY!"=="" (
        echo  [ERRO] API Key vazia.
        pause
        exit /b 1
    )

    echo|set /p="!APIKEY!"> config.txt
    echo.
    echo  [OK] API Key salva em config.txt
    echo  Para trocar: delete config.txt e reabra.
)
echo.

:: ══════════════════════════════════════════
:: [3/5] DEPENDENCIAS PYTHON
:: ══════════════════════════════════════════
echo  [3/5] Instalando dependencias Python...

set PKGS=flask flask-cors requests pytesseract opencv-python numpy Pillow

python -m pip install %PKGS% -q >nul 2>&1
if not errorlevel 1 goto :check_tesseract

pip install %PKGS% -q >nul 2>&1
if not errorlevel 1 goto :check_tesseract

pip3 install %PKGS% -q >nul 2>&1
if not errorlevel 1 goto :check_tesseract

echo  [ERRO] Nao foi possivel instalar dependencias.
pause
exit /b 1

:: ══════════════════════════════════════════
:: [4/5] TESSERACT OCR
:: ══════════════════════════════════════════
:check_tesseract
echo.
echo  [4/5] Verificando Tesseract OCR...

tesseract --version >nul 2>&1
if not errorlevel 1 goto :start_server

if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" goto :start_server

echo  [AVISO] Tesseract nao encontrado.
echo.
echo  Deseja instalar agora?
echo  [1] Sim
echo  [2] Nao
echo.

set /p TESS_CHOICE="Opcao: "

if "!TESS_CHOICE!"=="1" goto :instalar_tesseract
goto :skip_tesseract

:instalar_tesseract
set TESS_URL=https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe
set TESS_FILE=%TEMP%\tesseract.exe

powershell -Command "Invoke-WebRequest -Uri '%TESS_URL%' -OutFile '%TESS_FILE%'" >nul 2>&1

start "" "%TESS_FILE%"
exit /b

:skip_tesseract
echo  [INFO] Continuando sem OCR.
echo.
:: ══════════════════════════════════════════
:: [EXTRA] CRIAR ATALHOS NA AREA DE TRABALHO
:: ══════════════════════════════════════════
echo.
echo  [EXTRA] Criando atalhos...

set "DESKTOP=%USERPROFILE%\Desktop"
set "PROJECT_DIR=%~dp0SOC_IP_Analyzer"
set "START_BAT=%PROJECT_DIR%\start.bat"
set "UPDATE_BAT=%~dp0update.bat"
set "ICON_PATH=%PROJECT_DIR%\icon.ico"

:: DEBUG (opcional)
echo  Caminho projeto: %PROJECT_DIR%
echo  Start: %START_BAT%

:: ================================
:: ATALHO PRINCIPAL
:: ================================
if not exist "%DESKTOP%\SOC IP Analyzer.lnk" (
    echo  Criando atalho principal...

    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; ^
    $s = $ws.CreateShortcut('%DESKTOP%\SOC IP Analyzer.lnk'); ^
    $s.TargetPath = '%START_BAT%'; ^
    $s.WorkingDirectory = '%PROJECT_DIR%'; ^
    if (Test-Path '%ICON_PATH%') { $s.IconLocation = '%ICON_PATH%' }; ^
    $s.Save()"

) else (
    echo  [OK] Atalho principal ja existe.
)

:: ================================
:: ATALHO UPDATE
:: ================================
if not exist "%DESKTOP%\SOC Update.lnk" (
    echo  Criando atalho de update...

    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; ^
    $s = $ws.CreateShortcut('%DESKTOP%\SOC Update.lnk'); ^
    $s.TargetPath = '%UPDATE_BAT%'; ^
    $s.WorkingDirectory = '%~dp0'; ^
    if (Test-Path '%ICON_PATH%') { $s.IconLocation = '%ICON_PATH%' }; ^
    $s.Save()"

) else (
    echo  [OK] Atalho de update ja existe.
)

echo.

:: ══════════════════════════════════════════
:: [5/5] SERVIDOR
:: ══════════════════════════════════════════
:start_server
echo  [5/5] Iniciando servidor...
echo.
echo  ==========================================
echo   Acesse: http://127.0.0.1:5000
echo  ==========================================
echo.

timeout /t 2 >nul
start "" "http://127.0.0.1:5000"
python server.py

pause