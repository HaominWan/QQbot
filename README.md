# QQBot (Based on Lagrange.OneBot)

这是一个基于 [Lagrange.OneBot](https://github.com/LagrangeDev/Lagrange.Core) 和 Python 的 QQ 机器人项目。它集成了多种 AI 模型（OpenAI, Gemini, Groq）以及丰富的实用工具插件。

## ✨ 功能特性

### 🤖 AI 对话与交互
- **多模型支持**: 集成 OpenAI, Google Gemini, Groq 等多种 LLM API。
- **多模态能力**: 支持图片识别与理解（基于 Gemini）。
- **角色扮演**: 支持自定义 System Prompt，内置多种角色（如 Murasame）。
- **上下文记忆**: 支持私聊和群聊的上下文对话。

### 🛠️ 实用工具插件
- **AI 绘图**: 使用 Prodia API 生成高质量图片 (`.draw`)。
- **代码渲染**:
  - **Typst**: 将 Typst 代码渲染为图片 (`.typ` / `.typst`)。
  - **Markdown**: 将 Markdown 文本渲染为图片 (`.md` / `.markdown`)。
- **娱乐功能**:
  - **游戏王查卡**: 查询游戏王卡片信息 (`.YGO`)。
  - **P5 预告信**: 生成女神异闻录 5 风格的预告信 (`.P5`)。
  - **JMComic**: 漫画下载与 PDF 生成 (`.jm`)。

### ⚙️ 管理功能
- **重置对话**: 清除当前会话的上下文记忆 (`.reset`)。
- **热重载**: 支持插件和处理器的热重载。

## 🚀 快速开始

### 环境要求
- Windows / Linux / macOS
- Python 3.8+
- [Lagrange.OneBot](https://github.com/LagrangeDev/Lagrange.Core) (已包含在项目中或自行下载)

### 1. 安装依赖

```bash
pip install -r Bot/requirements.txt
```

### 2. 配置文件

#### 主配置
复制 `Bot/config.example.json` 为 `Bot/config.json`，并填入你的 API Key 和配置信息：

```json
{
  "api_keys": {
    "openai": "sk-...",
    "gemini": "AIza...",
    "groq": "gsk_...",
    "prodia": "..."
  },
  "bot_settings": {
    "super_users": [123456789],     // 管理员 QQ 号
    "test_groups": [123456789],     // 启用的群组 QQ 号
    "host": "127.0.0.1",
    "port": "8080",
    "proxy_url": "http://127.0.0.1:7890" // 代理地址（可选）
  }
}
```

#### 插件配置
如果需要使用 JMComic 功能，请检查 `Bot/plugins/option.yml` 配置文件。

### 3. 启动

#### Windows 用户
直接运行项目根目录下的 `run.bat` 脚本。该脚本会自动：
1. 关闭旧的 Lagrange 进程。
2. 启动 `Lagrange.OneBot.exe`。
3. 启动 Python Bot。

#### 手动启动
1. 启动 Lagrange.OneBot 并扫码登录。
2. 运行 Python Bot:
   ```bash
   python Bot/bot.py
   ```

## 📝 指令列表

| 指令 | 说明 | 示例 |
| --- | --- | --- |
| `.help` | 显示帮助信息 | `.help` |
| `.reset` | 重置当前对话上下文 | `.reset` |
| `.draw <提示词>` | AI 绘图 | `.draw beautiful girl, white hair` |
| `.typ <代码>` | 渲染 Typst 代码 | `.typ $ x^2 + y^2 = 1 $` |
| `.md <文本>` | 渲染 Markdown 文本 | `.md # Hello World` |
| `.YGO <卡名>` | 查询游戏王卡片 | `.YGO 增殖的G` |
| `.P5 <内容>` | 生成 P5 预告信 | `.P5 偷走你的心` |
| `.jm <代码>` | 下载 JM 漫画并转 PDF | `.jm 123456` |

## 📂 项目结构

```
QQbot/
├── Bot/
│   ├── bot.py              # 主程序入口
│   ├── config.py           # 配置加载
│   ├── handlers.py         # 消息分发处理
│   ├── command_handlers.py # 命令处理逻辑
│   ├── api.py              # LLM API 封装
│   ├── models/             # 数据模型 (User, Group)
│   └── plugins/            # 功能插件
│       ├── drawing.py      # 绘图插件
│       ├── gemini.py       # Gemini 多模态插件
│       ├── typst_renderer.py # Typst 渲染
│       └── ...
├── appsettings.json        # Lagrange 配置文件
├── run.bat                 # Windows 启动脚本
└── requirements.txt        # Python 依赖
```

## ⚠️ 免责声明

1. 本项目仅供学习和研究使用，请勿用于非法用途。
2. JMComic 插件涉及第三方内容，请遵守相关法律法规。
3. 请妥善保管你的 `config.json`，其中包含敏感的 API Key。

## 📄 License

MIT
