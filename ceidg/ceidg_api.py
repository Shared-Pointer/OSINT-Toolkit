"""
Klient API Hurtowni Danych CEIDG (dane.biznes.gov.pl) – wersja API v3
Zakres: wyłącznie JDG – Jednoosobowe Działalności Gospodarcze (zrodlo=CEIDG)
Dokumentacja MRT: https://dane.biznes.gov.pl / https://akademia.biznes.gov.pl/pl/portal/004856

Dostępne metody:
  search_firms          – GET /api/ceidg/v3/firmy   – lista firm wg kryteriów
  get_firm_by_nip       – GET /api/ceidg/v3/firma?nip=...
  get_firm_by_regon     – GET /api/ceidg/v3/firma?regon=...
  get_firm_by_id        – GET /api/ceidg/v3/firma/{id}
  get_firms_by_ids      – GET /api/ceidg/v3/firma?ids[]=...&ids[]=...
  get_changes           – GET /api/ceidg/v3/zmiana  – lista zmian w zadanym przedziale dat
  list_reports          – GET /api/ceidg/v3/raporty – lista dostępnych raportów
  download_report       – GET /api/ceidg/v3/raport/{id} – pobranie pliku raportu

Limity API:
  • 50 żądań / 3 minuty  → po przekroczeniu blokada 180 s od ostatniego żądania
  • 1000 żądań / 60 minut
  Rekomendowany przedział dat dla /zmiana: nie więcej niż 5 dni.

Autoryzacja:
  Bearer JWT token otrzymywany po złożeniu wniosku na dane.biznes.gov.pl.
  Przekazywany przez konstruktor lub zmienną środowiskową CEIDG_TOKEN.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

# ---------------------------------------------------------------------------
# Stałe
# ---------------------------------------------------------------------------

PROD_URL = "https://dane.biznes.gov.pl"
TEST_URL = "https://test-dane.biznes.gov.pl"

# CEIDG rejestruje wyłącznie JDG i spółki cywilne osób fizycznych.
# Wymuszamy zrodlo=CEIDG, żeby odfiltrować ewentualne wpisy z innych źródeł.
ZRODLO_CEIDG = "CEIDG"

# Możliwe statusy działalności w CEIDG
STATUS_AKTYWNY                       = "AKTYWNY"
STATUS_ZAWIESZONY                    = "ZAWIESZONY"
STATUS_WYKRESLONY                    = "WYKRESLONY"
STATUS_OCZEKUJE                      = "OCZEKUJE_NA_ROZPOCZECIE_DZIALANOSCI"
STATUS_WYLACZNIE_SPOLKA              = "WYLACZNIE_W_FORMIE_SPOLKI"

ALL_STATUSES = [
    STATUS_AKTYWNY,
    STATUS_ZAWIESZONY,
    STATUS_WYKRESLONY,
    STATUS_OCZEKUJE,
    STATUS_WYLACZNIE_SPOLKA,
]


# ---------------------------------------------------------------------------
# Modele danych
# ---------------------------------------------------------------------------


@dataclass
class Address:
    """Adres działalności lub zamieszkania."""
    ulica: Optional[str] = None
    budynek: Optional[str] = None
    lokal: Optional[str] = None
    miasto: Optional[str] = None
    kod: Optional[str] = None
    gmina: Optional[str] = None
    powiat: Optional[str] = None
    wojewodztwo: Optional[str] = None
    kraj: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Address":
        return cls(
            ulica=d.get("ulica"),
            budynek=d.get("budynek"),
            lokal=d.get("lokal"),
            miasto=d.get("miasto"),
            kod=d.get("kod"),
            gmina=d.get("gmina"),
            powiat=d.get("powiat"),
            wojewodztwo=d.get("wojewodztwo"),
            kraj=d.get("kraj"),
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
    """Kod PKD działalności."""
    kod: Optional[str] = None
    opis: Optional[str] = None
    przewazajacy: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "PkdCode":
        return cls(
            kod=d.get("kod"),
            opis=d.get("opis"),
            przewazajacy=bool(d.get("przewazajacy", False)),
        )


@dataclass
class Firm:
    """
    Dane JDG z CEIDG.

    Pola odpowiadają odpowiedzi z /api/ceidg/v3/firma i /api/ceidg/v3/firmy.
    Część pól dostępna tylko w odpowiedzi szczegółowej (/firma).
    """
    # -- identyfikatory --
    id: Optional[str] = None
    nip: Optional[str] = None
    regon: Optional[str] = None

    # -- dane osobowe właściciela --
    imie: Optional[str] = None
    nazwisko: Optional[str] = None

    # -- dane firmy --
    nazwa: Optional[str] = None
    status: Optional[str] = None          # AKTYWNY | ZAWIESZONY | WYKRESLONY | ...
    data_rozpoczecia: Optional[str] = None
    data_zawieszenia: Optional[str] = None
    data_wznowienia: Optional[str] = None
    data_wykreslenia: Optional[str] = None
    data_aktualizacji: Optional[str] = None

    # -- adresy --
    adres_dzialalnosci: Optional[Address] = None
    adres_zamieszkania: Optional[Address] = None
    adres_korespondencji: Optional[Address] = None

    # -- kontakt --
    email: Optional[str] = None
    www: Optional[str] = None
    telefon: Optional[str] = None
    adres_elektroniczny: Optional[str] = None  # e-Doręczenia

    # -- PKD --
    pkd: list[PkdCode] = field(default_factory=list)

    # -- spółka cywilna --
    w_spolce_cywilnej: bool = False
    spolki_cywilne_nip: list[str] = field(default_factory=list)

    # -- pozostałe --
    ma_zarzadce_sukcesyjnego: Optional[bool] = None
    wspolnota_majatkowa: Optional[bool] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Firm":
        def addr(key: str) -> Optional[Address]:
            raw = d.get(key)
            return Address.from_dict(raw) if raw else None

        pkd_list = [PkdCode.from_dict(p) for p in d.get("pkd", [])]

        # Obsługa spółek cywilnych: lista NIP partnerów
        spolki = d.get("spolkiCywilne") or d.get("wspolnicySpołkiCywilnej") or []
        if isinstance(spolki, list):
            nip_spolki = [
                s.get("nip") for s in spolki if isinstance(s, dict) and s.get("nip")
            ]
        else:
            nip_spolki = []

        return cls(
            id=d.get("id"),
            nip=d.get("nip"),
            regon=d.get("regon"),
            imie=d.get("imie"),
            nazwisko=d.get("nazwisko"),
            nazwa=d.get("nazwa"),
            status=d.get("status"),
            data_rozpoczecia=d.get("dataRozpoczecia") or d.get("dataRozpoczeciaUstrukturyzowanego"),
            data_zawieszenia=d.get("dataZawieszenia"),
            data_wznowienia=d.get("dataWznowienia"),
            data_wykreslenia=d.get("dataWykreslenia"),
            data_aktualizacji=d.get("dataAktualizacji") or d.get("dataMigracji"),
            adres_dzialalnosci=addr("adresDzialalnosci") or addr("adresDzialanosci"),
            adres_zamieszkania=addr("adresZamieszkania"),
            adres_korespondencji=addr("adresKorespondencji") or addr("adresDoKorespondencji"),
            email=d.get("email"),
            www=d.get("www"),
            telefon=d.get("telefon"),
            adres_elektroniczny=d.get("adresElektroniczny") or d.get("adresEDoreczenia"),
            pkd=pkd_list,
            w_spolce_cywilnej=bool(d.get("wSpolceCywilnej") or nip_spolki),
            spolki_cywilne_nip=nip_spolki,
            ma_zarzadce_sukcesyjnego=d.get("maZarzadceSukcesyjnego"),
            wspolnota_majatkowa=d.get("wspolnotaMajatkowa"),
        )

    @property
    def pkd_przewazajacy(self) -> Optional[PkdCode]:
        """Zwraca przeważający kod PKD lub pierwszy na liście."""
        for p in self.pkd:
            if p.przewazajacy:
                return p
        return self.pkd[0] if self.pkd else None

    @property
    def is_active(self) -> bool:
        return self.status == STATUS_AKTYWNY


@dataclass
class FirmListResponse:
    """Odpowiedź z metody FIRMY (lista z paginacją)."""
    firms: list[Firm]
    total: Optional[int] = None
    page: Optional[int] = None
    limit: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict) -> "FirmListResponse":
        raw_firms = (
            data.get("firmy")
            or data.get("wpisy")
            or data.get("zmiany")
            or []
        )
        # API v3 zwraca "liczba" = null gdy paginacja jest nieznana –
        # traktujemy None i 0 tak samo (nie wiadomo ile łącznie)
        total_raw = data.get("liczba") if data.get("liczba") is not None else data.get("total")
        return cls(
            firms=[Firm.from_dict(f) for f in raw_firms],
            total=total_raw,
            page=data.get("strona") or data.get("page"),
            limit=data.get("limit"),
        )


@dataclass
class ReportInfo:
    """Metadane raportu dostępnego do pobrania."""
    id: str
    name: Optional[str] = None
    url: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "ReportInfo":
        return cls(
            id=d.get("id", ""),
            name=d.get("nazwa"),
            url=d.get("raport"),
        )


# ---------------------------------------------------------------------------
# Wyjątki
# ---------------------------------------------------------------------------


class CeidgApiError(Exception):
    """Ogólny błąd klienta CEIDG API."""


class CeidgApiHTTPError(CeidgApiError):
    """Błąd HTTP z serwera (status != 2xx)."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class CeidgApiAuthError(CeidgApiError):
    """Brak lub nieprawidłowy token JWT."""


