#!/usr/bin/env bash
# Porneste dashboard-ul UGC Raphael Travel, local, gratis.
# Ruleaza asta de fiecare data cand vrei sa deschizi dashboard-ul:
#   ./scripts/start_dashboard.sh
# (prima data, poate trebui: chmod +x scripts/start_dashboard.sh)
set -e
cd "$(dirname "$0")/.."

echo "Raphael Travel -- pornire dashboard UGC"
echo "----------------------------------------"

if [ -d ".git" ]; then
  echo "Verific actualizari din GitHub..."
  git pull --ff-only || echo "(n-am putut actualiza automat -- continui cu codul local existent; verifica manual cu 'git status' daca ai schimbari locale ce blocheaza pull-ul)"
  echo ""
fi

if ! command -v python3 &> /dev/null; then
  echo "Python 3 nu e instalat."
  echo "Descarca de la: https://www.python.org/downloads/"
  exit 1
fi

if ! command -v ffmpeg &> /dev/null; then
  echo "ATENTIE: ffmpeg nu pare instalat sau nu e in PATH."
  echo "  Mac:    brew install ffmpeg"
  echo "  Linux:  sudo apt-get install ffmpeg"
  echo "Continui oricum -- generarea video va da eroare pana il instalezi."
  echo ""
fi

if [ ! -d ".venv" ]; then
  echo "Creez mediul virtual Python (.venv, o singura data)..."
  python3 -m venv .venv
fi

source .venv/bin/activate
echo "Instalez/actualizez dependintele Python..."
pip install --quiet --disable-pip-version-check -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

if ! grep -Eq "^ELEVENLABS_API_KEY=.+" .env; then
  echo ""
  echo "======================================================================"
  echo " Lipseste cheia ElevenLabs din .env."
  echo " Se deschide fisierul .env -- pune cheia ta dupa ELEVENLABS_API_KEY="
  echo " (o iei din contul ElevenLabs, workspace-ul Global -> Developers -> API Keys),"
  echo " salvezi, apoi ruleaza din nou acest script."
  echo "======================================================================"
  { open .env 2>/dev/null || xdg-open .env 2>/dev/null; } || echo "Deschide manual fisierul .env din folderul proiectului cu un editor de text."
  exit 0
fi

if ! grep -Eq "^ANTHROPIC_API_KEY=.+" .env; then
  echo "(info: ANTHROPIC_API_KEY lipseste -- totul functioneaza, doar 'Lipeste text liber' din formular nu merge fara ea.)"
fi

echo ""
echo "Pornesc dashboard-ul pe http://localhost:8000 ..."
echo "(lasa fereastra asta deschisa cat timp folosesti dashboard-ul; Ctrl+C ca sa opresti)"
( sleep 2; { open http://localhost:8000 2>/dev/null || xdg-open http://localhost:8000 2>/dev/null; } || true ) &

PYTHONPATH=src uvicorn travel_ugc.web.app:app --port 8000
