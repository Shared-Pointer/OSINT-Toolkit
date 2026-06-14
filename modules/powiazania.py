"""Powiązania właścicielskie — struktura zarządu i powiązane podmioty z KRS."""

from __future__ import annotations
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed

import requests

KRS_API = "https://api-krs.ms.gov.pl/api/krs/OdpisAktualny"


def _get_krs_number(nip: str) -> str | None:
    """Pobiera numer KRS na podstawie NIP z VAT API."""
    try:
        from datetime import date
        r = requests.get(
            f"https://wl-api.mf.gov.pl/api/search/nip/{nip}",
            params={"date": date.today().isoformat()},
            timeout=10,
        )
        if not r.ok:
            return None
        krs = r.json().get("result", {}).get("subject", {}).get("krs")
        return krs if krs else None
    except Exception:
        return None


def _fetch_krs_data(krs: str) -> dict | None:
    """Pobiera odpis aktualny z KRS API."""
    try:
        r = requests.get(f"{KRS_API}/{krs.zfill(10)}?rejestr=P&format=json", timeout=15)
        if not r.ok:
            r = requests.get(f"{KRS_API}/{krs.zfill(10)}?rejestr=S&format=json", timeout=15)
        if not r.ok:
            return None
        return r.json().get("odpis", {}).get("dane", {})
    except Exception:
        return None


def _parse_board(dane: dict) -> dict:
    """Wyciąga strukturę zarządu, prokurentów i rady nadzorczej."""
    dzial2 = dane.get("dzial2", {})
    repr_section = dzial2.get("reprezentacja", {})

    sklad = repr_section.get("sklad", [])
    funkcje = Counter(s.get("funkcjaWOrganie", "brak funkcji") for s in sklad)

    prokurenci = dzial2.get("prokurenci", [])

    organy_nadzoru = []
    raw_nadzor = dzial2.get("organNadzoru", [])
    if isinstance(raw_nadzor, list):
        for org in raw_nadzor:
            organy_nadzoru.append({
                "nazwa": org.get("nazwa", "ORGAN NADZORU"),
                "liczba_czlonkow": len(org.get("sklad", [])),
            })

    return {
        "organ_reprezentacji": repr_section.get("nazwaOrganu", ""),
        "sposob_reprezentacji": repr_section.get("sposobReprezentacji", ""),
        "sklad": [{"funkcja": f, "liczba": n} for f, n in funkcje.items()],
        "prokurenci_liczba": len(prokurenci),
        "organy_nadzoru": organy_nadzoru,
    }


def _parse_company(dane: dict) -> dict:
    """Wyciąga dane rejestrowe i oddziały spółki."""
    dzial1 = dane.get("dzial1", {})
    podmiot = dzial1.get("danePodmiotu", {})
    kapital = dzial1.get("kapital", {})

    oddzialy_raw = dzial1.get("jednostkiTerenoweOddzialy", [])
    oddzialy = [o.get("nazwa", "") for o in oddzialy_raw if o.get("nazwa")]

    kap_val = kapital.get("wysokoscKapitaluZakladowego", {})

    return {
        "forma_prawna": podmiot.get("formaPrawna", ""),
        "kapital_zakladowy": f"{kap_val.get('wartosc', '')} {kap_val.get('waluta', '')}".strip(),
        "oddzialy": oddzialy,
    }


def _check_entity_in_knf_uokik(name: str) -> dict:
    """Sprawdza nazwę podmiotu w KNF i UOKiK."""
    from modules import knf, uokik
    results = {}

    with ThreadPoolExecutor(max_workers=2) as ex:
        f_knf = ex.submit(knf.run, name, "name")
        f_uokik = ex.submit(uokik.run, name, "name")

        for future, key in [(f_knf, "knf"), (f_uokik, "uokik")]:
            try:
                r = future.result(timeout=45)
                results[key] = {
                    "status": r.get("status"),
                    "count": len(r.get("data", {}).get("decisions", [])) if key == "uokik"
                             else (1 if r.get("data", {}).get("warnings") else 0),
                    "hit": r.get("status") == "ok" and bool(
                        r.get("data", {}).get("warnings") if key == "knf"
                        else r.get("data", {}).get("decisions")
                    ),
                }
            except Exception as e:
                results[key] = {"status": "error", "error": str(e), "hit": False, "count": 0}

    return results


# ── Module interface ──────────────────────────────────────────────────────────

def run(query: str, query_type: str = "nip") -> dict:
    nip = re.sub(r"[\s\-]", "", query)

    try:
        # Znajdz numer KRS przez VAT API
        krs = _get_krs_number(nip)
        if not krs:
            return {
                "status": "skipped",
                "error": "Brak numeru KRS — podmiot nie figuruje w rejestrze sądowym (może być JDG lub osoba fizyczna).",
                "data": {},
            }

        # Pobierz odpis z KRS
        dane = _fetch_krs_data(krs)
        if not dane:
            return {"status": "not_found", "data": {"krs": krs}}

        board = _parse_board(dane)
        company = _parse_company(dane)

        # Sprawdz oddzialy w KNF/UOKiK (nazwy firm sa jawne)
        branch_checks = {}
        branches_to_check = company["oddzialy"][:5]  # max 5 oddziałów
        if branches_to_check:
            with ThreadPoolExecutor(max_workers=3) as ex:
                futures = {ex.submit(_check_entity_in_knf_uokik, name): name for name in branches_to_check}
                for future in _as_completed(futures):
                    name = futures[future]
                    try:
                        branch_checks[name] = future.result(timeout=60)
                    except Exception:
                        branch_checks[name] = {}

        return {
            "status": "ok",
            "data": {
                "krs": krs,
                "forma_prawna": company["forma_prawna"],
                "kapital_zakladowy": company["kapital_zakladowy"],
                "board": board,
                "oddzialy": company["oddzialy"],
                "branch_checks": branch_checks,
                "note": "Imiona i nazwiska członków zarządu są anonimizowane przez API KRS (RODO). "
                        "Widoczna jest struktura organów i liczba osób.",
            },
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "data": {}}
