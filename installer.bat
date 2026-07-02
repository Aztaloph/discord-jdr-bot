@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ========================================
echo       INSTALLATION DU BOT JDR
echo ========================================
echo.

:: Vérifie si l'environnement virtuel existe déjà
if exist "venv\Scripts\activate.bat" (
    echo [OK] Environnement virtuel deja present.
) else (
    echo [INFO] Creation de l'environnement virtuel...
    python -m venv venv
    if errorlevel 1 (
        echo.
        echo [ERREUR] Echec de la creation du venv. Verifiez Python.
        echo Assurez-vous que Python est installe et accessible.
        echo.
        pause
        exit /b 1
    )
    echo [OK] Environnement virtuel cree.
)

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
    echo [ERREUR] Echec de l'installation des依赖. Verifiez requirements.txt.
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
