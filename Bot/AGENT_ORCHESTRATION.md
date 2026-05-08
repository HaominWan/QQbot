# Agent Orchestration

当前编排层是一个轻量版本，目标是先把消息处理从散落的 handler 逻辑收拢成稳定管线。

## Pipeline

```text
OneBot event
  -> EventRouter
  -> AgentOrchestrator
  -> decide action
      -> IGNORE: 群聊未 at bot
      -> TOOL: 显式命令交给 ToolRouter
      -> CHAT: PersonaEngine + SessionManager + LLM
  -> send response
```

## Boundaries

- `handlers.py`: 只负责 OneBot 事件归一化、白名单群过滤、多模态预处理函数注册。
- `agent_orchestrator.py`: 负责一次消息运行的决策和执行顺序。
- `tool_router.py`: 负责命令前缀和工具处理器的注册、匹配、调用。
- `persona_engine.py`: 负责人格选择、提示词构造、输入清洗。
- `session_manager.py`: 负责私聊/群聊 session 生命周期。

## Next Steps

1. 引入 `Planner`：让模型输出结构化意图，例如 `chat`、`tool`、`ignore`、`clarify`。
2. 把高价值插件注册为可被 planner 选择的 agent tool，而不是只能靠前缀触发。
3. 增加群聊主动回复策略：根据提及、上下文相关度、冷却时间、用户关系决定是否插话。
4. 给 `AgentRunResult` 记录 trace，方便观察每次为什么回复或不回复。
