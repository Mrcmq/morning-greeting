"""每日早安脚本生成�?
使用 GPT-4o-mini 生成温暖的早安问候文案�?支持：日期信息、今日寄语、短新闻摘要、天气提示�?"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

import httpx


def beijing_now() -> datetime:
    """返回当前北京时间"""
    utc = datetime.now(timezone.utc)
    return utc.astimezone(timezone(timedelta(hours=8)))


def get_weather_info(city: str = "北京") -> str:
    """�?wttr.in 获取简明天气信息（免费，无需 API Key�?""
    try:
        resp = httpx.get(
            f"https://wttr.in/{city}?format=%C+%t&lang=zh",
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.text.strip()
    except Exception:
        pass
    return ""


def generate_morning_script(
    openai_api_key: str,
    model: str = "gpt-4o-mini",
    city: str = "北京",
    style: str = "温暖治愈",
    max_output_tokens: int = 300,
) -> dict:
    """调用 OpenAI API 生成早安文案，返回结构化结果�?""
    now = beijing_now()

    weekdays = {
        0: "星期一", 1: "星期�?, 2: "星期�?,
        3: "星期�?, 4: "星期�?, 5: "星期�?, 6: "星期�?,
    }
    date_str = now.strftime("%Y�?m�?d�?)
    weekday_cn = weekdays[now.weekday()]

    weather = get_weather_info(city)
    weather_hint = f"\n今日天气：{weather}" if weather else ""

    system_prompt = f"""你是一个专业的中文早安内容创作者。请生成一段温暖的早安问候文案�?
今日日期：{date_str}（{weekday_cn}）{weather_hint}
城市：{city}
风格要求：{style}

输出 JSON 格式，包含以下字段：
- title: 今日早安标题�?-15字，有感染力�?- greeting: 核心问候语�?0-60字，温暖开场）
- quote: 一句今日寄�?名人名言（带出处�?0-40字）
- daily_tip: 一个简短的生活小贴士或今日提醒�?0-40字）
- blessing: 结束祝福�?5-30字）
- full_script: 完整的播音稿�?50-250字），把以上串联成一篇流畅的早安文稿，适合口播
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": "请为今天生成一份温暖的早安文案，输�?JSON�?,
            },
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": max_output_tokens,
        "temperature": 0.8,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = httpx.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    content = data["choices"][0]["message"]["content"]
    script_data = json.loads(content)
    script_data["_meta"] = {
        "model": model,
        "date": now.isoformat(),
        "tokens_prompt": data["usage"]["prompt_tokens"],
        "tokens_completion": data["usage"]["completion_tokens"],
        "tokens_total": data["usage"]["total_tokens"],
        "cost_usd": estimate_cost(
            model,
            data["usage"]["prompt_tokens"],
            data["usage"]["completion_tokens"],
        ),
    }
    return script_data


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """估算 OpenAI API 调用成本（美元）"""
    pricing = {
        "gpt-4o-mini": (0.000_000_15, 0.000_000_60),
        "gpt-4o": (0.000_002_50, 0.000_010_00),
        "gpt-4.1-mini": (0.000_000_40, 0.000_001_60),
        "gpt-4.1-nano": (0.000_000_10, 0.000_000_40),
        # DeepSeek (�����/M tokens)
        "deepseek-chat": (0.000_000_07, 0.000_000_28),     # ~��0.1/M input
        "deepseek-reasoner": (0.000_000_28, 0.000_001_10),  # ~��0.4/M input
    }
    rate = pricing.get(model, pricing["gpt-4o-mini"])
    return (prompt_tokens * rate[0] + completion_tokens * rate[1])


if __name__ == "__main__":
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print(json.dumps({"error": "OPENAI_API_KEY 环境变量未设�?}, ensure_ascii=False))
        sys.exit(1)

    city = os.environ.get("CITY", "北京")
    style = os.environ.get("STYLE", "温暖治愈")

    result = generate_morning_script(api_key, city=city, style=style)
    output_path = os.environ.get("OUTPUT_DIR", ".")
    os.makedirs(output_path, exist_ok=True)

    with open(os.path.join(output_path, "script.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("=" * 40)
    print(f"📅 {result.get('title', '早安')}")
    print("=" * 40)
    print(result.get("full_script", ""))
    print("=" * 40)
    meta = result.get("_meta", {})
    print(f"Tokens: {meta.get('tokens_total', '?')} | 成本: ${meta.get('cost_usd', 0):.6f}")
    print(f"输出已保存到: {output_path}")


