# 每日早安 ｜ Daily Morning Greeting

> 一个全自动的每日早安短视频生成与多平台发布工作流。
> 每天定时生成，自动发布到 B站、YouTube 等平台，几乎零成本。

---

## 效果预览

一条典型的早安视频长这样：

```
┌──────────────────────────────────┐
│                                  │
│    ?? 早安，新的一天             │
│                                  │
│    "每一个清晨都是世界对你       │
│     说的最温柔的情话"            │
│                                  │
│    配乐轻声 ｜ 温暖女声配音      │
│    ────────────────              │
│    北京 晴 22°C                  │
└──────────────────────────────────┘
         （时长约 60 秒）
```

---

## 工作流程

```
  05:30 UTC+8（定时触发）
        │
        ▼
  ┌─────────────┐
  │  ① GPT-4o-mini  │  生成早安文案
  │  生成早安文案     │  （含日期、天气、寄语）
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │  ② TTS 语音  │  Edge TTS（免费）
  │  合成配音     │  或 OpenAI TTS
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │  ③ FFmpeg    │  背景 + 字幕 + 配音
  │  合成视频     │  → 竖版(9:16) + 横版(16:9)
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │  ④ 多平台    │  Bilibili / YouTube
  │  自动发布     │  （抖音/小红书预留）
  └─────────────┘
```

---

## 每条内容的成本

| 环节 | 选型 | 成本（人民币） |
|---|---|---|
| 文案生成 | GPT-4o-mini | ￥0.001 |
| 语音合成 | Edge TTS（免费） | ￥0 |
| 语音合成（升级） | OpenAI TTS | ￥0.02 |
| 背景图片 | 免费素材 / DALL-E 3 | ￥0 / ￥0.29 |
| 视频合成 | FFmpeg（免费） | ￥0 |
| GitHub Actions | 免费额度内 | ￥0 |
| **每日最低成本** | | **约 ￥0.001** |
| **每月最低成本** | | **约 ￥0.03** |

---

## 快速开始

### 1. Fork 这个仓库

点击 GitHub 右上角的 Fork 按钮。

### 2. 配置 Secrets

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret | 说明 | 是否必填 |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API Key | ? 必需 |
| `BILI_SESSDATA` | B站登录 Cookie（SESSDATA） | 发布 B站时需填 |
| `BILI_JCT` | B站登录 Cookie（bili_jct） | 发布 B站时需填 |
| `YOUTUBE_API_KEY` | YouTube Data API OAuth 凭据 | 发布 YouTube 时需填 |
| `USE_OPENAI_TTS` | 设为 true 启用 OpenAI TTS（默认 Edge） | 可选 |
| `BG_IMAGE_URL` | 背景图片直链 URL | 可选 |
| `BG_MUSIC_URL` | 背景音乐直链 URL | 可选 |

### 3. 手动触发测试

```bash
# 在 GitHub Actions 页面点击 "Run workflow"
# 或使用 gh CLI：
gh workflow run morning-greeting.yml -f city="上海" -f style="文艺清新"
```

### 4. 定时自动运行

默认每天早上 05:30（北京时间）自动触发。
如需调整，修改 `.github/workflows/morning-greeting.yml` 中的 cron 表达式。

---

## 本地开发

```bash
# 1. 克隆仓库
git clone <your-fork-url>
cd morning-greeting

# 2. 安装依赖
pip install -r requirements.txt
sudo apt install ffmpeg fonts-wqy-microhei  # Linux
# brew install ffmpeg                        # macOS

# 3. 设置环境变量
export OPENAI_API_KEY=sk-...
export CITY="北京"
export STYLE="温暖治愈"
export OUTPUT_DIR="./output"

# 4. 分步运行
python scripts/generate_script.py
python scripts/tts.py
python scripts/compose_video.py
python scripts/publish.py
```

---

## 自定义模板

### 修改文案风格

在仓库 Variables 中设置 `STYLE`：
- `温暖治愈`（默认）
- `励志向上`
- `文艺清新`
- `幽默风趣`
- `知识科普`

### 使用自己的背景图

方式一：将图片提交到 `backgrounds/` 目录，设置 Secret `BG_IMAGE_URL` 为 GitHub 直链

方式二：在工作流中自动从 Pexels / Unsplash API 获取每日随机背景

### 更换配音

默认使用微软晓晓（`zh-CN-XiaoxiaoNeural`），可选的 Edge TTS 中文声线：
- `zh-CN-XiaoxiaoNeural` - 晓晓（女声，温暖推荐）
- `zh-CN-YunxiNeural` - 云希（男声）
- `zh-CN-XiaoyiNeural` - 晓伊（女声，亲切）

---

## 平台发布配置

### 抖音（Playwright 浏览器自动化）

抖音开放平台对个人开发者门槛较高，本方案使用 Playwright 浏览器自动化发布。

