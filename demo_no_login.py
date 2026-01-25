"""Demo without login - shows all core capabilities"""

import sys
import time
sys.path.insert(0, ".")

from src.browser import BrowserSession, HumanizedActions

PROFILE_ID = "k197eg5j"


def demo():
    print("=" * 50)
    print("Axon Browser Worker Demo (No Login Required)")
    print("=" * 50)

    with BrowserSession(PROFILE_ID) as session:
        driver = session.driver
        human = HumanizedActions(driver)

        # 1. 访问小红书首页（不登录也能浏览）
        print("\n1. 访问小红书首页...")
        driver.get("https://www.xiaohongshu.com/explore")
        human.delay(3, 4)
        print(f"   当前URL: {driver.current_url}")

        # 2. 模拟人类滚动浏览
        print("\n2. 模拟人类滚动浏览...")
        for i in range(3):
            human.scroll(400)
            print(f"   滚动 {i+1}/3")
            human.delay(2, 3)

        # 3. 截图保存
        screenshot_path = "/tmp/xiaohongshu_demo.png"
        driver.save_screenshot(screenshot_path)
        print(f"\n3. 截图已保存: {screenshot_path}")

        # 4. 获取页面上的笔记数量
        from selenium.webdriver.common.by import By
        notes = driver.find_elements(By.XPATH, "//section[contains(@class,'note-item')]")
        print(f"\n4. 页面上找到 {len(notes)} 条笔记")

        # 5. 点击一条笔记查看详情（不登录也能看）
        if notes:
            print("\n5. 点击第一条笔记...")
            human.click(notes[0])
            human.delay(3, 4)
            print(f"   笔记详情页: {driver.current_url}")

            # 截图笔记详情
            detail_path = "/tmp/xiaohongshu_note.png"
            driver.save_screenshot(detail_path)
            print(f"   笔记截图: {detail_path}")

        print("\n" + "=" * 50)
        print("Demo 完成！浏览器将在 5 秒后关闭...")
        print("=" * 50)
        time.sleep(5)


if __name__ == "__main__":
    demo()
