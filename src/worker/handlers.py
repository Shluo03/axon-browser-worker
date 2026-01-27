"""Built-in task handlers - no login required"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By

from src.browser import HumanizedActions
from .detection import detect_block, BlockDetectionResult


def _save_diagnostic_artifacts(
    driver: WebDriver,
    artifact_path: Path,
    detection: BlockDetectionResult,
    metrics: Dict[str, Any],
) -> List[Path]:
    """
    Save diagnostic artifacts when blocked or for general debugging.
    
    Saves:
    - blocked.png / page.png (screenshot)
    - blocked.html (page source, truncated)
    - result.json (full metrics + detection info)
    """
    artifacts = []
    
    # Screenshot
    screenshot_name = "blocked.png" if detection.blocked else "page.png"
    screenshot = artifact_path / screenshot_name
    try:
        driver.save_screenshot(str(screenshot))
        artifacts.append(screenshot)
    except Exception:
        pass
    
    # Save HTML when blocked (truncated to 50KB)
    if detection.blocked:
        html_path = artifact_path / "blocked.html"
        try:
            html_content = driver.page_source[:50000]  # 50KB limit
            html_path.write_text(html_content, encoding="utf-8")
            artifacts.append(html_path)
        except Exception:
            pass
    
    # Always save result.json
    result_path = artifact_path / "result.json"
    try:
        result_data = {
            "metrics": metrics,
            "detection": detection.to_dict(),
        }
        result_path.write_text(
            json.dumps(result_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        artifacts.append(result_path)
    except Exception:
        pass
    
    return artifacts


def page_probe(
    driver: WebDriver,
    params: Dict[str, Any],
    artifact_path: Path,
) -> Tuple[Dict[str, Any], List[Path]]:
    """
    Open URL, screenshot, count elements.
    Now includes blocked detection!

    params: {"url": "https://...", "selector": "//div[@class='card']"}
    
    Returns metrics with:
    - blocked: true/false
    - block_reason: why blocked (if applicable)
    - final_url: actual URL after redirects
    """
    url = params.get("url", "https://example.com")
    selector = params.get("selector")

    driver.get(url)
    time.sleep(3)

    # Detect if blocked
    detection = detect_block(driver, original_url=url)

    metrics = {
        "url": url,
        "final_url": detection.final_url,
        "title": detection.page_title,
        # Block detection fields
        "blocked": detection.blocked,
        "block_reason": detection.block_reason,
        "page_fingerprint": detection.page_fingerprint,
    }

    if selector:
        elements = driver.find_elements(By.XPATH, selector)
        metrics["element_count"] = len(elements)

    # Save diagnostic artifacts
    artifacts = _save_diagnostic_artifacts(driver, artifact_path, detection, metrics)

    return metrics, artifacts


def scroll_probe(
    driver: WebDriver,
    params: Dict[str, Any],
    artifact_path: Path,
) -> Tuple[Dict[str, Any], List[Path]]:
    """
    Scroll N times, track new elements appearing.
    Now includes blocked detection!

    params: {"url": "...", "selector": "...", "scroll_count": 3}
    
    Returns metrics with:
    - blocked: true/false
    - block_reason: why blocked (if applicable)
    """
    url = params.get("url", "https://example.com")
    selector = params.get("selector", "//section")
    scroll_count = params.get("scroll_count", 3)

    driver.get(url)
    time.sleep(3)

    # Detect if blocked BEFORE scrolling
    detection = detect_block(driver, original_url=url)
    
    # If blocked, save diagnostics and return early
    if detection.blocked:
        metrics = {
            "url": url,
            "final_url": detection.final_url,
            "title": detection.page_title,
            "blocked": True,
            "block_reason": detection.block_reason,
            "page_fingerprint": detection.page_fingerprint,
            "initial_count": 0,
            "final_count": 0,
            "counts_per_scroll": [],
            "new_elements_loaded": 0,
        }
        artifacts = _save_diagnostic_artifacts(driver, artifact_path, detection, metrics)
        return metrics, artifacts

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
        
        # Re-check for blocks after each scroll (page might redirect)
        mid_detection = detect_block(driver, original_url=url)
        if mid_detection.blocked:
            metrics = {
                "url": url,
                "final_url": mid_detection.final_url,
                "title": mid_detection.page_title,
                "blocked": True,
                "block_reason": mid_detection.block_reason,
                "page_fingerprint": mid_detection.page_fingerprint,
                "initial_count": initial_count,
                "final_count": counts[-1],
                "counts_per_scroll": counts,
                "new_elements_loaded": counts[-1] - initial_count,
                "blocked_at_scroll": i + 1,
            }
            artifacts.extend(_save_diagnostic_artifacts(driver, artifact_path, mid_detection, metrics))
            return metrics, artifacts

    metrics = {
        "url": url,
        "final_url": driver.current_url,
        "title": driver.title,
        "blocked": False,
        "block_reason": None,
        "page_fingerprint": detection.page_fingerprint,
        "initial_count": initial_count,
        "final_count": counts[-1],
        "counts_per_scroll": counts,
        "new_elements_loaded": counts[-1] - initial_count,
    }
    
    # Save result.json even on success
    result_path = artifact_path / "result.json"
    try:
        result_path.write_text(
            json.dumps({"metrics": metrics, "detection": detection.to_dict()}, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        artifacts.append(result_path)
    except Exception:
        pass

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
