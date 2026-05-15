#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$ROOT/startup.log"

cd "$ROOT"
{
  echo "==== Startup $(date '+%Y-%m-%d %H:%M:%S') ===="
  echo "Working directory: $ROOT"
} > "$LOG"

if [[ -x "$ROOT/Bot/.venv/bin/python" ]]; then
  PYTHON="$ROOT/Bot/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

mkdir -p "$ROOT/Bot/tmp"

if "$PYTHON" "$ROOT/wait_port.py" --host 127.0.0.1 --port 8080 --timeout 1 >/dev/null 2>&1; then
  echo "QQ Bot websocket server already appears to be running on 127.0.0.1:8080; refusing to start a duplicate." | tee -a "$LOG"
  exit 1
fi

if [[ -n "${NAPCAT_LINUX_CMD:-}" ]]; then
  if command -v pgrep >/dev/null 2>&1 && pgrep -af "napcat|NapCat" >/dev/null 2>&1; then
    echo "NapCat appears to be running; skipping start." | tee -a "$LOG"
  else
    echo "Starting NapCat from NAPCAT_LINUX_CMD..." | tee -a "$LOG"
    nohup bash -lc "$NAPCAT_LINUX_CMD" >> "$LOG" 2>&1 &
    sleep 3
  fi
else
  echo "NAPCAT_LINUX_CMD is not set; start NapCat manually if it is not already running." | tee -a "$LOG"
fi

echo "Starting QQ Bot websocket server..." | tee -a "$LOG"
cd "$ROOT/Bot"
"$PYTHON" bot.py >> "$LOG" 2>&1 &
BOT_PID=$!

echo "Waiting for QQ Bot websocket server on 127.0.0.1:8080..." | tee -a "$LOG"
if ! "$PYTHON" "$ROOT/wait_port.py" --host 127.0.0.1 --port 8080 --timeout 60; then
  echo "QQ Bot did not open port 8080 in time. Check $LOG." | tee -a "$LOG"
  exit 1
fi

echo "QQ Bot websocket server is ready." | tee -a "$LOG"
echo "NapCatQQ should connect to: ws://127.0.0.1:8080/onebot/v11/ws" | tee -a "$LOG"

wait "$BOT_PID"
