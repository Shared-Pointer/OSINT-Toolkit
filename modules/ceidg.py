"""CEIDG module — wrapper + full API client (JDG only)."""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Any, Optional
import requests

PROD_URL = "https://dane.biznes.gov.pl"
ZRODLO_CEIDG = "CEIDG"

# ── Models ──────────────────────────────────────────────────────────────────

@dataclass
class Address:
    ulica: Optional[str] = None
    budynek: Optional[str] = None
    lokal: Optional[str] = None
    miasto: Optional[str] = None
    kod: Optional[str] = None
    wojewodztwo: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Address":
        return cls(
            ulica=d.get("ulica"), budynek=d.get("budynek"), lokal=d.get("lokal"),
            miasto=d.get("miasto"), kod=d.get("kod"), wojewodztwo=d.get("wojewodztwo"),
        )

    def __str__(self) -> str:
        parts = filter(None, [
            f"ul. {self.ulica} {self.budynek or ''}".strip() if self.ulica else None,
            f"lok. {self.lokal}" if self.lokal else None,
            f"{self.kod} {self.miasto}" if self.miasto else None,
            self.wojewodztwo,
        ])
        return ", ".join(parts)


@dataclass
class PkdCode:
    kod: Optional[str] = None
    opis: Optional[str] = None
    przewazajacy: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "PkdCode":
        return cls(kod=d.get("kod"), opis=d.get("opis"), przewazajacy=bool(d.get("przewazajacy", False)))


@dataclass
class Firm:
    id: Optional[str] = None
    nip: Optional[str] = None
    regon: Optional[str] = None
    imie: Optional[str] = None
    nazwisko: Optional[str] = None
    nazwa: Optional[str] = None
    status: Optional[str] = None
    data_rozpoczecia: Optional[str] = None
    data_zawieszenia: Optional[str] = None
    data_wykreslenia: Optional[str] = None
    adres_dzialalnosci: Optional[Address] = None
    email: Optional[str] = None
    www: Optional[str] = None
    telefon: Optional[str] = None
    pkd: list[PkdCode] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Firm":
        addr_raw = d.get("adresDzialalnosci") or d.get("adresDzialanosci")
        pkd_list = [PkdCode.from_dict(p) for p in d.get("pkd", [])]
        return cls(
            id=d.get("id"), nip=d.get("nip"), regon=d.get("regon"),
            imie=d.get("imie"), nazwisko=d.get("nazwisko"), nazwa=d.get("nazwa"),
            status=d.get("status"),
            data_rozpoczecia=d.get("dataRozpoczecia"),
            data_zawieszenia=d.get("dataZawieszenia"),
            data_wykreslenia=d.get("dataWykreslenia"),
            adres_dzialalnosci=Address.from_dict(addr_raw) if addr_raw else None,
            email=d.get("email"), www=d.get("www"), telefon=d.get("telefon"),
            pkd=pkd_list,
        )

    def to_dict(self) -> dict:
        pkd_prev = next((p for p in self.pkd if p.przewazajacy), self.pkd[0] if self.pkd else None)
        return {
            "nip": self.nip, "regon": self.regon,
            "nazwa": self.nazwa or f"{self.imie} {self.nazwisko}".strip(),
            "status": self.status,
            "data_rozpoczecia": self.data_rozpoczecia,
            "data_zawieszenia": self.data_zawieszenia,
            "data_wykreslenia": self.data_wykreslenia,
            "adres": str(self.adres_dzialalnosci) if self.adres_dzialalnosci else None,
            "email": self.email, "www": self.www, "telefon": self.telefon,
            "pkd_przewazajacy": f"{pkd_prev.kod} – {pkd_prev.opis}" if pkd_prev else None,
            "pkd_all": [f"{p.kod} – {p.opis}" for p in self.pkd],
        }


class CeidgApiError(Exception): pass
class CeidgApiAuthError(CeidgApiError): pass
class CeidgApiRateLimitError(CeidgApiError): pass


class CEIDGClient:
    def __init__(self, token: Optional[str] = None, base_url: str = PROD_URL, timeout: int = 30):
        resolved = token or os.environ.get("CEIDG_TOKEN")
        if not resolved:
            raise CeidgApiAuthError("Brak tokenu CEIDG_TOKEN.")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {resolved}", "Accept": "application/json"})

    def _get(self, path: str, params: dict | None = None) -> Any:
        resp = self._session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        if resp.status_code == 401: raise CeidgApiAuthError("Nieprawidłowy token (401).")
        if resp.status_code == 429: raise CeidgApiRateLimitError("Rate limit (429).")
        if resp.status_code == 204 or not resp.content: return {}
        if not resp.ok:
            raise CeidgApiError(f"HTTP {resp.status_code}")
        return resp.json()

    @staticmethod
    def _extract_firm_raw(data):
        if isinstance(data, list):
            return data[0] if data and isinstance(data[0], dict) else None
        if isinstance(data, dict):
            nested = data.get("firma")
            if nested is not None:
                if isinstance(nested, list):
                    return nested[0] if nested else None
                return nested
            if data.get("id") or data.get("nip"):
                return data
        return None

    def get_firm_by_nip(self, nip: str) -> Optional[Firm]:
        data = self._get("/api/ceidg/v3/firma", {"nip": nip})
        raw = self._extract_firm_raw(data)
        return Firm.from_dict(raw) if raw else None

    def search_firms(self, nazwa: Optional[str] = None, limit: int = 10, page: int = 1) -> list[Firm]:
        params: dict = {"zrodlo": ZRODLO_CEIDG, "limit": limit, "page": page}
        if nazwa: params["nazwa"] = nazwa
        data = self._get("/api/ceidg/v3/firmy", params)
        raw_firms = data.get("firmy") or data.get("wpisy") or []
        return [Firm.from_dict(f) for f in raw_firms]


# ── Module interface ─────────────────────────────────────────────────────────

def _is_nip(q: str) -> bool:
    return q.replace("-", "").replace(" ", "").isdigit() and len(q.replace("-", "").replace(" ", "")) == 10


def run(query: str, query_type: str = "auto") -> dict:
    token = os.environ.get("CEIDG_TOKEN", "")
    if not token:
        return {"status": "no_token", "error": "Brak zmiennej CEIDG_TOKEN", "data": {}}

    try:
        client = CEIDGClient(token=token)
        nip = query.replace("-", "").replace(" ", "")

        if query_type == "nip" or (query_type == "auto" and _is_nip(query)):
            firm = client.get_firm_by_nip(nip)
            if firm:
                return {"status": "ok", "data": firm.to_dict()}
            return {"status": "not_found", "data": {}}

        firms = client.search_firms(nazwa=query, limit=5)
        return {
            "status": "ok" if firms else "not_found",
            "data": {"firms": [f.to_dict() for f in firms]},
        }
    except CeidgApiAuthError as e:
        return {"status": "no_token", "error": str(e), "data": {}}
    except Exception as e:
        return {"status": "error", "error": str(e), "data": {}}
