"""Rekrutacje module — oferty pracy z pracuj.pl, NoFluffJobs, JustJoin.it."""

from __future__ import annotations
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
from urllib.parse import quote


# ── pracuj.pl ─────────────────────────────────────────────────────────────────

def _scrape_pracujpl(keyword: str, days_back: int = 30) -> list[dict]:
    from playwright.sync_api import sync_playwright

    url = f"https://www.pracuj.pl/praca/{quote(keyword)};kw?rd={days_back}&rop=50"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="pl-PL",
        )
        page = ctx.new_page()
        page.goto(url, timeout=30000)
        try:
            page.click('button:has-text("Akceptuj")', timeout=4000)
            time.sleep(0.5)
        except Exception:
            pass
        try:
            page.wait_for_selector('[data-test="default-offer"]', timeout=15000)
        except Exception:
            pass
        html = page.content()
        browser.close()

    return _parse_pracujpl(html, keyword)


def _parse_pracujpl(html: str, keyword: str) -> list[dict]:
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return []

    data = json.loads(m.group(1))
    queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
    grouped_offers = []

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

        inner = group.get("offers", [])
        url = inner[0].get("offerAbsoluteUri", "") if inner else ""

        offers.append({
            "title": group.get("jobTitle") or "",
            "company": group.get("companyName") or "",
            "salary": group.get("salaryDisplayText") or None,
            "locations": locations or ["—"],
            "date": (group.get("lastPublicated") or "")[:10],
            "url": url,
            "source": "pracuj.pl",
        })

    return offers


# ── NoFluffJobs ───────────────────────────────────────────────────────────────

def _scrape_nofluffjobs(keyword: str) -> list[dict]:
    from playwright.sync_api import sync_playwright

    url = f"https://nofluffjobs.com/praca?criteria=employer:{quote(keyword)}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="pl-PL",
        )
        page = ctx.new_page()
        page.goto(url, timeout=30000)
        try:
            page.click('button:has-text("Akceptuj")', timeout=3000)
        except Exception:
            pass
        try:
            page.wait_for_selector("nfj-posting-item, .posting-list-item, [class*='posting']", timeout=15000)
        except Exception:
            pass

        offers = page.evaluate("""() => {
            const results = [];
            const seen = new Set();

            // NFF Angular custom elements
            document.querySelectorAll('nfj-posting-item').forEach(item => {
                const link = item.querySelector('a[href*="/praca/"]');
                if (!link || seen.has(link.href)) return;
                seen.add(link.href);
                const title = item.querySelector('[class*="title"], [class*="position"]')?.textContent?.trim() || link.textContent?.trim() || '';
                const company = item.querySelector('[class*="company"], [class*="employer"]')?.textContent?.trim() || '';
                const loc = item.querySelector('[class*="location"], [class*="city"]')?.textContent?.trim() || '';
                const salary = item.querySelector('[class*="salary"]')?.textContent?.trim() || null;
                if (title) results.push({title, company, location: loc, salary, url: link.href});
            });

            // Fallback: generic posting links
            if (results.length === 0) {
                document.querySelectorAll('a[href*="nofluffjobs.com/praca/"]').forEach(a => {
                    if (seen.has(a.href)) return;
                    seen.add(a.href);
                    const card = a.closest('li, article, [class*="item"], [class*="card"]') || a;
                    const title = card.querySelector('h3, h4, [class*="title"]')?.textContent?.trim() || a.textContent?.trim() || '';
                    const company = card.querySelector('[class*="company"]')?.textContent?.trim() || '';
                    const loc = card.querySelector('[class*="location"], [class*="city"]')?.textContent?.trim() || '';
                    if (title && title.length > 3) results.push({title, company, location: loc, salary: null, url: a.href});
                });
            }
            return results;
        }""")

        browser.close()

    for o in offers:
        o["source"] = "nofluffjobs.com"
        o.setdefault("locations", [o.pop("location", "") or "—"])
        o.setdefault("date", "")
    return offers


# ── JustJoin.it ───────────────────────────────────────────────────────────────

