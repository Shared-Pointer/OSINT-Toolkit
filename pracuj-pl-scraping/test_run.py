from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import quote
import pandas as pd
import time

searchKeyword = "Python"
searchLocation = "Warszawa"
daysBack = 30

chromeOptions = Options()
chromeOptions.add_experimental_option("excludeSwitches", ["enable-automation"])
chromeOptions.add_experimental_option("useAutomationExtension", False)
chromeOptions.add_argument("--disable-blink-features=AutomationControlled")
chromeOptions.add_argument("--start-maximized")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chromeOptions)
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
})

kwEncoded = quote(searchKeyword)
locEncoded = quote(searchLocation)
startUrl = f"https://www.pracuj.pl/praca/{kwEncoded};kw/{locEncoded};wp?rd={daysBack}"
print(f"URL: {startUrl}")
driver.get(startUrl)
time.sleep(3)

try:
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Akceptuj wszystkie')]"))
    ).click()
    time.sleep(2)
    print("Cookies zaakceptowane.")
except Exception:
    print("Brak cookies popup.")

jobOffersList = []
page = 1

while True:
    print(f"\n--- Strona {page} ---")
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-test='default-offer']"))
        )
    except Exception as e:
        print(f"Brak ofert na stronie: {e}")
        break

    offers = driver.find_elements(By.CSS_SELECTOR, "[data-test='default-offer']")
    print(f"Ofert na stronie: {len(offers)}")

    for offer in offers:
        try:
            try:
                linkEl = offer.find_element(By.CSS_SELECTOR, "a[data-test='link-offer-title']")
            except Exception:
                linkEl = offer.find_element(By.CSS_SELECTOR, "a[data-test='link-offer']")
            title = offer.find_element(By.CSS_SELECTOR, "[data-test='offer-title']").text.strip()
            company = offer.find_element(By.CSS_SELECTOR, "[data-test='text-company-name']").text.strip()
            link = linkEl.get_attribute("href")
            try:
                region = offer.find_element(By.CSS_SELECTOR, "[data-test='text-region']").text.strip()
            except Exception:
                region = ""
            try:
                salary = offer.find_element(By.CSS_SELECTOR, "[data-test='offer-salary']").text.strip()
            except Exception:
                salary = ""
            jobOffersList.append({
                "job title": title,
                "company name": company,
                "region": region,
                "salary": salary,
                "link": link,
            })
        except Exception as e:
            print(f"  Błąd przy parsowaniu: {e}")
            continue

    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        nextBtn = driver.find_element(By.CSS_SELECTOR, "[data-test='bottom-pagination-button-next']")
        driver.execute_script("arguments[0].click();", nextBtn)
        page += 1
        time.sleep(3)
        if page > 3:
            print("Zatrzymano na stronie 3 (test).")
            break
    except Exception:
        print("Ostatnia strona.")
        break

print(f"\n=== WYNIKI ===")
print(f"Zebrano ofert łącznie: {len(jobOffersList)}")

if jobOffersList:
    df = pd.DataFrame(jobOffersList)
    df.to_excel("jobOffers.xlsx", index=False)
    print("Zapisano do jobOffers.xlsx")
    print(df[["job title", "company name", "salary"]].head(10).to_string())

driver.quit()
print("\nTest zakończony.")
