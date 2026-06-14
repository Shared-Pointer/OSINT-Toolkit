"""KRS module - api-krs.ms.gov.pl REST API."""

from __future__ import annotations
import re
from datetime import date

import requests

KRS_API = "https://api-krs.ms.gov.pl/api/krs/OdpisAktualny"
VAT_API = "https://wl-api.mf.gov.pl"


def _nip_to_krs(nip: str) -> str | None:
    try:
        r = requests.get(
            f"{VAT_API}/api/search/nip/{nip}",
            params={"date": date.today().isoformat()},
            timeout=10,
        )
        if not r.ok:
            return None
        return r.json().get("result", {}).get("subject", {}).get("krs") or None
    except Exception:
        return None


def _fetch_odpis(krs: str) -> dict | None:
    for rejestr in ("P", "S"):
        try:
            r = requests.get(
                f"{KRS_API}/{krs.zfill(10)}?rejestr={rejestr}&format=json",
                timeout=15,
            )
            if r.ok:
                return r.json().get("odpis", {}).get("dane", {})
        except Exception:
            continue
    return None


def _parse(dane: dict, krs: str) -> dict:
    dzial1 = dane.get("dzial1", {})
    podmiot = dzial1.get("danePodmiotu", {})
    identyf = podmiot.get("identyfikatory", {})
    siedziba = dzial1.get("siedzibaIAdres", {})
    adres = siedziba.get("adres", {})
    siedziba_m = siedziba.get("siedziba", {})
    kapital = dzial1.get("kapital", {})
    kap_val = kapital.get("wysokoscKapitaluZakladowego", {})

    ulica = adres.get("ulica", "")
    nr = adres.get("nrDomu", "")
    miasto = adres.get("miejscowosc", "") or siedziba_m.get("miejscowosc", "")
    kod = adres.get("kodPocztowy", "")
    adres_str = f"{ulica} {nr}, {kod} {miasto}".strip(" ,")

    return {
        "krs": krs.zfill(10),
        "nip": identyf.get("nip", ""),
        "regon": (identyf.get("regon") or "")[:9],
        "nazwa": podmiot.get("nazwa", ""),
        "forma_prawna": podmiot.get("formaPrawna", ""),
        "adres": adres_str,
        "kapital_zakladowy": f"{kap_val.get('wartosc', '')} {kap_val.get('waluta', '')}".strip(),
    }


# Module interface

def run(query: str, query_type: str = "nip") -> dict:
    nip = re.sub(r"[\s\-]", "", query)
    try:
        krs = _nip_to_krs(nip)
        if not krs:
            return {"status": "not_found", "data": {}}

        dane = _fetch_odpis(krs)
        if not dane:
            return {"status": "not_found", "data": {"krs": krs}}

        return {"status": "ok", "data": _parse(dane, krs)}
    except Exception as e:
        return {"status": "error", "error": str(e), "data": {}}
