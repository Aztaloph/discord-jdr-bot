@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ========================================
echo       INSTALLATION DU BOT JDR
echo ========================================
echo.

REM Verifie que Python est accessible
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python introuvable dans le PATH.
    echo Reinstallez Python en cochant "Add to PATH".
    echo.
    pause
    exit /b 1
)

REM Recree le venv si absent ou casse (ex: apres reinstallation de Python)
if not exist "venv\Scripts\python.exe" goto create_venv
venv\Scripts\python.exe -V >nul 2>&1
if not errorlevel 1 goto venv_ok
echo [INFO] Ancien venv invalide - recreation...
rmdir /s /q venv

:create_venv
echo [INFO] Creation de l'environnement virtuel...
python -m venv venv
if errorlevel 1 (
    echo.
    echo [ERREUR] Echec de la creation du venv. Verifiez Python.
    echo.
    pause
    exit /b 1
)
echo [OK] Environnement virtuel cree.

:venv_ok
echo [OK] Environnement virtuel pret.

echo.
echo Activation de l'environnement virtuel...
call venv\Scripts\activate.bat

echo.
echo ========================================
echo      MISE A JOUR DE PIP
echo ========================================
echo.
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERREUR] Echec de la mise a jour de pip.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   INSTALLATION DES DEPENDANCES
echo ========================================
echo.
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERREUR] Echec de l'installation des dependances. Verifiez requirements.txt.
    pause
    exit /b 1
)

echo.
echo ========================================
echo.
echo  Tout est configure avec succes !
echo  Lancez maintenant : launcher_bot.bat
echo.
echo ========================================
pause
