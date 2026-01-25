"""Integration test - verify AdsPower + Selenium + Platform works"""

import sys
sys.path.insert(0, ".")

from src.adspower import AdsPowerClient
from src.browser import BrowserSession
from src.platforms import XiaohongshuPlatform

PROFILE_ID = "k197eg5j"  # Your verified profile


def test_adspower_client():
    """Test AdsPower connection"""
    print("1. Testing AdsPower client...")
    client = AdsPowerClient()

    assert client.health_check(), "AdsPower not running!"
    print("   AdsPower is running")

    profiles = client.list_profiles()
    print(f"   Found {len(profiles)} profiles")


def test_browser_session():
    """Test browser session lifecycle"""
    print("\n2. Testing browser session...")

    with BrowserSession(PROFILE_ID) as session:
        session.driver.get("https://httpbin.org/ip")
        print(f"   Connected to browser")

        # Get IP to verify proxy
        ip_text = session.driver.find_element("tag name", "pre").text
        print(f"   IP: {ip_text}")

    print("   Session closed cleanly")


def test_humanized_actions():
    """Test human-like interactions"""
    print("\n3. Testing humanized actions...")

    with BrowserSession(PROFILE_ID) as session:
        session.driver.get("https://example.com")

        from src.browser import HumanizedActions
        human = HumanizedActions(session.driver)

        human.delay(1, 2)
        human.scroll(300)
        print("   Humanized scroll complete")


def test_platform_check():
    """Test platform detection (without login)"""
    print("\n4. Testing platform module...")

    with BrowserSession(PROFILE_ID) as session:
        platform = XiaohongshuPlatform(session.driver)
        platform.navigate_home()

        logged_in = platform.is_logged_in()
        print(f"   Xiaohongshu loaded, logged_in={logged_in}")


if __name__ == "__main__":
    print("=" * 50)
    print("Axon Browser Worker Integration Test")
    print("=" * 50)

    try:
        test_adspower_client()
        test_browser_session()
        test_humanized_actions()
        test_platform_check()

        print("\n" + "=" * 50)
        print("ALL TESTS PASSED")
        print("=" * 50)

    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        raise
