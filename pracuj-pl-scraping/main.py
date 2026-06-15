from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import quote
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import time

now = datetime.now()
currentDate = now.strftime("%d/%m/%Y")

# Please modify these variables
searchKeyword = "?"
searchLocation = "?"
senderAddress = "?"
senderKey = "?"
receiverAddress = "?"

# How many days back to search (1 = last 24h, 3 = last 3 days, 30 = last month)
daysBack = 1

# Set up Chrome (cross-platform: Windows / macOS / Linux)
chromeOptions = Options()
chromeOptions.add_experimental_option("detach", True)
chromeOptions.add_experimental_option("excludeSwitches", ["enable-automation"])
chromeOptions.add_experimental_option("useAutomationExtension", False)
chromeOptions.add_argument("--disable-blink-features=AutomationControlled")
chromeOptions.add_argument("--start-maximized")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chromeOptions)
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
})

# Navigate directly to search results
kwEncoded = quote(searchKeyword)
locEncoded = quote(searchLocation)
startUrl = f"https://www.pracuj.pl/praca/{kwEncoded};kw/{locEncoded};wp?rd={daysBack}"
driver.get(startUrl)
time.sleep(3)

# Accept cookies if present
try:
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Akceptuj wszystkie')]"))
    ).click()
    time.sleep(2)
except Exception:
    pass

jobOffersList = []

# Collect offers from every page
while True:
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-test='default-offer']"))
    )

    offers = driver.find_elements(By.CSS_SELECTOR, "[data-test='default-offer']")
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
        except Exception:
            continue

    # Go to next page or stop
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        nextBtn = driver.find_element(By.CSS_SELECTOR, "[data-test='bottom-pagination-button-next']")
        driver.execute_script("arguments[0].click();", nextBtn)
        time.sleep(2)
    except Exception:
        break

# Export to Excel
df = pd.DataFrame(jobOffersList)
df.to_excel("jobOffers.xlsx", index=False)

# Build and send email
message = MIMEMultipart()
message["From"] = senderAddress
message["To"] = receiverAddress
message["Subject"] = f"{searchKeyword} pracuj.pl - {searchLocation} - najnowsze oferty pracy! {currentDate}"

attachment = MIMEBase("application", "octet-stream")
attachment.set_payload(open("jobOffers.xlsx", "rb").read())
encoders.encode_base64(attachment)
attachment.add_header("Content-Disposition", 'attachment; filename="jobOffers.xlsx"')
message.attach(attachment)

session = smtplib.SMTP("smtp.gmail.com", 587)
session.starttls()
session.login(senderAddress, senderKey)
session.sendmail(senderAddress, receiverAddress, message.as_string())
session.quit()
print(f"Mail sent to {receiverAddress}")

driver.quit()
