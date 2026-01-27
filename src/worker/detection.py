"""Blocked/Captcha detection module - identify when we're being blocked"""

import re
from dataclasses import dataclass
from typing import Optional, List
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By


@dataclass
class BlockDetectionResult:
    """Result of block detection check"""
    blocked: bool
    block_reason: Optional[str] = None
    final_url: str = ""
    page_title: str = ""
    page_fingerprint: dict = None
    
    def __post_init__(self):
        if self.page_fingerprint is None:
            self.page_fingerprint = {}
    
    def to_dict(self) -> dict:
        return {
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "final_url": self.final_url,
            "page_title": self.page_title,
            "page_fingerprint": self.page_fingerprint,
        }


class BlockDetector:
    """
    Detects if browser has been blocked/redirected to captcha.
    
    Detection is passive - we only identify, never bypass.
    """
    
    BLOCKED_URL_PATTERNS = [
        r"verify",
        r"captcha", 
        r"challenge",
        r"security[_-]?check",
        r"robot",
        r"blocked",
        r"access[_-]?denied",
        r"forbidden",
        r"login.*required",
        r"auth.*required",
    ]
    
    BLOCKED_TITLE_KEYWORDS = [
        "验证", "验证码", "安全验证", "人机验证", "滑动验证",
        "访问被拒绝", "禁止访问", "请求被拦截",

        "verify", "verification", "captcha", "robot", "blocked",
        "access denied", "forbidden", "security check", "challenge",
        "are you human", "prove you're human",
    ]
    
    BLOCKED_BODY_KEYWORDS = [
        "请完成验证", "滑动滑块", "点击验证", "安全验证", 
        "请拖动滑块", "请按顺序点击", "网络异常", "访问频繁",
        "系统检测到", "操作过于频繁", "请稍后再试",
        "complete the captcha", "verify you are human", 
        "unusual traffic", "automated requests", "rate limit",
        "please try again later", "too many requests",
    ]
    
    # Specific platform patterns (extensible)
    PLATFORM_PATTERNS = {
        "xiaohongshu": {
            "verify_urls": ["xiaohongshu.com/web-login", "xiaohongshu.com/explore"],
            "keywords": ["小红书", "登录", "验证"],
        },
    }
    
    def __init__(self, original_url: str = None):
        """
        Args:
            original_url: The URL we intended to visit (for redirect detection)
        """
        self.original_url = original_url
    
    def detect(self, driver: WebDriver) -> BlockDetectionResult:
        """
        Run all detection checks.
        
        Returns:
            BlockDetectionResult with blocked status and details
        """
        final_url = driver.current_url
        page_title = driver.title or ""
        
        # Build fingerprint
        fingerprint = self._build_fingerprint(driver)
        
        # Check 1: URL patterns
        url_blocked, url_reason = self._check_url(final_url)
        if url_blocked:
            return BlockDetectionResult(
                blocked=True,
                block_reason=url_reason,
                final_url=final_url,
                page_title=page_title,
                page_fingerprint=fingerprint,
            )
        
        # Check 2: Redirect detection (if original URL provided)
        if self.original_url:
            redirect_blocked, redirect_reason = self._check_redirect(
                self.original_url, final_url
            )
            if redirect_blocked:
                return BlockDetectionResult(
                    blocked=True,
                    block_reason=redirect_reason,
                    final_url=final_url,
                    page_title=page_title,
                    page_fingerprint=fingerprint,
                )
        
        # Check 3: Title keywords
        title_blocked, title_reason = self._check_title(page_title)
        if title_blocked:
            return BlockDetectionResult(
                blocked=True,
                block_reason=title_reason,
                final_url=final_url,
                page_title=page_title,
                page_fingerprint=fingerprint,
            )
        
        # Check 4: Body content (lightweight - only if suspicious)
        if fingerprint.get("element_count", 0) < 10:
            body_blocked, body_reason = self._check_body(driver)
            if body_blocked:
                return BlockDetectionResult(
                    blocked=True,
                    block_reason=body_reason,
                    final_url=final_url,
                    page_title=page_title,
                    page_fingerprint=fingerprint,
                )
        
        # Check 5: Empty page with redirect
        if fingerprint.get("element_count", 0) == 0 and self.original_url:
            if self._is_different_domain(self.original_url, final_url):
                return BlockDetectionResult(
                    blocked=True,
                    block_reason="empty_page_redirect",
                    final_url=final_url,
                    page_title=page_title,
                    page_fingerprint=fingerprint,
                )
        
        return BlockDetectionResult(
            blocked=False,
            final_url=final_url,
            page_title=page_title,
            page_fingerprint=fingerprint,
        )
    
    def _check_url(self, url: str) -> tuple[bool, Optional[str]]:
        """Check URL for blocking patterns"""
        url_lower = url.lower()
        for pattern in self.BLOCKED_URL_PATTERNS:
            if re.search(pattern, url_lower):
                return True, f"url_pattern:{pattern}"
        return False, None
    
    def _check_redirect(self, original: str, final: str) -> tuple[bool, Optional[str]]:
        """Check if redirected to a different domain (potential block)"""
        # Extract domains
        from urllib.parse import urlparse
        orig_domain = urlparse(original).netloc
        final_domain = urlparse(final).netloc
        
        # Same domain is fine
        if orig_domain == final_domain:
            return False, None
        
        # Check if final URL looks like a verify/login page
        if any(kw in final.lower() for kw in ["login", "verify", "captcha", "auth"]):
            return True, f"captcha_redirect:{final_domain}"
        
        return False, None
    
    def _check_title(self, title: str) -> tuple[bool, Optional[str]]:
        """Check page title for blocking keywords"""
        title_lower = title.lower()
        for keyword in self.BLOCKED_TITLE_KEYWORDS:
            if keyword.lower() in title_lower:
                return True, f"title_keyword:{keyword}"
        return False, None
    
    def _check_body(self, driver: WebDriver) -> tuple[bool, Optional[str]]:
        """Check body content for blocking keywords (lightweight)"""
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            text = body.text[:2000] 
            text_lower = text.lower()
            
            for keyword in self.BLOCKED_BODY_KEYWORDS:
                if keyword.lower() in text_lower:
                    return True, f"body_keyword:{keyword}"
        except Exception:
            pass
        return False, None
    
    def _build_fingerprint(self, driver: WebDriver) -> dict:
        """Build page fingerprint for diagnostics"""
        try:
            # Count basic elements
            all_elements = driver.find_elements(By.XPATH, "//*")
            links = driver.find_elements(By.TAG_NAME, "a")
            images = driver.find_elements(By.TAG_NAME, "img")
            forms = driver.find_elements(By.TAG_NAME, "form")
            inputs = driver.find_elements(By.TAG_NAME, "input")
            
            return {
                "element_count": len(all_elements),
                "link_count": len(links),
                "image_count": len(images),
                "form_count": len(forms),
                "input_count": len(inputs),
            }
        except Exception:
            return {"element_count": 0}
    
    def _is_different_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs have different domains"""
        from urllib.parse import urlparse
        return urlparse(url1).netloc != urlparse(url2).netloc


def detect_block(driver: WebDriver, original_url: str = None) -> BlockDetectionResult:
    """
    Convenience function to detect blocking.
    
    Usage:
        result = detect_block(driver, original_url="https://xiaohongshu.com/explore")
        if result.blocked:
            print(f"Blocked! Reason: {result.block_reason}")
    """
    detector = BlockDetector(original_url)
    return detector.detect(driver)

