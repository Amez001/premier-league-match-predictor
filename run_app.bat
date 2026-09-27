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

echo Attente du serveur...
python scripts\wait_for_server.py http://localhost:8000/api/teams 20
if errorlevel 1 (
    echo Le serveur met plus longtemps que prevu a demarrer.
    echo Verifie la fenetre "PL Predictor - serveur" pour d'eventuelles erreurs,
    echo puis ouvre http://localhost:8000 toi-meme une fois pret.
) else (
    start "" http://localhost:8000
)
exit /b 0

:popderror
popd
:error
echo.
echo Une erreur est survenue pendant le demarrage - voir les messages ci-dessus.
pause
exit /b 1
