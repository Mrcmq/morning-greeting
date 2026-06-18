"""首次登录 Cookie 采集工具

在本地运行，手动扫码登录后保存登录态。
后续 GitHub Actions 自动发布时使用保存的 Cookie 恢复会话。

用法:
  # 采集抖音登录态
  python scripts/save_session.py douyin

  # 采集小红书登录态
  python scripts/save_session.py xiaohongshu

  # 采集后输出 base64（可复制到 GitHub Secrets）
  python scripts/save_session.py douyin --to-secret

流程:
  1. 启动浏览器（窗口可见）
  2. 导航到平台登录页
  3. 等待你扫码 / 手机号登录
  4. 登录成功后按回车键确认
  5. Cookie 自动保存到 .sessions/ 目录
"""

import asyncio
import base64
import json
import os
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.browser_publisher import SessionManager


PLATFORM_CONFIG = {
    "douyin": {
        "name": "抖音",
        "login_url": "https://creator.douyin.com/",
        "check_url": "https://creator.douyin.com/creator-micro/content/upload",
        "success_indicators": [
            "creator.douyin.com/creator-micro",
            "/content/manage",
            "/content/upload",
        ],
    },
    "xiaohongshu": {
        "name": "小红书",
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
    """交互式采集登录态。"""
    config = PLATFORM_CONFIG.get(platform)
    if not config:
        print(f"不支持的平台: {platform}")
        print(f"可选: {', '.join(PLATFORM_CONFIG.keys())}")
        sys.exit(1)

    print(f"\n{'='*55}")
    print(f"  {config['name']} 登录态采集")
    print(f"{'='*55}")
    print()
    print("即将打开浏览器窗口。")
    print("请在浏览器中完成登录（扫码 / 手机号 / 密码）。")
    print("登录成功后，回到此终端按 Enter 键保存 Cookie。")
    print()
    print(f"登录页面: {config['login_url']}")
    print()

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        # 启动浏览器（可视化模式）
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

        # 反检测
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)

        # 导航到登陆页
        await page.goto(config["login_url"], wait_until="domcontentloaded")
        print(f"? 已打开 {config['name']} 登录页面")
        print()

        # 等待用户在终端按 Enter 键
        await asyncio.to_thread(input, "登录完成后，按 Enter 键继续...")

        # 等待一下确保页面已跳转
        await asyncio.sleep(3)

        # 检查当前 URL 是否表明已登录
        current_url = page.url
        print(f"\n当前页面 URL: {current_url}")

        is_logged_in = any(
            ind in current_url for ind in config["success_indicators"]
        )
        if not is_logged_in:
            print()
            print("? 看起来可能还未登录成功。")
            print("  当前 URL 未匹配到已登录标记。")
            action = await asyncio.to_thread(
                input, "  仍要保存当前 Cookie 吗？(y/n): "
            )
            if action.lower() != "y":
                print("取消保存。")
                await browser.close()
                sys.exit(0)

        # 保存登录态
        path = await SessionManager.save_session(page, platform)
        print(f"\n? 登录态已保存到: {path}")

        if to_secret:
            secret = SessionManager.encode_to_secret(platform)
            if secret:
                print(f"\n{'='*55}")
                print(f"  GitHub Secret 值（复制以下内容）:")
                print(f"{'='*55}")
                print()
                print(secret)
                print()
                print(f"  将此值添加到仓库 Secrets:")
                print(f"    平台: {platform}")
                print(f"    Key:  {config['name'].upper()}_SESSION")
                print()

        await browser.close()

    print("完成。现在可以关闭此窗口了。")
    return path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="采集平台登录态")
    parser.add_argument("platform", choices=["douyin", "xiaohongshu"], help="目标平台")
    parser.add_argument(
        "--to-secret", action="store_true",
        help="同时输出 base64 编码的 GitHub Secret 值",
    )
    args = parser.parse_args()

    asyncio.run(collect_session(args.platform, to_secret=args.to_secret))


if __name__ == "__main__":
    main()
