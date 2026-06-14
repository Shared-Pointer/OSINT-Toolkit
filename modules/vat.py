"""VAT scraper - Wykaz Podatników VAT (MF/KAS)."""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from urllib.parse import urljoin

import requests

PROD_URL = "https://wl-api.mf.gov.pl"


# Models

@dataclass
class EntityPerson:
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nip: Optional[str] = None
    company_name: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "EntityPerson":
        return cls(first_name=d.get("firstName"), last_name=d.get("lastName"),
                   nip=d.get("nip"), company_name=d.get("companyName"))

    def __str__(self) -> str:
        if self.company_name:
            return self.company_name
        return f"{self.first_name or ''} {self.last_name or ''}".strip()


@dataclass
class Entity:
    name: str
    nip: Optional[str] = None
    regon: Optional[str] = None
    krs: Optional[str] = None
    status_vat: Optional[str] = None
    residence_address: Optional[str] = None
    working_address: Optional[str] = None
    account_numbers: list[str] = field(default_factory=list)
    registration_legal_date: Optional[str] = None
    removal_date: Optional[str] = None
    representatives: list[EntityPerson] = field(default_factory=list)
    partners: list[EntityPerson] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Entity":
        return cls(
            name=d.get("name", ""),
            nip=d.get("nip"), regon=d.get("regon"), krs=d.get("krs"),
            status_vat=d.get("statusVat"),
            residence_address=d.get("residenceAddress"),
            working_address=d.get("workingAddress"),
            account_numbers=d.get("accountNumbers") or [],
            registration_legal_date=d.get("registrationLegalDate"),
            removal_date=d.get("removalDate"),
            representatives=[EntityPerson.from_dict(p) for p in d.get("representatives", [])],
            partners=[EntityPerson.from_dict(p) for p in d.get("partners", [])],
        )

    def to_dict(self) -> dict:
        return {
            "nip": self.nip, "regon": self.regon, "krs": self.krs,
            "nazwa": self.name, "status_vat": self.status_vat,
            "adres": self.working_address or self.residence_address,
            "rachunki_bankowe": self.account_numbers,
            "data_rejestracji": self.registration_legal_date,
            "data_wykreslenia": self.removal_date,
            "reprezentanci": [str(p) for p in self.representatives],
            "wspolnicy": [str(p) for p in self.partners],
        }


class VATApiError(Exception): pass


class WykazPodatnikowVATClient:
    def __init__(self, base_url: str = PROD_URL, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    def _get(self, path: str, params: dict) -> dict:
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        resp = self._session.get(url, params=params, timeout=self.timeout)
        if resp.status_code != 200:
            raise VATApiError(f"HTTP {resp.status_code}")
        return resp.json()

    def _today(self) -> str:
        return date.today().isoformat()

    def search_by_nip(self, nip: str) -> Optional[Entity]:
        data = self._get(f"/api/search/nip/{nip}", {"date": self._today()})
        subject = data.get("result", {}).get("subject")
        return Entity.from_dict(subject) if subject else None


# Module interface

def _is_nip(q: str) -> bool:
    return q.replace("-", "").replace(" ", "").isdigit() and len(q.replace("-", "").replace(" ", "")) == 10


def run(query: str, query_type: str = "auto") -> dict:
    try:
        client = WykazPodatnikowVATClient()

        if query_type == "nip" or (query_type == "auto" and _is_nip(query)):
            nip = query.replace("-", "").replace(" ", "")
            entity = client.search_by_nip(nip)
            if entity:
                return {"status": "ok", "data": entity.to_dict()}
            return {"status": "not_found", "data": {}}

        return {"status": "skipped", "error": "Moduł VAT wymaga NIP.", "data": {}}

    except VATApiError as e:
        return {"status": "error", "error": str(e), "data": {}}
    except Exception as e:
        return {"status": "error", "error": str(e), "data": {}}