def _scrape_justjoinit(keyword: str) -> list[dict]:
    from playwright.sync_api import sync_playwright

    url = f"https://justjoin.it/job-offers/all-locations/all-categories?keyword={quote(keyword)}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="pl-PL",
        )
        page = ctx.new_page()
        page.goto(url, timeout=30000)
        try:
            page.click('button:has-text("Akceptuj")', timeout=3000)
        except Exception:
            pass

        # Czekaj na listę ofert
        try:
            page.wait_for_selector('[data-index], article[class*="offer"], [class*="OfferCard"]', timeout=15000)
        except Exception:
            pass

        # Scrolluj żeby załadować więcej
        for _ in range(3):
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            time.sleep(0.6)

        offers = page.evaluate("""() => {
            const results = [];
            const seen = new Set();

            // JustJoin virtual list items
            const containers = [
                ...document.querySelectorAll('[data-index]'),
                ...document.querySelectorAll('article'),
                ...document.querySelectorAll('[class*="OfferCard"], [class*="offer-card"]'),
            ];

            containers.forEach(container => {
                const link = container.querySelector('a[href*="/job-offer/"]') || container.querySelector('a[href]');
                const href = link?.href || '';
                if (!href || seen.has(href)) return;
                seen.add(href);

                const title = container.querySelector('h2, h3, [class*="Title"], [class*="title"]')?.textContent?.trim() || '';
                const company = container.querySelector('[class*="Company"], [class*="company"], [class*="employer"]')?.textContent?.trim() || '';
                const loc = container.querySelector('[class*="City"], [class*="city"], [class*="location"]')?.textContent?.trim() || '';
                const salary = container.querySelector('[class*="Salary"], [class*="salary"]')?.textContent?.trim() || null;

                if (title && title.length > 3) {
                    results.push({title, company, location: loc, salary, url: href});
                }
            });
            return results;
        }""")

        browser.close()

    for o in offers:
        o["source"] = "justjoin.it"
        o.setdefault("locations", [o.pop("location", "") or "—"])
        o.setdefault("date", "")
    return offers


# ── Module interface ──────────────────────────────────────────────────────────

def _is_nip(q: str) -> bool:
    d = q.replace("-", "").replace(" ", "")
    return d.isdigit() and len(d) == 10


def _shorten(name: str) -> str:
    short = re.sub(
        r"\b(SPÓŁKA AKCYJNA|SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ|"
        r"SPÓŁKA JAWNA|SPÓŁKA KOMANDYTOWA|SPÓŁKA PARTNERSKA|SPÓŁKA CYWILNA|"
        r"S\.A\.|SP\. Z O\.O\.|SP\. J\.|SP\. K\.|S\.K\.A\.|"
        r"AKCYJNA|OGRANICZONĄ|ODPOWIEDZIALNOŚCIĄ)\b",
        "", name, flags=re.IGNORECASE,
    ).strip(" ,.-")
    words = short.split()
    return " ".join(words[:3]) if words else name


def run(query: str, query_type: str = "auto") -> dict:
    if query_type == "nip" or (query_type == "auto" and _is_nip(query)):
        return {"status": "skipped", "error": "Moduł Rekrutacje wymaga nazwy firmy, nie NIP.", "data": {}}

    search_query = _shorten(query) if query_type == "name" else query

    scrapers = {
        "pracuj.pl": _scrape_pracujpl,
        "nofluffjobs.com": _scrape_nofluffjobs,
        "justjoin.it": _scrape_justjoinit,
    }

    all_offers: list[dict] = []
    source_stats: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(fn, search_query): name for name, fn in scrapers.items()}
        for future in _as_completed(futures):
            name = futures[future]
            try:
                offers = future.result(timeout=60)
                source_stats[name] = {"count": len(offers), "error": None}
                all_offers.extend(offers)
            except Exception as e:
                source_stats[name] = {"count": 0, "error": str(e)}

    # Fallback: jeśli skrócona nazwa nic nie dała — spróbuj oryginalną na pracuj.pl
    if not all_offers and search_query != query:
        try:
            fallback = _scrape_pracujpl(query)
            all_offers.extend(fallback)
            source_stats["pracuj.pl"] = {"count": len(fallback), "error": None}
        except Exception:
            pass

    if not all_offers:
        return {
            "status": "not_found",
            "data": {"offers": [], "total_count": 0, "query_used": search_query, "sources": source_stats},
        }

    return {
        "status": "ok",
        "data": {
            "offers": all_offers,
            "total_count": len(all_offers),
            "query_used": search_query,
            "sources": source_stats,
        },
    }
