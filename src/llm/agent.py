"""LLM Decision Agent - assists with exceptions and unknown states"""

import json
from typing import Optional, Dict, Any
from openai import OpenAI
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By


class DecisionAgent:
    """
    LLM agent that assists when Selenium encounters unknown situations.
    Only called on exceptions - not for every action.
    """

    def __init__(
        self,
        driver: WebDriver,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat"
    ):
        self.driver = driver
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def find_element(self, description: str) -> Optional[Dict[str, str]]:
        """
        Find element by natural language description.
        Returns {"by": "xpath|css", "value": "..."} or None.
        """
        html = self._get_simplified_html()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": f"""Find the element matching: "{description}"

HTML (simplified):
{html[:4000]}

Return JSON only: {{"by": "xpath", "value": "//..."}}
Or {{"by": "css", "value": "..."}}
Or {{"error": "not found"}}"""
            }],
            temperature=0.1,
            max_tokens=200
        )

        try:
            return json.loads(response.choices[0].message.content)
        except Exception:
            return None

    def handle_popup(self) -> bool:
        """
        Detect and close popup/modal. Returns True if handled.
        """
        html = self._get_simplified_html()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": f"""Is there a popup/modal/dialog on this page? If yes, how to close it?

HTML:
{html[:3000]}

Return JSON: {{"has_popup": true/false, "close_selector": "xpath or css to close button"}}"""
            }],
            temperature=0.1,
            max_tokens=150
        )

        try:
            result = json.loads(response.choices[0].message.content)
            if result.get("has_popup") and result.get("close_selector"):
                selector = result["close_selector"]
                by = By.XPATH if selector.startswith("/") else By.CSS_SELECTOR
                self.driver.find_element(by, selector).click()
                return True
        except Exception:
            pass

        return False

    def decide_action(self, task: str, error: str) -> Dict[str, Any]:
        """
        Decide what to do when task fails.
        Returns {"action": "retry|skip|abort", "reason": "..."}
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": f"""Task failed. What should we do?

Task: {task}
Error: {error}

Return JSON: {{"action": "retry" or "skip" or "abort", "reason": "brief explanation"}}"""
            }],
            temperature=0.3,
            max_tokens=100
        )

        try:
            return json.loads(response.choices[0].message.content)
        except Exception:
            return {"action": "retry", "reason": "parse failed, defaulting to retry"}

    def _get_simplified_html(self) -> str:
        """Get simplified page HTML for LLM analysis"""
        return self.driver.execute_script("""
            function s(el, d=0) {
                if (d > 3) return '';
                let r = '<' + el.tagName.toLowerCase();
                if (el.id) r += ' id="' + el.id + '"';
                if (el.className) r += ' class="' + el.className.toString().slice(0,50) + '"';
                if (el.type) r += ' type="' + el.type + '"';
                r += '>';
                if (!el.children.length) r += (el.textContent || '').trim().slice(0, 30);
                else for (let c of el.children) r += s(c, d+1);
                return r + '</' + el.tagName.toLowerCase() + '>';
            }
            return s(document.body);
        """)
