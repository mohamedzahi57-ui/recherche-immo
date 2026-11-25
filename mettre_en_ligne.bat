@echo off
chcp 65001 >nul
REM Premiere mise en ligne de la version consultation (a lancer une seule fois).
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
.venv\Scripts\python mettre_en_ligne.py
echo.
pause