**首次设置（在本地电脑上运行）：**

```bash
# 1. 安装依赖
pip install playwright
playwright install chromium

# 2. 运行登录态采集（会弹出浏览器窗口）
python scripts/save_session.py douyin

# 3. 在浏览器中扫码登录
# 4. 登录后按 Enter 键，Cookie 自动保存到 .sessions/

# 5. 生成 GitHub Secret 值
python scripts/save_session.py douyin --to-secret
```

把输出的 base64 字符串添加到仓库 Secrets，Key 为 `DOUYIN_SESSION`。

Cookie 有效期约 7-30 天，过期后重新运行上述步骤即可。

### 小红书（Playwright 浏览器自动化）

同抖音方案，使用 Playwright 模拟发布。

**首次设置：**

```bash
# 采集小红书登录态
python scripts/save_session.py xiaohongshu

# 输出 Secret 值
python scripts/save_session.py xiaohongshu --to-secret
```

Key 为 `XIAOHONGSHU_SESSION`。

### Bilibili

1. 登录 bilibili.com
2. 浏览器按 F12 → Application → Cookies
3. 复制 `SESSDATA` 和 `bili_jct` 的值
4. 添加到 GitHub Secrets

### YouTube

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建项目，启用 YouTube Data API v3
3. 创建 OAuth 2.0 凭据（桌面应用类型）
4. 下载 `client_secret.json`
5. 首次运行时需完成 OAuth 授权流程

### 抖音 / 小红书 / 微博

官方 API 门槛较高（需企业资质），预留了浏览器自动化的接口。
可自行扩展使用 Playwright 模拟发布流程。

---

## 项目结构

```
morning-greeting/
├── .github/
│   └── workflows/
│       └── morning-greeting.yml    # 主工作流（定时触发）
├── scripts/
│   ├── generate_script.py          # ① 文案生成
│   ├── tts.py                      # ② 语音合成
│   ├── compose_video.py            # ③ 视频合成
│   └── publish.py                  # ④ 多平台发布
├── config/
│   └── config.yaml                 # 配置文件
├── backgrounds/                    # 背景素材（可自定义）
├── assets/                         # 其他素材
├── fonts/                          # 字体文件
├── requirements.txt                # Python 依赖
├── .gitignore
├── LICENSE
└── README.md
```

---


## 手机推送通知

每天视频生成后，你可以通过微信或 Telegram 在手机上收到结果，不用打开 GitHub。

### 方案 A：ServerChan（微信推送，推荐国内用户）

最简单的方式，注册即用，免费版每天 5 条，一条早安完全够用。

`ash
# 1. 打开 https://sct.ftqq.com
# 2. 用 GitHub 账号登录
# 3. 进入「SendKey」页面，复制你的 Key
# 4. 添加到 GitHub Secrets:

# 仓库 Settings → Secrets and variables → Actions
# New repository secret
#   Name: SERVERCHAN_SENDKEY
#   Value: <你复制的 SendKey>
`

配置完成后，每天早上你会收到这样的微信消息：

`
☀️ 早安，愿你今天比昨天更靠近梦想  [¥0.002]
📝 每一个清晨都是世界对你说...
💰 LLM: .0002 | TTS: .0000
   合计: ¥0.0015
📡 B站: ✅ 抖音: ✅ 小红书: ✅
🔗 查看详情: github.com/xxx/actions/42
`

### 方案 B：PushPlus（微信推送备选）

功能和 ServerChan 类似，免费版每天 200 条。

`ash
# 1. 打开 https://www.pushplus.plus
# 2. 微信扫码登录
# 3. 复制你的 Token
# 4. 添加到 GitHub Secrets:
#   Name: PUSHPLUS_TOKEN
`

### 方案 C：Telegram Bot（支持发视频）

如果你用 Telegram，Bot 可以**直接发视频文件**到手机。

`ash
# 1. 在 Telegram 搜索 @BotFather
# 2. 发送 /newbot，按提示创建机器人
# 3. 记下 Bot Token（类似 123456:ABC-def_GHI）
# 4. 搜索你的 bot 用户名，发送 /start
# 5. 访问以下链接获取 Chat ID（将 YOUR_TOKEN 替换）:
#    https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
#    返回 JSON 中的 message.chat.id 就是你需要的
# 6. 添加到 GitHub Secrets:
#   Name: TELEGRAM_BOT_TOKEN
#   Name: TELEGRAM_CHAT_ID
`

### 同时开多个渠道

可以同时配置 ServerChan 和 Telegram，脚本会自动检测已配置的渠道并发推送。
## 技术栈

- **文案**: OpenAI GPT-4o-mini
- **语音**: Microsoft Edge TTS（免费） / OpenAI TTS
- **视频**: FFmpeg + ASS 字幕
- **自动化**: GitHub Actions（cron 定时触发）
- **发布**: Bilibili API / YouTube Data API

---

## License

MIT


