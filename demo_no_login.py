"""Demo without login - shows all core capabilities"""

import sys
import time
sys.path.insert(0, ".")

from src.browser import BrowserSession, HumanizedActions

PROFILE_ID = "k197eg5j"


def demo():
    print("=" * 50)
    print("Axon Browser Worker Demo (No Login Required)")
    print("=" * 50)

    with BrowserSession(PROFILE_ID) as session:
        driver = session.driver
        human = HumanizedActions(driver)

        # 1. Visit Xiaohongshu homepage
        print("\n1. Visiting Xiaohongshu homepage...")
        driver.get("https://www.xiaohongshu.com/explore")
        human.delay(3, 4)
        print(f"   Current URL: {driver.current_url}")

        # 2. Simulate human scrolling
        print("\n2. Simulating human scrolling...")
        for i in range(3):
            human.scroll(400)
            print(f"   Scroll {i+1}/3")
            human.delay(2, 3)

        # 3. Take screenshot
        screenshot_path = "/tmp/xiaohongshu_demo.png"
        driver.save_screenshot(screenshot_path)
        print(f"\n3. Screenshot saved: {screenshot_path}")

        # 4. Count notes on page
        from selenium.webdriver.common.by import By
        notes = driver.find_elements(By.XPATH, "//section[contains(@class,'note-item')]")
        print(f"\n4. Found {len(notes)} notes on page")

        # 5. Click first note to view details
        if notes:
            print("\n5. Clicking first note...")
            human.click(notes[0])
            human.delay(3, 4)
            print(f"   Note detail page: {driver.current_url}")

            # Screenshot note details
            detail_path = "/tmp/xiaohongshu_note.png"
            driver.save_screenshot(detail_path)
            print(f"   Note screenshot: {detail_path}")

        print("\n" + "=" * 50)
        print("Demo completed! Browser will close in 5 seconds...")
        print("=" * 50)
        time.sleep(5)


if __name__ == "__main__":
    demo()