class CeidgApiRateLimitError(CeidgApiError):
    """Przekroczono limit zapytań (429)."""


class CeidgApiValidationError(CeidgApiError):
    """Błąd walidacji parametrów po stronie klienta."""


# ---------------------------------------------------------------------------
# Główna klasa klienta
# ---------------------------------------------------------------------------


class CEIDGClient:
    """
    Klient REST API Hurtowni Danych CEIDG (MRT), v3.
    Obsługuje wyłącznie JDG (zrodlo=CEIDG).

    Parametry:
        token    – Bearer JWT token (lub ustaw zmienną środowiskową CEIDG_TOKEN).
        base_url – endpoint API (domyślnie: produkcja).
        timeout  – timeout HTTP w sekundach (domyślnie 30).
        session  – opcjonalny requests.Session (np. z własnym retry).

    Przykład::

        from ceidg_api import CEIDGClient

        client = CEIDGClient(token="eyJhbGci...")

        # Szukaj aktywnych JDG po NIP
        firma = client.get_firm_by_nip("1234567890")
        print(firma.nazwa, firma.status)

        # Lista firm po fragmencie nazwy
        wyniki = client.search_firms(nazwa="Kowalski", status=["AKTYWNY"])
        for f in wyniki.firms:
            print(f.nip, f.nazwa)
    """

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = PROD_URL,
        timeout: int = 30,
        session: Optional[requests.Session] = None,
    ) -> None:
        resolved_token = token or os.environ.get("CEIDG_TOKEN")
        if not resolved_token:
            raise CeidgApiAuthError(
                "Brak tokenu JWT. Podaj token= lub ustaw zmienną CEIDG_TOKEN."
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {resolved_token}",
            "Accept": "application/json",
        })

    # ------------------------------------------------------------------
    # Wewnętrzna metoda HTTP
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
        except requests.ConnectionError as exc:
            raise CeidgApiError(f"Błąd połączenia: {exc}") from exc
        except requests.Timeout:
            raise CeidgApiError("Przekroczono czas oczekiwania na odpowiedź API.")

        if resp.status_code == 401:
            raise CeidgApiAuthError("Nieprawidłowy lub wygasły token JWT (401).")
        if resp.status_code == 429:
            raise CeidgApiRateLimitError(
                "Przekroczono limit zapytań (429). Odczekaj 180 s od ostatniego żądania."
            )
        if resp.status_code == 204:
            return {}   # brak danych – poprawna odpowiedź
        if not resp.ok:
            try:
                msg = resp.json().get("message", resp.text)
            except Exception:
                msg = resp.text
            raise CeidgApiHTTPError(resp.status_code, msg)

        if not resp.content:
            return {}
        return resp.json()

    def _get_raw(self, path: str) -> bytes:
        """Pobiera surowe bajty (np. plik raportu)."""
        url = f"{self.base_url}{path}"
        try:
            resp = self._session.get(url, timeout=self.timeout)
        except requests.ConnectionError as exc:
            raise CeidgApiError(f"Błąd połączenia: {exc}") from exc
        except requests.Timeout:
            raise CeidgApiError("Przekroczono czas oczekiwania.")

        if resp.status_code == 401:
            raise CeidgApiAuthError("Nieprawidłowy lub wygasły token JWT (401).")
        if not resp.ok:
            raise CeidgApiHTTPError(resp.status_code, resp.text)
        return resp.content

    @staticmethod
    def _extract_firm_raw(data):
        """
        API v3 zwraca dane firmy na trzy sposoby (nieudokumentowane w prod.):
          {"firma": {...}}  – opakowany obiekt
          {...}             – bezpośredni obiekt
          [{...}, ...]      – lista (spotykane dla /firma/{uuid} i /firma?nip=)
        """
        if isinstance(data, list):
            return data[0] if data and isinstance(data[0], dict) else None
        if isinstance(data, dict):
            nested = data.get("firma")
            if nested is not None:
                if isinstance(nested, list):
                    return nested[0] if nested and isinstance(nested[0], dict) else None
                return nested
            if data.get("id") or data.get("nip") or data.get("regon"):
                return data
        return None


    # ------------------------------------------------------------------
    # 1. Wyszukiwanie listy firm po kryteriach
    #    GET /api/ceidg/v3/firmy
    # ------------------------------------------------------------------

    def search_firms(
        self,
        nazwa: Optional[str] = None,
        nip: Optional[str] = None,
        regon: Optional[str] = None,
        imie: Optional[str] = None,
        nazwisko: Optional[str] = None,
        pkd: Optional[str] = None,
        ulica: Optional[str] = None,
        miasto: Optional[str] = None,
        wojewodztwo: Optional[str] = None,
        powiat: Optional[str] = None,
        gmina: Optional[str] = None,
        status: Optional[list[str]] = None,
        dataod: Optional[str] = None,
        datado: Optional[str] = None,
        aktod: Optional[str] = None,
        aktdo: Optional[str] = None,
        sort: Optional[str] = None,
        limit: int = 25,
        page: int = 1,
    ) -> FirmListResponse:
        """
        Zwraca listę JDG spełniających zadane kryteria (paginacja).

        Parametry:
            nazwa       – fragment nazwy firmy
            nip         – NIP przedsiębiorcy
            regon       – REGON
            imie        – imię właściciela
            nazwisko    – nazwisko właściciela
            pkd         – kod PKD bez kropki, np. "6201Z"
            ulica       – fragment ulicy
            miasto      – miasto
            wojewodztwo – województwo
            powiat      – powiat
            gmina       – gmina
            status      – lista statusów (domyślnie wszystkie); dozwolone wartości:
                          AKTYWNY, ZAWIESZONY, WYKRESLONY,
                          OCZEKUJE_NA_ROZPOCZECIE_DZIALANOSCI,
                          WYLACZNIE_W_FORMIE_SPOLKI
            dataod      – data rozpoczęcia działalności – od (YYYY-MM-DD)
            datado      – data rozpoczęcia działalności – do (YYYY-MM-DD)
            aktod       – data aktualizacji wpisu – od (YYYY-MM-DD)
            aktdo       – data aktualizacji wpisu – do (YYYY-MM-DD)
            sort        – pole sortowania, np. "nazwa" lub "-data"
            limit       – wyniki na stronę (domyślnie 25)
            page        – numer strony (domyślnie 1)

        Zwraca:
            FirmListResponse z listą firm i metadanymi paginacji.
        """
        params: dict[str, Any] = {
            "zrodlo": ZRODLO_CEIDG,
            "limit": limit,
            "page": page,
        }
        if nazwa:        params["nazwa"] = nazwa
        if nip:          params["nip"] = nip
        if regon:        params["regon"] = regon
        if imie:         params["imie"] = imie
        if nazwisko:     params["nazwisko"] = nazwisko
        if pkd:          params["pkd"] = pkd
        if ulica:        params["ulica"] = ulica
        if miasto:       params["miasto"] = miasto
        if wojewodztwo:  params["wojewodztwo"] = wojewodztwo
        if powiat:       params["powiat"] = powiat
        if gmina:        params["gmina"] = gmina
        if dataod:       params["dataod"] = dataod
        if datado:       params["datado"] = datado
        if aktod:        params["aktod"] = aktod
        if aktdo:        params["aktdo"] = aktdo
        if sort:         params["sort"] = sort

        # Status: v3 przyjmuje wielokrotny parametr &status=X&status=Y
        if status:
            invalid = [s for s in status if s not in ALL_STATUSES]
            if invalid:
                raise CeidgApiValidationError(
                    f"Nieprawidłowe statusy: {invalid}. "
                    f"Dozwolone: {ALL_STATUSES}"
                )
            # requests obsługuje listy jako wielokrotny parametr
            params["status"] = status

        data = self._get("/api/ceidg/v3/firmy", params)
        return FirmListResponse.from_dict(data)

    # ------------------------------------------------------------------
    # 2. Szczegółowe dane firmy po NIP
    #    GET /api/ceidg/v3/firma?nip=...
    # ------------------------------------------------------------------

    def get_firm_by_nip(self, nip: str) -> Optional[Firm]:
        """
        Pobiera pełne dane JDG po numerze NIP.

        Parametry:
            nip – 10-cyfrowy NIP.

        Zwraca:
            Firm lub None jeśli nie znaleziono.
        """
        data = self._get("/api/ceidg/v3/firma", {"nip": nip})
        raw = self._extract_firm_raw(data)
        return Firm.from_dict(raw) if raw else None

    # ------------------------------------------------------------------
    # 3. Szczegółowe dane firmy po REGON
    #    GET /api/ceidg/v3/firma?regon=...
    # ------------------------------------------------------------------

    def get_firm_by_regon(self, regon: str) -> Optional[Firm]:
        """
        Pobiera pełne dane JDG po numerze REGON (9 lub 14 cyfr).

        Parametry:
            regon – numer REGON.

        Zwraca:
            Firm lub None jeśli nie znaleziono.
        """
        data = self._get("/api/ceidg/v3/firma", {"regon": regon})
        raw = self._extract_firm_raw(data)
        return Firm.from_dict(raw) if raw else None

    # ------------------------------------------------------------------
    # 4. Szczegółowe dane firmy po UUID (id wpisu)
    #    GET /api/ceidg/v3/firma/{id}
    # ------------------------------------------------------------------

    def get_firm_by_id(self, firm_id: str) -> Optional[Firm]:
        """
        Pobiera pełne dane JDG po wewnętrznym identyfikatorze UUID wpisu CEIDG.

        Parametry:
            firm_id – UUID wpisu, np. "31F87519-9395-4FCF-8E19-6D5C0522FA7A".

        Zwraca:
            Firm lub None jeśli nie znaleziono.
        """
        data = self._get(f"/api/ceidg/v3/firma/{firm_id}")
        raw = self._extract_firm_raw(data)
        return Firm.from_dict(raw) if raw else None

    # ------------------------------------------------------------------
    # 5. Dane wielu firm po liście UUID (batch po ids[])
    #    GET /api/ceidg/v3/firma?ids[]=...&ids[]=...
    # ------------------------------------------------------------------

    def get_firms_by_ids(self, ids: list[str]) -> list[Firm]:
        """
        Pobiera dane wielu JDG na podstawie listy UUID wpisów CEIDG.

        Uwaga: API v3 nie obsługuje batch po ids[] jako jednego żądania –
        metoda wykonuje kolejne wywołania get_firm_by_id dla każdego UUID.
        Pamiętaj o limicie 50 żądań / 3 min.

        Parametry:
            ids – lista UUID wpisów CEIDG.

        Zwraca:
            Listę obiektów Firm (pomija nieznalezione UUID).
        """
        if not ids:
            raise CeidgApiValidationError("Lista ids nie może być pusta.")
        results = []
        for firm_id in ids:
            firm = self.get_firm_by_id(firm_id)
            if firm:
                results.append(firm)
        return results

    # ------------------------------------------------------------------
    # 6. Lista zmian wpisów w przedziale dat
    #    GET /api/ceidg/v3/zmiana?dataod=...&datado=...
    # ------------------------------------------------------------------

    def get_changes(
        self,
        dataod: str,
        datado: Optional[str] = None,
        limit: int = 25,
        page: int = 1,
    ) -> FirmListResponse:
        """
        Zwraca listę wpisów zmienionych w zadanym przedziale dat.

        Używa endpointu /zmiana (wymaga formatu YYYY-MM-DD).
        Jeśli /zmiana zwróci 0 wyników, automatycznie odpytuje /firmy
        z parametrami aktod/aktdo (filtr po dacie aktualizacji wpisu) –
        co jest bardziej niezawodnym sposobem w API v3.

        Rekomendowany zakres: nie więcej niż 5 dni.

        Parametry:
            dataod – data początkowa (YYYY-MM-DD), wymagana.
            datado – data końcowa (YYYY-MM-DD); domyślnie: brak (do teraz).
            limit  – wyniki na stronę (domyślnie 25).
            page   – numer strony (domyślnie 1).

        Zwraca:
            FirmListResponse z listą zmienionych wpisów.
        """
        if not dataod:
            raise CeidgApiValidationError("Parametr 'dataod' jest wymagany.")

        # Próba 1: dedykowany endpoint /zmiana
        params: dict[str, Any] = {
            "dataod": dataod,
            "limit": limit,
            "page": page,
        }
        if datado:
            params["datado"] = datado

        data = self._get("/api/ceidg/v3/zmiana", params)
        result = FirmListResponse.from_dict(data)

        # Próba 2: jeśli /zmiana zwróciło 0 wyników, użyj /firmy z aktod/aktdo
        # (API v3 obsługuje filtr po dacie aktualizacji wpisu w głównej metodzie)
        if not result.firms:
            fallback_params: dict[str, Any] = {
                "zrodlo": ZRODLO_CEIDG,
                "aktod": dataod,
                "limit": limit,
                "page": page,
            }
            if datado:
                fallback_params["aktdo"] = datado
            fallback_data = self._get("/api/ceidg/v3/firmy", fallback_params)
            result = FirmListResponse.from_dict(fallback_data)

        return result

    # ------------------------------------------------------------------
    # 7. Lista dostępnych raportów
    #    GET /api/ceidg/v3/raporty
    # ------------------------------------------------------------------

    def list_reports(
        self,
        dataod: Optional[str] = None,
        datado: Optional[str] = None,
    ) -> list[ReportInfo]:
        """
        Zwraca listę raportów dostępnych do pobrania.

        Parametry:
            dataod – zakres dat raportów – od (YYYY-MM-DD).
            datado – zakres dat raportów – do (YYYY-MM-DD).

        Zwraca:
            Listę obiektów ReportInfo (id, nazwa, url do pobrania).
        """
        params: dict[str, Any] = {}
        if dataod:
            params["dataod"] = dataod
        if datado:
            params["datado"] = datado
        data = self._get("/api/ceidg/v3/raporty", params or None)
        raw = data.get("raporty") or []
        return [ReportInfo.from_dict(r) for r in raw]

    # ------------------------------------------------------------------
    # 8. Pobranie pliku raportu
    #    GET /api/ceidg/v3/raport/{id}
    # ------------------------------------------------------------------

    def download_report(self, report_id: str) -> bytes:
        """
        Pobiera wybrany raport jako bajty (zwykle plik ZIP lub CSV).

        Parametry:
            report_id – identyfikator raportu (UUID lub pełna nazwa z list_reports).

        Zwraca:
            Zawartość pliku jako bytes. Zapis na dysk po stronie wywołującego.

        Przykład::

            data = client.download_report("0e8d5775-9eaf-4d9d-ab34-829f706a893e")
            with open("raport.zip", "wb") as f:
                f.write(data)
        """
        if not report_id:
            raise CeidgApiValidationError("Parametr 'report_id' jest wymagany.")
        return self._get_raw(f"/api/ceidg/v3/raport/{report_id}")
