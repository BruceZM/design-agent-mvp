#!/bin/sh
# 公开项目用一个远程仓库；Agent 执行时仍需要 CRM 自己的本地 Git/worktree。
# 克隆后运行此脚本建立内部基线，保留已经存在的 CRM Git 历史和工作区。
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
# CDPATH 清空防止 cd 受用户配置影响而输出额外路径；变量始终加引号兼容空格。
CRM_DIR="$PROJECT_DIR/customer-manager"

command -v git >/dev/null
if [ -e "$CRM_DIR/.git" ]; then
  # .git 可能是目录，也可能是 worktree 元数据文件，用 -e 后再交给 Git 校验。
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
# 只纳入固定基线文件，不把 node_modules、密钥或本地产物暂存进仓库。
git -C "$CRM_DIR" add -- .gitignore README.md package.json package-lock.json \
  tsconfig.json vite.config.ts index.html src docs
git -C "$CRM_DIR" -c user.name='Design Agent' \
  -c user.email='design-agent@localhost' -c core.hooksPath=/dev/null \
  commit -m 'Initialize local CRM baseline from project checkout'
echo '已初始化独立的本地 CRM 仓库，Agent 将基于此 main 创建任务分支。'
