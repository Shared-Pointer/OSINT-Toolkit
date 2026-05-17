"""
Klient API Wykazu Podatników VAT – Ministerstwo Finansów / KAS
Dokumentacja: https://wl-api.mf.gov.pl/
Wersja API: 1.6.0

Metody:
  search_by_bank_account        – GET /api/search/bank-account/{bank-account}
  search_by_bank_accounts       – GET /api/search/bank-accounts/{bank-accounts}
  search_by_nip                 – GET /api/search/nip/{nip}
  search_by_nips                – GET /api/search/nips/{nips}
  search_by_regon               – GET /api/search/regon/{regon}
  search_by_regons              – GET /api/search/regons/{regons}
  check_nip_bank_account        – GET /api/check/nip/{nip}/bank-account/{bank-account}
  check_regon_bank_account      – GET /api/check/regon/{regon}/bank-account/{bank-account}

Limity:
  • search – 100 zapytań/dzień, maks. 30 podmiotów jednocześnie
  • check  – 5 000 podmiotów/dzień
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional
from urllib.parse import urljoin

import requests

# ---------------------------------------------------------------------------
# Stałe
# ---------------------------------------------------------------------------

PROD_URL = "https://wl-api.mf.gov.pl"
TEST_URL = "https://wl-test.mf.gov.pl"

MAX_BATCH = 30  # maksymalna liczba identyfikatorów w zapytaniu batch


# ---------------------------------------------------------------------------
# Modele danych (dataclassy)
# ---------------------------------------------------------------------------


@dataclass
class EntityPerson:
    """Osoba powiązana z podmiotem (reprezentant, prokurent, wspólnik)."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nip: Optional[str] = None
    pesel: Optional[str] = None
    company_name: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "EntityPerson":
        return cls(
            first_name=d.get("firstName"),
            last_name=d.get("lastName"),
            nip=d.get("nip"),
            pesel=d.get("pesel"),
            company_name=d.get("companyName"),
        )


@dataclass
class Entity:
    """Pełne dane podmiotu z Wykazu Podatników VAT."""
    name: str
    nip: Optional[str] = None
    regon: Optional[str] = None
    pesel: Optional[str] = None
    krs: Optional[str] = None
    status_vat: Optional[str] = None          # Czynny | Zwolniony | Niezarejestrowany
    residence_address: Optional[str] = None
    working_address: Optional[str] = None
    account_numbers: list[str] = field(default_factory=list)
    has_virtual_accounts: Optional[bool] = None
    registration_legal_date: Optional[str] = None
    registration_denial_date: Optional[str] = None
    registration_denial_basis: Optional[str] = None
    restoration_date: Optional[str] = None
    restoration_basis: Optional[str] = None
    removal_date: Optional[str] = None
    removal_basis: Optional[str] = None
    exemption_sme_date: Optional[str] = None
    representatives: list[EntityPerson] = field(default_factory=list)
    authorized_clerks: list[EntityPerson] = field(default_factory=list)
    partners: list[EntityPerson] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Entity":
        def persons(key: str) -> list[EntityPerson]:
            return [EntityPerson.from_dict(p) for p in d.get(key, [])]

        return cls(
            name=d.get("name", ""),
            nip=d.get("nip"),
            regon=d.get("regon"),
            pesel=d.get("pesel"),
            krs=d.get("krs"),
            status_vat=d.get("statusVat"),
            residence_address=d.get("residenceAddress"),
            working_address=d.get("workingAddress"),
            account_numbers=d.get("accountNumbers") or [],
            has_virtual_accounts=d.get("hasVirtualAccounts"),
            registration_legal_date=d.get("registrationLegalDate"),
            registration_denial_date=d.get("registrationDenialDate"),
            registration_denial_basis=d.get("registrationDenialBasis"),
            restoration_date=d.get("restorationDate"),
            restoration_basis=d.get("restorationBasis"),
            removal_date=d.get("removalDate"),
            removal_basis=d.get("removalBasis"),
            exemption_sme_date=d.get("exemptionSmeDate"),
            representatives=persons("representatives"),
            authorized_clerks=persons("authorizedClerks"),
            partners=persons("partners"),
        )


