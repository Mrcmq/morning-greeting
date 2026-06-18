"""早安视频多平台发布器

支持平台：
  - Bilibili:    官方 API（SESSDATA + bili_jct）
  - YouTube:     YouTube Data API v3（OAuth）
  - 抖音:        Playwright 浏览器自动化（Cookie 登录态）
  - 小红书:      Playwright 浏览器自动化（Cookie 登录态）
  - 微博:        预留（支持扩展）

首次使用抖音/小红书前，请在本地运行:
  python scripts/save_session.py douyin
  python scripts/save_session.py xiaohongshu
"""

import asyncio
import json
import os
import sys
import time


# -----------------------------------------------------------
#  平台发布函数
# -----------------------------------------------------------

def publish_to_bilibili(
    video_path: str,
    title: str,
    description: str,
    sessdata: str,
    bili_jct: str,
) -> dict:
    """通过 Bilibili API 上传视频。

    需准备 SESSDATA 和 bili_jct（浏览器 F12 → Cookies）。
    """
    try:
        from bilibili_api import video, credential
    except ImportError:
        print("正在安装 bilibili-api-python...")
        import subprocess
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "bilibili-api-python"],
            stdout=subprocess.DEVNULL,
        )
        from bilibili_api import video, credential

    cred = credential.Credential(sessdata=sessdata, bili_jct=bili_jct)
    v = video.VideoUploader(credential=cred)
    result = v.upload(video_path, title=title, description=description)
    print(f"Bilibili 上传完成: {result}")
    return result


def publish_to_youtube(
    video_path: str,
    title: str,
    description: str,
    privacy_status: str = "public",
) -> dict:
    """通过 YouTube Data API v3 上传视频。"""
    try:
        from googleapiclient.http import MediaFileUpload
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        import pickle
    except ImportError:
        print("正在安装 google-api-python-client...")
        import subprocess
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install",
             "google-api-python-client", "google-auth-oauthlib"],
            stdout=subprocess.DEVNULL,
        )
        from googleapiclient.http import MediaFileUpload
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        import pickle

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None
    token_path = "token_youtube.pickle"
    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secret.json", SCOPES,
            )
            creds = flow.run_local_server(port=0)
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)

    from googleapiclient.discovery import build
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["早安", "每日问候", "morning", "daily"],
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    response = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media,
    ).execute()
    print(f"YouTube 上传完成: https://youtu.be/{response['id']}")
    return response


async def publish_to_browser_async(
    platform: str,
    video_path: str,
    title: str,
    description: str,
) -> dict:
    """通过浏览器自动化发布到抖音 / 小红书。"""
    from scripts.browser_publisher import publish_to_browser
    result = await publish_to_browser(
        platform=platform,
        video_path=video_path,
        title=title,
        description=description,
        headless=True,
    )
    return result


def publish_to_weibo_placeholder(
    video_path: str, title: str, description: str,
) -> dict:
    """微博发布（预留）。"""
    print("-" * 40)
    print(f"微博发布：预留占位")
    print(f"视频: {video_path} | 标题: {title[:20]}")
    print("-" * 40)
    return {"status": "placeholder", "platform": "weibo"}


# -----------------------------------------------------------
#  async 发布入口
# -----------------------------------------------------------

async def publish_all(
    video_file: str,
    title: str,
    description: str,
    platforms: list,
) -> dict:
    """同时发布到多个平台。"""

    results = {}
    browser_tasks = []

    for platform in platforms:
        print(f"\n--- 正在发布到 {platform} ---")

        try:
            if platform == "bilibili":
                sessdata = os.environ.get("BILI_SESSDATA", "")
                bili_jct = os.environ.get("BILI_JCT", "")
                if sessdata and bili_jct:
                    results[platform] = publish_to_bilibili(
                        video_file, title, description, sessdata, bili_jct,
                    )
                else:
                    print("跳过 Bilibili：缺少 BILI_SESSDATA / BILI_JCT")
                    results[platform] = {"status": "skipped", "reason": "missing_secrets"}

            elif platform == "youtube":
                api_key = os.environ.get("YOUTUBE_API_KEY", "")
                if api_key:
                    results[platform] = publish_to_youtube(
                        video_file, title, description,
                    )
                else:
                    print("跳过 YouTube：缺少 YOUTUBE_API_KEY")
                    results[platform] = {"status": "skipped", "reason": "missing_secrets"}

            elif platform == "douyin":
                browser_tasks.append(
                    ("douyin", publish_to_browser_async(
                        "douyin", video_file, title, description,
                    ))
                )

            elif platform == "xiaohongshu":
                browser_tasks.append(
                    ("xiaohongshu", publish_to_browser_async(
                        "xiaohongshu", video_file, title, description,
                    ))
                )

            elif platform == "weibo":
                results[platform] = publish_to_weibo_placeholder(
                    video_file, title, description,
                )

            else:
                print(f"未知平台: {platform}")
                results[platform] = {"status": "error", "error": f"unknown platform: {platform}"}

        except Exception as e:
            print(f"发布到 {platform} 失败: {e}")
            results[platform] = {"status": "error", "error": str(e)}

    # 并发执行浏览器自动化任务（抖音 + 小红书可同时跑）
    if browser_tasks:
        print(f"\n--- 浏览器自动化发布任务 ({len(browser_tasks)} 个) ---")
        for pname, coro in browser_tasks:
            try:
                results[pname] = await coro
            except Exception as e:
                print(f"{pname} 浏览器发布失败: {e}")
                results[pname] = {"status": "error", "error": str(e)}

    return results


# -----------------------------------------------------------
#  CLI 入口
# -----------------------------------------------------------

if __name__ == "__main__":
    output_dir = os.environ.get("OUTPUT_DIR", ".")
    script_path = os.path.join(output_dir, "script.json")

    if not os.path.exists(script_path):
        print(json.dumps({"error": "script.json 不存在"}, ensure_ascii=False))
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    title = script_data.get("title", "早安")
    full_script = script_data.get("full_script", "")
    meta = script_data.get("_meta", {})

    description = f"{title}\n\n{full_script}\n\n#每日早安 #早安问候 #AI生成"

    platforms_str = os.environ.get("PLATFORMS", "bilibili,youtube")
    platforms = [p.strip() for p in platforms_str.split(",")]

    use_vertical = os.environ.get("USE_VERTICAL", "true").lower() in ("1", "true")
    if use_vertical:
        video_file = meta.get(
            "video_portrait",
            os.path.join(output_dir, "morning_portrait.mp4"),
        )
    else:
        video_file = meta.get(
            "video_landscape",
            os.path.join(output_dir, "morning_landscape.mp4"),
        )

    if not os.path.exists(video_file):
        print(json.dumps({"error": f"视频文件不存在: {video_file}"}, ensure_ascii=False))
        sys.exit(1)

    # 执行发布
    results = asyncio.run(publish_all(
        video_file, title, description, platforms,
    ))

    print("\n" + "=" * 40)
    print("发布结果汇总:")
    print(json.dumps(results, ensure_ascii=False, indent=2))

    script_data["_meta"]["publish_results"] = results
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script_data, f, ensure_ascii=False, indent=2)
