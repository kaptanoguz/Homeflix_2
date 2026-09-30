#!/bin/bash
# Homeflix 2 — başlatıcı
#   ./run.sh              uygulama penceresiyle açar
#   ./run.sh --browser    varsayılan tarayıcıda açar
#   ./run.sh --headless   sadece sunucu (ekransız / arka plan)
cd "$(dirname "$0")" || exit 1
PORT="${HOMEFLIX_PORT:-5000}"

if [ ! -x venv/bin/python ]; then
    echo "İlk kurulum yapılıyor…"
    /usr/bin/python3 -m venv --system-site-packages venv || exit 1
    venv/bin/pip install -q -r requirements.txt || exit 1
fi

pkill -f "python.*Homeflix_Linux/app.py" 2>/dev/null
# homeflix.service çalışıyorsa app.py yalnızca pencereyi açar
exec venv/bin/python app.py "$@"
