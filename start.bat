@echo off
setlocal enabledelayedexpansion
title SOC IP Analyzer v5.5
cd /d "%~dp0"
color 0B

echo.
echo  ==========================================
echo       SOC IP Analyzer v5.5 - Check Point
echo  ==========================================
echo.

:: ══════════════════════════════════════════
:: [1/5] PYTHON
:: ══════════════════════════════════════════
echo  [1/5] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  [AVISO] Python nao encontrado.
    echo.
    if exist "python-manager-26.0.msix" (
        echo  Iniciando instalador do Python...
        start "" "python-manager-26.0.msix"
        echo.
        echo  Instale o Python e execute este arquivo novamente.
    ) else (
        echo  Instale o Python em: https://python.org
    )
    echo.
    pause
    exit /b 1
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
if not errorlevel 1 (
    echo  [OK] Dependencias prontas.
    goto :check_tesseract
)

pip install %PKGS% -q >nul 2>&1
if not errorlevel 1 (
    echo  [OK] Dependencias prontas.
    goto :check_tesseract
)

pip3 install %PKGS% -q >nul 2>&1
if not errorlevel 1 (
    echo  [OK] Dependencias prontas.
    goto :check_tesseract
)

echo  [ERRO] Nao foi possivel instalar dependencias.
echo  Tente manualmente: python -m pip install flask flask-cors requests pytesseract opencv-python numpy Pillow
pause
exit /b 1

:: ══════════════════════════════════════════
:: [4/5] TESSERACT OCR
:: ══════════════════════════════════════════
:check_tesseract
echo.
echo  [4/5] Verificando Tesseract OCR...

:: Verifica no PATH primeiro
tesseract --version >nul 2>&1
if not errorlevel 1 (
    echo  [OK] Tesseract encontrado no PATH.
    goto :start_server
)

:: Verifica no caminho padrao de instalacao
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo  [OK] Tesseract encontrado em C:\Program Files\Tesseract-OCR
    goto :start_server
)

:: Tesseract nao encontrado — perguntar se deseja instalar
echo  [AVISO] Tesseract nao encontrado.
echo.
echo  O Tesseract e necessario para a funcao de extrair IPs de prints/imagens.
echo  Sem ele o servidor funciona normalmente, mas o OCR ficara desativado.
echo.
echo  ----------------------------------------
echo   Deseja baixar e instalar o Tesseract?
echo  ----------------------------------------
echo.
echo   [1] Sim — baixar e instalar agora (recomendado)
echo   [2] Nao — continuar sem OCR
echo.
set /p TESS_CHOICE="  Digite 1 ou 2 e pressione ENTER: "

if "!TESS_CHOICE!"=="1" goto :instalar_tesseract
if "!TESS_CHOICE!"=="2" goto :skip_tesseract

echo  Opcao invalida. Continuando sem Tesseract.
goto :skip_tesseract

:instalar_tesseract
echo.
echo  Baixando Tesseract v5.4.0...
echo  (pode demorar alguns minutos dependendo da sua conexao)
echo.

set TESS_URL=https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe
set TESS_FILE=%TEMP%\tesseract-setup.exe

:: Tenta baixar com PowerShell (disponivel no Windows 7+)
powershell -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%TESS_URL%' -OutFile '%TESS_FILE%' -UseBasicParsing }" >nul 2>&1

if not exist "%TESS_FILE%" (
    echo  [ERRO] Falha ao baixar o instalador.
    echo  Baixe manualmente em:
    echo  https://github.com/UB-Mannheim/tesseract/releases
    echo.
    goto :skip_tesseract
)

echo  [OK] Download concluido.
echo.
echo  ============================================================
echo   INSTALACAO DO TESSERACT
echo  ============================================================
echo.
echo   O instalador sera aberto agora.
echo.
echo   IMPORTANTE:
echo   1. Conclua a instalacao normalmente
echo   2. Mantenha o caminho padrao sugerido pelo instalador
echo   3. Apos finalizar, FECHE esta janela e abra o start.bat
echo      novamente para iniciar o servidor com OCR ativado.
echo.
echo  ============================================================
echo.
pause

start "" "%TESS_FILE%"

echo.
echo  Quando terminar a instalacao, feche e reabra o start.bat.
echo.
pause
exit /b 0

:skip_tesseract
echo  [INFO] Continuando sem Tesseract — OCR desativado.
echo.

:: ══════════════════════════════════════════
:: [5/5] SERVIDOR
:: ══════════════════════════════════════════
:start_server
echo  [5/5] Iniciando servidor...
echo.
echo  ==========================================
echo   Acesse: http://127.0.0.1:5000
echo   Para encerrar feche esta janela.
echo  ==========================================
echo.

:: Informa status do OCR
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo  OCR: ATIVO  - extracao de prints disponivel
) else (
    tesseract --version >nul 2>&1
    if not errorlevel 1 (
        echo  OCR: ATIVO  - extracao de prints disponivel
    ) else (
        echo  OCR: INATIVO - instale o Tesseract para usar OCR
    )
)
echo.

timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:5000"
python server.py

pause
