"""Base platform interface - mirrors SocialProvider pattern from AXON"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from src.browser.humanize import HumanizedActions


@dataclass
class PostResult:
    """Result of posting - matches PostResponse from AXON"""
    id: str
    post_id: str
    release_url: str
    status: str


@dataclass
class WarmupStats:
    """Stats from warmup session"""
    duration_minutes: int
    posts_viewed: int
    likes_given: int
    comments_read: int


class BasePlatform(ABC):
    """
    Base class for browser-automated platforms.
    Mirrors the SocialProvider interface from AXON.
    """

    IDENTIFIER: str = "base"
    NAME: str = "Base Platform"
    BASE_URL: str = ""

    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)
        self.human = HumanizedActions(driver)

    @abstractmethod
    def login(self, phone: str, password: str) -> bool:
        """Login to platform. Returns True if successful."""
        pass

    @abstractmethod
    def is_logged_in(self) -> bool:
        """Check if currently logged in."""
        pass

    @abstractmethod
    def post(self, content: Dict[str, Any]) -> PostResult:
        """
        Post content to platform.

        content: {
            "message": str,
            "media": [{"type": "image"|"video", "path": str}],
            "settings": {...}
        }
        """
        pass

    @abstractmethod
    def warmup(self, duration_minutes: int = 5) -> WarmupStats:
        """Run warmup session - browse, like, engage naturally."""
        pass

    def navigate_home(self):
        """Go to platform home page"""
        self.driver.get(self.BASE_URL)
        self.human.delay(2, 4)
