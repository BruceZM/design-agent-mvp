#!/bin/zsh
set -eu
TASK_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_DIR="$TASK_DIR/design-agent"
CRM_DIR="$TASK_DIR/customer-manager"
mkdir -p "$AGENT_DIR/runtime"
MVP_BACKEND_PID=""
MVP_CRM_PID=""
cleanup() {
  if [[ -n "$MVP_BACKEND_PID" ]]; then kill "$MVP_BACKEND_PID" 2>/dev/null || true; fi
  if [[ -n "$MVP_CRM_PID" ]]; then kill "$MVP_CRM_PID" 2>/dev/null || true; fi
}
trap cleanup INT TERM EXIT
command -v uv >/dev/null
command -v node >/dev/null
"$TASK_DIR/scripts/init-local-crm.sh"
cd "$AGENT_DIR"
uv sync --locked
cd "$AGENT_DIR/frontend"
if [[ ! -d node_modules ]]; then npm ci; fi
npm run build
cd "$CRM_DIR"
if [[ ! -d node_modules ]]; then npm ci; fi
cd "$AGENT_DIR"
if ! curl -sf http://127.0.0.1:8011/api/health >/dev/null; then
  uv run uvicorn app.main:app --app-dir "$AGENT_DIR/backend" --host 127.0.0.1 --port 8011 --no-access-log >"$AGENT_DIR/runtime/backend.log" 2>&1 &
  MVP_BACKEND_PID=$!
  echo $! >"$AGENT_DIR/runtime/backend.pid"
fi
if ! curl -sf http://127.0.0.1:5174 >/dev/null; then
  cd "$CRM_DIR"
  npm run dev >"$AGENT_DIR/runtime/customer-manager.log" 2>&1 &
  MVP_CRM_PID=$!
  echo $! >"$AGENT_DIR/runtime/customer-manager.pid"
fi
for attempt in {1..30}; do
  if curl -sf http://127.0.0.1:8011/api/health >/dev/null && curl -sf http://127.0.0.1:5174 >/dev/null; then break; fi
  sleep 0.3
done
curl -sf http://127.0.0.1:8011/api/health >/dev/null
curl -sf http://127.0.0.1:5174 >/dev/null
echo 'Design Agent: http://127.0.0.1:8011'
echo '客户管理基线: http://127.0.0.1:5174'
echo '后台日志保存在 design-agent/runtime/。保持此终端运行，Ctrl+C 停止本脚本启动的服务。'
if [[ -n "$MVP_BACKEND_PID" || -n "$MVP_CRM_PID" ]]; then wait; fi
