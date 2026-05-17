"""
main_test_ceidg.py – manualne testy wszystkich 8 metod CEIDGClient.

Uruchomienie:
    pip install requests
    export CEIDG_TOKEN="eyJhbGci..."
    python main_test_ceidg.py
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

from ceidg_api import (
    CEIDGClient,
    CeidgApiError,
    CeidgApiAuthError,
    CeidgApiRateLimitError,
    PROD_URL,
    STATUS_AKTYWNY,
)

# ---------------------------------------------------------------------------
# Konfiguracja – uzupełnij przed uruchomieniem
# ---------------------------------------------------------------------------

TOKEN = os.environ.get("CEIDG_TOKEN", "eyJraWQ...")

# Wpisz znajomy NIP i REGON JDG – używane w testach [3] i [4]
TEST_NIP   = "8311198801"   # <- podmień
TEST_REGON = "100175340"    # <- podmień

# Zakres dat do testu /zmiana
DATE_TO   = date.today().isoformat()
DATE_FROM = (date.today() - timedelta(days=3)).isoformat()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEP = "─" * 62


def header(nr: int, title: str) -> None:
    print(f"\n{'═' * 62}")
    print(f"  [{nr}/8]  {title}")
    print(f"{'═' * 62}")


def ok(label: str, value: object) -> None:
    val = str(value) if value is not None else "—"
    print(f"  ✔  {label:<32} {val}")


def info(msg: str) -> None:
    print(f"  ℹ  {msg}")


def err(msg: str) -> None:
    print(f"  ✘  {msg}")


def print_firm(f, list_mode: bool = False) -> None:
    print(f"  Nazwa:          {f.nazwa or '—'}")
    if list_mode:
        print(f"  NIP/REGON:      (niedostępne w trybie listy – użyj get_firm_by_id)")
    else:
        print(f"  NIP:            {f.nip or '—'}")
        print(f"  REGON:          {f.regon or '—'}")
    name_part = f"{f.imie or ''} {f.nazwisko or ''}".strip()
    if name_part:
        print(f"  Właściciel:     {name_part}")
    print(f"  Status:         {f.status or '—'}")
    if f.adres_dzialalnosci:
        print(f"  Adres:          {f.adres_dzialalnosci}")
    if f.pkd_przewazajacy:
        pkd = f.pkd_przewazajacy
        print(f"  PKD główne:     {pkd.kod} – {pkd.opis or '—'}")
    if f.email:
        print(f"  e-mail:         {f.email}")
    if f.www:
        print(f"  WWW:            {f.www}")
    print(f"  Data rozp.:     {f.data_rozpoczecia or '—'}")
    if f.w_spolce_cywilnej:
        print(f"  Spółka cyw.:    TAK")
    if f.id:
        print(f"  UUID wpisu:     {f.id}")


def run(fn):
    try:
        return fn()
    except CeidgApiAuthError as e:
        err(f"BŁĄD AUTORYZACJI: {e}")
    except CeidgApiRateLimitError as e:
        err(f"LIMIT ZAPYTAŃ: {e}")
    except CeidgApiError as e:
        err(f"BŁĄD API: {e}")
    except Exception as e:
        err(f"NIEOCZEKIWANY BŁĄD: {e}")
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if TOKEN == "WSTAW_TOKEN_TUTAJ":
        print("\n  ⚠  Brak tokenu JWT.")
        print("  Ustaw zmienną środowiskową CEIDG_TOKEN lub edytuj TOKEN w pliku.\n")
        sys.exit(1)

    client = CEIDGClient(token=TOKEN, base_url=PROD_URL)
    print(f"\n  Klient CEIDG API v3 – testy ({date.today()})")
    print(f"  Endpoint: {PROD_URL}")

    # -----------------------------------------------------------------------
    # 1. search_firms – lista aktywnych firm
    # -----------------------------------------------------------------------
    header(1, "search_firms(status=['AKTYWNY'], limit=3)")
    result = run(lambda: client.search_firms(status=[STATUS_AKTYWNY], limit=3))
    if result:
        total_info = str(result.total) if result.total is not None else "nieznana (API zwraca null)"
        ok("Łącznie wyników:", total_info)
        ok("Firm na tej stronie:", len(result.firms))
        info("/firmy celowo nie zwraca NIP/REGON – to ograniczenie API v3")
        for f in result.firms[:2]:
            print(f"  {SEP}")
            print_firm(f, list_mode=True)

    # UUID z [1] do testów [5] i [6]
    uuid_1 = result.firms[0].id if result and result.firms else None
    uuid_2 = result.firms[1].id if result and len(result.firms) > 1 else None

    # -----------------------------------------------------------------------
    # 2. search_firms – wyszukiwanie po nazwisku
    # -----------------------------------------------------------------------
    header(2, "search_firms(nazwisko='Kowalski', status=['AKTYWNY'], limit=2)")
    result2 = run(lambda: client.search_firms(
        nazwisko="Kowalski", status=[STATUS_AKTYWNY], limit=2,
    ))
    if result2:
        ok("Znaleziono (łącznie):", str(result2.total) if result2.total is not None else "nieznana")
        for f in result2.firms[:1]:
            print(f"  {SEP}")
            print_firm(f, list_mode=True)

    # -----------------------------------------------------------------------
    # 3. get_firm_by_nip – stały, znany NIP
    # -----------------------------------------------------------------------
    header(3, f"get_firm_by_nip(nip={TEST_NIP!r})")
    firm3 = run(lambda: client.get_firm_by_nip(TEST_NIP))
    if firm3:
        print_firm(firm3)
    else:
        print("  Brak wyników.")

    # -----------------------------------------------------------------------
    # 4. get_firm_by_regon – stały, znany REGON
    # -----------------------------------------------------------------------
    header(4, f"get_firm_by_regon(regon={TEST_REGON!r})")
    firm4 = run(lambda: client.get_firm_by_regon(TEST_REGON))
    if firm4:
        print_firm(firm4)
    else:
        print("  Brak wyników.")

    # -----------------------------------------------------------------------
    # 5. get_firm_by_id – UUID pobrany z [1]
    # -----------------------------------------------------------------------
    header(5, f"get_firm_by_id(id={uuid_1!r})")
    if uuid_1:
        firm5 = run(lambda: client.get_firm_by_id(uuid_1))
        if firm5:
            print_firm(firm5)
        else:
            print("  Brak wyników.")
    else:
        info("Pominięto – brak UUID z kroku [1]")

    # -----------------------------------------------------------------------
    # 6. get_firms_by_ids – dwa UUID z [1]
    # -----------------------------------------------------------------------
    ids_batch = [i for i in [uuid_1, uuid_2] if i]
    header(6, f"get_firms_by_ids – {len(ids_batch)} UUID")
    if ids_batch:
        info("API v3 nie obsługuje batch ids[] – metoda robi kolejne wywołania get_firm_by_id")
        firms6 = run(lambda: client.get_firms_by_ids(ids_batch))
        if firms6 is not None:
            ok("Znaleziono firm:", len(firms6))
            for f in firms6:
                print(f"  {SEP}")
                print_firm(f)
    else:
        info("Pominięto – brak UUID z kroku [1]")

    # -----------------------------------------------------------------------
    # 7. get_changes – zmiany w ostatnich 3 dniach
    # -----------------------------------------------------------------------
    header(7, f"get_changes(dataod={DATE_FROM!r}, datado={DATE_TO!r}, limit=3)")
    info("Próba 1: /zmiana  |  fallback: /firmy z aktod/aktdo")
    changes = run(lambda: client.get_changes(dataod=DATE_FROM, datado=DATE_TO, limit=3))
    if changes is not None:
        ok("Zmienionych wpisów łącznie:", str(changes.total) if changes.total is not None else "nieznana")
        ok("Na tej stronie:", len(changes.firms))
        for f in changes.firms[:1]:
            print(f"  {SEP}")
            print_firm(f, list_mode=True)

    # -----------------------------------------------------------------------
    # 8. list_reports + download_report
    # -----------------------------------------------------------------------
    header(8, "list_reports() + download_report()")
    reports = run(lambda: client.list_reports())
    if reports is not None:
        ok("Dostępnych raportów:", len(reports))
        if reports:
            r = reports[0]
            ok("Pierwszy raport – id:", r.id)
            ok("Nazwa:", r.name)
            ok("URL:", r.url)
            print(f"\n  Pobieranie raportu {r.id!r}...")
            content = run(lambda: client.download_report(r.id))
            if content:
                ok("Rozmiar:", f"{len(content):,} bajtów")
                # with open(f"raport_{r.id}.zip", "wb") as fh:
                #     fh.write(content)
                print("  (Zapis na dysk pominięty)")
        else:
            print("  Brak dostępnych raportów.")

    # -----------------------------------------------------------------------
    print(f"\n{'═' * 62}")
    print("  Wszystkie testy zakończone.")
    print(f"{'═' * 62}\n")


if __name__ == "__main__":
    main()
