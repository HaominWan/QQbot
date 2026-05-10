# Linux / WSL2 部署指南

这份指南基于 WSL2 + Ubuntu 24.04 验证。项目运行方式是：

- Python bot 在 WSL2 里监听 OneBot v11 反向 WebSocket。
- NapCatQQ 单独安装并登录 QQ。
- NapCat 的 WebSocket Client 连接到 bot：`ws://127.0.0.1:8080/onebot/v11/ws`。

Windows 版 `NapCat.Shell.Windows.OneKey/` 不能直接搬到 Linux 使用。

## 1. 验证 WSL2 环境

在 PowerShell 里确认 Ubuntu 是 WSL2：

```powershell
wsl -l -v
```

进入 Ubuntu 后检查：

```bash
uname -a
lsb_release -a
python3 --version
node --version || true
npm --version || true
```

Ubuntu 24.04 默认可能没有 `python` 命令，只有 `python3`，后面会安装 `python-is-python3` 兼容。

## 2. 安装系统依赖

```bash
sudo apt update
sudo apt install -y \
  python3-full python3-venv python3-pip python-is-python3 \
  nodejs npm rsync \
  curl ca-certificates git build-essential \
  xvfb xauth screen \
  fonts-noto-cjk fonts-noto-color-emoji
```

确认 Node/npm 来自 Linux，而不是 Windows PATH：

```bash
which node
which npm
node --version
npm --version
```

正常应类似：

```text
/usr/bin/node
/usr/bin/npm
```

如果 `which npm` 指向 `/mnt/c/...`，当前终端可能混进了 Windows npm。先刷新命令缓存并显式使用 Linux npm：

```bash
hash -r
/usr/bin/node --version
/usr/bin/npm --version
```

## 3. 复制项目到 WSL

建议把项目复制到 WSL 的 Linux 文件系统，不要直接在 `/mnt/d/...` 下跑。复制时排除 Codex 临时目录、虚拟环境、依赖目录和 Windows NapCat 包，避免权限和性能问题。

```bash
rm -rf ~/projects/QQbot
mkdir -p ~/projects

rsync -a \
  --exclude '.git/' \
  --exclude '.codex-temp/' \
  --exclude 'node_modules/' \
  --exclude 'Bot/.venv/' \
  --exclude 'Bot/tmp/' \
  --exclude 'Bot/memory_db/' \
  --exclude 'NapCat.Shell.Windows.OneKey/' \
  /mnt/d/Projects/QQbot/ \
  ~/projects/QQbot/
```

注意源路径 `/mnt/d/Projects/QQbot/` 末尾的 `/` 很重要。不要在 `~/projects/QQbot` 里面再执行 `cp -a /mnt/d/Projects/QQbot ~/projects/QQbot`，否则会得到嵌套的 `~/projects/QQbot/QQbot`。

检查文件：

```bash
cd ~/projects/QQbot
test -f package.json && echo "package.json OK"
test -f run.sh && echo "run.sh OK"
```

## 4. 安装项目依赖

```bash
cd ~/projects/QQbot

python3 -m venv Bot/.venv
source Bot/.venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r Bot/requirements.txt

/usr/bin/npm install
chmod +x run.sh
```

如果没有激活 venv 就执行 `pip install`，Ubuntu 24.04 会报 `externally-managed-environment`。这是正常保护机制，回到上面的 venv 步骤即可。

## 5. 配置 bot

```bash
cd ~/projects/QQbot
cp Bot/config.example.json Bot/config.json
nano Bot/config.json
```

至少确认这些字段：

```json
{
  "bot_settings": {
    "super_users": [你的QQ号],
    "test_groups": [测试群号],
    "host": "127.0.0.1",
    "port": "8080",
    "proxy_url": "http://127.0.0.1:7890"
  }
}
```

`proxy_url` 按实际情况填写；没有代理时可以留空字符串或按你的配置处理。

## 6. 先验证 bot 本体

开第一个 WSL 终端启动 bot：

```bash
cd ~/projects/QQbot/Bot
source .venv/bin/activate
python bot.py
```

再开第二个 WSL 终端验证端口：

```bash
cd ~/projects/QQbot
Bot/.venv/bin/python wait_port.py --host 127.0.0.1 --port 8080 --timeout 5
echo $?
```

返回 `0` 表示 bot 已成功监听 `127.0.0.1:8080`。

## 7. 安装 NapCatQQ

下载并运行 NapCat 安装器：

```bash
cd ~
curl -L -o napcat.sh https://raw.githubusercontent.com/NapNeko/NapCat-Installer/main/script/install.sh
sudo bash napcat.sh --tui
```

如果下载 GitHub 很慢或失败，可以临时给 WSL 设置 Windows 代理。假设 Windows 代理端口是 `7890`：

```bash
export WIN_HOST=$(awk '/nameserver/ {print $2; exit}' /etc/resolv.conf)
export http_proxy=http://$WIN_HOST:7890
export https_proxy=http://$WIN_HOST:7890
```

