"""抖音 & 小红书 Playwright 自动化发布模块

使用 Playwright 控制浏览器，自动发布短视频到：
  - 抖音创作服务平台 (creator.douyin.com)
  - 小红书创作者中心 (creator.xiaohongshu.com)

使用方式:
  1. 首次使用: 本地运行 python scripts/save_session.py 扫码登录保存 cookie
  2. 日常运行: 将 cookie 存入 GitHub Secrets，工作流自动调用

注意事项:
  - 抖音/小红书有反爬检测，建议使用 headed 模式+真实 UA
  - Cookie 有效期约 7-30 天，过期后需重新登录
  - 发布频率建议不超过 3 条/天/账号
"""

import asyncio
import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


# ============================================================
#  SessionManager：管理登录态 Cookie
# ============================================================

class SessionManager:
    """跨运行周期的登录态管理。

    Cookie 在 GitHub Actions 中以 base64 编码的 Secret 存储，
    在本地以 JSON 文件存储。
    """

    SESSIONS_DIR = Path(".sessions")

    @classmethod
    def ensure_dir(cls):
        cls.SESSIONS_DIR.mkdir(exist_ok=True)

    @classmethod
    def session_path(cls, platform: str) -> Path:
        cls.ensure_dir()
        return cls.SESSIONS_DIR / f"{platform}_session.json"

    @classmethod
    async def load_session(
        cls,
        page,
        platform: str,
        secret_env: str = "",
    ) -> bool:
        """从文件或 Secret 加载登录态。

        优先级：
          1. 环境变量（GitHub Secret base64）
          2. 本地文件
        """
        data = None

        # 尝试从环境变量加载
        env_value = os.environ.get(secret_env, "") if secret_env else ""
        if env_value:
            try:
                decoded = base64.b64decode(env_value).decode("utf-8")
                data = json.loads(decoded)
                print(f"[Session] 从环境变量 {secret_env} 加载 {platform} 登录态")
            except Exception as e:
                print(f"[Session] Secret 解码失败: {e}")

        # 尝试从本地文件加载
        if not data:
            path = cls.session_path(platform)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print(f"[Session] 从本地文件加载 {platform} 登录态")

        if not data:
            return False

        # 恢复 Cookie
        cookies = data.get("cookies", [])
        if cookies:
            await page.context.add_cookies(cookies)
            print(f"[Session] 恢复了 {len(cookies)} 个 Cookie")

        # 恢复 localStorage
        local_storage = data.get("localStorage", {})
        if local_storage:
            try:
                await page.evaluate(
                    "items => items.forEach(([k, v]) => localStorage.setItem(k, v))",
                    list(local_storage.items()),
                )
                print(f"[Session] 恢复了 {len(local_storage)} 个 localStorage 条目")
            except Exception as e:
                print(f"[Session] localStorage 恢复失败 (非关键): {e}")

        return True

    @classmethod
    async def save_session(cls, page, platform: str) -> str:
        """保存当前登录态到文件。"""
        cls.ensure_dir()
        cookies = await page.context.cookies()
        local_storage = await page.evaluate(
            "() => JSON.parse(JSON.stringify(localStorage))"
        )

        data = {
            "platform": platform,
            "saved_at": datetime.now().isoformat(),
            "cookies": cookies,
            "localStorage": local_storage,
        }

        path = cls.session_path(platform)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[Session] 登录态已保存到 {path}")
        return str(path)

    @classmethod
    def encode_to_secret(cls, platform: str) -> str:
        """将登录态编码为 base64，用于存入 GitHub Secret。"""
        path = cls.session_path(platform)
        if not path.exists():
            print(f"[Session] 文件不存在: {path}")
            return ""

        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()

        encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
        return encoded


# ============================================================
#  BrowserPublisher 基类
# ============================================================

