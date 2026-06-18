"""�״ε�¼ Cookie �ɼ�����

�ڱ������У��ֶ�ɨ���¼�󱣴��¼̬��
���� GitHub Actions �Զ�����ʱʹ�ñ���� Cookie �ָ��Ự��

�÷�:
  # �ɼ������¼̬
  python scripts/save_session.py douyin

  # �ɼ�С�����¼̬
  python scripts/save_session.py xiaohongshu

  # �ɼ������ base64���ɸ��Ƶ� GitHub Secrets��
  python scripts/save_session.py douyin --to-secret

����:
  1. �������������ڿɼ���
  2. ������ƽ̨��¼ҳ
  3. �ȴ���ɨ�� / �ֻ��ŵ�¼
  4. ��¼�ɹ��󰴻س���ȷ��
  5. Cookie �Զ����浽 .sessions/ Ŀ¼
"""

import asyncio
import base64
import json
import os
import sys
from pathlib import Path

# ����Ŀ��Ŀ¼���� sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.browser_publisher import SessionManager


PLATFORM_CONFIG = {
    "douyin": {
        "name": "����",
        "login_url": "https://creator.douyin.com/",
        "check_url": "https://creator.douyin.com/creator-micro/content/upload",
        "success_indicators": [
            "creator.douyin.com/creator-micro",
            "/content/manage",
            "/content/upload",
        ],
    },
    "xiaohongshu": {
        "name": "С����",
        "login_url": "https://creator.xiaohongshu.com/",
        "check_url": "https://creator.xiaohongshu.com/publish/publish_video",
        "success_indicators": [
            "creator.xiaohongshu.com/publish",
            "creator.xiaohongshu.com/note",
            "/publish/publish_video",
        ],
    },
}


async def collect_session(platform: str, to_secret: bool = False):
    """����ʽ�ɼ���¼̬��"""
    config = PLATFORM_CONFIG.get(platform)
    if not config:
        print(f"��֧�ֵ�ƽ̨: {platform}")
        print(f"��ѡ: {', '.join(PLATFORM_CONFIG.keys())}")
        sys.exit(1)

    print(f"\n{'='*55}")
    print(f"  {config['name']} ��¼̬�ɼ�")
    print(f"{'='*55}")
    print()
    print("��������������ڡ�")
    print("�������������ɵ�¼��ɨ�� / �ֻ��� / ���룩��")
    print("��¼�ɹ��󣬻ص����ն˰� Enter ������ Cookie��")
    print()
    print(f"��¼ҳ��: {config['login_url']}")
    print()

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        # �������������ӻ�ģʽ��
        browser = await pw.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        page = await context.new_page()

        # �����
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)

        # ��������½ҳ
        await page.goto(config["login_url"], wait_until="domcontentloaded")
        print(f"? �Ѵ� {config['name']} ��¼ҳ��")
        print()

        # �ȴ��û����ն˰� Enter ��
        await asyncio.to_thread(input, "��¼��ɺ󣬰� Enter ������...")

        # �ȴ�һ��ȷ��ҳ������ת
        await asyncio.sleep(3)

        # ��鵱ǰ URL �Ƿ�����ѵ�¼
        current_url = page.url
        print(f"\n��ǰҳ�� URL: {current_url}")

        is_logged_in = any(
            ind in current_url for ind in config["success_indicators"]
        )
        if not is_logged_in:
            print()
            print("? ���������ܻ�δ��¼�ɹ���")
            print("  ��ǰ URL δƥ�䵽�ѵ�¼��ǡ�")
            action = await asyncio.to_thread(
                input, "  ��Ҫ���浱ǰ Cookie ��(y/n): "
            )
            if action.lower() != "y":
                print("ȡ�����档")
                await browser.close()
                sys.exit(0)

        # �����¼̬
        path = await SessionManager.save_session(page, platform)
        print(f"\n? ��¼̬�ѱ��浽: {path}")

        if to_secret:
            secret = SessionManager.encode_to_secret(platform)
            if secret:
                print(f"\n{'='*55}")
                print(f"  GitHub Secret ֵ�������������ݣ�:")
                print(f"{'='*55}")
                print()
                print(secret)
                print()
                print(f"  ����ֵ��ӵ��ֿ� Secrets:")
                print(f"    ƽ̨: {platform}")
                print(f"    Key:  {config['name'].upper()}_SESSION")
                print()

        await browser.close()

    print("��ɡ����ڿ��Թرմ˴����ˡ�")
    return path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="�ɼ�ƽ̨��¼̬")
    parser.add_argument("platform", choices=["douyin", "xiaohongshu"], help="Ŀ��ƽ̨")
    parser.add_argument(
        "--to-secret", action="store_true",
        help="ͬʱ��� base64 ����� GitHub Secret ֵ",
    )
    args = parser.parse_args()

    asyncio.run(collect_session(args.platform, to_secret=args.to_secret))


if __name__ == "__main__":
    main()
