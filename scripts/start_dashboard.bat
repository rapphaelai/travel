@echo off
REM Porneste dashboard-ul UGC Raphael Travel, local, gratis.
REM Ruleaza asta (dublu-clic) de fiecare data cand vrei sa deschizi dashboard-ul.

setlocal
cd /d "%~dp0.."

echo Raphael Travel -- pornire dashboard UGC
echo ----------------------------------------

where python >nul 2>nul
if errorlevel 1 (
  echo Python nu e instalat sau nu e in PATH.
  echo Descarca de la: https://www.python.org/downloads/
  echo IMPORTANT: bifeaza "Add python.exe to PATH" la instalare.
  pause
  exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo ATENTIE: ffmpeg nu pare instalat sau nu e in PATH.
  echo   Instaleaza cu: winget install ffmpeg
  echo Continui oricum -- generarea video va da eroare pana il instalezi.
  echo.
)

if not exist ".venv" (
  echo Creez mediul virtual Python ^(.venv, o singura data^)...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
echo Instalez/actualizez dependintele Python...
pip install --quiet --disable-pip-version-check -r requirements.txt

if not exist ".env" (
  copy .env.example .env >nul
)

findstr /r /c:"^ELEVENLABS_API_KEY=..*" .env >nul 2>nul
if errorlevel 1 (
  echo.
  echo ======================================================================
  echo  Lipseste cheia ElevenLabs din .env.
  echo  Se deschide fisierul .env -- pune cheia ta dupa ELEVENLABS_API_KEY=
  echo  ^(o iei din contul ElevenLabs, workspace-ul Global -^> Developers -^> API Keys^),
  echo  salvezi fisierul, apoi ruleaza din nou acest fisier ^(dublu-clic^).
  echo ======================================================================
  notepad .env
  pause
  exit /b 0
)

echo.
echo Pornesc dashboard-ul pe http://localhost:8000 ...
echo (lasa fereastra asta deschisa cat timp folosesti dashboard-ul; Ctrl+C ca sa opresti)
start "" http://localhost:8000

set PYTHONPATH=src
uvicorn travel_ugc.web.app:app --port 8000

pause
