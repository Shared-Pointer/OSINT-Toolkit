"""UOKiK module — wrapper wokół istniejącego scrapera decyzji UOKiK."""

from __future__ import annotations
import html
import re
import os
from urllib.parse import parse_qs, unquote, urljoin, urlparse
import base64

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://decyzje.uokik.gov.pl/bp/dec_prez.nsf"
DDG_HTML = "https://html.duckduckgo.com/html/"
BING_HTML = "https://www.bing.com/search"


def _dedupe(results):
    seen = set()
    out = []
    for item in results:
        if item["url"] in seen:
            continue
        out.append(item)
        seen.add(item["url"])
    return out


def _normalize_query(query: str):
    q = " ".join(query.split()).strip()
    variants = [q, f'"{q}"']
    seen = {q, f'"{q}"'}
    cleaned = re.sub(r"[^\w\s]", " ", q).strip()
    if cleaned not in seen:
        variants.append(cleaned)
        seen.add(cleaned)
    return variants


def _extract_uokik_results(html_text: str, base_url: str):
    soup = BeautifulSoup(html_text, "html.parser")
    results = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if not href:
            continue
        full_url = urljoin(base_url, href)
        if "decyzje.uokik.gov.pl" not in full_url:
            continue
        if "/bp/dec_prez.nsf/" not in full_url.lower():
            continue
        title = a.get_text(" ", strip=True) or full_url
        results.append({"title": title, "url": full_url})
    return _dedupe(results)


def _unwrap_url(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for key in ("uddg", "r", "url", "u"):
        if key in qs and qs[key]:
            val = qs[key][0]
            if val.startswith("http"):
                return val
    match = re.search(r"https?://[^\s&]+", url)
    return match.group(0) if match else url


def _search_site(session: requests.Session, query: str):
    for variant in _normalize_query(query):
        for endpoint, params in [
            (f"{BASE_URL}/SearchView", {"SearchView": "", "Query": variant, "SearchOrder": "4", "SearchMax": "50"}),
            (f"{BASE_URL}/SearchView", {"Query": variant}),
        ]:
            try:
                resp = session.get(endpoint, params=params, timeout=30)
                if not resp.ok:
                    continue
                resp.encoding = resp.apparent_encoding or resp.encoding
                results = _extract_uokik_results(resp.text, resp.url)
                if results:
                    return results
            except Exception:
                continue
    return []


def _search_duckduckgo(session: requests.Session, query: str):
    allowed = ("decyzje.uokik.gov.pl", "uokik.gov.pl")
    for variant in _normalize_query(query):
        ddg_query = f"site:decyzje.uokik.gov.pl {variant}"
        try:
            resp = session.get(DDG_HTML, params={"q": ddg_query}, timeout=30)
            if not resp.ok or resp.status_code in (403, 429):
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for a in soup.select('a.result__a[href], a[data-testid="result-title-a"][href]'):
                href = _unwrap_url(a.get("href", ""))
                title = a.get_text(" ", strip=True)
                if any(d in href for d in allowed):
                    results.append({"title": title, "url": href})
            if results:
                return _dedupe(results)
        except Exception:
            continue
    return []


def search(query: str) -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "pl-PL,pl;q=0.9"}
    with requests.Session() as session:
        session.headers.update(headers)
        for finder in (_search_site, _search_duckduckgo):
            results = finder(session, query)
            if results:
                return results
    return []


# ── Module interface ─────────────────────────────────────────────────────────

_LEGAL_SUFFIXES = re.compile(
    r"\b(SPÓŁKA AKCYJNA|SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ|SPÓŁKA JAWNA|"
    r"SPÓŁKA KOMANDYTOWA|SPÓŁKA PARTNERSKA|SPÓŁKA CYWILNA|"
    r"S\.A\.|SP\. Z O\.O\.|SP\. J\.|SP\. K\.|S\.K\.A\.|"
    r"AKCYJNA|OGRANICZONĄ|ODPOWIEDZIALNOŚCIĄ)\b",
    re.IGNORECASE,
)


def _shorten_name(name: str) -> str:
    """Wyciąga rdzeń nazwy firmy — usuwa formę prawną i nadmiarowe słowa."""
    short = _LEGAL_SUFFIXES.sub("", name).strip(" ,.-")
    # Jeśli po usunięciu zostaje tylko jedno słowo, użyj go
    words = short.split()
    if not words:
        return name
    # Bierz pierwsze 2-3 znaczące słowa
    return " ".join(words[:3])


def run(query: str, query_type: str = "auto") -> dict:
    try:
        # Spróbuj pełną nazwą, potem skróconą jeśli brak wyników
        results = search(query)
        if not results and len(query.split()) > 2:
            short = _shorten_name(query)
            if short.lower() != query.lower():
                results = search(short)
        return {
            "status": "ok" if results else "not_found",
            "data": {"decisions": results[:20]},
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "data": {}}
