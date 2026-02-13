"""Xiaohongshu (Little Red Book) platform implementation"""

import random
import time
from typing import Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from .base import BasePlatform, PostResult, WarmupStats


# Selectors - update these when site changes
class S:
    LOGIN_BTN = "//button[contains(text(),'登录')]"
    PHONE_INPUT = "//input[@placeholder='手机号']"
    PASSWORD_INPUT = "//input[@type='password']"
    SUBMIT_BTN = "//button[@type='submit']"
    USER_AVATAR = "//div[contains(@class,'user-avatar')]"
    NOTE_CARD = "//section[contains(@class,'note-item')]"
    LIKE_BTN = "//span[contains(@class,'like-wrapper')]"
    PUBLISH_BTN = "//div[contains(@class,'publish-btn')]"
    TITLE_INPUT = "//input[@placeholder='填写标题']"
    CONTENT_INPUT = "//div[@contenteditable='true']"
    POST_SUBMIT = "//button[contains(text(),'发布')]"
    UPLOAD_INPUT = "//input[@type='file']"


class XiaohongshuPlatform(BasePlatform):
    """Xiaohongshu browser automation"""

    IDENTIFIER = "xiaohongshu"
    NAME = "小红书"
    BASE_URL = "https://www.xiaohongshu.com"

    def login(self, phone: str, password: str) -> bool:
        self.navigate_home()

        if self.is_logged_in():
            return True

        try:
            # Click login
            login_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, S.LOGIN_BTN)))
            self.human.click(login_btn)
            self.human.delay(1, 2)

            # Enter phone
            phone_input = self.wait.until(EC.presence_of_element_located((By.XPATH, S.PHONE_INPUT)))
            self.human.type_text(phone_input, phone)
            self.human.delay(0.5, 1)

            # Enter password
            pwd_input = self.driver.find_element(By.XPATH, S.PASSWORD_INPUT)
            self.human.type_text(pwd_input, password)
            self.human.delay(0.5, 1)

            # Submit
            submit_btn = self.driver.find_element(By.XPATH, S.SUBMIT_BTN)
            self.human.click(submit_btn)

            time.sleep(3)
            return self.is_logged_in()

        except Exception:
            return False

    def is_logged_in(self) -> bool:
        try:
            self.driver.find_element(By.XPATH, S.USER_AVATAR)
            return True
        except Exception:
            return False

    def warmup(self, duration_minutes: int = 5) -> WarmupStats:
        """Browse and engage naturally"""
        stats = WarmupStats(duration_minutes, 0, 0, 0)
        self.navigate_home()

        end_time = time.time() + duration_minutes * 60

        while time.time() < end_time:
            # Browse feed
            self.human.browse(duration_sec=random.randint(20, 40))

            # Click random note
            try:
                notes = self.driver.find_elements(By.XPATH, S.NOTE_CARD)
                if notes:
                    note = random.choice(notes[:8])
                    self.human.click(note)
                    stats.posts_viewed += 1

                    # Read note
                    self.human.delay(5, 12)

                    # Maybe like (15% chance)
                    if random.random() < 0.15:
                        try:
                            like_btn = self.driver.find_element(By.XPATH, S.LIKE_BTN)
                            self.human.click(like_btn)
                            stats.likes_given += 1
                        except Exception:
                            pass

                    # Go back
                    self.driver.back()
                    self.human.delay(1, 2)

            except Exception:
                self.navigate_home()

        return stats

    def post(self, content: Dict[str, Any]) -> PostResult:
        """
        Post a note.

        content: {
            "message": "Post content",
            "title": "Post title",  # optional
            "media": [{"path": "/path/to/image.jpg"}],  # optional
            "tags": ["tag1", "tag2"]  # optional
        }
        """
        try:
            # Click publish
            publish_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, S.PUBLISH_BTN)))
            self.human.click(publish_btn)
            self.human.delay(1, 2)

            # Upload images if any
            if content.get("media"):
                upload = self.driver.find_element(By.XPATH, S.UPLOAD_INPUT)
                for media in content["media"]:
                    upload.send_keys(media["path"])
                    self.human.delay(2, 4)

            # Title
            if content.get("title"):
                title_input = self.wait.until(EC.presence_of_element_located((By.XPATH, S.TITLE_INPUT)))
                self.human.type_text(title_input, content["title"])
                self.human.delay(0.5, 1)

            # Content
            content_input = self.driver.find_element(By.XPATH, S.CONTENT_INPUT)
            text = content["message"]

            # Add tags
            if content.get("tags"):
                text += " " + " ".join(f"#{t}" for t in content["tags"])

            self.human.type_text(content_input, text)
            self.human.delay(0.5, 1)

            # Submit
            submit_btn = self.driver.find_element(By.XPATH, S.POST_SUBMIT)
            self.human.click(submit_btn)

            time.sleep(5)

            # TODO: extract actual post_id and url from response
            return PostResult(
                id=content.get("id", ""),
                post_id="pending",
                release_url=self.driver.current_url,
                status="published"
            )

        except Exception as e:
            return PostResult(
                id=content.get("id", ""),
                post_id="",
                release_url="",
                status=f"error: {e}"
            )
