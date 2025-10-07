@echo off
REM Script para construir o executável do Proxmox Manager usando PyInstaller

REM Define o nome do arquivo principal a ser compilado
set MAIN_FILE=main.py

REM Define o nome do executável de saída (opcional, PyInstaller usa o nome do script por padrão)
set EXE_NAME=ProxmoxManager

REM Define o diretório de saída para a pasta 'dist'
set DIST_PATH=dist

echo ===================================================
echo INICIANDO O PROCESSO DE BUILD COM PYINSTALLER
echo ===================================================

REM 1. Limpa diretórios temporários e de saída antigos
echo

1/3
Limpando pastas temporarias (build) e de saida (%DIST_PATH%)...
if exist "%DIST_PATH%" rmdir /s /q "%DIST_PATH%"
if exist "build" rmdir /s /q "build"

REM 2. Executa o PyInstaller
REM --onefile: Cria um unico executavel
REM --noconsole: Nao exibe a janela do console (essencial para aplicativos GUI como PyQt)
REM --icon: Define o icone do executavel (garanta que o arquivo favicon.png esteja no formato .ico)
REM --hidden-import: Forca a inclusao de modulos que o PyInstaller nao detecta automaticamente (como os backends do proxmoxer)
REM --name: Define o nome do executavel
REM --distpath: Define o caminho de saida
echo

2/3
Executando PyInstaller...
pyinstaller --onefile --noconsole --icon "./resources/favicon.ico" --name "%EXE_NAME%" --distpath "%DIST_PATH%" --hidden-import proxmoxer.backends.http --hidden-import proxmoxer.backends.https --hidden-import proxmoxer.backends --hidden-import certifi "%MAIN_FILE%"

if ERRORLEVEL 1 (
echo.
echo ❌ ERRO: Falha na execucao do PyInstaller. Verifique as mensagens acima.
echo.
) else (
echo.
echo ===================================================
echo ✅ SUCESSO!
echo O executavel '%EXE_NAME%.exe' foi criado em:
echo %DIST_PATH%%EXE_NAME%.exe
echo ===================================================
)

echo "3/3 Removendo pasta temporaria 'build'..."
if exist "build" rmdir /s /q "build"

pause