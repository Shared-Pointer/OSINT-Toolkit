import json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    
    # Dodaj User-Agent aby uniknąć blokady
    page.set_extra_http_headers({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    
    page.goto("https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne")
    
    # Czekanie na załadowanie strony
    page.wait_for_load_state("networkidle")
    
    # Pobranie wszystkich tabel z klasą warning-list-table
    warning_tables = page.query_selector_all("table.warning-list-table")
    
    data = []
    if warning_tables:
        print(f"Found {len(warning_tables)} tables\n")
        for table in warning_tables:
            rows = table.query_selector_all("tr.warning-row")
            for row in rows:
                tds = row.query_selector_all("td")
                if len(tds) == 6:
                    entry = {
                        "number": tds[0].inner_text().strip(),
                        "company": tds[1].inner_text().strip(),
                        "krs": tds[2].inner_text().strip(),
                        "prosecutor": tds[3].inner_text().strip(),
                        "date": tds[4].inner_text().strip(),
                        "description": tds[5].inner_text().strip()
                    }
                    data.append(entry)
    else:
        print("No tables with class 'warning-list-table' found")
    
    browser.close()

# Wyjście jako JSON
print(json.dumps(data, ensure_ascii=False, indent=2))

# Zapisz do pliku JSON
with open('knfList.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("Data saved to warnings.json")