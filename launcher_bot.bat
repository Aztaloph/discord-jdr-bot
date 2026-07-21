@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Verifie que l'environnement virtuel existe et fonctionne
if not exist "venv\Scripts\python.exe" goto venv_missing
venv\Scripts\python.exe -V >nul 2>&1
if not errorlevel 1 goto venv_ok

echo.
echo [ERREUR] Environnement virtuel casse (Python reinstalle ?).
echo Relancez : installer.bat
echo.
pause
exit /b 1

:venv_missing
echo.
echo [ERREUR] Environnement virtuel introuvable.
echo.
echo Veuillez d'abord executer : installer.bat
echo.
pause
exit /b 1

:venv_ok
echo.
echo ========================================
echo     LANCEMENT DU BOT DISCORD JDR
echo ========================================
echo.

REM Verifie les dependances critiques (dotenv, discord.py)
venv\Scripts\python.exe -c "import dotenv, discord" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Dependances manquantes - installation en cours...
    echo.
    venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERREUR] Echec de l'installation des dependances.
        echo Executez installer.bat ou verifiez requirements.txt.
        echo.
        pause
        exit /b 1
    )
    echo.
    echo [OK] Dependances installees.
    echo.
)

echo Connexion a Discord...
echo.

REM Evite les erreurs d'encodage des emojis dans la console Windows
set PYTHONUTF8=1
venv\Scripts\python.exe main.py
set EXITCODE=%ERRORLEVEL%

echo.
echo ========================================
echo Le bot s'est arrete (ou une erreur est
echo survenue). Voir les messages ci-dessus.
echo ========================================
pause
exit /b %EXITCODE%