class BrowserPublisher:
    """浏览器自动化发布基类，封装通用逻辑。"""

    PLATFORM = ""        # 子类覆写
    LOGIN_URL = ""       # 子类覆写
    UPLOAD_URL = ""      # 子类覆写
    SECRET_ENV = ""      # 子类覆写

    def __init__(self, headless: bool = True, slow_mo: int = 500):
        self.headless = headless
        self.slow_mo = slow_mo
        self.browser = None
        self.context = None
        self.page = None
        self.screenshot_dir = Path(".screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)

    async def __aenter__(self):
        await self._launch()
        return self

    async def __aexit__(self, *args):
        await self._close()

    async def _launch(self):
        """启动浏览器。"""
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        self.context = await self.browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        self.page = await self.context.new_page()
        self.page.set_default_timeout(30000)  # 30s

        # 反检测
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        """)

        print(f"[{self.PLATFORM}] 浏览器已启动 (headless={self.headless})")

    async def _close(self):
        """关闭浏览器。"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, "_pw"):
            await self._pw.stop()

    async def _screenshot(self, name: str):
        """保存截图（用于调试）。"""
        ts = datetime.now().strftime("%H%M%S")
        path = self.screenshot_dir / f"{self.PLATFORM}_{name}_{ts}.png"
        await self.page.screenshot(path=str(path))
        print(f"[截图] 已保存: {path}")
        return path

    async def restore_or_login(self) -> bool:
        """尝试恢复登录态；如果失败则打印指引。"""
        restored = await SessionManager.load_session(
            self.page, self.PLATFORM, self.SECRET_ENV,
        )

        if not restored:
            print(f"\n{'='*50}")
            print(f"  {self.PLATFORM} 未检测到登录态")
            print(f"  请先在本地运行:")
            print(f"    python scripts/save_session.py {self.PLATFORM}")
            print(f"{'='*50}")
            return False

        # 验证登录态是否有效：访问 upload 页面
        print(f"[{self.PLATFORM}] 正在验证登录态...")
        await self.page.goto(self.UPLOAD_URL, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        # 检查是否被重定向到登录页
        current_url = self.page.url
        login_indicators = ["login", "passport", "sign", "oauth"]
        if any(kw in current_url.lower() for kw in login_indicators):
            print(f"[{self.PLATFORM}] 登录态已过期 (URL: {current_url})")
            await self._screenshot("session_expired")
            return False

        print(f"[{self.PLATFORM}] 登录态有效 ?")
        return True

    async def publish(
        self, video_path: str, title: str, description: str,
    ) -> dict:
        """发布视频（子类覆写具体流程）。"""
        raise NotImplementedError

    @staticmethod
    def truncate(text: str, max_len: int = 100) -> str:
        """截断过长的文本。"""
        return text[:max_len] if len(text) > max_len else text


# ============================================================
#  DouyinPublisher
# ============================================================

class DouyinPublisher(BrowserPublisher):
    """抖音创作服务平台自动发布。"""

    PLATFORM = "douyin"
    LOGIN_URL = "https://creator.douyin.com/"
    UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
    SECRET_ENV = "DOUYIN_SESSION"

    async def publish(
        self, video_path: str, title: str, description: str,
    ) -> dict:
        """发布视频到抖音。

        流程:
          1. 导航到上传页
          2. 选择视频文件
          3. 等待上传完成
          4. 填写标题和描述
          5. 设置封面（可选）
          6. 发布
        """
        print(f"\n{'='*50}")
        print(f"  发布到抖音")
        print(f"  视频: {video_path}")
        print(f"  标题: {self.truncate(title, 30)}")
        print(f"{'='*50}")

        result = {"platform": "douyin", "status": "unknown"}

        try:
            # 步骤 1: 导航到上传页
            print("[抖音] 进入上传页面...")
            await self.page.goto(self.UPLOAD_URL, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            await self._screenshot("01_upload_page")

            # 步骤 2: 上传视频文件
            # 抖音的上传按钮是一个隐藏的 input[type=file]
            print("[抖音] 选择视频文件...")
            file_chooser = None

            # 尝试多种选择器找到文件上传入口
            upload_selectors = [
                "input[type=file]",
                ".upload-input input[type=file]",
                ".drag-area input[type=file]",
                ".upload-area input",
                '[class*="upload"] input[type=file]',
                "input.accept-video",
            ]

            for selector in upload_selectors:
                try:
                    async with self.page.expect_file_chooser(timeout=5000) as fc_info:
                        await self.page.click(selector, timeout=3000)
                    file_chooser = await fc_info.value
                    break
                except Exception:
                    continue

            if not file_chooser:
                # 最后的 fallback：直接通过 JS 设置文件
                print("[抖音] 尝试 JS 方式上传文件...")
                await self.page.evaluate("""
                    () => {
                        const input = document.createElement('input');
                        input.type = 'file';
                        input.accept = 'video/*';
                        input.style.display = 'none';
                        document.body.appendChild(input);
                        return input;
                    }
                """)
                async with self.page.expect_file_chooser(timeout=5000) as fc_info:
                    await self.page.evaluate(
                        "document.querySelector('input[type=file]:last-child').click()"
                    )
                file_chooser = await fc_info.value

            if not file_chooser:
                await self._screenshot("02_upload_failed")
                raise RuntimeError("无法找到文件上传入口")

            await file_chooser.set_files(video_path)
            print("[抖音] 文件已选择，等待上传处理...")

            # 步骤 3: 等待上传完成（看进度条消失或状态变化）
            await asyncio.sleep(5)
            upload_complete = False
            for i in range(60):  # 最多等 5 分钟
                await asyncio.sleep(5)
                try:
                    # 检查是否存在上传中的提示
                    processing = await self.page.locator(
                        '[class*="progress"], [class*="loading"], [class*="uploading"]'
                    ).count()
                    if processing == 0:
                        upload_complete = True
                        break
                except Exception:
                    upload_complete = True
                    break
                if i % 6 == 0:
                    print(f"[抖音] 上传处理中... ({i*5}s)")

            if not upload_complete:
                print("[抖音] 上传可能超时，继续尝试发布...")

            await self._screenshot("03_upload_done")
            print("[抖音] 视频上传完成 ?")

            # 步骤 4: 填写标题（最多 30 字）
            safe_title = title[:30]
            print(f"[抖音] 填写标题: {safe_title}")
            title_selectors = [
                '[placeholder*="标题"]',
                '[placeholder*="作品"]',
                '[class*="title"] input',
                '[class*="title"] textarea',
                "textarea",
            ]
            for sel in title_selectors:
                try:
                    el = self.page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        await el.click()
                        await el.fill("")
                        await el.type(safe_title, delay=50)
                        break
                except Exception:
                    continue

            # 步骤 5: 填写描述
            if description:
                safe_desc = description[:100]
                print(f"[抖音] 填写描述: {self.truncate(safe_desc, 40)}...")
                desc_selectors = [
                    '[placeholder*="描述"]',
                    '[placeholder*="简介"]',
                    '[class*="desc"] textarea',
                    '[class*="description"] textarea',
                ]
                for sel in desc_selectors:
                    try:
                        el = self.page.locator(sel).first
                        if await el.is_visible(timeout=2000):
                            await el.click()
                            await el.fill("")
                            await el.type(safe_desc, delay=20)
                            break
                    except Exception:
                        continue

            # 步骤 6: 选择发布设置（公开、关闭评论等）
            # 默认保持平台默认设置

            await asyncio.sleep(2)
            await self._screenshot("04_before_publish")

            # 步骤 7: 点击发布按钮
            print("[抖音] 正在点击发布...")
            publish_selectors = [
                '[class*="publish"] button:has-text("发布")',
                '[class*="submit"] button:has-text("发布")',
                'button:has-text("发布")',
                '[class*="publish-btn"]',
                'button:has-text("发表")',
            ]
            published = False
            for sel in publish_selectors:
                try:
                    btn = self.page.locator(sel).first
                    if await btn.is_visible(timeout=3000):
                        await btn.click()
                        published = True
                        print("[抖音] 已点击发布按钮")
                        break
                except Exception:
                    continue

            if not published:
                await self._screenshot("05_publish_button_not_found")
                raise RuntimeError("找不到发布按钮")

            # 步骤 8: 等待发布成功
            await asyncio.sleep(8)
            await self._screenshot("06_after_publish")

            # 检查成功标记
            success_indicators = [
                "发布成功",
                "作品已发布",
                "发布完成",
                "success",
            ]
            page_text = await self.page.content()
            is_success = any(ind in page_text for ind in success_indicators)

            if is_success:
                result["status"] = "success"
                print("[抖音] 发布成功 ?")
            else:
                result["status"] = "submitted"
                print("[抖音] 已提交发布（等待平台确认）")

        except Exception as e:
            print(f"[抖音] 发布失败: {e}")
            await self._screenshot("error")
            result["status"] = "error"
            result["error"] = str(e)

        return result


# ============================================================
#  XiaohongshuPublisher
# ============================================================

class XiaohongshuPublisher(BrowserPublisher):
    """小红书创作者中心自动发布。"""

    PLATFORM = "xiaohongshu"
    LOGIN_URL = "https://creator.xiaohongshu.com/"
    UPLOAD_URL = "https://creator.xiaohongshu.com/publish/publish_video"
    SECRET_ENV = "XIAOHONGSHU_SESSION"

    async def publish(
        self, video_path: str, title: str, description: str,
    ) -> dict:
        """发布视频到小红书。

        流程:
          1. 导航到发布页
          2. 上传视频文件
          3. 等待转码完成
          4. 填写标题和正文
          5. 添加话题标签
          6. 发布
        """
        print(f"\n{'='*50}")
        print(f"  发布到小红书")
        print(f"  视频: {video_path}")
        print(f"  标题: {self.truncate(title, 20)}")
        print(f"{'='*50}")

        result = {"platform": "xiaohongshu", "status": "unknown"}

        try:
            # 步骤 1: 导航到发布页
            print("[小红书] 进入发布页面...")
            await self.page.goto(self.UPLOAD_URL, wait_until="domcontentloaded")
            await asyncio.sleep(4)
            await self._screenshot("01_publish_page")

            # 步骤 2: 上传视频
            print("[小红书] 选择视频文件...")
            file_chooser = None
            upload_selectors = [
                "input[type=file]",
                '[class*="upload"] input[type=file]',
                ".upload-container input",
                ".video-upload input",
            ]

            for selector in upload_selectors:
                try:
                    async with self.page.expect_file_chooser(timeout=5000) as fc_info:
                        el = self.page.locator(selector).first
                        if await el.is_visible(timeout=3000):
                            await el.click()
                    file_chooser = await fc_info.value
                    break
                except Exception:
                    continue

            if not file_chooser:
                print("[小红书] 尝试触发文件选择器...")
                async with self.page.expect_file_chooser(timeout=8000) as fc_info:
                    await self.page.evaluate("""
                        () => {
                            const btn = document.querySelector(
                                '[class*="upload"], [class*="Upload"], .upload-area'
                            );
                            if (btn) btn.click();
                        }
                    """)
                file_chooser = await fc_info.value

            if not file_chooser:
                await self._screenshot("02_upload_failed")
                raise RuntimeError("无法找到小红书视频上传入口")

            await file_chooser.set_files(video_path)
            print("[小红书] 文件已选择，等待转码...")

            # 步骤 3: 等待转码/上传完成
            await asyncio.sleep(8)
            for i in range(60):
                await asyncio.sleep(5)
                try:
                    loading = await self.page.locator(
                        '[class*="progress"], [class*="loading"]'
                    ).count()
                    if loading == 0:
                        break
                except Exception:
                    break
                if i % 6 == 0:
                    print(f"[小红书] 处理中... ({i*5}s)")

            await self._screenshot("03_video_ready")
            print("[小红书] 视频处理完成 ?")

            # 步骤 4: 填写标题（小红书标题最多 20 字）
            safe_title = title[:20]
            print(f"[小红书] 填写标题: {safe_title}")
            title_selectors = [
                '[placeholder*="标题"]',
                '[placeholder*="填写标题"]',
                '[class*="title"] input',
                "input[placeholder]",
            ]
            for sel in title_selectors:
                try:
                    el = self.page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        await el.click()
                        await el.fill("")
                        await el.type(safe_title, delay=50)
                        break
                except Exception:
                    continue

            # 步骤 5: 填写正文 / 描述
            content_text = description[:200] if description else ""
            if content_text:
                print(f"[小红书] 填写正文 ({len(content_text)}字)...")
                body_selectors = [
                    '[placeholder*="正文"]',
                    '[placeholder*="填写正文"]',
                    '[placeholder*="写点什么"]',
                    '[contenteditable="true"]',
                    '[class*="ql-editor"]',
                    '[class*="editor"]',
                ]
                for sel in body_selectors:
                    try:
                        el = self.page.locator(sel).first
                        if await el.is_visible(timeout=2000):
                            await el.click()
                            await el.fill("")
                            await el.type(content_text, delay=15)
                            break
                    except Exception:
                        continue

            # 步骤 6: 添加话题标签
            hashtags = ["#每日早安", "#早安问候", "#AI生成"]
            for tag in hashtags:
                try:
                    tag_input_sel = '[placeholder*="话题"], [placeholder*="标签"]'
                    el = self.page.locator(tag_input_sel).first
                    if await el.is_visible(timeout=2000):
                        await el.click()
                        await el.fill(tag)
                        await asyncio.sleep(1)
                        # 选择联想出来的第一个话题
                        try:
                            suggestion = self.page.locator(
                                '[class*="suggestion"]:first-child, [class*="option"]:first-child'
                            ).first
                            if await suggestion.is_visible(timeout=2000):
                                await suggestion.click()
                        except Exception:
                            pass
                except Exception:
                    continue

            await asyncio.sleep(2)
            await self._screenshot("04_before_publish")

            # 步骤 7: 发布
            print("[小红书] 点击发布...")
            publish_selectors = [
                'button:has-text("发布")',
                'button:has-text("发布笔记")',
                '[class*="publish"] button',
                '[class*="submit"] button',
            ]
            published = False
            for sel in publish_selectors:
                try:
                    btn = self.page.locator(sel).first
                    if await btn.is_visible(timeout=3000) and await btn.is_enabled():
                        await btn.click()
                        published = True
                        print("[小红书] 已点击发布")
                        break
                except Exception:
                    continue

            if not published:
                await self._screenshot("05_publish_button_not_found")
                raise RuntimeError("找不到小红书发布按钮")

            await asyncio.sleep(8)
            await self._screenshot("06_after_publish")

            success_indicators = ["发布成功", "发布完成", "笔记已发布", "success"]
            page_text = await self.page.content()
            is_success = any(ind in page_text for ind in success_indicators)

            if is_success:
                result["status"] = "success"
                print("[小红书] 发布成功 ?")
            else:
                result["status"] = "submitted"
                print("[小红书] 已提交发布")

        except Exception as e:
            print(f"[小红书] 发布失败: {e}")
            await self._screenshot("error")
            result["status"] = "error"
            result["error"] = str(e)

        return result


# ============================================================
#  CLI 入口：作为独立脚本运行时
# ============================================================

async def publish_to_browser(
    platform: str,
    video_path: str,
    title: str,
    description: str,
    headless: bool = True,
) -> dict:
    """统一入口：通过浏览器自动化发布视频。"""
    if platform == "douyin":
        publisher_class = DouyinPublisher
    elif platform == "xiaohongshu":
        publisher_class = XiaohongshuPublisher
    else:
        return {"status": "error", "error": f"不支持的平台: {platform}"}

    async with publisher_class(headless=headless, slow_mo=300) as publisher:
        ok = await publisher.restore_or_login()
        if not ok:
            return {"status": "login_required"}

        result = await publisher.publish(video_path, title, description)
        return result


if __name__ == "__main__":
    # 作为独立脚本运行
    import argparse

    parser = argparse.ArgumentParser(description="浏览器自动发布视频")
    parser.add_argument("platform", choices=["douyin", "xiaohongshu"], help="目标平台")
    parser.add_argument("video", help="视频文件路径")
    parser.add_argument("--title", default="早安", help="视频标题")
    parser.add_argument("--desc", default="", help="视频描述")
    parser.add_argument("--headed", action="store_true", help="可视化模式（非无头）")

    args = parser.parse_args()

    result = asyncio.run(publish_to_browser(
        args.platform, args.video, args.title, args.desc,
        headless=not args.headed,
    ))
    print("\n结果:", json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "success":
        sys.exit(1)
