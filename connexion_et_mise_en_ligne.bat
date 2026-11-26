@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  ETAPE 1 : connexion a GitHub
echo  - A la question (Y/n), tapez Y puis Entree
echo  - Un code XXXX-XXXX s'affiche : appuyez sur Entree,
echo    collez le code sur la page GitHub (Ctrl+V),
echo    puis Continue et Authorize GitHub.
echo ============================================================
echo.
"C:\Program Files\GitHub CLI\gh.exe" auth status >nul 2>&1
if errorlevel 1 "C:\Program Files\GitHub CLI\gh.exe" auth login --hostname github.com --git-protocol https --web --scopes workflow
"C:\Program Files\GitHub CLI\gh.exe" auth status >nul 2>&1
if errorlevel 1 (
  echo.
  echo La connexion GitHub n'a pas abouti. Relancez ce fichier.
  pause
  exit /b 1
)
echo.
echo ============================================================
echo  ETAPE 2 : mise en ligne (1 a 2 minutes)
echo ============================================================
set PYTHONIOENCODING=utf-8
.venv\Scripts\python mettre_en_ligne.py > data\mise_en_ligne.log 2>&1
type data\mise_en_ligne.log
echo.
pause
