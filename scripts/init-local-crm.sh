#!/bin/sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
CRM_DIR="$PROJECT_DIR/customer-manager"

command -v git >/dev/null
if [ -e "$CRM_DIR/.git" ]; then
  git -C "$CRM_DIR" rev-parse --git-dir >/dev/null
  git -C "$CRM_DIR" show-ref --verify --quiet refs/heads/main || {
    echo '客户管理仓库缺少 main 分支，请先检查本地 Git 状态。' >&2
    exit 1
  }
  exit 0
fi

if [ ! -f "$CRM_DIR/package.json" ] || [ ! -d "$CRM_DIR/src" ]; then
  echo '客户管理项目目录不完整，无法初始化。' >&2
  exit 1
fi

git -C "$CRM_DIR" init -b main
git -C "$CRM_DIR" add -- .gitignore README.md package.json package-lock.json \
  tsconfig.json vite.config.ts index.html src docs
git -C "$CRM_DIR" -c user.name='Design Agent' \
  -c user.email='design-agent@localhost' -c core.hooksPath=/dev/null \
  commit -m 'Initialize local CRM baseline from project checkout'
echo '已初始化独立的本地 CRM 仓库，Agent 将基于此 main 创建任务分支。'