安装器菜单里选择：

```text
1. Shell安装
```

Shell 安装适合先验证；Docker 安装适合后续长期服务化部署。

安装完成后会输出安装位置和启动命令。若安装位置在 `/root/Napcat`，直接用当前用户启动会出现 `Permission denied`，可以先用 sudo 启动，或迁移到当前用户目录。

推荐迁移：

```bash
sudo mv /root/Napcat /home/$USER/Napcat
sudo chown -R $USER:$USER /home/$USER/Napcat
```

如果迁移后日志出现仍在查找 `/root/Napcat/.../napcat.mjs`，说明安装时写入了绝对路径，替换为新路径：

```bash
grep -RIl "/root/Napcat" ~/Napcat | xargs sed -i "s#/root/Napcat#/home/$USER/Napcat#g"
grep -RIn "/root/Napcat" ~/Napcat 2>/dev/null | head
```

第二条没有输出即可。

## 8. 启动 NapCat

前台启动：

```bash
xvfb-run -a ~/Napcat/opt/QQ/qq --no-sandbox
```

后台启动：

```bash
screen -dmS napcat bash -c "xvfb-run -a ~/Napcat/opt/QQ/qq --no-sandbox"
screen -r napcat
```

如果看到 GPU 初始化相关错误，一般可以先忽略，重点看 WebUI 和 NapCat 是否继续启动。

查看 WebUI token：

```bash
cat ~/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/webui.json
```

里面通常有：

```json
{
  "host": "::",
  "port": 6099,
  "token": "你的token"
}
```

Windows 浏览器打开：

```text
http://127.0.0.1:6099
```

用 `webui.json` 里的 token 登录。

## 9. 配置 WebSocket Client

在 NapCat WebUI 里进入 WebSocket Client 配置，新增或编辑：

```text
启用：打开
名称：QQBot
URL：ws://127.0.0.1:8080/onebot/v11/ws
消息格式：Array
Token：留空
心跳间隔：30000
重连间隔：30000
```

这里的 `ws://127.0.0.1:8080/onebot/v11/ws` 是填到 WebUI 的 URL，不是终端命令，不要粘到 bash 里执行。

保存后回到 bot 终端，看到类似日志表示连通：

```text
[NapCat]NapCat connected from path
```

## 10. 功能验证

在 `Bot/config.json` 配置过的测试群里发送：

```text
.help
```

有回复说明消息链路跑通。再测试渲染：

```text
.md **hello** $E=mc^2$
.typ hello
```

如果 `.md` 失败，优先检查 Node/npm 是否来自 Linux，以及 `npm install` 是否在项目根目录成功执行。

## 11. 常见问题

### `cp: cannot access .codex-temp/... Permission denied`

不要复制 `.codex-temp`，使用本指南的 `rsync --exclude` 命令。

### 项目变成 `~/projects/QQbot/QQbot`

复制命令目标写错了。清掉后用源路径带尾部 `/` 的 `rsync`：

```bash
rm -rf ~/projects/QQbot
rsync -a /mnt/d/Projects/QQbot/ ~/projects/QQbot/
```

实际使用时记得加上本指南里的 exclude。

### `externally-managed-environment`

说明 pip 在系统 Python 上运行了。先激活 venv：

```bash
cd ~/projects/QQbot
source Bot/.venv/bin/activate
python -m pip install -r Bot/requirements.txt
```

### `npm error ENOENT package.json`

确认当前目录是项目根目录：

```bash
cd ~/projects/QQbot
ls package.json
/usr/bin/npm install
```

### npm 日志跑到 `C:\Users\...\npm-cache`

说明用了 Windows npm。使用：

```bash
which npm
/usr/bin/npm install
```

### `/root/Napcat/opt/QQ/qq: Permission denied`

NapCat 装在 root 目录，当前用户没权限。迁移到 home：

```bash
sudo mv /root/Napcat /home/$USER/Napcat
sudo chown -R $USER:$USER /home/$USER/Napcat
```

### `Cannot find module '//root/Napcat/.../napcat.mjs'`

迁移目录后旧路径仍写在文件里，替换路径：

```bash
grep -RIl "/root/Napcat" ~/Napcat | xargs sed -i "s#/root/Napcat#/home/$USER/Napcat#g"
```

### 把 `URL：ws://...` 粘到终端报错

这是 WebUI 配置项，不是命令。请填到 NapCat WebSocket Client 的 URL 输入框。

## 12. 停止与清理

停止 bot：在 bot 终端按 `Ctrl+C`。

停止后台 NapCat：

```bash
screen -S napcat -X quit
```

清理项目运行产物：

```bash
cd ~/projects/QQbot
rm -rf Bot/tmp Bot/memory_db startup.log
```

完整删除 WSL 里的测试项目：

```bash
rm -rf ~/projects/QQbot
```

删除 NapCat：

```bash
rm -rf ~/Napcat ~/napcat.sh
```

如果仍保留了 root 目录：

```bash
sudo rm -rf /root/Napcat
```
