"""Robi screenshoty potrzebne do showcase PDF."""
import os, time
from playwright.sync_api import sync_playwright

OUT = "/Users/kajetan/OSINT-Toolkit/showcase_imgs"
os.makedirs(OUT, exist_ok=True)

NIP_WSB   = "8942450411"
NIP_PADLO = "8731247021"

def wait_and_shoot(page, path, wait_ms=600):
    time.sleep(wait_ms / 1000)
    page.screenshot(path=path, full_page=False)
    print(f"  saved: {path}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()

    # Screenshot 1 — strona główna
    page.goto("http://localhost:5001/", timeout=10000)
    page.wait_for_load_state("networkidle")
    wait_and_shoot(page, f"{OUT}/1_home.png")

    # Screenshot 2 — wpisany NIP WSB z rozwijanym dropdown
    page.fill('input[name="query"]', NIP_WSB)
    page.click('select[name="query_type"]')
    wait_and_shoot(page, f"{OUT}/2_nip_dropdown.png")
    page.select_option('select[name="query_type"]', "nip")

    # Wygeneruj raport WSB (pobierz przez requests, nie przez Playwright download)
    import urllib.request, urllib.parse
    data = urllib.parse.urlencode({
        "query": NIP_WSB, "query_type": "nip",
        "modules": ["vat", "krs", "knf", "uokik", "rekrutacje"],
    }, doseq=True).encode()
    req = urllib.request.Request("http://localhost:5001/generate",
                                  data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    # tylko pobieramy PDF — screenshoty raportu webiwebu robimy osobno

    # Screenshot raportu webowego — używamy route do HTML preview
    # Zamiast tego, po prostu sfotografujemy formularz z wypełnionym NIP
    page.goto("http://localhost:5001/", timeout=10000)
    page.fill('input[name="query"]', NIP_WSB)
    page.select_option('select[name="query_type"]', "nip")
    # Odznacz CEIDG (wymaga tokenu)
    ceidg_cb = page.locator('input[name="modules"][value="ceidg"]')
    if ceidg_cb.is_checked():
        ceidg_cb.uncheck()
    wait_and_shoot(page, f"{OUT}/3_wsb_ready.png")

    # Screenshot 6-7 — KNF alert (Marek Padło)
    page.goto("http://localhost:5001/", timeout=10000)
    page.fill('input[name="query"]', NIP_PADLO)
    page.select_option('select[name="query_type"]', "nip")
    ceidg_cb = page.locator('input[name="modules"][value="ceidg"]')
    if ceidg_cb.is_checked():
        ceidg_cb.uncheck()
    wait_and_shoot(page, f"{OUT}/6_padlo_ready.png")

    browser.close()

print("Gotowe!")
