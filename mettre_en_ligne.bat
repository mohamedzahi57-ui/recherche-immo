@echo off
chcp 65001 >nul
REM Premiere mise en ligne de la version consultation (a lancer une seule fois).
REM Le deroulement est aussi ecrit dans data\mise_en_ligne.log
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
.venv\Scripts\python mettre_en_ligne.py > data\mise_en_ligne.log 2>&1
type data\mise_en_ligne.log
echo.
pause
