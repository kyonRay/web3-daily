#!/bin/bash
# Web3 Daily — 部署脚本
# 将当日 HTML 部署为 YYYY-MM-DD.html，然后重新生成 index.html 目录页
set -euo pipefail

REPO_DIR="/Users/kyonguo/web3-daily"
OBSIDIAN_DIR="/Users/kyonguo/Library/Mobile Documents/iCloud~md~obsidian/Documents/kyons_vault/tech/web3/diary"
TODAY=$(date '+%Y-%m-%d')

cd "$REPO_DIR"

# ── 1. 找到当日 HTML ──
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

SIZE=$(stat -f%z "$HTML_FILE" 2>/dev/null)
if [ "$SIZE" -eq 0 ]; then
  echo "ERROR: HTML file is empty"
  exit 1
fi
echo "HTML: ${TODAY}.html ($(echo "scale=1; $SIZE/1024" | bc) KB)"

# ── 2. 部署为独立页面 ──
cp "$HTML_FILE" "${REPO_DIR}/${TODAY}.html"
echo "→ ${TODAY}.html saved"

# ── 3. 生成目录页 ──
/usr/bin/env python3 "${REPO_DIR}/generate_index.py"

# ── 4. Commit & Push ──
git add "${TODAY}.html" index.html

if git diff --cached --quiet; then
  echo "No changes to commit (same content as last time)"
else
  git commit -m "📰 Web3 日报 ${TODAY}"
  git push origin main
  echo "✅ Pushed to GitHub Pages"
fi
