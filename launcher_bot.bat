@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: Verifie que l'environnement virtuel existe
if not exist "venv\Scripts\activate.bat" (
    echo.
    echo [ERREUR] Environnement virtuel introuvable.
    echo.
    echo Veuillez d'abord executer : installer.bat
    echo Cela cree l'environnement et installe les dependances.
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo     LANCEMENT DU BOT DISCORD JDR
echo ========================================
echo.

call venv\Scripts\activate.bat

echo.
echo Connexion a Discord...
echo.
python main.py

echo.
echo ========================================
echo Le bot s'est arrete (ou une erreur est
echo survenue). Voir les messages ci-dessus.
echo ========================================
pause
