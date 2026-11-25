@echo off
REM Copie les cles du fichier .env dans les secrets GitHub de la version en ligne.
cd /d "%~dp0"
.venv\Scripts\python publier_secrets.py
pause
