import html
import re
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
import base64


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
    variants = [q, query.strip(), q.replace(".", " "), q.replace(".", ""), f"\"{q}\"", f"*{q}*"]

    if "." in q:
        host = q.split("/")[0]
        variants.extend([host, re.sub(r"^www\.", "", host), host.split(".")[0], host.replace(".", " ")])

    variants.extend([re.sub(r"[^\w\s\-.]", " ", q).strip()])

    seen = set()
    out = []
    for item in variants:
        item = " ".join(item.split()).strip()
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out


def _extract_uokik_results(html_text: str, base_url: str, relaxed: bool = False):
    soup = BeautifulSoup(html_text, "html.parser")
    results = []

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        title = a.get_text(" ", strip=True)
        if not href:
            continue

        full_url = urljoin(base_url, href)
        low = full_url.lower()

        if "decyzje.uokik.gov.pl" not in full_url:
            continue

        if relaxed:
            if "/bp/dec_prez.nsf/" not in low:
                continue
            if low.endswith((".css", ".js", ".gif", ".jpg", ".jpeg", ".png", ".ico", ".svg", ".woff", ".woff2", ".ttf")):
                continue
        else:
            # UOKiK pages are often OpenDocument links, but keep broader acceptance.
            if "opendocument" not in low and "searchview" not in low:
                if "/0/" not in low and "/bp/" not in low:
                    continue

        results.append({"title": title or full_url, "url": full_url})

    return _dedupe(results)


