"""Built-in task handlers - no login required"""

import time
from pathlib import Path
from typing import Dict, Any, List, Tuple
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By

from src.browser import HumanizedActions


def page_probe(
    driver: WebDriver,
    params: Dict[str, Any],
    artifact_path: Path,
) -> Tuple[Dict[str, Any], List[Path]]:
    """
    Open URL, screenshot, count elements.

    params: {"url": "https://...", "selector": "//div[@class='card']"}
    """
    url = params.get("url", "https://example.com")
    selector = params.get("selector")

    driver.get(url)
    time.sleep(3)

    metrics = {
        "url": driver.current_url,
        "title": driver.title,
    }

    if selector:
        elements = driver.find_elements(By.XPATH, selector)
        metrics["element_count"] = len(elements)

    # Screenshot
    screenshot = artifact_path / "page.png"
    driver.save_screenshot(str(screenshot))

    return metrics, [screenshot]


def scroll_probe(
    driver: WebDriver,
    params: Dict[str, Any],
    artifact_path: Path,
) -> Tuple[Dict[str, Any], List[Path]]:
    """
    Scroll N times, track new elements appearing.

    params: {"url": "...", "selector": "...", "scroll_count": 3}
    """
    url = params.get("url", "https://example.com")
    selector = params.get("selector", "//section")
    scroll_count = params.get("scroll_count", 3)

    driver.get(url)
    time.sleep(3)

    human = HumanizedActions(driver)
    artifacts = []

    # Initial count
    initial_count = len(driver.find_elements(By.XPATH, selector))
    counts = [initial_count]

    for i in range(scroll_count):
        human.scroll(500)
        time.sleep(2)

        current_count = len(driver.find_elements(By.XPATH, selector))
        counts.append(current_count)

        # Screenshot each scroll
        ss = artifact_path / f"scroll_{i+1}.png"
        driver.save_screenshot(str(ss))
        artifacts.append(ss)

    metrics = {
        "url": driver.current_url,
        "initial_count": initial_count,
        "final_count": counts[-1],
        "counts_per_scroll": counts,
        "new_elements_loaded": counts[-1] - initial_count,
    }

    return metrics, artifacts


def perf_probe(
    driver: WebDriver,
    params: Dict[str, Any],
    artifact_path: Path,
) -> Tuple[Dict[str, Any], List[Path]]:
    """
    Measure page load performance.

    params: {"url": "..."}
    """
    url = params.get("url", "https://example.com")

    start = time.time()
    driver.get(url)
    load_time = time.time() - start

    # Get performance timing from browser
    perf = driver.execute_script("""
        const t = performance.timing;
        return {
            dns: t.domainLookupEnd - t.domainLookupStart,
            connect: t.connectEnd - t.connectStart,
            ttfb: t.responseStart - t.requestStart,
            download: t.responseEnd - t.responseStart,
            dom_interactive: t.domInteractive - t.navigationStart,
            dom_complete: t.domComplete - t.navigationStart,
        };
    """)

    # Count resources
    resources = driver.execute_script(
        "return performance.getEntriesByType('resource').length"
    )

    metrics = {
        "url": driver.current_url,
        "load_time_ms": int(load_time * 1000),
        "resource_count": resources,
        **perf,
    }

    screenshot = artifact_path / "page.png"
    driver.save_screenshot(str(screenshot))

    return metrics, [screenshot]
