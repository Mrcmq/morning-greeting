"""通知推送模块

支持将每日早安生成结果推送到手机：
  - Server Chan（微信推送，推荐国内用户）
  - Telegram Bot（国际用户，支持发视频）
  - PushPlus（微信推送备选）

使用方式：
  在工作流中设置对应的 Secret，自动触发推送。
"""

import json
import os
import sys
from pathlib import Path


# ============================================================
#  消息构建
# ============================================================

def build_message(script_data: dict) -> dict:
    """从 script.json 构建推送消息内容。"""
    meta = script_data.get("_meta", {})
    title = script_data.get("title", "早安")
    full_script = script_data.get("full_script", "")
    publish_results = meta.get("publish_results", {})

    # 发布状态摘要
    publish_summary = ""
    if publish_results:
        lines = []
        for platform, result in publish_results.items():
            status = result.get("status", "?")
            icon = {"success": "?", "submitted": "??", "skipped": "??",
                     "placeholder": "?", "login_required": "??", "error": "?"}.get(
                         status, "?"
            )
            lines.append(f"{icon} {platform}: {status}")
        publish_summary = "\n".join(lines)

    # 成本
    llm_cost = meta.get("cost_usd", 0) or 0
    tts_cost = meta.get("tts_cost_usd", 0) or 0
    total_usd = llm_cost + tts_cost
    total_rmb = total_usd * 7.3

    # 视频文件路径
    video_portrait = meta.get("video_portrait", "")
    video_landscape = meta.get("video_landscape", "")
    has_video = bool(video_portrait and Path(video_portrait).exists())

    content_lines = [
        f"?? {title}",
        "",
    ]
    if full_script:
        # 截取前 80 字做预览
        preview = full_script[:80]
        if len(full_script) > 80:
            preview += "..."
        content_lines.append(f"?? {preview}")
        content_lines.append("")

    content_lines.append("?? 成本")
    content_lines.append(f"   LLM: ${llm_cost:.4f}  |  TTS: ${tts_cost:.4f}")
    content_lines.append(f"   合计: ￥{total_rmb:.4f}")
    content_lines.append("")

    if publish_summary:
        content_lines.append("?? 发布状态")
        content_lines.append(publish_summary)
        content_lines.append("")

    # GitHub Actions 运行链接
    gh_run_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    gh_repo = os.environ.get("GITHUB_REPOSITORY", "")
    gh_run_id = os.environ.get("GITHUB_RUN_ID", "")
    if gh_repo and gh_run_id:
        run_url = f"{gh_run_url}/{gh_repo}/actions/runs/{gh_run_id}"
        content_lines.append(f"?? 查看详情: {run_url}")

    text = "\n".join(content_lines)

    return {
        "title": f"?? {title}  [￥{total_rmb:.4f}]",
        "content": text,
        "has_video": has_video,
        "video_portrait": video_portrait,
    }


# ============================================================
#  Server Chan（微信推送）
# ============================================================

def notify_serverchan(send_key: str, msg: dict) -> dict:
    """通过 Server Chan 推送微信消息。

    注册: https://sct.ftqq.com
    免费版: 每天 5 条，够用
    Pro: ￥5/月，不限条数 + 文件推送
    """
    import httpx

    url = f"https://sctapi.ftqq.com/{send_key}.send"
    payload = {
        "title": msg["title"],
        "content": msg["content"],
    }

    try:
        resp = httpx.post(url, data=payload, timeout=15)
        result = resp.json()
        if resp.status_code == 200 and result.get("code") == 0:
            print(f"[ServerChan] 微信推送成功 ?")
            return {"status": "success", "platform": "serverchan"}
        else:
            print(f"[ServerChan] API 返回异常: {result}")
            return {"status": "error", "error": str(result)}
    except Exception as e:
        print(f"[ServerChan] 推送失败: {e}")
        return {"status": "error", "error": str(e)}


# ============================================================
#  PushPlus（微信推送备选）
# ============================================================

