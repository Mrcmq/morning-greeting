"""���� & С���� Playwright �Զ�������ģ��

ʹ�� Playwright ������������Զ���������Ƶ����
  - �����������ƽ̨ (creator.douyin.com)
  - С���鴴�������� (creator.xiaohongshu.com)

ʹ�÷�ʽ:
  1. �״�ʹ��: �������� python scripts/save_session.py ɨ���¼���� cookie
  2. �ճ�����: �� cookie ���� GitHub Secrets���������Զ�����

ע������:
  - ����/С�����з�����⣬����ʹ�� headed ģʽ+��ʵ UA
  - Cookie ��Ч��Լ 7-30 �죬���ں������µ�¼
  - ����Ƶ�ʽ��鲻���� 3 ��/��/�˺�
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
#  SessionManager�������¼̬ Cookie
# ============================================================

class SessionManager:
    """���������ڵĵ�¼̬�����

    Cookie �� GitHub Actions ���� base64 ����� Secret �洢��
    �ڱ����� JSON �ļ��洢��
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
        """���ļ��� Secret ���ص�¼̬��

        ���ȼ���
          1. ����������GitHub Secret base64��
          2. �����ļ�
        """
        data = None

        # ���Դӻ�����������
        env_value = os.environ.get(secret_env, "") if secret_env else ""
        if env_value:
            try:
                decoded = base64.b64decode(env_value).decode("utf-8")
                data = json.loads(decoded)
                print(f"[Session] �ӻ������� {secret_env} ���� {platform} ��¼̬")
            except Exception as e:
                print(f"[Session] Secret ����ʧ��: {e}")

        # ���Դӱ����ļ�����
        if not data:
            path = cls.session_path(platform)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print(f"[Session] �ӱ����ļ����� {platform} ��¼̬")

        if not data:
            return False

        # �ָ� Cookie
        cookies = data.get("cookies", [])
        if cookies:
            await page.context.add_cookies(cookies)
            print(f"[Session] �ָ��� {len(cookies)} �� Cookie")

        # �ָ� localStorage
        local_storage = data.get("localStorage", {})
        if local_storage:
            try:
                await page.evaluate(
                    "items => items.forEach(([k, v]) => localStorage.setItem(k, v))",
                    list(local_storage.items()),
                )
                print(f"[Session] �ָ��� {len(local_storage)} �� localStorage ��Ŀ")
            except Exception as e:
                print(f"[Session] localStorage �ָ�ʧ�� (�ǹؼ�): {e}")

        return True

    @classmethod
    async def save_session(cls, page, platform: str) -> str:
        """���浱ǰ��¼̬���ļ���"""
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

        print(f"[Session] ��¼̬�ѱ��浽 {path}")
        return str(path)

    @classmethod
    def encode_to_secret(cls, platform: str) -> str:
        """����¼̬����Ϊ base64�����ڴ��� GitHub Secret��"""
        path = cls.session_path(platform)
        if not path.exists():
            print(f"[Session] �ļ�������: {path}")
            return ""

        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()

        encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
        return encoded


# ============================================================
#  BrowserPublisher ����
# ============================================================

