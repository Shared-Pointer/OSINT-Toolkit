#!/bin/bash
# OSINT Toolkit — uruchomienie (Mac / Linux)

if [ ! -d "venv" ]; then
    echo "Tworzenie środowiska wirtualnego..."
    python3 -m venv venv
    venv/bin/pip install -q -r requirements.txt
    venv/bin/playwright install chromium
fi

# CEIDG token (opcjonalny)
# export CEIDG_TOKEN=twoj_token_tutaj

echo "Uruchamianie OSINT Toolkit na http://localhost:5001"
venv/bin/python3 app.py
