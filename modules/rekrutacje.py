"""Rekrutacje module — oferty pracy z pracuj.pl (Playwright + __NEXT_DATA__ JSON)."""

from __future__ import annotations
import json
import re
import time
from urllib.parse import quote
from typing import Optional


def _scrape_pracujpl(keyword: str, days_back: int = 30) -> dict:
    from playwright.sync_api import sync_playwright

    kw_encoded = quote(keyword)
    url = f"https://www.pracuj.pl/praca/{kw_encoded};kw?rd={days_back}&rop=50"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="pl-PL",
        )
        page = ctx.new_page()
        page.goto(url, timeout=30000)

        # Zamknij dialog cookies jeśli się pojawi
        try:
            page.click('button:has-text("Akceptuj")', timeout=4000)
            time.sleep(0.5)
        except Exception:
            pass

        # Czekaj na oferty — jeśli nie ma, pobierz HTML i tak (może być brak wyników)
        try:
            page.wait_for_selector('[data-test="default-offer"]', timeout=15000)
        except Exception:
            pass  # brak ofert lub CF challenge — sprawdzimy __NEXT_DATA__

        html = page.content()
        browser.close()

    return _parse_next_data(html, keyword)


def _parse_next_data(html: str, keyword: str) -> dict:
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return {"offers": [], "total_count": 0, "query_used": keyword}

    data = json.loads(m.group(1))
    queries = data["props"]["pageProps"]["dehydratedState"]["queries"]

    grouped_offers = []
    total_count = 0

    for q in queries:
        key = str(q.get("queryKey", ""))
        if (
            "jobOffers" in key
            and "main" not in key.lower()
            and "count" not in key.lower()
            and "positioned" not in key.lower()
        ):
            qdata = q["state"]["data"]
            grouped_offers = qdata.get("groupedOffers", [])
            total_count = qdata.get("offersTotalCount", len(grouped_offers))
            break

    offers = []
    for group in grouped_offers:
        locations = [
            o.get("displayWorkplace", "")
            for o in group.get("offers", [])
            if o.get("displayWorkplace")
        ]
        if group.get("isWholePoland") or (
            group.get("offers") and group["offers"][0].get("isWholePoland")
        ):
            locations = ["Cała Polska"]

        # Wyciągnij URL z pierwszej oferty w grupie
        offer_url = ""
        inner_offers = group.get("offers", [])
        if inner_offers:
            offer_url = inner_offers[0].get("offerAbsoluteUri", "")

        # Typy pracy i kontraktu — mogą być listą stringów lub listą słowników
        def _extract_list(items):
            result = []
            for item in (items or []):
                if isinstance(item, str):
                    result.append(item)
                elif isinstance(item, dict):
                    result.append(item.get("name") or item.get("label") or "")
            return [x for x in result if x]

        work_modes = _extract_list(group.get("workModes", []))
        contract_types = _extract_list(group.get("typesOfContract", []))

        offers.append({
            "title": group.get("jobTitle") or "",
            "company": group.get("companyName") or "",
            "salary": group.get("salaryDisplayText") or None,
            "locations": locations or ["—"],
            "date": (group.get("lastPublicated") or "")[:10],
            "url": offer_url,
            "work_modes": work_modes,
            "contract_types": contract_types,
        })

    return {
        "offers": offers,
        "total_count": total_count,
        "query_used": keyword,
        "days_back": 30,
    }


# ── Module interface ─────────────────────────────────────────────────────────

def _is_nip(q: str) -> bool:
    d = q.replace("-", "").replace(" ", "")
    return d.isdigit() and len(d) == 10


def _shorten(name: str) -> str:
    """Usuwa formę prawną — zostawia rdzeń nazwy do wyszukiwania."""
    import re as _re
    short = _re.sub(
        r"\b(SPÓŁKA AKCYJNA|SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ|"
        r"SPÓŁKA JAWNA|SPÓŁKA KOMANDYTOWA|SPÓŁKA PARTNERSKA|SPÓŁKA CYWILNA|"
        r"S\.A\.|SP\. Z O\.O\.|SP\. J\.|SP\. K\.|S\.K\.A\.|"
        r"AKCYJNA|OGRANICZONĄ|ODPOWIEDZIALNOŚCIĄ)\b",
        "", name, flags=_re.IGNORECASE,
    ).strip(" ,.-")
    words = short.split()
    return " ".join(words[:3]) if words else name


def run(query: str, query_type: str = "auto") -> dict:
    if query_type == "nip" or (query_type == "auto" and _is_nip(query)):
        return {
            "status": "skipped",
            "error": "Moduł Rekrutacje wymaga nazwy firmy, nie NIP.",
            "data": {},
        }

    # Skróć formę prawną przed wyszukiwaniem
    search_query = _shorten(query) if query_type == "name" else query

    try:
        result = _scrape_pracujpl(search_query)
        offers = result.get("offers", [])

        # Jeśli skrócona nazwa nie dała wyników, spróbuj oryginalną
        if not offers and search_query != query:
            result = _scrape_pracujpl(query)
            offers = result.get("offers", [])

        if not offers:
            return {"status": "not_found", "data": result}

        return {"status": "ok", "data": result}

    except Exception as e:
        return {"status": "error", "error": str(e), "data": {}}
