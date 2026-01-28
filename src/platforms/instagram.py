"""Instagram platform implementation"""

import random
import time
from typing import Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

from .base import BasePlatform, PostResult, WarmupStats


# Selectors - Instagram DOM changes frequently, may need updates
class S:
    # Login
    LOGIN_USERNAME = "//input[@name='username']"
    LOGIN_PASSWORD = "//input[@name='password']"
    LOGIN_SUBMIT = "//button[@type='submit']"
    
    # Login detection
    PROFILE_ICON = "//a[contains(@href,'/accounts/')]"
    NAV_PROFILE = "//*[name()='svg' and @aria-label='Profile']"
    HOME_ICON = "//*[name()='svg' and @aria-label='Home']"
    
    # Feed
    POST_ARTICLE = "//article"
    POST_IMAGE = "//article//img"
    LIKE_BTN = "//*[name()='svg' and @aria-label='Like']"
    UNLIKE_BTN = "//*[name()='svg' and @aria-label='Unlike']"
    COMMENT_BTN = "//*[name()='svg' and @aria-label='Comment']"
    
    # Create post
    CREATE_BTN = "//*[name()='svg' and @aria-label='New post']"
    FILE_INPUT = "//input[@type='file']"
    NEXT_BTN = "//button[contains(text(),'Next')]"
    CAPTION_INPUT = "//textarea[@aria-label='Write a caption...']"
    SHARE_BTN = "//button[contains(text(),'Share')]"
    
    # Dialogs
    NOT_NOW_BTN = "//button[contains(text(),'Not Now')]"
    TURN_ON_BTN = "//button[contains(text(),'Turn On')]"