def _unwrap_url(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    for key in ("uddg", "r", "url"):
        if key in qs and qs[key]:
            return unquote(qs[key][0])

    if "u" in qs and qs["u"]:
        token = qs["u"][0]
        if token.startswith("http"):
            return token

        raw = token[2:] if token.startswith("a1") else token
        raw += "=" * (-len(raw) % 4)
        try:
            decoded = base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8", "ignore")
            if decoded.startswith("http"):
                return decoded
        except Exception:
            pass

    # Fallback: extract any http(s) URL from the string
    match = re.search(r"https?://[^\s&]+", url)
    if match:
        return match.group(0)

    return url


def _is_noise_title(title: str) -> bool:
    noise = {
        "przejdź do zawartości",
        "english",
        "polski",
        "privacy",
        "cookies",
        "about",
        "help",
        "sign in",
        "log in",
    }
    t = " ".join(title.split()).strip().lower()
    return t in noise or len(t) < 3


def _extract_search_engine_results(html_text: str, base_url: str, allowed_domains: tuple[str, ...], engine: str):
    soup = BeautifulSoup(html_text, "html.parser")
    results = []

    if engine == "bing":
        anchors = soup.select("li.b_algo h2 a[href], h2 a[href], a[href][data-template]")
    elif engine == "duckduckgo":
        anchors = soup.select('a[data-testid="result-title-a"][href], a.result__a[href], article a[href]')
    else:
        anchors = soup.select("a[href]")

    for a in anchors:
        href = a.get("href", "")
        if not href:
            continue

        full_url = _unwrap_url(urljoin(base_url, href))
        title = a.get_text(" ", strip=True) or full_url

        if _is_noise_title(title):
            continue

        if any(domain in full_url for domain in allowed_domains):
            results.append({"title": title, "url": full_url})

    return _dedupe(results)


def _form_payload(form, query: str):
    payload = {}

    for tag in form.find_all(["input", "textarea", "select"]):
        name = tag.get("name")
        if not name:
            continue

        tag_type = (tag.get("type") or "").lower()
        if tag_type in {"submit", "button", "image", "reset"}:
            continue

        if tag.name == "select":
            selected = tag.find("option", selected=True)
            payload[name] = selected.get("value", "") if selected else ""
        else:
            payload[name] = tag.get("value", "")

    for key in ("Query", "query", "SearchQuery", "SearchFor", "SearchText", "SearchString", "q"):
        if key in payload:
            payload[key] = query

    if not any(key in payload for key in ("Query", "query", "SearchQuery", "SearchFor", "SearchText", "SearchString", "q")):
        payload["Query"] = query

    return payload


def _search_site(session: requests.Session, query: str):
    base_response = session.get(BASE_URL, timeout=30)
    base_response.raise_for_status()
    base_response.encoding = base_response.apparent_encoding or base_response.encoding

    soup = BeautifulSoup(base_response.text, "html.parser")
    forms = soup.find_all("form")

    search_forms = [
        form for form in forms
        if "searchview" in (form.get("action", "") or "").lower()
        or form.find("input", attrs={"name": "Query"})
        or form.find("input", attrs={"name": "SearchView"})
    ]
    targets = search_forms or [None]

    for variant in _normalize_query(query):
        for form in targets:
            if form is None:
                endpoints = [
                    (f"{BASE_URL}/SearchView", {"SearchView": "", "Query": variant, "SearchOrder": "4", "SearchMax": "0"}),
                    (f"{BASE_URL}/SearchView", {"SearchView": "", "Query": variant, "SearchMax": "50"}),
                    (f"{BASE_URL}/SearchView", {"Query": variant}),
                ]
                for endpoint, params in endpoints:
                    response = session.get(endpoint, params=params, timeout=30)
                    response.raise_for_status()
                    response.encoding = response.apparent_encoding or response.encoding
                    results = _extract_uokik_results(response.text, response.url)
                    if results:
                        return results
            else:
                action = urljoin(base_response.url, form.get("action", ""))
                method = (form.get("method") or "get").lower()
                payload = _form_payload(form, variant)

                response = (
                    session.post(action, data=payload, timeout=30)
                    if method == "post"
                    else session.get(action, params=payload, timeout=30)
                )
                response.raise_for_status()
                response.encoding = response.apparent_encoding or response.encoding

                results = _extract_uokik_results(response.text, response.url)
                if results:
                    return results

    return []


def _search_queries(query: str):
    variants = _normalize_query(query)
    out = []

    for v in variants:
        out.extend([
            f'site:decyzje.uokik.gov.pl/bp/dec_prez.nsf/OpenDocument {v}',
            f"site:decyzje.uokik.gov.pl {v}",
            f"site:uokik.gov.pl {v}",
            f"site:uokik.gov.pl decyzja {v}",
        ])

    seen = set()
    for item in out:
        item = " ".join(item.split()).strip()
        if item and item not in seen:
            seen.add(item)
            yield item


def _safe_get(session: requests.Session, url: str, **kwargs):
    try:
        response = session.get(url, **kwargs)
        if response.status_code in (403, 429):
            return None
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        return response
    except requests.RequestException:
        return None


def _search_duckduckgo(session: requests.Session, query: str):
    allowed = ("decyzje.uokik.gov.pl", "uokik.gov.pl")

    ddg_headers = {
        "User-Agent": session.headers.get("User-Agent", "Mozilla/5.0"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
        "Referer": "https://duckduckgo.com/",
    }

    for ddg_query in _search_queries(query):
        response = _safe_get(session, DDG_HTML, params={"q": ddg_query}, headers=ddg_headers, timeout=30)
        if not response:
            continue

        results = _extract_search_engine_results(
            response.text,
            response.url,
            allowed,
            engine="duckduckgo",
        )
        if results:
            return results

    return []


def _search_bing(session: requests.Session, query: str):
    allowed = ("decyzje.uokik.gov.pl", "uokik.gov.pl")

    bing_headers = {
        "User-Agent": session.headers.get("User-Agent", "Mozilla/5.0"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
        "Referer": "https://www.bing.com/",
    }

    for bing_query in _search_queries(query):
        response = _safe_get(session, BING_HTML, params={"q": bing_query}, headers=bing_headers, timeout=30)
        if not response:
            continue

        results = _extract_search_engine_results(
            response.text,
            response.url,
            allowed,
            engine="bing",
        )
        if results:
            return results

    return []


def _search_latest(session: requests.Session):
    # Try to list newest decisions without a query
    endpoints = [
        f"{BASE_URL}/SearchView?OpenView",
        f"{BASE_URL}/SearchView?OpenView&Count=50",
        f"{BASE_URL}/SearchView?OpenView&Start=1&Count=50",
        f"{BASE_URL}/SearchView",
        f"{BASE_URL}/SearchView?SearchView",
        f"{BASE_URL}/SearchView?SearchView&Count=50",
    ]

    candidates = _discover_view_urls(session) + endpoints

    for base in candidates:
        for params in ("", "Count=50", "Start=1&Count=50"):
            url = base if not params else _with_params(base, params)
            response = _safe_get(session, url, timeout=30)
            if not response:
                continue
            results = _extract_uokik_results(response.text, response.url, relaxed=True)
            if results:
                return results

    return []


def _discover_view_urls(session: requests.Session):
    response = _safe_get(session, f"{BASE_URL}/", timeout=30) or _safe_get(session, BASE_URL, timeout=30)
    if not response:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    urls = set()

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if "?openview" not in href.lower():
            continue
        full_url = urljoin(response.url, href)
        if "/bp/dec_prez.nsf/" in full_url.lower():
            urls.add(full_url)

    return list(urls)


def _with_params(url: str, params: str) -> str:
    return f"{url}{'&' if '?' in url else '?'}{params}"


def search(query: str):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
        "Referer": f"{BASE_URL}/",
    }

    with requests.Session() as session:
        session.headers.update(headers)

        if query.lower() in {"latest", "najnowsze"}:
            return _search_latest(session)

        for finder in (_search_site, _search_duckduckgo, _search_bing):
            results = finder(session, query)
            if results:
                return results

    return []


if __name__ == "__main__":
    q = input("fraza (np. latest): ").strip()
    if not q:
        raise SystemExit("Brak frazy wyszukiwania.")

    data = search(q)

    print(f"wyników: {len(data)}")
    for row in data[:20]:
        print(row)

    if not data:
        print("Brak trafień. Spróbuj 'latest' (najnowsze decyzje) albo pełną nazwę podmiotu.")

    pd.DataFrame(data).to_csv("uokik.csv", index=False, encoding="utf-8-sig")