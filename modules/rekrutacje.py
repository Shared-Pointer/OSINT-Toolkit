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
        page.wait_for_selector('[data-test="default-offer"]', timeout=20000)

        # Zamknij dialog cookies jeśli się pojawi
        try:
            page.click('button:has-text("Akceptuj")', timeout=3000)
            time.sleep(0.5)
        except Exception:
            pass

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


def run(query: str, query_type: str = "auto") -> dict:
    # pracuj.pl to wyszukiwanie po słowach kluczowych — NIP nie zadziała
    if query_type == "nip" or (query_type == "auto" and _is_nip(query)):
        return {
            "status": "skipped",
            "error": "Moduł Rekrutacje wymaga nazwy firmy, nie NIP. "
                     "Wpisz nazwę firmy w polu zapytania.",
            "data": {},
        }

    try:
        result = _scrape_pracujpl(query)
        offers = result.get("offers", [])
        total = result.get("total_count", 0)

        if not offers:
            return {"status": "not_found", "data": result}

        return {"status": "ok", "data": result}

    except Exception as e:
        return {"status": "error", "error": str(e), "data": {}}