@dataclass
class EntityResponse:
    """Odpowiedź na zapytanie o pojedynczy podmiot (search)."""
    subject: Optional[Entity]
    request_id: Optional[str]
    request_date_time: Optional[str]

    @classmethod
    def from_dict(cls, data: dict) -> "EntityResponse":
        result = data.get("result", {})
        subject_raw = result.get("subject")
        return cls(
            subject=Entity.from_dict(subject_raw) if subject_raw else None,
            request_id=result.get("requestId"),
            request_date_time=result.get("requestDateTime"),
        )


@dataclass
class EntityListResponse:
    """Odpowiedź na zapytanie o podmiot po numerze rachunku (search – single)."""
    subjects: list[Entity]
    request_id: Optional[str]
    request_date_time: Optional[str]

    @classmethod
    def from_dict(cls, data: dict) -> "EntityListResponse":
        result = data.get("result", {})
        return cls(
            subjects=[Entity.from_dict(s) for s in result.get("subjects", [])],
            request_id=result.get("requestId"),
            request_date_time=result.get("requestDateTime"),
        )


@dataclass
class EntryItem:
    """Pojedynczy wpis w odpowiedzi batch (identifier + podmioty lub błąd)."""
    identifier: str
    subjects: list[Entity] = field(default_factory=list)
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def has_error(self) -> bool:
        return self.error_code is not None

    @classmethod
    def from_dict(cls, d: dict) -> "EntryItem":
        error = d.get("error")
        return cls(
            identifier=d.get("identifier", ""),
            subjects=[Entity.from_dict(s) for s in d.get("subjects", [])],
            error_code=error.get("code") if error else None,
            error_message=error.get("message") if error else None,
        )


@dataclass
class EntryListResponse:
    """Odpowiedź na zapytanie batch (wiele NIP / REGON / rachunków)."""
    entries: list[EntryItem]
    request_id: Optional[str]
    request_date_time: Optional[str]

    @classmethod
    def from_dict(cls, data: dict) -> "EntryListResponse":
        result = data.get("result", {})
        return cls(
            entries=[EntryItem.from_dict(e) for e in result.get("entries", [])],
            request_id=result.get("requestId"),
            request_date_time=result.get("requestDateTime"),
        )


@dataclass
class EntityCheckResponse:
    """Odpowiedź na zapytanie check (TAK / NIE)."""
    account_assigned: Optional[str]   # "TAK" lub "NIE"
    request_id: Optional[str]
    request_date_time: Optional[str]

    @property
    def is_assigned(self) -> bool:
        """True jeżeli rachunek jest przypisany do podmiotu."""
        return (self.account_assigned or "").upper() == "TAK"

    @classmethod
    def from_dict(cls, data: dict) -> "EntityCheckResponse":
        result = data.get("result", {})
        return cls(
            account_assigned=result.get("accountAssigned"),
            request_id=result.get("requestId"),
            request_date_time=result.get("requestDateTime"),
        )


# ---------------------------------------------------------------------------
# Wyjątki
# ---------------------------------------------------------------------------


class VATApiError(Exception):
    """Ogólny błąd klienta API."""


class VATApiHTTPError(VATApiError):
    """Błąd HTTP zwrócony przez serwer (status != 200)."""

    def __init__(self, status_code: int, message: str, code: str = ""):
        self.status_code = status_code
        self.api_code = code
        super().__init__(f"HTTP {status_code} [{code}]: {message}")


class VATApiValidationError(VATApiError):
    """Błąd walidacji parametrów po stronie klienta."""


# ---------------------------------------------------------------------------
# Pomocnicze funkcje walidacji
# ---------------------------------------------------------------------------


