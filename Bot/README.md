# QQBot

基于 [NapCatQQ](https://github.com/NapNeko/NapCatQQ) + Python 的 QQ 机器人，以 DeepSeek 为主对话模型，内置丛雨角色扮演人格，支持图片/视频识别、Markdown/公式渲染、表情包系统、向量长期记忆等多模态能力。

## 功能一览

| 能力 | 说明 |
|------|------|
| 角色扮演 | 内置丛雨人格（主人/守护模式），傲娇恋人风格，支持表情包辅助情绪表达 |
| 长期记忆 | 群消息用 FastEmbed 向量化并存入 SQLite，LLM 调用时混合检索相关历史作为上下文 |
| 联网搜索 | 遇到热点、新闻、价格、天气、赛程等时效问题时自动检索网页并注入回答上下文 |
| 图片识别 | 消息含图片时自动调用 HuggingFace BLIP 识别并告知 AI |
| 视频分析 | 调用 Gemini 2.0 Flash 分析视频内容 |
| 语音转文字 | 调用 Groq Whisper 转录语音消息 |
| Markdown 渲染 | AI 回复中的代码块、表格、数学公式自动渲染为图片发送 |
| 数学公式 | KaTeX 渲染，支持 `$…$` 行内和 `$$…$$` 块级公式 |
| Typst 渲染 | 将 Typst 代码渲染为图片 |
| 游戏王查卡 | 查询游戏王卡片信息与图片 |
| P5 预告信 | 生成女神异闻录 5 风格预告信 |
| AI 绘图 | 调用 HuggingFace FLUX.1-schnell 生成图片 |
| Pixiv 搜图 | 按 PID、作品/作者名或 tag 随机返回高质量图片 |
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
# 确认当前目录能看到 package.json；如果没有，说明目录不对或下载包不完整
dir package.json        # Windows PowerShell
# ls package.json       # Linux/macOS
npm install
```

如果这里报 `ENOENT: no such file or directory, open '...\package.json'`，说明你当前目录没有
`package.json`。请先切到项目根目录（包含 `Bot/`、`package.json`、`run.bat` 的那一层）再执行：

```powershell
cd D:\你的项目目录\QQBot
npm install
```

如果你拿到的是不包含 `package.json` 的旧压缩包，可以手动安装 Markdown 渲染依赖：

```powershell
npm install markdown-it markdown-it-texmath katex puppeteer
```

> 首次运行时 FastEmbed 会自动下载向量模型（默认 `BAAI/bge-small-zh-v1.5`，约 90 MB），之后离线可用。
> 可提前手动下载：
> `Bot/.venv/Scripts/python -c "from fastembed import TextEmbedding; list(TextEmbedding(model_name='BAAI/bge-small-zh-v1.5').embed(['warmup']))"`

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
    "prodia":     "",
    "hf_token":   "",
    "pixiv_refresh_token": ""
  },
  "model_settings": {
    "deepseek_base_url":    "https://api.deepseek.com",
    "deepseek_model":       "deepseek-v4-flash",
    "deepseek_temperature": 0.75
  },
  "web_search_settings": {
    "enabled": true,
    "max_results": 4,
    "timeout_seconds": 10,
    "auto_for_time_sensitive": true,
    "allow_model_request": true
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
    "window_size":        30,
    "search_results":     3,
    "context_max_chars":  1500,
    "context_placement":  "user_message"
  },
  "pixiv_settings": {
    "min_bookmarks": 100,
    "sample_pool": 80,
    "default_count": 1,
    "max_count": 3,
    "allow_r18": false,
    "allow_ai": false
  }
}
```

**字段说明：**

| 字段 | 用途 | 是否必填 |
|------|------|----------|
| `deepseek` | 主对话模型 | 必填 |
| `web_search_settings.enabled` | 是否启用联网搜索增强 | 默认 true |
| `web_search_settings.max_results` | 每次注入 LLM 的搜索结果数量 | 默认 4 |
| `web_search_settings.auto_for_time_sensitive` | 遇到明显时效问题时是否直接搜索 | 默认 true |
| `web_search_settings.allow_model_request` | 是否允许模型通过 `<web_search>` 标记主动请求搜索 | 默认 true |
| `gemini` | 视频分析（google-genai） | 推荐填写 |
| `groq` | 语音转文字（Whisper） | 可选 |
| `hf_token` | HuggingFace Token，图片识别与 AI 绘图必填（免费账号即可） | 必填 |
| `pixiv_refresh_token` | Pixiv 登录 refresh token，用于 Pixiv 搜图/推荐 | Pixiv 功能必填 |
| `prodia` | 已弃用 | — |
| `super_users` | 主人 QQ 号列表，拥有管理指令权限 | 必填 |
| `test_groups` | 允许 Bot 响应的群号列表 | 必填 |
| `proxy_url` | HTTP 代理 | 按需填写 |
| `memory_settings.window_size` | 内存中保留的最近消息数 | 默认 30 |
| `memory_settings.search_results` | 每次从向量 DB 检索的历史条数 | 默认 3 |
| `memory_settings.context_max_chars` | 长期记忆注入 LLM 上下文的最大字符数 | 默认 1500 |
| `memory_settings.context_placement` | 长期记忆注入位置，`user_message` 更有利于缓存命中 | 默认 `user_message` |

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

群聊默认需要 @ Bot，私聊直接发送；超级用户启用 `.agent on` 后，当前群会对高置信度求助或工具意图自主响应。★ 为超级用户专属，🔧 为维修中。

| 指令 | 说明 | 权限 |
|------|------|------|
| `.help` | 显示帮助 | 所有人 |
| `.help <插件名>` | 显示指定插件语法，如 `.help pixiv` | 所有人 |
| `.reset` | 重启 Bot 进程（同时重启 NapCat 如未运行） | ★ |
| `.stop` | 强制停止 Bot 与 NapCat | ★ |
| `.clean` | 清空当前群的向量记忆数据库和当前对话上下文 | ★ |
| `.agent on/off/status` | 切换当前群自主回复模式，默认关闭 | ★ |
| `.ban <插件名>` | 在当前群禁用可管理插件，例如 `.ban jm` | ★ |
| `.unban <插件名>` | 在当前群重新启用插件，例如 `.unban jm` | ★ |
| `.ban user:<QQ号>` | 禁止 Bot 回复指定用户（群聊和私聊均生效） | ★ |
| `.unban user:<QQ号>` | 解除指定用户的回复封禁 | ★ |
| `.draw <提示词>` | AI 绘图（HuggingFace FLUX） | 所有人 |
| `.typ <代码>` | 渲染 Typst 代码为图片 | 所有人 |
| `.md <文本>` | 渲染 Markdown 为图片 | 所有人 |
| `.YGO <卡名>` | 游戏王查卡 | 所有人 |
| `.P5 <内容>` | P5 风格预告信 | 所有人 |
| `.jm <编号>` | 下载 JMComic 并转 PDF | 🔧 |
| `.jm recommend [数量]` | 获取今日 JM 推荐栏本子编号，默认 10 个、最多 20 个 | 所有人 |
| `.pixiv <PID/tag/关键词> [-n 1-3]` | Pixiv 搜图，默认按角色/tag/标题搜索 | 所有人 |
| `.pixiv drawer:<画师名> [-n 1-3]` | Pixiv 按画师搜索作品 | 所有人 |
| `.pixiv recommend [-n 1-3]` | Pixiv 每日推荐，随机返回排行榜高质量图 | 所有人 |
| `.ciallo` | NPUCraft 地图与数据面板链接 | 所有人 |

### Agent 自主路由

`.agent on` 只在当前群生效，默认关闭。启用后，未 @ 的消息只会走高置信度规则，不会把每条群消息都丢给大模型判断。

当前支持的自主路由：

| 意图 | 示例 | 自动转成 |
|------|------|----------|
| JM 编号 | `想看JM1436338` | `.jm 1436338` |
| JM 推荐栏序号 | `我想看推荐栏第2个` | 最近一次推荐列表的第 2 个编号 |
| JM 推荐栏 | `今天还没看jm本子` | `.jm recommend` |
| Pixiv PID/推荐/搜索 | `pixiv 12345678`、`来点p站推荐`、`搜pixiv 斯卡蒂` | `.pixiv ...` |
| 游戏王查卡 | `游戏王查卡 青眼白龙` | `.YGO 青眼白龙` |
| 绘图 | `帮我画 一只猫坐在键盘上` | `.draw ...` |
| P5 预告信 | `生成P5预告信 群友今晚必早睡` | `.P5 ...` |
| Markdown/Typst 渲染 | `渲染markdown: # 标题`、`渲染typst: $x^2$` | `.md ...` / `.typ ...` |

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
│   ├── web_search.py           # 联网搜索模块（DuckDuckGo HTML/API 回退）
│   ├── config.py               # 配置加载
│   ├── command_handlers.py     # 命令解析与分发
│   ├── config.example.json     # 配置模板
│   ├── requirements.txt        # Python 依赖
│   ├── memory/
│   │   └── vector_memory.py    # FastEmbed + SQLite 向量记忆（后台线程初始化）
│   ├── models/
│   │   ├── User.py             # 私聊会话模型
│   │   └── Group.py            # 群聊会话模型（含滑动窗口 + 记忆注入）
│   ├── roles/
│   │   └── murasame_card.py    # 丛雨角色卡（人格提示词）
│   ├── plugins/
│   │   ├── vision.py           # 图片识别（HuggingFace BLIP）
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

GPL-3.0-only. See [LICENSE](../LICENSE).

本项目以 GNU General Public License v3.0 授权。第三方依赖遵循其各自许可证。
