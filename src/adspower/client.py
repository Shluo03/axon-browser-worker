"""AdsPower Local API Client"""

import requests
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class BrowserConnection:
    """Browser connection info returned by AdsPower"""
    profile_id: str
    selenium_address: str
    cdp_url: str
    chromedriver_path: str


class AdsPowerClient:
    """AdsPower Local API Client - manages browser profiles"""

    def __init__(self, api_url: str = "http://127.0.0.1:50325", timeout: int = 30):
        self.api_url = api_url
        self.timeout = timeout
        self._session = requests.Session()

    def health_check(self) -> bool:
        """Check if AdsPower is running"""
        try:
            resp = self._get("/status")
            return resp.get("code") == 0
        except Exception:
            return False

    def start(self, profile_id: str) -> BrowserConnection:
        """Start browser profile, return connection info"""
        resp = self._get("/api/v1/browser/start", params={"user_id": profile_id})
        if resp.get("code") != 0:
            raise AdsPowerError(f"Start failed: {resp.get('msg')}")

        data = resp["data"]
        return BrowserConnection(
            profile_id=profile_id,
            selenium_address=data["ws"]["selenium"],
            cdp_url=data["ws"]["puppeteer"],
            chromedriver_path=data["webdriver"],
        )

    def stop(self, profile_id: str) -> bool:
        """Stop browser profile"""
        resp = self._get("/api/v1/browser/stop", params={"user_id": profile_id})
        return resp.get("code") == 0

    def list_profiles(self, page: int = 1, page_size: int = 100) -> list:
        """List all profiles"""
        resp = self._get("/api/v1/user/list", params={"page": page, "page_size": page_size})
        return resp.get("data", {}).get("list", [])

    def create_profile(self, name: str, proxy: Optional[Dict[str, Any]] = None) -> str:
        """Create new profile, return profile_id"""
        payload = {"name": name, "group_id": "0"}
        if proxy:
            payload["user_proxy_config"] = {
                "proxy_type": proxy.get("type", "http"),
                "proxy_host": proxy["host"],
                "proxy_port": proxy["port"],
                "proxy_user": proxy.get("user", ""),
                "proxy_password": proxy.get("password", ""),
            }

        resp = self._post("/api/v1/user/create", json=payload)
        if resp.get("code") != 0:
            raise AdsPowerError(f"Create failed: {resp.get('msg')}")
        return resp["data"]["id"]

    def _get(self, endpoint: str, **kwargs) -> Dict:
        kwargs.setdefault("timeout", self.timeout)
        r = self._session.get(f"{self.api_url}{endpoint}", **kwargs)
        r.raise_for_status()
        return r.json()

    def _post(self, endpoint: str, **kwargs) -> Dict:
        kwargs.setdefault("timeout", self.timeout)
        r = self._session.post(f"{self.api_url}{endpoint}", **kwargs)
        r.raise_for_status()
        return r.json()


class AdsPowerError(Exception):
    """AdsPower API error"""
    pass
