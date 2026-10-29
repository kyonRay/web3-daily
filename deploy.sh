#!/bin/bash
# Copy today's Markdown into content/ and rebuild the Pages site.
# The Obsidian vault path is local to the machine that runs the morning job.
# Override it with WEB3_DAILY_VAULT. This script does not read or write HTML
# exports; the site renders content/*.md.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT_DIR="${WEB3_DAILY_VAULT:-/Users/kyonguo/Library/Mobile Documents/iCloud~md~obsidian/Documents/kyons_vault/tech/web3/diary}"
TODAY="$(date '+%Y-%m-%d')"

cd "$REPO_DIR"

MD=""
for candidate in \
  "$VAULT_DIR/${TODAY}-Web3-Daily.md" \
  "$VAULT_DIR/${TODAY}.md"
do
  if [[ -f "$candidate" ]]; then
    MD="$candidate"
    break
  fi
done

if [[ -z "$MD" ]]; then
  echo "ERROR: no markdown for ${TODAY} in:" >&2
  echo "  ${VAULT_DIR}" >&2
  echo "Looked for ${TODAY}-Web3-Daily.md and ${TODAY}.md" >&2
  exit 1
fi

cp "$MD" "$REPO_DIR/content/${TODAY}.md"
echo "content/${TODAY}.md <= $(basename "$MD")"

if ! python3 -c 'import markdown' >/dev/null 2>&1; then
  echo "ERROR: Python package 'markdown' is not installed." >&2
  echo "Run: python3 -m pip install -r requirements.txt" >&2
  exit 1
fi

python3 "$REPO_DIR/scripts/build.py"

git add -- content index.html feed.xml sitemap.xml 404.html assets
git add -- [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].html

if git diff --cached --quiet; then
  echo "No changes to commit"
else
  git commit -m "📰 Web3 日报 ${TODAY}"
  git push origin main
  echo "Pushed to GitHub Pages"
fi
