@echo off
REM ==============================================================
REM  Installe (ou retire) le demarrage automatique de l'application
REM  a l'ouverture de session Windows, sans fenetre noire.
REM    installer_demarrage_auto.bat          -> installe
REM    installer_demarrage_auto.bat retirer  -> retire
REM ==============================================================
chcp 65001 >nul
cd /d "%~dp0"
set "RACCOURCI=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Recherche immo.lnk"

if /i "%~1"=="retirer" (
  del "%RACCOURCI%" 2>nul
  echo Demarrage automatique retire.
  exit /b 0
)

powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:RACCOURCI);" ^
  "$s.TargetPath='%~dp0.venv\Scripts\pythonw.exe';" ^
  "$s.Arguments='\"%~dp0demarrage_auto.pyw\"';" ^
  "$s.WorkingDirectory='%~dp0';" ^
  "$s.Description='Recherche immo (demarrage automatique)';" ^
  "$s.Save()"
echo Demarrage automatique installe : l'application se lancera seule a chaque ouverture de session.
