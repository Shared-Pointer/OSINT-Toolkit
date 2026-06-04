"""KRS module — Portal Rejestrów Sądowych ekrs.ms.gov.pl (Playwright scraper)."""

from __future__ import annotations
import re
from typing import Optional


def _scrape_krs(query: str, query_type: str) -> Optional[dict]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0"})

        # Wyszukiwarka KRS
        page.goto("https://ekrs.ms.gov.pl/web/wyszukiwarka-krs/strona-glowna/", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=30000)

        # Wybór trybu wyszukiwania i wpisanie wartości
        try:
            if query_type in ("nip", "auto"):
                # Szukamy pola NIP
                nip_input = page.query_selector('input[placeholder*="NIP"], input[id*="nip"], input[formcontrolname*="nip"]')
                if nip_input:
                    nip_input.fill(query)
                else:
                    # Fallback: pierwsze pole tekstowe
                    page.fill('input[type="text"]', query)
            else:
                krs_input = page.query_selector('input[placeholder*="KRS"], input[id*="krs"]')
                if krs_input:
                    krs_input.fill(query)
                else:
                    page.fill('input[type="text"]', query)

            # Submit
            btn = page.query_selector('button[type="submit"], button:has-text("Szukaj"), button:has-text("Wyszukaj")')
            if btn:
                btn.click()
            else:
                page.keyboard.press("Enter")

            page.wait_for_load_state("networkidle", timeout=20000)

        except Exception:
            browser.close()
            return None

        # Próba wyciągnięcia danych z wyników
        result = {}

        # Nazwa firmy
        for sel in ['h1', 'h2', '.company-name', '[class*="name"]', 'td:first-child']:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text().strip()
                if len(text) > 3 and not text.lower().startswith(("szukaj", "wynik", "portal")):
                    result["nazwa"] = text
                    break

        # Zbierz wszystkie tabele z danymi
        rows = page.query_selector_all("table tr, .data-row")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = cells[0].inner_text().strip().lower()
                value = cells[1].inner_text().strip()
                if "krs" in label and not result.get("krs"):
                    result["krs"] = re.sub(r"\D", "", value).zfill(10) if re.search(r"\d", value) else value
                elif "nip" in label and not result.get("nip"):
                    result["nip"] = re.sub(r"[\s\-]", "", value)
                elif "regon" in label and not result.get("regon"):
                    result["regon"] = value
                elif "forma" in label and not result.get("forma_prawna"):
                    result["forma_prawna"] = value
                elif any(k in label for k in ("siedzib", "adres", "ulica")) and not result.get("adres"):
                    result["adres"] = value
                elif "kapita" in label and not result.get("kapital_zakladowy"):
                    result["kapital_zakladowy"] = value

        browser.close()

    return result if result else None


# ── Module interface ─────────────────────────────────────────────────────────

def _is_nip(q: str) -> bool:
    d = q.replace("-", "").replace(" ", "")
    return d.isdigit() and len(d) == 10


def run(query: str, query_type: str = "auto") -> dict:
    if query_type not in ("nip", "krs", "auto"):
        return {"status": "skipped", "error": "KRS wymaga NIP lub numeru KRS.", "data": {}}
    if query_type == "auto" and not _is_nip(query) and not query.replace(" ", "").isdigit():
        return {"status": "skipped", "error": "KRS wymaga NIP lub numeru KRS — podaj numer, nie nazwę firmy.", "data": {}}

    _GARBAGE = {"wyszukiwarka krs", "nazwa / firma", "nazwa/firma"}

    try:
        data = _scrape_krs(query.replace("-", "").replace(" ", ""), query_type)
        if not data:
            return {"status": "not_found", "data": {}}
        # Wykryj gdy scraper złapał etykiety formularza zamiast danych
        nazwa = (data.get("nazwa") or "").strip().lower()
        krs_val = (data.get("krs") or "").strip().lower()
        if nazwa in _GARBAGE or krs_val in _GARBAGE:
            return {"status": "not_found", "data": {}}
        return {"status": "ok", "data": data}
    except Exception as e:
        return {"status": "error", "error": str(e), "data": {}}
