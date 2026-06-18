"""早安 TTS 语音合成模块

方案选择（通过 USE_OPENAI_TTS 环境变量切换）：
  默认: Edge TTS（免费，中文语音效果好，微软晓晓）
  可选: OpenAI TTS（更自然的语调，$0.015/1K chars）
"""

import asyncio
import json
import os
import sys


async def synthesize_edge_tts(text: str, output_path: str, voice: str = "zh-CN-XiaoxiaoNeural") -> str:
    """使用 Edge TTS（免费）合成中文语音。
    
    Args:
        text: 要朗读的中文文本
        output_path: 输出音频文件路径 (.mp3)
        voice: 微软中文语音名称
              可选: zh-CN-XiaoxiaoNeural (晓晓, 女声, 温暖)
                    zh-CN-YunxiNeural (云希, 男声)
                    zh-CN-XiaoyiNeural (晓伊, 女声, 亲切)
                    
    Returns:
        生成的音频文件路径
    """
    try:
        import edge_tts
    except ImportError:
        print("正在安装 edge-tts...")
        import subprocess
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "edge-tts"],
            stdout=subprocess.DEVNULL,
        )
        import edge_tts  # noqa: F811

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)
    return output_path


async def synthesize_openai_tts(
    api_key: str,
    text: str,
    output_path: str,
    voice: str = "nova",
    model: str = "tts-1",
) -> str:
    """使用 OpenAI TTS 合成语音（需付费）。
    
    OpenAI TTS-1 定价: $0.015 / 1K 字符。
    
    Args:
        api_key: OpenAI API Key
        text: 要朗读的文本
        output_path: 输出音频文件路径
        voice: alloy, echo, fable, nova, onyx, shimmer
        model: tts-1 或 tts-1-hd
    """
    import httpx

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": "mp3",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/speech",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)

    return output_path


def estimate_tts_cost(text: str, provider: str = "edge") -> float:
    """估算 TTS 成本（美元）"""
    char_count = len(text)
    if provider == "openai":
        return (char_count / 1000) * 0.015
    return 0.0  # Edge TTS 免费


if __name__ == "__main__":
    output_dir = os.environ.get("OUTPUT_DIR", ".")
    os.makedirs(output_dir, exist_ok=True)

    # 读取上一步生成的脚本
    script_path = os.path.join(output_dir, "script.json")
    if not os.path.exists(script_path):
        print(json.dumps({"error": "script.json 不存在，请先运行 generate_script.py"}, ensure_ascii=False))
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    full_script = script_data.get("full_script", "")
    if not full_script:
        print(json.dumps({"error": "script.json 中缺少 full_script 字段"}, ensure_ascii=False))
        sys.exit(1)

    title = script_data.get("title", "早安").strip()

    # 决定 TTS 方案
    use_openai = os.environ.get("USE_OPENAI_TTS", "").lower() in ("1", "true", "yes")

    output_path = os.path.join(output_dir, f"audio.mp3")

    if use_openai:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            print(json.dumps({"error": "USE_OPENAI_TTS=true 但未设置 OPENAI_API_KEY"}, ensure_ascii=False))
            sys.exit(1)
        voice = os.environ.get("OPENAI_TTS_VOICE", "nova")
        cost = estimate_tts_cost(full_script, "openai")
        print(f"使用 OpenAI TTS (voice={voice}) | 预估成本: ${cost:.6f}")
        result = asyncio.run(synthesize_openai_tts(api_key, full_script, output_path, voice=voice))
    else:
        voice = os.environ.get("EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural")
        print(f"使用 Edge TTS (voice={voice}) - 免费")
        result = asyncio.run(synthesize_edge_tts(full_script, output_path, voice=voice))

    print(f"音频已生成: {result}")

    # 记录成本到 meta
    script_data.setdefault("_meta", {})
    script_data["_meta"]["tts_provider"] = "openai" if use_openai else "edge"
    script_data["_meta"]["tts_cost_usd"] = estimate_tts_cost(full_script, "openai" if use_openai else "edge")
    script_data["_meta"]["audio_path"] = result
    script_data["_meta"]["text_chars"] = len(full_script)

    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script_data, f, ensure_ascii=False, indent=2)
