"""早安视频合成器

使用 FFmpeg 将以下元素合成为最终视频：
  - 背景视频/图片（渐变或静态画面）
  - 字幕（从脚本逐句生成，自动换行）
  - TTS 配音音频
  - 可选：背景音乐

输出格式：
  - 9:16 竖版（抖音/快手/小红书）
  - 16:9 横版（B站/YouTube）
"""

import json
import os
import subprocess
import sys
import textwrap
import tempfile
from pathlib import Path


def get_video_duration(audio_path: str) -> float:
    """用 FFprobe 获取音频时长（秒）"""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of",
            "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def wrap_text(text: str, max_chars_per_line: int = 12) -> str:
    """将长篇文本按字数拆分为多行（用于字幕显示）"""
    lines = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        wrapped = textwrap.fill(paragraph, width=max_chars_per_line)
        lines.append(wrapped)
    return "\n".join(lines)


def create_subtitle_ass(
    script_data: dict, duration: float, output_path: str
) -> str:
    """生成 ASS 字幕文件（支持中文字体、渐变、阴影）。

    将 full_script 按标点拆分为若干句，每句分配均等时间。
    """
    import re

    full_text = script_data.get("full_script", "")
    title = script_data.get("title", "早安")

    sentences = re.split(r"(?<=[。？！\n])", full_text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        sentences = [full_text]

    seg_duration = duration / len(sentences)

    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,2,8,60,60,120,134
Style: Title,Microsoft YaHei,64,&H00FFF5E1,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,4,0,1,3,2,5,60,60,200,134

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    ass_body = ""

    title_start = 0.0
    title_end = min(3.0, duration * 0.15)
    wrapped_title = wrap_text(title, max_chars_per_line=8)
    for line in wrapped_title.split("\n"):
        if line.strip():
            ass_body += (
                f"Dialogue: 1,{title_start:.1f},{title_end:.1f},"
                f"Title,,0,0,0,,{line.strip()}\n"
            )

    for i, sentence in enumerate(sentences):
        start = seg_duration * i + title_end
        end = seg_duration * (i + 1) + title_end
        if i == len(sentences) - 1:
            end = duration
        wrapped = wrap_text(sentence, max_chars_per_line=14)
        for line in wrapped.split("\n"):
            if line.strip():
                ass_body += (
                    f"Dialogue: 0,{start:.1f},{end:.1f},"
                    f"Default,,0,0,0,,{line.strip()}\n"
                )

    content = ass_header + ass_body
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path


def compose_video(
    audio_path: str,
    output_path: str,
    script_data: dict,
    background_image: str = "",
    bg_music_path: str = "",
    width: int = 1080,
    height: int = 1920,
) -> str:
    """使用 FFmpeg 合成最终视频。"""
    duration = get_video_duration(audio_path)
    temp_dir = tempfile.mkdtemp()

    ass_path = os.path.join(temp_dir, "subtitles.ass")
    create_subtitle_ass(script_data, duration, ass_path)

    if background_image and os.path.exists(background_image):
        bg_filter = (
            f"movie='{background_image}'"
            f":loop=1,scale={width}:{height}:force_original_aspect_ratio=1,"
            f"crop={width}:{height}"
        )
    else:
        bg_filter = (
            f"color=c=0xFFF5E1:s={width}x{height}:d={duration}:r=24,"
            f"drawbox=x=0:y=0:w={width}:h={height}:color=white@0.3"
        )

    ass_escaped = ass_path.replace("\\", "\\\\").replace(":", "\\:").replace(",", "\\,")
    subtitle_filter = f"subtitles='{ass_escaped}'"

    if bg_music_path and os.path.exists(bg_music_path):
        audio_filter = (
            f"[1:a]volume=0.15[a_bg];"
            f"[0:a][a_bg]amix=inputs=2:duration=first[a_out]"
        )
        filter_complex = (
            f"[0:v]{bg_filter},format=rgb24[v0];"
            f"[v0]{subtitle_filter}[v_out];"
            f"{audio_filter}"
        )
    else:
        filter_complex = (
            f"[0:v]{bg_filter},format=rgb24[v0];"
            f"[v0]{subtitle_filter}[v_out]"
        )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=24",
        "-i", audio_path,
    ]

    if bg_music_path and os.path.exists(bg_music_path):
        cmd += ["-i", bg_music_path]

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[v_out]",
    ]

    if bg_music_path and os.path.exists(bg_music_path):
        cmd += ["-map", "[a_out]"]
    else:
        cmd += ["-map", "1:a"]

    cmd += [
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_path,
    ]

    print(f"FFmpeg 命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("FFmpeg stderr:", result.stderr[:1000])
        raise RuntimeError(f"FFmpeg 合成失败 (return code {result.returncode})")

    return output_path


if __name__ == "__main__":
    output_dir = os.environ.get("OUTPUT_DIR", ".")
    os.makedirs(output_dir, exist_ok=True)

    script_path = os.path.join(output_dir, "script.json")
    if not os.path.exists(script_path):
        print(json.dumps({"error": "script.json 不存在"}, ensure_ascii=False))
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    audio_path = os.path.join(output_dir, "audio.mp3")
    if not os.path.exists(audio_path):
        print(json.dumps({"error": "audio.mp3 不存在"}, ensure_ascii=False))
        sys.exit(1)

    bg_image = os.environ.get("BG_IMAGE", "")
    bg_music = os.environ.get("BG_MUSIC", "")

    portrait_path = os.path.join(output_dir, "morning_portrait.mp4")
    compose_video(
        audio_path, portrait_path, script_data,
        background_image=bg_image, bg_music_path=bg_music,
        width=1080, height=1920,
    )
    print(f"竖版视频已生成: {portrait_path}")

    landscape_path = os.path.join(output_dir, "morning_landscape.mp4")
    compose_video(
        audio_path, landscape_path, script_data,
        background_image=bg_image, bg_music_path=bg_music,
        width=1920, height=1080,
    )
    print(f"横版视频已生成: {landscape_path}")

    script_data.setdefault("_meta", {})
    script_data["_meta"]["video_portrait"] = portrait_path
    script_data["_meta"]["video_landscape"] = landscape_path
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script_data, f, ensure_ascii=False, indent=2)
