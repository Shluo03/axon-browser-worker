import requests
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

ADSPOWER_API = "http://127.0.0.1:50325"
PROFILE_ID = "k197eg5j"

def main():
    # 1. Start AdsPower profile
    resp = requests.get(
        f"{ADSPOWER_API}/api/v1/browser/start",
        params={"user_id": PROFILE_ID}
    ).json()

    if resp.get("code") != 0:
        raise RuntimeError(f"AdsPower start failed: {resp}")

    selenium_addr = resp["data"]["ws"]["selenium"]
    chromedriver_path = resp["data"]["webdriver"]
    print("Selenium debugger address:", selenium_addr)
    print("ChromeDriver path:", chromedriver_path)

    try:
        # 2. Attach Selenium 
        options = Options()
        options.debugger_address = selenium_addr
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)

        # 3. Visit test page
        driver.get("https://example.com")
        time.sleep(2)
        print("Page title:", driver.title)

    finally:
        # 4. Close profile
        requests.get(
            f"{ADSPOWER_API}/api/v1/browser/stop",
            params={"user_id": PROFILE_ID}
        )

if __name__ == "__main__":
    main()
