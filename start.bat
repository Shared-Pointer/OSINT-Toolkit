@echo off
REM OSINT Toolkit — uruchomienie (Windows)

if not exist venv (
    echo Tworzenie srodowiska wirtualnego...
    python -m venv venv
    venv\Scripts\pip install -q -r requirements.txt
    venv\Scripts\playwright install chromium
)

REM CEIDG token (opcjonalny)
REM set CEIDG_TOKEN=twoj_token_tutaj

echo Uruchamianie OSINT Toolkit na http://localhost:5001
venv\Scripts\python app.py
