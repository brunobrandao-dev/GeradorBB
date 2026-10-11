@echo off
title GeradorBB — Build
echo.
echo  ============================================
echo   GeradorBB — Gerando executavel...
echo  ============================================
echo.

cd /d "%~dp0"

:: Instala PyInstaller se necessario
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo  Instalando PyInstaller...
    python -m pip install pyinstaller --quiet
)

:: Limpa builds anteriores
if exist dist\GeradorBB rmdir /s /q dist\GeradorBB
if exist build rmdir /s /q build

:: Roda o build
echo  Compilando (pode demorar 2-5 minutos)...
python -m PyInstaller GeradorBB.spec --noconfirm

if errorlevel 1 (
    echo.
    echo  ERRO no build. Verifique as mensagens acima.
    pause
    exit /b 1
)

:: Move engine.exe para _internal\ (fica oculto do cliente)
echo  Organizando arquivos...
if exist dist\GeradorBB\engine.exe  move /y dist\GeradorBB\engine.exe  dist\GeradorBB\_internal\engine.exe  >nul

:: Copia arquivos de dados necessarios para dist/
echo  Copiando arquivos de dados...
if not exist dist\GeradorBB\banco   mkdir dist\GeradorBB\banco
if not exist dist\GeradorBB\projeto mkdir dist\GeradorBB\projeto

:: Copia config padrao (sem sessao do desenvolvedor)
copy /y config_app.json dist\GeradorBB\config_app.json >nul 2>&1

:: Gera versao.json com versao atual
echo {"versao": "4.0"} > dist\GeradorBB\versao.json

echo.
echo  ============================================
echo   Build concluido!
echo   Pasta: dist\GeradorBB\
echo   Executavel principal: dist\GeradorBB\GeradorBB.exe
echo  ============================================
echo.
echo   O cliente so ve:
echo     GeradorBB.exe
echo     _internal\  (arquivos do sistema)
echo.
echo  Para distribuir: compacte a pasta dist\GeradorBB\ em .zip
echo  e envie para os clientes.
echo.
pause
