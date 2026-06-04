"""KRS module — Ministerstwo Sprawiedliwości, Rejestr Przedsiębiorców."""

from __future__ import annotations
from typing import Optional
import requests

BASE_URL = "https://api.rejestry.ms.gov.pl"


class KRSApiError(Exception): pass


class KRSClient:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 OSINT-Toolkit/1.0",
        })

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = self._session.get(f"{BASE_URL}{path}", params=params, timeout=self.timeout)
        if not resp.ok:
            raise KRSApiError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def search_by_nip(self, nip: str) -> Optional[dict]:
        """Szuka podmiotu po NIP. Zwraca pierwszy wynik lub None."""
        data = self._get("/api/krs/podmiotSearch", {"nip": nip})
        items = data.get("odpis", []) or data.get("items", []) or []
        if isinstance(data, list):
            items = data
        return items[0] if items else None

    def search_by_krs(self, krs: str) -> Optional[dict]:
        """Szuka podmiotu po numerze KRS."""
        krs_padded = krs.zfill(10)
        data = self._get("/api/krs/podmiotSearch", {"krs": krs_padded})
        items = data.get("odpis", []) or data.get("items", []) or []
        if isinstance(data, list):
            items = data
        return items[0] if items else None

    def get_odpis(self, krs: str) -> Optional[dict]:
        """Pobiera pełny odpis aktualny dla danego numeru KRS."""
        krs_padded = krs.zfill(10)
        try:
            return self._get(f"/api/krs/OdpisAktualny/{krs_padded}", {"rejestr": "P", "format": "json"})
        except KRSApiError:
            try:
                return self._get(f"/api/krs/OdpisAktualny/{krs_padded}", {"rejestr": "S", "format": "json"})
            except KRSApiError:
                return None


def _parse_odpis(odpis: dict) -> dict:
    """Wyciąga kluczowe pola z odpisu KRS."""
    nagl = odpis.get("naglowekA") or {}
    dane = (odpis.get("odpis", {}) or {}).get("dane", {}) or odpis.get("dane", {}) or {}

    # Próba wyciągnięcia z różnych możliwych kształtów odpowiedzi
    podmiot = dane.get("dzial1", {}).get("danePodmiotu", {}) or {}
    zarzad = dane.get("dzial2", {}).get("organPrzedsiebiorcy", {}) or {}
    kapital = dane.get("dzial1", {}).get("kapital", {}) or {}
    adres = dane.get("dzial1", {}).get("siedzibaIAdres", {}) or {}

    czlonkowie = zarzad.get("wspólnicyLubCzlonkowie", []) or zarzad.get("czlonkowie", []) or []
    if isinstance(czlonkowie, dict):
        czlonkowie = [czlonkowie]

    return {
        "krs": nagl.get("numerKRS") or odpis.get("krs"),
        "nazwa": podmiot.get("nazwa") or nagl.get("nazwa"),
        "forma_prawna": podmiot.get("formaPrawna"),
        "nip": podmiot.get("nip"),
        "regon": podmiot.get("regon"),
        "adres": f"{adres.get('ulica', '')} {adres.get('nrDomu', '')}, {adres.get('kodPocztowy', '')} {adres.get('miejscowosc', '')}".strip(", "),
        "kapital_zakladowy": kapital.get("wysokoscKapitaluZakladowego"),
        "zarzad": [
            f"{os.get('imie1', '')} {os.get('imie2', '')} {os.get('nazwisko', '')}".strip()
            for os in czlonkowie
            if isinstance(os, dict)
        ][:10],
        "raw_available": True,
    }


# ── Module interface ─────────────────────────────────────────────────────────

def _is_nip(q: str) -> bool:
    d = q.replace("-", "").replace(" ", "")
    return d.isdigit() and len(d) == 10


def _is_krs(q: str) -> bool:
    d = q.replace("-", "").replace(" ", "")
    return d.isdigit() and len(d) <= 10


def run(query: str, query_type: str = "auto") -> dict:
    try:
        client = KRSClient()
        nip = query.replace("-", "").replace(" ", "")

        raw = None

        if query_type == "krs" or (query_type == "auto" and _is_krs(query) and not _is_nip(query)):
            raw = client.get_odpis(nip)
        elif query_type == "nip" or (query_type == "auto" and _is_nip(query)):
            # Najpierw szukamy po NIP → dostajemy KRS → pobieramy odpis
            result = client.search_by_nip(nip)
            if result:
                krs_num = result.get("krs") or result.get("numerKRS", "")
                if krs_num:
                    raw = client.get_odpis(str(krs_num))
                if not raw:
                    raw = result
        else:
            return {"status": "skipped", "error": "KRS wymaga NIP lub numeru KRS.", "data": {}}

        if not raw:
            return {"status": "not_found", "data": {}}

        return {"status": "ok", "data": _parse_odpis(raw)}

    except KRSApiError as e:
        return {"status": "error", "error": str(e), "data": {}}
    except Exception as e:
        return {"status": "error", "error": str(e), "data": {}}