def _today_str() -> str:
    return date.today().isoformat()


def _format_date(d: date | str | None) -> str:
    if d is None:
        return _today_str()
    if isinstance(d, date):
        return d.isoformat()
    # zakładamy format YYYY-MM-DD
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(d)):
        raise VATApiValidationError(
            f"Nieprawidłowy format daty: '{d}'. Oczekiwany: YYYY-MM-DD"
        )
    return str(d)


def _validate_batch(items: list[str], label: str) -> None:
    if not items:
        raise VATApiValidationError(f"Lista {label} nie może być pusta.")
    if len(items) > MAX_BATCH:
        raise VATApiValidationError(
            f"Lista {label} może zawierać maks. {MAX_BATCH} elementów "
            f"(podano {len(items)})."
        )


# ---------------------------------------------------------------------------
# Główna klasa klienta
# ---------------------------------------------------------------------------


class WykazPodatnikowVATClient:
    """
    Klient REST API Wykazu Podatników VAT (MF / KAS), v1.6.0.

    Parametry:
        base_url    – adres bazowy API (domyślnie: środowisko produkcyjne).
        timeout     – timeout HTTP w sekundach (domyślnie 30).
        session     – opcjonalny obiekt requests.Session (np. z własnym retry).

    Przykład użycia::

        from vat_api import WykazPodatnikowVATClient

        client = WykazPodatnikowVATClient()

        # Szukaj po NIP na dzisiaj
        resp = client.search_by_nip("1234567890")
        print(resp.subject.name, resp.subject.status_vat)

        # Sprawdź czy rachunek należy do firmy o danym NIP
        check = client.check_nip_bank_account(
            nip="1234567890",
            bank_account="12345678901234567890123456"
        )
        print(check.is_assigned)   # True / False
    """

    def __init__(
        self,
        base_url: str = PROD_URL,
        timeout: int = 30,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    # ------------------------------------------------------------------
    # Wewnętrzna metoda HTTP
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any]) -> dict:
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        try:
            response = self._session.get(url, params=params, timeout=self.timeout)
        except requests.ConnectionError as exc:
            raise VATApiError(f"Błąd połączenia z API: {exc}") from exc
        except requests.Timeout as exc:
            raise VATApiError(f"Przekroczono czas oczekiwania na odpowiedź API.") from exc

        if response.status_code != 200:
            try:
                body = response.json()
                msg = body.get("message", response.text)
                code = body.get("code", "")
            except Exception:
                msg = response.text
                code = ""
            raise VATApiHTTPError(response.status_code, msg, code)

        return response.json()

    # ------------------------------------------------------------------
    # 1. Szukaj po numerze rachunku bankowego (pojedynczy rachunek)
    #    GET /api/search/bank-account/{bank-account}
    # ------------------------------------------------------------------

    def search_by_bank_account(
        self,
        bank_account: str,
        date: date | str | None = None,
    ) -> EntityListResponse:
        """
        Wyszukuje podmioty powiązane z jednym numerem rachunku bankowego.

        Parametry:
            bank_account – numer rachunku (26 cyfr, bez spacji).
            date         – dzień, na który ma być udzielona odpowiedź
                           (format: YYYY-MM-DD lub obiekt date; domyślnie: dziś).

        Zwraca:
            EntityListResponse z listą podmiotów i kluczem requestId.
        """
        data = self._get(
            f"/api/search/bank-account/{bank_account}",
            {"date": _format_date(date)},
        )
        return EntityListResponse.from_dict(data)

    # ------------------------------------------------------------------
    # 2. Szukaj po wielu numerach rachunków bankowych (batch, maks. 30)
    #    GET /api/search/bank-accounts/{bank-accounts}
    # ------------------------------------------------------------------

    def search_by_bank_accounts(
        self,
        bank_accounts: list[str],
        date: date | str | None = None,
    ) -> EntryListResponse:
        """
        Wyszukuje podmioty po liście numerów rachunków bankowych (maks. 30).

        Parametry:
            bank_accounts – lista numerów rachunków (maks. 30 pozycji).
            date          – dzień na jaki ma być udzielona odpowiedź
                            (format: YYYY-MM-DD lub obiekt date; domyślnie: dziś).

        Zwraca:
            EntryListResponse z wpisami per-rachunek.
        """
        _validate_batch(bank_accounts, "rachunków bankowych")
        joined = ",".join(bank_accounts)
        data = self._get(
            f"/api/search/bank-accounts/{joined}",
            {"date": _format_date(date)},
        )
        return EntryListResponse.from_dict(data)

    # ------------------------------------------------------------------
    # 3. Szukaj po pojedynczym NIP
    #    GET /api/search/nip/{nip}
    # ------------------------------------------------------------------

    def search_by_nip(
        self,
        nip: str,
        date: date | str | None = None,
    ) -> EntityResponse:
        """
        Wyszukuje pojedynczy podmiot po numerze NIP.

        Parametry:
            nip  – 10-cyfrowy numer NIP.
            date – dzień na jaki ma być udzielona odpowiedź
                   (format: YYYY-MM-DD lub obiekt date; domyślnie: dziś).

        Zwraca:
            EntityResponse z danymi podmiotu.
        """
        data = self._get(
            f"/api/search/nip/{nip}",
            {"date": _format_date(date)},
        )
        return EntityResponse.from_dict(data)

    # ------------------------------------------------------------------
    # 4. Szukaj po wielu numerach NIP (batch, maks. 30)
    #    GET /api/search/nips/{nips}
    # ------------------------------------------------------------------

    def search_by_nips(
        self,
        nips: list[str],
        date: date | str | None = None,
    ) -> EntryListResponse:
        """
        Wyszukuje podmioty po liście numerów NIP (maks. 30).

        Parametry:
            nips – lista 10-cyfrowych numerów NIP (maks. 30 pozycji).
            date – dzień na jaki ma być udzielona odpowiedź
                   (format: YYYY-MM-DD lub obiekt date; domyślnie: dziś).

        Zwraca:
            EntryListResponse z wpisami per-NIP.
        """
        _validate_batch(nips, "numerów NIP")
        joined = ",".join(nips)
        data = self._get(
            f"/api/search/nips/{joined}",
            {"date": _format_date(date)},
        )
        return EntryListResponse.from_dict(data)

    # ------------------------------------------------------------------
    # 5. Szukaj po pojedynczym numerze REGON
    #    GET /api/search/regon/{regon}
    # ------------------------------------------------------------------

    def search_by_regon(
        self,
        regon: str,
        date: date | str | None = None,
    ) -> EntityResponse:
        """
        Wyszukuje pojedynczy podmiot po numerze REGON.

        Parametry:
            regon – numer REGON (9 lub 14 cyfr).
            date  – dzień na jaki ma być udzielona odpowiedź
                    (format: YYYY-MM-DD lub obiekt date; domyślnie: dziś).

        Zwraca:
            EntityResponse z danymi podmiotu.
        """
        data = self._get(
            f"/api/search/regon/{regon}",
            {"date": _format_date(date)},
        )
        return EntityResponse.from_dict(data)

    # ------------------------------------------------------------------
    # 6. Szukaj po wielu numerach REGON (batch, maks. 30)
    #    GET /api/search/regons/{regons}
    # ------------------------------------------------------------------

    def search_by_regons(
        self,
        regons: list[str],
        date: date | str | None = None,
    ) -> EntryListResponse:
        """
        Wyszukuje podmioty po liście numerów REGON (maks. 30).

        Parametry:
            regons – lista numerów REGON (maks. 30 pozycji).
            date   – dzień na jaki ma być udzielona odpowiedź
                     (format: YYYY-MM-DD lub obiekt date; domyślnie: dziś).

        Zwraca:
            EntryListResponse z wpisami per-REGON.
        """
        _validate_batch(regons, "numerów REGON")
        joined = ",".join(regons)
        data = self._get(
            f"/api/search/regons/{joined}",
            {"date": _format_date(date)},
        )
        return EntryListResponse.from_dict(data)

    # ------------------------------------------------------------------
    # 7. Sprawdź NIP + numer rachunku (check)
    #    GET /api/check/nip/{nip}/bank-account/{bank-account}
    # ------------------------------------------------------------------

    def check_nip_bank_account(
        self,
        nip: str,
        bank_account: str,
        date: date | str | None = None,
    ) -> EntityCheckResponse:
        """
        Sprawdza, czy podany rachunek bankowy jest przypisany do podmiotu
        o wskazanym NIP (metoda uproszczona „check").

        Parametry:
            nip          – 10-cyfrowy numer NIP.
            bank_account – numer rachunku bankowego (26 cyfr, bez spacji).
            date         – dzień na jaki ma być udzielona odpowiedź
                           (format: YYYY-MM-DD lub obiekt date; domyślnie: dziś).

        Zwraca:
            EntityCheckResponse z polem is_assigned (bool) i requestId.
        """
        data = self._get(
            f"/api/check/nip/{nip}/bank-account/{bank_account}",
            {"date": _format_date(date)},
        )
        return EntityCheckResponse.from_dict(data)

    # ------------------------------------------------------------------
    # 8. Sprawdź REGON + numer rachunku (check)
    #    GET /api/check/regon/{regon}/bank-account/{bank-account}
    # ------------------------------------------------------------------

    def check_regon_bank_account(
        self,
        regon: str,
        bank_account: str,
        date: date | str | None = None,
    ) -> EntityCheckResponse:
        """
        Sprawdza, czy podany rachunek bankowy jest przypisany do podmiotu
        o wskazanym numerze REGON (metoda uproszczona „check").

        Parametry:
            regon        – numer REGON (9 lub 14 cyfr).
            bank_account – numer rachunku bankowego (26 cyfr, bez spacji).
            date         – dzień na jaki ma być udzielona odpowiedź
                           (format: YYYY-MM-DD lub obiekt date; domyślnie: dziś).

        Zwraca:
            EntityCheckResponse z polem is_assigned (bool) i requestId.
        """
        data = self._get(
            f"/api/check/regon/{regon}/bank-account/{bank_account}",
            {"date": _format_date(date)},
        )
        return EntityCheckResponse.from_dict(data)


