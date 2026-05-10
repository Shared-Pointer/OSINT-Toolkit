# Scraper
## KNF - Ostrzeżenia publiczne
Robię scraping, bo Eurobozon API nie działa zupełnie, nie można wejść do dokumentacji.
Nie pozdrawiam państwa polskiego, które nic nie potrafi zrobić dobrze.

Ten scraper dotyczy listy publicznej ostrzeżeń KNF. Skrypt pobiera dane z tabeli na stronie https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne, ekstrahuje informacje o ostrzeżeniach (Lp., Nazwa firmy, KRS, Prokuratura, Data, Opis) i zapisuje je w formacie JSON do pliku `knfList.json`.

## Instalacja i uruchomienie
1. Tworzenie virtual environment
   `python3 -m venv .venv`
2. Aktywacja środowiska
   `source .venv/bin/activate`
3. Aktualizacja pip'a
   `pip install --upgrade pip`
4. Instalacja niezbędnych bibliotek
   `pip install -r requirements.txt`
5. Inicjalizacja Playwright
   `playwright install`
6. Uruchomienie skryptu
   `python3 main.py`

Po uruchomieniu dane zostaną wyświetlone na konsoli oraz zapisane do pliku `knfList.json`.