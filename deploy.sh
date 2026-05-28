#!/bin/bash
# Web3 Daily — 部署脚本
# 将当日 HTML 复制到 repo 根目录并推送到 GitHub Pages
set -euo pipefail

REPO_DIR="/Users/kyonguo/web3-daily"
OBSIDIAN_DIR="/Users/kyonguo/Library/Mobile Documents/iCloud~md~obsidian/Documents/kyons_vault/tech/web3/diary"
TODAY=$(date '+%Y-%m-%d')

cd "$REPO_DIR"

# 检查当日 HTML 是否存在
HTML_FILE="${OBSIDIAN_DIR}/${TODAY}-Web3-Daily.html"
if [ ! -f "$HTML_FILE" ]; then
  echo "ERROR: HTML not found: $HTML_FILE"
  EXISTING=$(ls -t "$OBSIDIAN_DIR"/*-Web3-Daily.html 2>/dev/null | head -1)
  if [ -n "$EXISTING" ]; then
    echo "Falling back to latest: $(basename "$EXISTING")"
    HTML_FILE="$EXISTING"
    TODAY=$(basename "$EXISTING" | sed 's/-Web3-Daily.html//')
  else
    echo "ERROR: No HTML files found in Obsidian vault"
    exit 1
  fi
fi

SIZE=$(stat -f%z "$HTML_FILE" 2>/dev/null || stat -c%s "$HTML_FILE" 2>/dev/null)
if [ "$SIZE" -eq 0 ]; then
  echo "ERROR: HTML file is empty"
  exit 1
fi
echo "HTML size: $(echo "scale=1; $SIZE/1024" | bc) KB"

# 1. 复制到 index.html（最新版）
cp "$HTML_FILE" "${REPO_DIR}/index.html"
echo "→ index.html updated"

# 2. 复制到 archive/（历史存档）
mkdir -p "${REPO_DIR}/archive"
ARCHIVE_FILE="archive/${TODAY}-Web3-Daily.html"
cp "$HTML_FILE" "${REPO_DIR}/${ARCHIVE_FILE}"
echo "→ ${ARCHIVE_FILE} saved"

# 3. 检查是否需要更新 README 中的最新日期
if grep -q "最新更新" README.md; then
  sed -i '' "s/最新更新：.*/最新更新：${TODAY}/" README.md
fi

# 4. Commit & Push
git add index.html archive/ "${ARCHIVE_FILE}"
# 如果 HTML 没变（同一天重复运行），也会正常 commit；用 --allow-empty 避免空提交错误
if git diff --cached --quiet; then
  echo "No changes to commit (same content as last time)"
else
  git commit -m "📰 Web3 日报 ${TODAY}"
  git push origin main
  echo "✅ Pushed to GitHub Pages"
fi