# ---------------------------------------------------------------------------
# Przykład użycia (uruchom: python vat_api.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Domyślnie używa środowiska testowego
    client = WykazPodatnikowVATClient(base_url=TEST_URL)

    print("=== Wyszukiwanie po NIP ===")
    try:
        resp = client.search_by_nip("1111111111", date="2024-01-15")
        if resp.subject:
            s = resp.subject
            print(f"  Nazwa:      {s.name}")
            print(f"  NIP:        {s.nip}")
            print(f"  REGON:      {s.regon}")
            print(f"  Status VAT: {s.status_vat}")
            print(f"  Rachunki:   {s.account_numbers}")
        else:
            print("  Brak wyników.")
        print(f"  requestId:  {resp.request_id}")
    except VATApiError as e:
        print(f"  Błąd: {e}")

    print("\n=== Sprawdzenie NIP + rachunek ===")
    try:
        check = client.check_nip_bank_account(
            nip="1111111111",
            bank_account="90249000050247256316596736",
            date="2024-01-15",
        )
        print(f"  Rachunek przypisany: {check.account_assigned}")
        print(f"  is_assigned (bool):  {check.is_assigned}")
        print(f"  requestId:           {check.request_id}")
    except VATApiError as e:
        print(f"  Błąd: {e}")