class BrowserPublisher:
    """������Զ����������࣬��װͨ���߼���"""

    PLATFORM = ""        # ���าд
    LOGIN_URL = ""       # ���าд
    UPLOAD_URL = ""      # ���าд
    SECRET_ENV = ""      # ���าд

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
        """����������"""
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

        # �����
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        """)

        print(f"[{self.PLATFORM}] ���������� (headless={self.headless})")

    async def _close(self):
        """�ر��������"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, "_pw"):
            await self._pw.stop()

    async def _screenshot(self, name: str):
        """�����ͼ�����ڵ��ԣ���"""
        ts = datetime.now().strftime("%H%M%S")
        path = self.screenshot_dir / f"{self.PLATFORM}_{name}_{ts}.png"
        await self.page.screenshot(path=str(path))
        print(f"[��ͼ] �ѱ���: {path}")
        return path

    async def restore_or_login(self) -> bool:
        """���Իָ���¼̬�����ʧ�����ӡָ����"""
        restored = await SessionManager.load_session(
            self.page, self.PLATFORM, self.SECRET_ENV,
        )

        if not restored:
            print(f"\n{'='*50}")
            print(f"  {self.PLATFORM} δ��⵽��¼̬")
            print(f"  �����ڱ�������:")
            print(f"    python scripts/save_session.py {self.PLATFORM}")
            print(f"{'='*50}")
            return False

        # ��֤��¼̬�Ƿ���Ч������ upload ҳ��
        print(f"[{self.PLATFORM}] ������֤��¼̬...")
        await self.page.goto(self.UPLOAD_URL, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        # ����Ƿ��ض��򵽵�¼ҳ
        current_url = self.page.url
        login_indicators = ["login", "passport", "sign", "oauth"]
        if any(kw in current_url.lower() for kw in login_indicators):
            print(f"[{self.PLATFORM}] ��¼̬�ѹ��� (URL: {current_url})")
            await self._screenshot("session_expired")
            return False

        print(f"[{self.PLATFORM}] ��¼̬��Ч ?")
        return True

    async def publish(
        self, video_path: str, title: str, description: str,
    ) -> dict:
        """������Ƶ�����าд�������̣���"""
        raise NotImplementedError

    @staticmethod
    def truncate(text: str, max_len: int = 100) -> str:
        """�ضϹ������ı���"""
        return text[:max_len] if len(text) > max_len else text


# ============================================================
#  DouyinPublisher
# ============================================================

class DouyinPublisher(BrowserPublisher):
    """�����������ƽ̨�Զ�������"""

    PLATFORM = "douyin"
    LOGIN_URL = "https://creator.douyin.com/"
    UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
    SECRET_ENV = "DOUYIN_SESSION"

    async def publish(
        self, video_path: str, title: str, description: str,
    ) -> dict:
        """������Ƶ�������

        ����:
          1. �������ϴ�ҳ
          2. ѡ����Ƶ�ļ�
          3. �ȴ��ϴ����
          4. ��д���������
          5. ���÷��棨��ѡ��
          6. ����
        """
        print(f"\n{'='*50}")
        print(f"  ����������")
        print(f"  ��Ƶ: {video_path}")
        print(f"  ����: {self.truncate(title, 30)}")
        print(f"{'='*50}")

        result = {"platform": "douyin", "status": "unknown"}

        try:
            # ���� 1: �������ϴ�ҳ
            print("[����] �����ϴ�ҳ��...")
            await self.page.goto(self.UPLOAD_URL, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            await self._screenshot("01_upload_page")

            # ���� 2: �ϴ���Ƶ�ļ�
            # ������ϴ���ť��һ�����ص� input[type=file]
            print("[����] ѡ����Ƶ�ļ�...")
            file_chooser = None

            # ���Զ���ѡ�����ҵ��ļ��ϴ����
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
                # ���� fallback��ֱ��ͨ�� JS �����ļ�
                print("[����] ���� JS ��ʽ�ϴ��ļ�...")
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
                raise RuntimeError("�޷��ҵ��ļ��ϴ����")

            await file_chooser.set_files(video_path)
            print("[����] �ļ���ѡ�񣬵ȴ��ϴ�����...")

            # ���� 3: �ȴ��ϴ���ɣ�����������ʧ��״̬�仯��
            await asyncio.sleep(5)
            upload_complete = False
            for i in range(60):  # ���� 5 ����
                await asyncio.sleep(5)
                try:
                    # ����Ƿ�����ϴ��е���ʾ
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
                    print(f"[����] �ϴ�������... ({i*5}s)")

            if not upload_complete:
                print("[����] �ϴ����ܳ�ʱ���������Է���...")

            await self._screenshot("03_upload_done")
            print("[����] ��Ƶ�ϴ���� ?")

            # ���� 4: ��д���⣨��� 30 �֣�
            safe_title = title[:30]
            print(f"[����] ��д����: {safe_title}")
            title_selectors = [
                '[placeholder*="����"]',
                '[placeholder*="��Ʒ"]',
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

            # ���� 5: ��д����
            if description:
                safe_desc = description[:100]
                print(f"[����] ��д����: {self.truncate(safe_desc, 40)}...")
                desc_selectors = [
                    '[placeholder*="����"]',
                    '[placeholder*="���"]',
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

            # ���� 6: ѡ�񷢲����ã��������ر����۵ȣ�
            # Ĭ�ϱ���ƽ̨Ĭ������

            await asyncio.sleep(2)
            await self._screenshot("04_before_publish")

            # ���� 7: ���������ť
            print("[����] ���ڵ������...")
            publish_selectors = [
                '[class*="publish"] button:has-text("����")',
                '[class*="submit"] button:has-text("����")',
                'button:has-text("����")',
                '[class*="publish-btn"]',
                'button:has-text("����")',
            ]
            published = False
            for sel in publish_selectors:
                try:
                    btn = self.page.locator(sel).first
                    if await btn.is_visible(timeout=3000):
                        await btn.click()
                        published = True
                        print("[����] �ѵ��������ť")
                        break
                except Exception:
                    continue

            if not published:
                await self._screenshot("05_publish_button_not_found")
                raise RuntimeError("�Ҳ���������ť")

            # ���� 8: �ȴ������ɹ�
            await asyncio.sleep(8)
            await self._screenshot("06_after_publish")

            # ���ɹ����
            success_indicators = [
                "�����ɹ�",
                "��Ʒ�ѷ���",
                "�������",
                "success",
            ]
            page_text = await self.page.content()
            is_success = any(ind in page_text for ind in success_indicators)

            if is_success:
                result["status"] = "success"
                print("[����] �����ɹ� ?")
            else:
                result["status"] = "submitted"
                print("[����] ���ύ�������ȴ�ƽ̨ȷ�ϣ�")

        except Exception as e:
            print(f"[����] ����ʧ��: {e}")
            await self._screenshot("error")
            result["status"] = "error"
            result["error"] = str(e)

        return result


# ============================================================
#  XiaohongshuPublisher
# ============================================================

class XiaohongshuPublisher(BrowserPublisher):
    """С���鴴���������Զ�������"""

    PLATFORM = "xiaohongshu"
    LOGIN_URL = "https://creator.xiaohongshu.com/"
    UPLOAD_URL = "https://creator.xiaohongshu.com/publish/publish_video"
    SECRET_ENV = "XIAOHONGSHU_SESSION"

    async def publish(
        self, video_path: str, title: str, description: str,
    ) -> dict:
        """������Ƶ��С���顣

        ����:
          1. ����������ҳ
          2. �ϴ���Ƶ�ļ�
          3. �ȴ�ת�����
          4. ��д���������
          5. ��ӻ����ǩ
          6. ����
        """
        print(f"\n{'='*50}")
        print(f"  ������С����")
        print(f"  ��Ƶ: {video_path}")
        print(f"  ����: {self.truncate(title, 20)}")
        print(f"{'='*50}")

        result = {"platform": "xiaohongshu", "status": "unknown"}

        try:
            # ���� 1: ����������ҳ
            print("[С����] ���뷢��ҳ��...")
            await self.page.goto(self.UPLOAD_URL, wait_until="domcontentloaded")
            await asyncio.sleep(4)
            await self._screenshot("01_publish_page")

            # ���� 2: �ϴ���Ƶ
            print("[С����] ѡ����Ƶ�ļ�...")
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
                print("[С����] ���Դ����ļ�ѡ����...")
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
                raise RuntimeError("�޷��ҵ�С������Ƶ�ϴ����")

            await file_chooser.set_files(video_path)
            print("[С����] �ļ���ѡ�񣬵ȴ�ת��...")

            # ���� 3: �ȴ�ת��/�ϴ����
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
                    print(f"[С����] ������... ({i*5}s)")

            await self._screenshot("03_video_ready")
            print("[С����] ��Ƶ������� ?")

            # ���� 4: ��д���⣨С���������� 20 �֣�
            safe_title = title[:20]
            print(f"[С����] ��д����: {safe_title}")
            title_selectors = [
                '[placeholder*="����"]',
                '[placeholder*="��д����"]',
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

            # ���� 5: ��д���� / ����
            content_text = description[:200] if description else ""
            if content_text:
                print(f"[С����] ��д���� ({len(content_text)}��)...")
                body_selectors = [
                    '[placeholder*="����"]',
                    '[placeholder*="��д����"]',
                    '[placeholder*="д��ʲô"]',
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

            # ���� 6: ��ӻ����ǩ
            hashtags = ["#ÿ���簲", "#�簲�ʺ�", "#AI����"]
            for tag in hashtags:
                try:
                    tag_input_sel = '[placeholder*="����"], [placeholder*="��ǩ"]'
                    el = self.page.locator(tag_input_sel).first
                    if await el.is_visible(timeout=2000):
                        await el.click()
                        await el.fill(tag)
                        await asyncio.sleep(1)
                        # ѡ����������ĵ�һ������
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

            # ���� 7: ����
            print("[С����] �������...")
            publish_selectors = [
                'button:has-text("����")',
                'button:has-text("�����ʼ�")',
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
                        print("[С����] �ѵ������")
                        break
                except Exception:
                    continue

            if not published:
                await self._screenshot("05_publish_button_not_found")
                raise RuntimeError("�Ҳ���С���鷢����ť")

            await asyncio.sleep(8)
            await self._screenshot("06_after_publish")

            success_indicators = ["�����ɹ�", "�������", "�ʼ��ѷ���", "success"]
            page_text = await self.page.content()
            is_success = any(ind in page_text for ind in success_indicators)

            if is_success:
                result["status"] = "success"
                print("[С����] �����ɹ� ?")
            else:
                result["status"] = "submitted"
                print("[С����] ���ύ����")

        except Exception as e:
            print(f"[С����] ����ʧ��: {e}")
            await self._screenshot("error")
            result["status"] = "error"
            result["error"] = str(e)

        return result


# ============================================================
#  CLI ��ڣ���Ϊ�����ű�����ʱ
# ============================================================

async def publish_to_browser(
    platform: str,
    video_path: str,
    title: str,
    description: str,
    headless: bool = True,
) -> dict:
    """ͳһ��ڣ�ͨ��������Զ���������Ƶ��"""
    if platform == "douyin":
        publisher_class = DouyinPublisher
    elif platform == "xiaohongshu":
        publisher_class = XiaohongshuPublisher
    else:
        return {"status": "error", "error": f"��֧�ֵ�ƽ̨: {platform}"}

    async with publisher_class(headless=headless, slow_mo=300) as publisher:
        ok = await publisher.restore_or_login()
        if not ok:
            return {"status": "login_required"}

        result = await publisher.publish(video_path, title, description)
        return result


if __name__ == "__main__":
    # ��Ϊ�����ű�����
    import argparse

    parser = argparse.ArgumentParser(description="������Զ�������Ƶ")
    parser.add_argument("platform", choices=["douyin", "xiaohongshu"], help="Ŀ��ƽ̨")
    parser.add_argument("video", help="��Ƶ�ļ�·��")
    parser.add_argument("--title", default="�簲", help="��Ƶ����")
    parser.add_argument("--desc", default="", help="��Ƶ����")
    parser.add_argument("--headed", action="store_true", help="���ӻ�ģʽ������ͷ��")

    args = parser.parse_args()

    result = asyncio.run(publish_to_browser(
        args.platform, args.video, args.title, args.desc,
        headless=not args.headed,
    ))
    print("\n���:", json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "success":
        sys.exit(1)
