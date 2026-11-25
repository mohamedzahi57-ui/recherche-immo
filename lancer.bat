@echo off
REM ==============================================================
REM  Lancement de l'application de recherche immobiliere.
REM  Double-cliquez sur ce fichier. La premiere fois, l'installation
REM  prend 1 a 2 minutes.
REM ==============================================================
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python n'est pas installe. Installez-le depuis le Microsoft Store ^("Python 3.13"^) puis relancez.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Premiere installation en cours...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo L'installation a echoue. Astuce : placez le dossier dans un chemin court, par ex. C:\immo
  pause
  exit /b 1
)

if not exist ".env" copy ".env.example" ".env" >nul

start "" http://localhost:5000
".venv\Scripts\python.exe" app.py
pause
