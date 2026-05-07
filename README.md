# QQBot

基于 [NapCatQQ](https://github.com/NapNeko/NapCatQQ) + Python 的 QQ 机器人，以 DeepSeek 为主对话模型，内置丛雨角色扮演人格，支持图片/视频识别、Markdown/公式渲染、表情包系统、向量长期记忆等多模态能力。

## 功能一览

| 能力 | 说明 |
|------|------|
| 角色扮演 | 内置丛雨人格（主人/守护模式），傲娇恋人风格，支持表情包辅助情绪表达 |
| 长期记忆 | 所有群消息向量化存入 ChromaDB，LLM 调用时自动检索相关历史作为上下文 |
| 图片识别 | 消息含图片时自动调用 Gemini 2.0 Flash 识别并告知 AI |
| 视频分析 | 调用 Gemini 2.0 Flash 分析视频内容 |
| 语音转文字 | 调用 Groq Whisper 转录语音消息 |
| Markdown 渲染 | AI 回复中的代码块、表格、数学公式自动渲染为图片发送 |
| 数学公式 | KaTeX 渲染，支持 `$…$` 行内和 `$$…$$` 块级公式 |
| Typst 渲染 | 将 Typst 代码渲染为图片 |
| 游戏王查卡 | 查询游戏王卡片信息与图片 |
| P5 预告信 | 生成女神异闻录 5 风格预告信 |
| AI 绘图 | 调用 Prodia API 生成图片（维修中） |
| JMComic | 漫画下载并转 PDF（维修中） |

## 部署

### 前置要求

- **Python 3.11+**（建议用 venv）
- **Node.js 18+**（Markdown/公式渲染依赖 Puppeteer）
- **NapCatQQ Shell 版**（OneBot v11 反向 WebSocket 模式）

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

> 首次运行时 sentence-transformers 会自动下载向量模型（约 90 MB），之后离线可用。  
> 可提前手动下载：  
> `Bot/.venv/Scripts/python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"`

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
  },
  "memory_settings": {
    "enabled":        true,
    "db_path":        "./memory_db",
    "window_size":    30,
    "search_results": 6
  }
}
```

**字段说明：**

| 字段 | 用途 | 是否必填 |
|------|------|----------|
| `deepseek` | 主对话模型 | 必填 |
| `gemini` | 图片/视频分析（google-genai） | 推荐填写 |
| `groq` | 语音转文字（Whisper） | 可选 |
| `prodia` | AI 绘图（维修中） | 可选 |
| `super_users` | 主人 QQ 号列表，拥有管理指令权限 | 必填 |
| `test_groups` | 允许 Bot 响应的群号列表 | 必填 |
| `proxy_url` | HTTP 代理 | 按需填写 |
| `memory_settings.window_size` | 内存中保留的最近消息数 | 默认 30 |
| `memory_settings.search_results` | 每次从向量 DB 检索的历史条数 | 默认 6 |

### 3. 配置 NapCatQQ

使用 NapCat Shell Windows OneKey 版本：

1. 首次登录：运行 `NapCat.Shell.Windows.OneKey/NapCat.44498.Shell/napcat.bat`，扫码登录
2. 后续快速登录：运行 `napcat.quick.bat`（已预填 QQ 号，无需扫码）
3. 进入 NapCat「网络配置」，添加 **反向 WebSocket**：
   - URL：`ws://127.0.0.1:8080/onebot/v11/ws`

### 4. 启动 Bot

**Windows（推荐）：**

```bat
run.bat
```

脚本会自动：
- 检测 NapCat 是否运行，未运行则自动以快速登录方式启动
- 启动 bot.py（自动检测 venv）
- 等待 8080 端口就绪

**手动启动：**

```bash
cd Bot
python bot.py
```

日志出现 `[NapCat] NapCat connected from path` 表示连接成功，`[Memory] Vector memory ready` 表示长期记忆就绪。

### 5. 表情包（可选）

在 `Bot/stickers/` 目录下放置图片并更新 `Bot/stickers/manifest.json`：

```json
{
  "shy":  "害羞、被夸奖、被摸头、慌乱时",
  "smug": "完成任务后的得意、自满时"
}
```

同一情绪可放多张（`shy0.jpg`、`shy1.gif`），发送时随机选择。

## 指令列表

群聊需要 @ Bot，私聊直接发送。★ 为超级用户专属，🔧 为维修中。

| 指令 | 说明 | 权限 |
|------|------|------|
| `.help` | 显示帮助 | 所有人 |
| `.reset` | 重启 Bot 进程（同时重启 NapCat 如未运行） | ★ |
| `.stop` | 强制停止 Bot 与 NapCat | ★ |
| `.clean` | 清空当前群的向量记忆数据库 | ★ |
| `.draw <提示词>` | AI 绘图（Prodia） | 🔧 |
| `.typ <代码>` | 渲染 Typst 代码为图片 | 所有人 |
| `.md <文本>` | 渲染 Markdown 为图片 | 所有人 |
| `.YGO <卡名>` | 游戏王查卡 | 所有人 |
| `.P5 <内容>` | P5 风格预告信 | 所有人 |
| `.jm <编号>` | 下载 JMComic 并转 PDF | 🔧 |

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
│   ├── config.example.json     # 配置模板
│   ├── requirements.txt        # Python 依赖
│   ├── memory/
│   │   └── vector_memory.py    # ChromaDB 向量记忆（后台线程初始化）
│   ├── models/
│   │   ├── User.py             # 私聊会话模型
│   │   └── Group.py            # 群聊会话模型（含滑动窗口 + 记忆注入）
│   ├── roles/
│   │   └── murasame_card.py    # 丛雨角色卡（人格提示词）
│   ├── plugins/
│   │   ├── vision.py           # 图片识别
│   │   ├── gemini.py           # 视频/图片分析（google-genai）
│   │   ├── markdown.py         # Markdown 渲染调度
│   │   ├── renderMarkdown.js   # Markdown 渲染（Node.js + Puppeteer + KaTeX）
│   │   ├── stickers.py         # 表情包系统
│   │   ├── typst_renderer.py   # Typst 渲染
│   │   └── ...
│   └── stickers/
│       ├── manifest.json       # 表情包情绪描述
│       └── *.jpg / *.gif       # 表情包图片（不随仓库分发）
├── package.json                # Node.js 依赖
├── run.bat                     # Windows 一键启动入口
├── run.ps1                     # 启动脚本（含 NapCat 检测与启动）
└── wait_port.ps1               # 端口等待工具
```

## 注意事项

- `Bot/config.json` 含 API Key，已加入 `.gitignore`
- 向量记忆数据库存于 `Bot/memory_db/`，已加入 `.gitignore`
- 中国大陆建议配置代理访问 DeepSeek / Gemini
- Puppeteer 首次运行会下载 Chromium
- 表情包图片不包含在仓库中，需自行准备

## License

MIT
