"""Human-like browser interactions"""

import random
import time
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys


class HumanizedActions:
    """Simulates human-like browser interactions"""

    def __init__(self, driver: WebDriver):
        self.driver = driver

    def delay(self, min_sec: float = 0.5, max_sec: float = 2.0):
        """Random delay"""
        time.sleep(random.uniform(min_sec, max_sec))

    def type_text(self, element: WebElement, text: str, typo_rate: float = 0.02):
        """Type text like a human with random speed and occasional typos"""
        element.click()
        self.delay(0.2, 0.5)

        for char in text:
            time.sleep(random.uniform(0.05, 0.18))

            # Occasional typo
            if random.random() < typo_rate:
                element.send_keys(random.choice("abcdefghijklmnopqrstuvwxyz"))
                time.sleep(random.uniform(0.1, 0.25))
                element.send_keys(Keys.BACKSPACE)

            element.send_keys(char)

    def click(self, element: WebElement):
        """Click element like a human - scroll into view first"""
        self.driver.execute_script(
            "arguments[0].scrollIntoView({behavior:'smooth',block:'center'})",
            element
        )
        self.delay(0.3, 0.6)

        # Click with slight offset
        size = element.size
        offset_x = random.randint(3, max(3, size["width"] - 3))
        offset_y = random.randint(3, max(3, size["height"] - 3))

        actions = ActionChains(self.driver)
        actions.move_to_element_with_offset(element, offset_x, offset_y)
        actions.pause(random.uniform(0.05, 0.15))
        actions.click()
        actions.perform()

    def scroll(self, pixels: int = 500):
        """Scroll down with human-like behavior"""
        scrolled = 0
        while scrolled < pixels:
            step = random.randint(80, 180)
            step = min(step, pixels - scrolled)
            self.driver.execute_script(f"window.scrollBy(0,{step})")
            scrolled += step
            time.sleep(random.uniform(0.08, 0.25))

            # Occasionally pause to "read"
            if random.random() < 0.1:
                time.sleep(random.uniform(1, 3))

    def browse(self, duration_sec: int = 60):
        """Browse page naturally for given duration"""
        end_time = time.time() + duration_sec

        while time.time() < end_time:
            self.scroll(random.randint(200, 500))
            self.delay(2, 6)

            # Occasionally scroll back up
            if random.random() < 0.08:
                self.driver.execute_script("window.scrollTo({top:0,behavior:'smooth'})")
                self.delay(1, 2)
