"""֪ͨ����ģ��

֧�ֽ�ÿ���簲���ɽ�����͵��ֻ���
  - Server Chan��΢�����ͣ��Ƽ������û���
  - Telegram Bot�������û���֧�ַ���Ƶ��
  - PushPlus��΢�����ͱ�ѡ��

ʹ�÷�ʽ��
  �ڹ����������ö�Ӧ�� Secret���Զ��������͡�
"""

import json
import os
import sys
from pathlib import Path


# ============================================================
#  ��Ϣ����
# ============================================================

def build_message(script_data: dict) -> dict:
    """�� script.json ����������Ϣ���ݡ�"""
    meta = script_data.get("_meta", {})
    title = script_data.get("title", "�簲")
    full_script = script_data.get("full_script", "")
    publish_results = meta.get("publish_results", {})

    # ����״̬ժҪ
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

    # �ɱ�
    llm_cost = meta.get("cost_usd", 0) or 0
    tts_cost = meta.get("tts_cost_usd", 0) or 0
    total_usd = llm_cost + tts_cost
    total_rmb = total_usd * 7.3

    # ��Ƶ�ļ�·��
    video_portrait = meta.get("video_portrait", "")
    video_landscape = meta.get("video_landscape", "")
    has_video = bool(video_portrait and Path(video_portrait).exists())

    content_lines = [
        f"?? {title}",
        "",
    ]
    if full_script:
        # ��ȡǰ 80 ����Ԥ��
        preview = full_script[:80]
        if len(full_script) > 80:
            preview += "..."
        content_lines.append(f"?? {preview}")
        content_lines.append("")

    content_lines.append("?? �ɱ�")
    content_lines.append(f"   LLM: ${llm_cost:.4f}  |  TTS: ${tts_cost:.4f}")
    content_lines.append(f"   �ϼ�: ��{total_rmb:.4f}")
    content_lines.append("")

    if publish_summary:
        content_lines.append("?? ����״̬")
        content_lines.append(publish_summary)
        content_lines.append("")

    # GitHub Actions ��������
    gh_run_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    gh_repo = os.environ.get("GITHUB_REPOSITORY", "")
    gh_run_id = os.environ.get("GITHUB_RUN_ID", "")
    if gh_repo and gh_run_id:
        run_url = f"{gh_run_url}/{gh_repo}/actions/runs/{gh_run_id}"
        content_lines.append(f"?? �鿴����: {run_url}")

    text = "\n".join(content_lines)

    return {
        "title": f"?? {title}  [��{total_rmb:.4f}]",
        "content": text,
        "has_video": has_video,
        "video_portrait": video_portrait,
    }


# ============================================================
#  Server Chan��΢�����ͣ�
# ============================================================

def notify_serverchan(send_key: str, msg: dict) -> dict:
    """ͨ�� Server Chan ����΢����Ϣ��

    ע��: https://sct.ftqq.com
    ��Ѱ�: ÿ�� 5 ��������
    Pro: ��5/�£��������� + �ļ�����
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
            print(f"[ServerChan] ΢�����ͳɹ� ?")
            return {"status": "success", "platform": "serverchan"}
        else:
            print(f"[ServerChan] API �����쳣: {result}")
            return {"status": "error", "error": str(result)}
    except Exception as e:
        print(f"[ServerChan] ����ʧ��: {e}")
        return {"status": "error", "error": str(e)}


# ============================================================
#  PushPlus��΢�����ͱ�ѡ��
# ============================================================

def notify_pushplus(token: str, msg: dict) -> dict:
    """ͨ�� PushPlus ����΢����Ϣ��

    ע��: https://www.pushplus.plus
    ��Ѱ�: ÿ�� 200 ��
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
            print(f"[PushPlus] ΢�����ͳɹ� ?")
            return {"status": "success", "platform": "pushplus"}
        else:
            print(f"[PushPlus] API �����쳣: {result}")
            return {"status": "error", "error": str(result)}
    except Exception as e:
        print(f"[PushPlus] ����ʧ��: {e}")
        return {"status": "error", "error": str(e)}


# ============================================================
#  Telegram Bot
# ============================================================

def notify_telegram(bot_token: str, chat_id: str, msg: dict) -> dict:
    """ͨ�� Telegram Bot ������Ϣ��֧����Ƶ����

    ��Ҫ:
      1. �� Telegram ���� @BotFather������ bot ��� token
      2. ������� bot������ /start
      3. ���� https://api.telegram.org/bot<token>/getUpdates ��ȡ chat_id
    """
    import httpx

    result = {"status": "unknown", "platform": "telegram"}
    base_url = f"https://api.telegram.org/bot{bot_token}"

    try:
        # 1. �ȷ�������Ϣ
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
            print(f"[Telegram] ��Ϣ����ʧ��: {text_data}")
            result["status"] = "error"
            result["error"] = str(text_data)
            return result

        print(f"[Telegram] ��Ϣ�ѷ��� ?")

        # 2. �������Ƶ�ļ������Է���
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
                    print(f"[Telegram] ��Ƶ�ѷ��� ?")
                else:
                    print(f"[Telegram] ��Ƶ����ʧ�ܣ��ǹؼ���: {file_data}")

        result["status"] = "success"

    except Exception as e:
        print(f"[Telegram] ����ʧ��: {e}")
        result["status"] = "error"
        result["error"] = str(e)

    return result


# ============================================================
#  ͳһ���
# ============================================================

def send_notifications(script_data: dict) -> dict:
    """��黷���������õ���������������֪ͨ��"""
    msg = build_message(script_data)
    results = {}

    # 1. ServerChan
    send_key = os.environ.get("SERVERCHAN_SENDKEY", "")
    if send_key:
        print("\n--- ���� ServerChan��΢�ţ� ---")
        results["serverchan"] = notify_serverchan(send_key, msg)

    # 2. PushPlus
    pushplus_token = os.environ.get("PUSHPLUS_TOKEN", "")
    if pushplus_token:
        print("\n--- ���� PushPlus��΢�ţ� ---")
        results["pushplus"] = notify_pushplus(pushplus_token, msg)

    # 3. Telegram
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if tg_token and tg_chat_id:
        print("\n--- ���� Telegram ---")
        results["telegram"] = notify_telegram(tg_token, tg_chat_id, msg)

    if not results:
        print("\nδ�����κ�����������")
        print("����΢�����ͣ���ע�� ServerChan: https://sct.ftqq.com")
        print("  �� �� GitHub Secrets �����: SERVERCHAN_SENDKEY")
        print("���� Telegram ���ͣ��봴�� Bot:")
        print("  �� ���: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID")

    return results


if __name__ == "__main__":
    output_dir = os.environ.get("OUTPUT_DIR", ".")
    script_path = os.path.join(output_dir, "script.json")

    if not os.path.exists(script_path):
        print(json.dumps({"error": "script.json ������"}, ensure_ascii=False))
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    results = send_notifications(script_data)
    print("\n���ͽ��:", json.dumps(results, ensure_ascii=False, indent=2))

    script_data.setdefault("_meta", {})
    script_data["_meta"]["notifications"] = results
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script_data, f, ensure_ascii=False, indent=2)
