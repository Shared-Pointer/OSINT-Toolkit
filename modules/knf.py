"""KNF module - lista ostrzeżeń publicznych KNF."""

from __future__ import annotations
import threading
import time
from typing import Optional

_cache: dict = {"data": None, "ts": 0.0}
_cache_lock = threading.Lock()
CACHE_TTL = 3600 * 6  # 6h


def _get_all_warnings() -> list[dict]:
    now = time.time()
    with _cache_lock:
        if _cache["data"] is not None and (now - _cache["ts"]) < CACHE_TTL:
            return _cache["data"]

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0"})
        page.goto("https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne", timeout=60000)
        page.wait_for_load_state("networkidle", timeout=60000)

        data = []
        for table in page.query_selector_all("table.warning-list-table"):
            for row in table.query_selector_all("tr"):
                tds = row.query_selector_all("td")
                if len(tds) == 6:
                    data.append({
                        "number": tds[0].inner_text().strip(),
                        "company": tds[1].inner_text().strip(),
                        "krs": tds[2].inner_text().strip(),
                        "prosecutor": tds[3].inner_text().strip(),
                        "date": tds[4].inner_text().strip(),
                        "description": tds[5].inner_text().strip(),
                    })
        browser.close()

    # don't cache empty results - page may not have loaded properly
    if data:
        with _cache_lock:
            _cache["data"] = data
            _cache["ts"] = now
    return data


def _filter(warnings: list[dict], query: str) -> list[dict]:
    q = query.lower().replace("-", "").replace(" ", "")
    matched = []
    for w in warnings:
        company_norm = w["company"].lower().replace("-", "").replace(" ", "")
        krs_norm = w["krs"].replace("-", "").replace(" ", "")
        if q in company_norm or (q.isdigit() and q in krs_norm):
            matched.append(w)
    return matched


# Module interface

def run(query: str, query_type: str = "auto") -> dict:
    try:
        warnings = _get_all_warnings()
        matches = _filter(warnings, query)
        return {
            "status": "ok",
            "data": {
                "found": len(matches) > 0,
                "matches": matches,
                "total_in_list": len(warnings),
            },
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "data": {}}