class InstagramPlatform(BasePlatform):
    """Instagram browser automation"""

    IDENTIFIER = "instagram"
    NAME = "Instagram"
    BASE_URL = "https://www.instagram.com"

    def login(self, username: str, password: str) -> bool:
        """
        Login to Instagram.
        
        Note: Instagram may require additional verification (2FA, suspicious login).
        Use with AdsPower profiles that already have cookies/session.
        """
        self.driver.get(f"{self.BASE_URL}/accounts/login/")
        self.human.delay(2, 4)

        if self.is_logged_in():
            return True

        try:
            # Enter username
            username_input = self.wait.until(
                EC.presence_of_element_located((By.XPATH, S.LOGIN_USERNAME))
            )
            self.human.type_text(username_input, username)
            self.human.delay(0.5, 1)

            # Enter password
            password_input = self.driver.find_element(By.XPATH, S.LOGIN_PASSWORD)
            self.human.type_text(password_input, password)
            self.human.delay(0.5, 1)

            # Submit
            submit_btn = self.driver.find_element(By.XPATH, S.LOGIN_SUBMIT)
            self.human.click(submit_btn)

            self.human.delay(4, 6)
            
            # Handle "Save Login Info" popup
            self._dismiss_popup()
            
            # Handle "Turn on Notifications" popup
            self._dismiss_popup()

            return self.is_logged_in()

        except Exception as e:
            print(f"Instagram login failed: {e}")
            return False

    def is_logged_in(self) -> bool:
        """Check if currently logged in by looking for nav elements"""
        try:
            # Look for home icon in nav (only visible when logged in)
            self.driver.find_element(By.XPATH, S.HOME_ICON)
            return True
        except Exception:
            pass
        
        try:
            # Alternative: check for profile link
            self.driver.find_element(By.XPATH, S.NAV_PROFILE)
            return True
        except Exception:
            pass
        
        return False

    def warmup(self, duration_minutes: int = 5) -> WarmupStats:
        """
        Browse feed and engage naturally.
        
        Actions:
        - Scroll through feed
        - View posts (click to expand)
        - Occasionally like posts (low rate to avoid detection)
        """
        stats = WarmupStats(duration_minutes, 0, 0, 0)
        self.navigate_home()
        self.human.delay(2, 4)

        end_time = time.time() + duration_minutes * 60

        while time.time() < end_time:
            try:
                # Scroll feed
                scroll_amount = random.randint(300, 600)
                self.human.scroll(scroll_amount)
                self.human.delay(2, 5)

                # Find posts in viewport
                posts = self.driver.find_elements(By.XPATH, S.POST_ARTICLE)
                
                if posts and random.random() < 0.3:  # 30% chance to interact
                    post = random.choice(posts[:5])
                    stats.posts_viewed += 1
                    
                    # Scroll post into view
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                        post
                    )
                    self.human.delay(2, 4)
                    
                    # Maybe like (10% chance - keep low to avoid detection)
                    if random.random() < 0.10:
                        try:
                            like_btn = post.find_element(By.XPATH, f".{S.LIKE_BTN}")
                            self.human.click(like_btn)
                            stats.likes_given += 1
                            self.human.delay(1, 2)
                        except Exception:
                            pass  # Already liked or button not found

                # Random pause to simulate reading
                self.human.delay(3, 8)

            except Exception as e:
                print(f"Warmup iteration error: {e}")
                self.navigate_home()
                self.human.delay(2, 4)

        return stats

    def post(self, content: Dict[str, Any]) -> PostResult:
        """
        Create a new Instagram post.

        content: {
            "message": "Caption text",
            "media": [{"path": "/path/to/image.jpg"}],  # Required - at least 1 image
            "location": "Location name",  # Optional
            "tags": ["tag1", "tag2"]  # Optional - will be added as hashtags
        }
        
        Note: Instagram requires at least one image/video for posts.
        """
        if not content.get("media"):
            return PostResult(
                id=content.get("id", ""),
                post_id="",
                release_url="",
                status="error: Instagram requires media (image/video)"
            )

        try:
            self.navigate_home()
            self.human.delay(2, 3)

            # Click create button
            create_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, S.CREATE_BTN))
            )
            self.human.click(create_btn)
            self.human.delay(1, 2)

            # Upload file
            file_input = self.wait.until(
                EC.presence_of_element_located((By.XPATH, S.FILE_INPUT))
            )
            
            # Upload first image
            media_path = content["media"][0]["path"]
            file_input.send_keys(media_path)
            self.human.delay(3, 5)

            # Click Next (crop screen)
            next_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, S.NEXT_BTN))
            )
            self.human.click(next_btn)
            self.human.delay(1, 2)

            # Click Next (filters screen)
            next_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, S.NEXT_BTN))
            )
            self.human.click(next_btn)
            self.human.delay(1, 2)

            # Enter caption
            caption_input = self.wait.until(
                EC.presence_of_element_located((By.XPATH, S.CAPTION_INPUT))
            )
            
            caption = content.get("message", "")
            
            # Add hashtags
            if content.get("tags"):
                caption += "\n\n" + " ".join(f"#{tag}" for tag in content["tags"])
            
            self.human.type_text(caption_input, caption)
            self.human.delay(1, 2)

            # Share
            share_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, S.SHARE_BTN))
            )
            self.human.click(share_btn)

            # Wait for upload
            self.human.delay(5, 10)

            return PostResult(
                id=content.get("id", ""),
                post_id="pending",  # TODO: extract from response
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

    def _dismiss_popup(self):
        """Dismiss common Instagram popups (Save Login, Notifications)"""
        try:
            not_now = self.driver.find_element(By.XPATH, S.NOT_NOW_BTN)
            self.human.click(not_now)
            self.human.delay(1, 2)
        except Exception:
            pass

    def explore_hashtag(self, hashtag: str, view_count: int = 5) -> int:
        """
        Browse posts under a hashtag.
        
        Returns number of posts viewed.
        """
        self.driver.get(f"{self.BASE_URL}/explore/tags/{hashtag}/")
        self.human.delay(3, 5)
        
        viewed = 0
        
        try:
            posts = self.driver.find_elements(By.XPATH, "//article//a")
            
            for post in posts[:view_count]:
                try:
                    self.human.click(post)
                    self.human.delay(3, 6)
                    viewed += 1
                    
                    # Close modal (press Escape)
                    self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                    self.human.delay(1, 2)
                    
                except Exception:
                    pass
                    
        except Exception:
            pass
        
        return viewed