def notify_pushplus(token: str, msg: dict) -> dict:
    """通过 PushPlus 推送微信消息。

    注册: https://www.pushplus.plus
    免费版: 每天 200 条
    """
    import httpx

    url = "https://www.pushplus.plus/send"
    payload = {
        "token": token,
        "title": msg["title"],
        "content": msg["content"],
        "template": "txt",
    }

    try:
        resp = httpx.post(url, json=payload, timeout=15)
        result = resp.json()
        if resp.status_code == 200 and result.get("code") == 200:
            print(f"[PushPlus] 微信推送成功 ?")
            return {"status": "success", "platform": "pushplus"}
        else:
            print(f"[PushPlus] API 返回异常: {result}")
            return {"status": "error", "error": str(result)}
    except Exception as e:
        print(f"[PushPlus] 推送失败: {e}")
        return {"status": "error", "error": str(e)}


# ============================================================
#  Telegram Bot
# ============================================================

def notify_telegram(bot_token: str, chat_id: str, msg: dict) -> dict:
    """通过 Telegram Bot 发送消息（支持视频）。

    需要:
      1. 在 Telegram 搜索 @BotFather，创建 bot 获得 token
      2. 搜索你的 bot，发送 /start
      3. 访问 https://api.telegram.org/bot<token>/getUpdates 获取 chat_id
    """
    import httpx

    result = {"status": "unknown", "platform": "telegram"}
    base_url = f"https://api.telegram.org/bot{bot_token}"

    try:
        # 1. 先发文字消息
        text_url = f"{base_url}/sendMessage"
        text_payload = {
            "chat_id": chat_id,
            "text": msg["content"],
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }
        text_resp = httpx.post(text_url, json=text_payload, timeout=15)
        text_data = text_resp.json()

        if not text_data.get("ok"):
            print(f"[Telegram] 消息发送失败: {text_data}")
            result["status"] = "error"
            result["error"] = str(text_data)
            return result

        print(f"[Telegram] 消息已发送 ?")

        # 2. 如果有视频文件，尝试发送
        if msg.get("has_video") and msg.get("video_portrait"):
            video_path = msg["video_portrait"]
            if os.path.exists(video_path):
                video_url = f"{base_url}/sendVideo"
                with open(video_path, "rb") as f:
                    file_resp = httpx.post(
                        video_url,
                        data={"chat_id": chat_id},
                        files={"video": f},
                        timeout=120,
                    )
                file_data = file_resp.json()
                if file_data.get("ok"):
                    print(f"[Telegram] 视频已发送 ?")
                else:
                    print(f"[Telegram] 视频发送失败（非关键）: {file_data}")

        result["status"] = "success"

    except Exception as e:
        print(f"[Telegram] 推送失败: {e}")
        result["status"] = "error"
        result["error"] = str(e)

    return result


# ============================================================
#  统一入口
# ============================================================

def send_notifications(script_data: dict) -> dict:
    """检查环境变量配置的推送渠道，发送通知。"""
    msg = build_message(script_data)
    results = {}

    # 1. ServerChan
    send_key = os.environ.get("SERVERCHAN_SENDKEY", "")
    if send_key:
        print("\n--- 推送 ServerChan（微信） ---")
        results["serverchan"] = notify_serverchan(send_key, msg)

    # 2. PushPlus
    pushplus_token = os.environ.get("PUSHPLUS_TOKEN", "")
    if pushplus_token:
        print("\n--- 推送 PushPlus（微信） ---")
        results["pushplus"] = notify_pushplus(pushplus_token, msg)

    # 3. Telegram
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if tg_token and tg_chat_id:
        print("\n--- 推送 Telegram ---")
        results["telegram"] = notify_telegram(tg_token, tg_chat_id, msg)

    if not results:
        print("\n未配置任何推送渠道。")
        print("如需微信推送，请注册 ServerChan: https://sct.ftqq.com")
        print("  → 在 GitHub Secrets 中添加: SERVERCHAN_SENDKEY")
        print("如需 Telegram 推送，请创建 Bot:")
        print("  → 添加: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID")

    return results


if __name__ == "__main__":
    output_dir = os.environ.get("OUTPUT_DIR", ".")
    script_path = os.path.join(output_dir, "script.json")

    if not os.path.exists(script_path):
        print(json.dumps({"error": "script.json 不存在"}, ensure_ascii=False))
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    results = send_notifications(script_data)
    print("\n推送结果:", json.dumps(results, ensure_ascii=False, indent=2))

    script_data.setdefault("_meta", {})
    script_data["_meta"]["notifications"] = results
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script_data, f, ensure_ascii=False, indent=2)
