"""
main_test.py – manualne testy wszystkich 8 metod WykazPodatnikowVATClient.

Każda sekcja odpowiada jednej metodzie klasy i drukuje czytelny wynik.
Używa środowiska PRODUKCYJNEGO (wl-api.mf.gov.pl) z publicznie dostępnymi danymi.

Dane testowe (publicznie znane, duże spółki):
  NIP  5260250274 – Ministerstwo Finansów / KAS (właściciel API)
  NIP  5270103391 – PKN ORLEN S.A.
  REGON 000002217 – Ministerstwo Finansów / KAS
  REGON 610188201 – PKN ORLEN S.A.
  Rachunek: pobrany dynamicznie z search_by_nip → pierwszy z listy

Uruchomienie:
  pip install requests
  python main_test.py
"""

from __future__ import annotations

import sys
from datetime import date

from vat_api import (
    EntityCheckResponse,
    EntityListResponse,
    EntityResponse,
    EntryListResponse,
    VATApiError,
    WykazPodatnikowVATClient,
    PROD_URL,
)

# ---------------------------------------------------------------------------
# Konfiguracja
# ---------------------------------------------------------------------------

TEST_DATE   = date.today()          # zapytania na dzisiaj
NIP_1       = "5260250274"          # Ministerstwo Finansów / KAS
NIP_2       = "5270103391"          # PKN ORLEN S.A.
REGON_1     = "000002217"           # Ministerstwo Finansów / KAS
REGON_2     = "610188201"           # PKN ORLEN S.A.

# Rachunek zostanie pobrany dynamicznie w sekcji 1 i użyty w dalszych testach.
FALLBACK_ACCOUNT = "68101010230000261395100000"  # konto zapasowe (BGK)

# ---------------------------------------------------------------------------
# Helpers do drukowania
# ---------------------------------------------------------------------------

SEPARATOR = "─" * 62


def header(nr: int, title: str) -> None:
    print(f"\n{'═' * 62}")
    print(f"  [{nr}/8]  {title}")
    print(f"{'═' * 62}")


def ok(label: str, value: object) -> None:
    print(f"  ✔  {label:<30} {value}")


def section(label: str) -> None:
    print(f"  {SEPARATOR}")
    print(f"  {label}")
    print(f"  {SEPARATOR}")


def print_entity(e, prefix: str = "") -> None:
    """Drukuje podstawowe pola Entity."""
    p = prefix
    print(f"{p}  Nazwa:          {e.name}")
    print(f"{p}  NIP:            {e.nip}")
    print(f"{p}  REGON:          {e.regon}")
    print(f"{p}  KRS:            {e.krs}")
    print(f"{p}  Status VAT:     {e.status_vat}")
    print(f"{p}  Adres siedziby: {e.residence_address}")
    print(f"{p}  Rachunki ({len(e.account_numbers)}):", end="")
    if e.account_numbers:
        print()
        for acc in e.account_numbers[:3]:
            print(f"{p}                  {acc}")
        if len(e.account_numbers) > 3:
            print(f"{p}                  … (+{len(e.account_numbers) - 3} więcej)")
    else:
        print(" brak")
    print(f"{p}  Repr. ({len(e.representatives)}):", end="")
    for r in e.representatives[:2]:
        print(f" {r.first_name} {r.last_name}", end="")
    print()


def print_request_meta(request_id, request_dt) -> None:
    print()
    ok("requestId:", request_id)
    ok("requestDateTime:", request_dt)


def run(label: str, fn):
    """Wywołuje fn(), obsługuje błędy, zwraca wynik lub None."""
    try:
        result = fn()
        return result
    except VATApiError as exc:
        print(f"  ✘ BŁĄD API: {exc}")
        return None
    except Exception as exc:
        print(f"  ✘ NIEOCZEKIWANY BŁĄD: {exc}")
        return None


# ---------------------------------------------------------------------------
# Główna funkcja testowa
# ---------------------------------------------------------------------------

