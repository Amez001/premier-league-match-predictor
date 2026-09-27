@echo off
setlocal
cd /d "%~dp0"
title PL Predictor - demarrage

python -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
    echo Installation des dependances Python...
    python -m pip install -r requirements.txt -e . || goto :error
)

if not exist "frontend\dist\index.html" (
    echo Construction de l'interface web ^(premiere fois, ~1 min^)...
    pushd frontend
    call npm install || goto :popderror
    call npm run build || goto :popderror
    popd
)

echo Demarrage du serveur sur http://localhost:8000 ...
start "PL Predictor - serveur (laisser ouvert)" cmd /k "python -m uvicorn api.main:app --port 8000"

ping -n 3 127.0.0.1 >nul
start "" http://localhost:8000
exit /b 0

:popderror
popd
:error
echo.
echo Une erreur est survenue pendant le demarrage - voir les messages ci-dessus.
pause
exit /b 1
