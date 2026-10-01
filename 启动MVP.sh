#!/bin/zsh
# 本地一键启动；命令失败或使用未设置变量时停止，不把失败安装当作正常启动。
set -eu
# 按脚本所在位置定位项目，支持从其他工作目录调用；不把密钥写进命令行。
TASK_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_DIR="$TASK_DIR/design-agent"
CRM_DIR="$TASK_DIR/customer-manager"
mkdir -p "$AGENT_DIR/runtime"
MVP_BACKEND_PID=""
MVP_CRM_PID=""
# 只停止本脚本新启动并记录 PID 的服务；已存在的服务不会被 cleanup 接管。
cleanup() {
  if [[ -n "$MVP_BACKEND_PID" ]]; then kill "$MVP_BACKEND_PID" 2>/dev/null || true; fi
  if [[ -n "$MVP_CRM_PID" ]]; then kill "$MVP_CRM_PID" 2>/dev/null || true; fi
}
# 退出和 Ctrl+C 时清理自己启动的子进程，避免留下重复监听端口的服务。
trap cleanup INT TERM EXIT
# 先检查运行时，再初始化本地 CRM Git；初始化脚本不会覆盖已有仓库。
command -v uv >/dev/null
command -v node >/dev/null
"$TASK_DIR/scripts/init-local-crm.sh"
cd "$AGENT_DIR"
# 锁文件确保 Python 依赖版本一致；前端构建后由 FastAPI 提供 dist。
uv sync --locked
cd "$AGENT_DIR/frontend"
if [[ ! -d node_modules ]]; then npm ci; fi
npm run build
cd "$CRM_DIR"
if [[ ! -d node_modules ]]; then npm ci; fi
cd "$AGENT_DIR"
# 已有健康服务就复用；否则后台启动并保存 PID，日志落入忽略的 runtime。
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
# 短轮询等待两个服务可用；最后再次 curl，启动失败会以非零退出显式暴露。
for attempt in {1..30}; do
  if curl -sf http://127.0.0.1:8011/api/health >/dev/null && curl -sf http://127.0.0.1:5174 >/dev/null; then break; fi
  sleep 0.3
done
curl -sf http://127.0.0.1:8011/api/health >/dev/null
curl -sf http://127.0.0.1:5174 >/dev/null
echo 'Design Agent: http://127.0.0.1:8011'
echo '客户管理基线: http://127.0.0.1:5174'
echo '后台日志保存在 design-agent/runtime/。保持此终端运行，Ctrl+C 停止本脚本启动的服务。'
# 保持本次启动的服务随终端运行；关闭终端会中断后台任务，关闭网页则不会。
if [[ -n "$MVP_BACKEND_PID" || -n "$MVP_CRM_PID" ]]; then wait; fi