def main() -> None:
    client = WykazPodatnikowVATClient(base_url=PROD_URL, timeout=15)
    print(f"\n  Klient VAT API – testy ({TEST_DATE})")
    print(f"  Endpoint: {PROD_URL}")

    # Rachunek wybrany dynamicznie (wypełniony po sekcji 3)
    dynamic_account: str = FALLBACK_ACCOUNT

    # -----------------------------------------------------------------------
    # 1. search_by_nip – pojedynczy NIP
    # -----------------------------------------------------------------------
    header(1, f"search_by_nip(nip={NIP_1!r})")
    resp: EntityResponse | None = run("search_by_nip", lambda: client.search_by_nip(NIP_1, TEST_DATE))
    if resp and resp.subject:
        s = resp.subject
        print_entity(s)
        if s.account_numbers:
            dynamic_account = s.account_numbers[0]
            print(f"\n  → Pobrany rachunek do dalszych testów: {dynamic_account}")
        print_request_meta(resp.request_id, resp.request_date_time)
    else:
        print("  Brak podmiotu w odpowiedzi.")

    # -----------------------------------------------------------------------
    # 2. search_by_nips – lista NIP (batch)
    # -----------------------------------------------------------------------
    header(2, f"search_by_nips(nips=[{NIP_1!r}, {NIP_2!r}])")
    resp2: EntryListResponse | None = run(
        "search_by_nips",
        lambda: client.search_by_nips([NIP_1, NIP_2], TEST_DATE),
    )
    if resp2:
        for entry in resp2.entries:
            section(f"identifier: {entry.identifier}")
            if entry.has_error:
                print(f"  ✘ [{entry.error_code}] {entry.error_message}")
            else:
                for subj in entry.subjects[:1]:   # pokazujemy pierwszego
                    print_entity(subj, prefix="  ")
        print_request_meta(resp2.request_id, resp2.request_date_time)

    # -----------------------------------------------------------------------
    # 3. search_by_regon – pojedynczy REGON
    # -----------------------------------------------------------------------
    header(3, f"search_by_regon(regon={REGON_1!r})")
    resp3: EntityResponse | None = run(
        "search_by_regon",
        lambda: client.search_by_regon(REGON_1, TEST_DATE),
    )
    if resp3 and resp3.subject:
        print_entity(resp3.subject)
        print_request_meta(resp3.request_id, resp3.request_date_time)
    else:
        print("  Brak podmiotu w odpowiedzi.")

    # -----------------------------------------------------------------------
    # 4. search_by_regons – lista REGON (batch)
    # -----------------------------------------------------------------------
    header(4, f"search_by_regons(regons=[{REGON_1!r}, {REGON_2!r}])")
    resp4: EntryListResponse | None = run(
        "search_by_regons",
        lambda: client.search_by_regons([REGON_1, REGON_2], TEST_DATE),
    )
    if resp4:
        for entry in resp4.entries:
            section(f"identifier: {entry.identifier}")
            if entry.has_error:
                print(f"  ✘ [{entry.error_code}] {entry.error_message}")
            else:
                for subj in entry.subjects[:1]:
                    print_entity(subj, prefix="  ")
        print_request_meta(resp4.request_id, resp4.request_date_time)

    # -----------------------------------------------------------------------
    # 5. search_by_bank_account – pojedynczy rachunek
    # -----------------------------------------------------------------------
    header(5, f"search_by_bank_account(bank_account={dynamic_account!r})")
    resp5: EntityListResponse | None = run(
        "search_by_bank_account",
        lambda: client.search_by_bank_account(dynamic_account, TEST_DATE),
    )
    if resp5:
        ok("Znalezionych podmiotów:", len(resp5.subjects))
        for subj in resp5.subjects[:1]:
            print_entity(subj)
        print_request_meta(resp5.request_id, resp5.request_date_time)

    # -----------------------------------------------------------------------
    # 6. search_by_bank_accounts – lista rachunków (batch)
    # -----------------------------------------------------------------------
    header(6, f"search_by_bank_accounts(bank_accounts=[{dynamic_account!r}])")
    resp6: EntryListResponse | None = run(
        "search_by_bank_accounts",
        lambda: client.search_by_bank_accounts([dynamic_account], TEST_DATE),
    )
    if resp6:
        for entry in resp6.entries:
            section(f"identifier: {entry.identifier}")
            if entry.has_error:
                print(f"  ✘ [{entry.error_code}] {entry.error_message}")
            else:
                ok("Podmiotów w wpisie:", len(entry.subjects))
                for subj in entry.subjects[:1]:
                    print_entity(subj, prefix="  ")
        print_request_meta(resp6.request_id, resp6.request_date_time)

    # -----------------------------------------------------------------------
    # 7. check_nip_bank_account – NIP + rachunek
    # -----------------------------------------------------------------------
    header(7, f"check_nip_bank_account(nip={NIP_1!r}, bank_account={dynamic_account!r})")
    resp7: EntityCheckResponse | None = run(
        "check_nip_bank_account",
        lambda: client.check_nip_bank_account(NIP_1, dynamic_account, TEST_DATE),
    )
    if resp7:
        ok("accountAssigned:", resp7.account_assigned)
        ok("is_assigned (bool):", resp7.is_assigned)
        print_request_meta(resp7.request_id, resp7.request_date_time)

    # -----------------------------------------------------------------------
    # 8. check_regon_bank_account – REGON + rachunek
    # -----------------------------------------------------------------------
    header(8, f"check_regon_bank_account(regon={REGON_1!r}, bank_account={dynamic_account!r})")
    resp8: EntityCheckResponse | None = run(
        "check_regon_bank_account",
        lambda: client.check_regon_bank_account(REGON_1, dynamic_account, TEST_DATE),
    )
    if resp8:
        ok("accountAssigned:", resp8.account_assigned)
        ok("is_assigned (bool):", resp8.is_assigned)
        print_request_meta(resp8.request_id, resp8.request_date_time)

    # -----------------------------------------------------------------------
    # Podsumowanie
    # -----------------------------------------------------------------------
    print(f"\n{'═' * 62}")
    print("  Wszystkie testy zakończone.")
    print(f"{'═' * 62}\n")


if __name__ == "__main__":
    main()
