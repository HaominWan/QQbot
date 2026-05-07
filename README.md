# QQBot

基于 [NapCatQQ](https://github.com/NapNeko/NapCatQQ) + Python 的 QQ 机器人，以 DeepSeek 为主对话模型，内置丛雨角色扮演人格，支持图片识别、Markdown/公式渲染、表情包系统等多模态能力。

## 功能一览

| 能力 | 说明 |
|------|------|
| 角色扮演 | 内置丛雨人格（主人/守护模式），傲娇恋人风格，支持表情包辅助情绪表达 |
| 图片识别 | 消息含图片时自动调用 Gemini 2.0 Flash（via OpenRouter）识别并告知 AI |
| Markdown 渲染 | AI 回复中的代码块、表格、数学公式自动渲染为图片发送 |
| 数学公式 | KaTeX 渲染，支持 `$…$` 行内和 `$$…$$` 块级公式 |
| AI 绘图 | 调用 Prodia API 生成图片 |
| Typst 渲染 | 将 Typst 代码渲染为图片 |
| 游戏王查卡 | 查询游戏王卡片信息与图片 |
| P5 预告信 | 生成女神异闻录 5 风格预告信 |
| JMComic | 漫画下载并转 PDF |
| 语音转文字 | 调用 Groq Whisper 转录语音消息 |
| 会话重置 | 清空当前上下文记忆 |

## 部署

### 前置要求

- **Python 3.11+**（建议用 venv）
- **Node.js 18+**（Markdown/公式渲染依赖 Puppeteer）
- **NapCatQQ**（任意版本，OneBot v11 反向 WebSocket 模式）

### 1. 克隆并安装依赖

```bash
git clone <repo-url>
cd QQBot

# Python 依赖
python -m venv Bot/.venv
Bot/.venv/Scripts/activate       # Windows
# source Bot/.venv/bin/activate  # Linux/macOS
pip install -r Bot/requirements.txt

# Node 依赖（Markdown 渲染）
npm install
```

### 2. 配置文件

复制 `Bot/config.example.json` 为 `Bot/config.json` 并填写：

```json
{
  "api_keys": {
    "deepseek":   "sk-...",
    "openrouter": "sk-or-v1-...",
    "gemini":     "AIza...",
    "groq":       "gsk_...",
    "openai":     "",
    "prodia":     ""
  },
  "model_settings": {
    "deepseek_base_url":    "https://api.deepseek.com",
    "deepseek_model":       "deepseek-v4-flash",
    "deepseek_temperature": 0.75
  },
  "bot_settings": {
    "super_users": [你的QQ号],
    "test_groups":  [启用Bot的群号],
    "host":      "127.0.0.1",
    "port":      "8080",
    "proxy_url": "http://127.0.0.1:7890"
  }
}
```

**字段说明：**

| 字段 | 用途 | 是否必填 |
|------|------|----------|
| `deepseek` | 主对话模型 | 必填 |
| `openrouter` | 图片识别（Gemini 2.0 Flash） | 推荐填写 |
| `gemini` | 视频分析（旧接口） | 可选 |
| `groq` | 语音转文字（Whisper） | 可选 |
| `prodia` | AI 绘图 | 可选 |
| `super_users` | 主人 QQ 号列表（启用恋人模式） | 必填 |
| `test_groups` | 允许 Bot 响应的群号列表 | 必填 |
| `proxy_url` | HTTP 代理（访问 OpenRouter / DeepSeek） | 按需填写 |

### 3. 配置 NapCatQQ

1. 启动 NapCatQQ 并登录 QQ 账号
2. 进入「网络配置」，添加一个 **反向 WebSocket** 连接：
   - URL：`ws://127.0.0.1:8080/onebot/v11/ws`
3. 保存并启用

### 4. 启动 Bot

**Windows（推荐）：**

```bat
run.bat
```

脚本会自动检测 venv 并等待 8080 端口就绪。

**手动启动：**

```bash
cd Bot
python bot.py
```

日志出现 `[NapCat] NapCat connected from path` 表示连接成功。

### 5. 表情包（可选）

在 `Bot/stickers/` 目录下放置图片并更新 `Bot/stickers/manifest.json`：

```
stickers/
  shy0.jpg
  shy1.gif        # 同一情绪可放多张，发送时随机选择
  smug0.jpg
  manifest.json
```

`manifest.json` 格式：

```json
{
  "shy":  "害羞、被夸奖、被摸头、慌乱时",
  "smug": "完成任务后的得意、自满时"
}
```

## 指令列表

群聊需要 @ Bot，私聊直接发送。

| 指令 | 说明 |
|------|------|
| `.help` | 显示帮助 |
| `.reset` | 清空当前会话上下文 |
| `.draw <提示词>` | AI 绘图（Prodia） |
| `.typ <代码>` | 渲染 Typst 代码为图片 |
| `.md <文本>` | 渲染 Markdown 为图片 |
| `.YGO <卡名>` | 游戏王查卡 |
| `.P5 <内容>` | P5 风格预告信 |
| `.jm <编号>` | 下载 JMComic 并转 PDF |

## 项目结构

```
QQBot/
├── Bot/
│   ├── bot.py                  # WebSocket 服务器 & 消息收发
│   ├── handlers.py             # 消息路由 & 多模态预处理
│   ├── agent_orchestrator.py   # Agent 编排（决策/对话/工具调用）
│   ├── persona_engine.py       # 人格系统（主人/守护模式判断）
│   ├── session_manager.py      # 会话管理（私聊/群聊上下文）
│   ├── api.py                  # DeepSeek API 封装（含重试）
│   ├── config.py               # 配置加载
│   ├── command_handlers.py     # 命令解析与分发
│   ├── config.example.json     # 配置模板（复制为 config.json 后填写）
│   ├── requirements.txt        # Python 依赖
│   ├── models/
│   │   ├── User.py             # 私聊会话模型
│   │   └── Group.py            # 群聊会话模型
│   ├── roles/
│   │   └── murasame_card.py    # 丛雨角色卡（人格提示词）
│   ├── plugins/
│   │   ├── vision.py           # 图片识别（OpenRouter → Gemini 2.0 Flash）
│   │   ├── markdown.py         # Markdown 渲染（Python 侧调度）
│   │   ├── renderMarkdown.js   # Markdown 渲染（Node.js + Puppeteer + KaTeX）
│   │   ├── stickers.py         # 表情包加载与随机选取
│   │   ├── drawing.py          # AI 绘图（Prodia）
│   │   ├── gemini.py           # 视频/音频分析
│   │   └── ...
│   └── stickers/
│       ├── manifest.json       # 表情包情绪描述（需自行准备）
│       └── *.jpg / *.gif       # 表情包图片（不随仓库分发）
├── package.json                # Node.js 依赖
├── run.bat                     # Windows 一键启动
└── run.ps1                     # PowerShell 启动脚本
```

## 注意事项

- `Bot/config.json` 含有 API Key，已加入 `.gitignore`，不会提交到 Git
- 中国大陆访问 OpenRouter 建议配置代理
- Puppeteer 首次运行会自动下载 Chromium，需要网络连接
- 表情包图片不包含在仓库中，需自行准备后放入 `Bot/stickers/`

## License

MIT
