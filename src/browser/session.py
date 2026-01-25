"""Browser session management with AdsPower"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from src.adspower import AdsPowerClient, BrowserConnection


class BrowserSession:
    """
    Manages browser lifecycle with AdsPower.

    Usage:
        with BrowserSession("profile_id") as session:
            session.driver.get("https://example.com")
    """

    def __init__(self, profile_id: str, adspower: AdsPowerClient = None):
        self.profile_id = profile_id
        self.adspower = adspower or AdsPowerClient()
        self._connection: BrowserConnection = None
        self._driver: webdriver.Chrome = None

    @property
    def driver(self) -> webdriver.Chrome:
        if not self._driver:
            raise RuntimeError("Session not started")
        return self._driver

    def start(self) -> "BrowserSession":
        """Start browser and connect Selenium"""
        self._connection = self.adspower.start(self.profile_id)

        options = Options()
        options.debugger_address = self._connection.selenium_address
        service = Service(executable_path=self._connection.chromedriver_path)
        self._driver = webdriver.Chrome(service=service, options=options)

        return self

    def stop(self):
        """Close browser"""
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

        if self._connection:
            self.adspower.stop(self.profile_id)
            self._connection = None

    def __enter__(self) -> "BrowserSession":
        return self.start()

    def __exit__(self, *args):
        self.stop()
