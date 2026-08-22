# Security policy

## 本地敏感数据

以下内容只应保存在本地，不应提交到 Git：

- `Bot/config.json` 与 `.env*` 中的 API Key、refresh token 和代理凭据；
- 管理员 QQ 号、测试群号及 `Bot/data/` 中的运行状态；
- `*.db*`、`*.sqlite*` 中的聊天记录、向量记忆和用户/群标识；
- 私钥、证书密钥库以及个人角色提示词。

Bot 主配置只跟踪不含真实值的 `Bot/config.example.json`。程序读取 API 凭据时采用
环境变量优先、本地配置回退的顺序。本地配置仍是运行所必需的；首次部署时复制示例
文件：

```bash
cp Bot/config.example.json Bot/config.json
```

提交前运行：

```bash
python scripts/check_tracked_secrets.py
git check-ignore -v Bot/config.json Bot/data/test_groups.json
```

第一条命令检查当前已跟踪文件和所有未被忽略的待提交文件，识别禁入路径与常见密钥
格式；加 `--history` 可审计所有可达提交：

```bash
python scripts/check_tracked_secrets.py --history
```

## 凭据泄露响应

如果敏感值曾进入提交历史，仅在新提交中删除文件并不能消除泄露。应按以下顺序处理：

1. 立即在对应服务商处吊销并轮换全部受影响的凭据；
2. 检查服务商的调用、登录和账单日志，确认是否存在未授权使用；
3. 通知协作者暂停推送，并备份必要的本地分支；
4. 从所有分支和标签重写敏感文件及硬编码密钥的历史；
5. 强制更新远端后，要求协作者重新克隆，随后再次运行 `--history` 审计。

历史重写会改变提交哈希，且无法让已经被第三方克隆的凭据恢复安全，因此必须先轮换
凭据。不要把真实密钥写入替换规则、命令行参数、Issue、日志或清理提交说明。

## 报告安全问题

请通过仓库维护者提供的私密渠道报告漏洞或凭据泄露，不要在公开 Issue 中粘贴密钥、
QQ 号、群号、聊天记录或完整配置文件。
