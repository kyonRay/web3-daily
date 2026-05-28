#!/usr/bin/env python3
"""Generate index.html + feed.xml for Web3 Daily archives."""
import os, re, html as html_mod
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser

REPO_DIR = "/Users/kyonguo/web3-daily"
INDEX_PATH = os.path.join(REPO_DIR, "index.html")
FEED_PATH = os.path.join(REPO_DIR, "feed.xml")
BASE_URL = "https://kyonray.github.io/web3-daily"

PAT_REPORT = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")

# ── helpers ──

def get_reports():
    reports = []
    for f in os.listdir(REPO_DIR):
        m = PAT_REPORT.match(f)
        if m:
            dt = datetime.strptime(m.group(1), "%Y-%m-%d")
            reports.append((dt, m.group(1)))
    reports.sort(key=lambda x: x[1], reverse=True)
    return reports

def weekday_cn(dt):
    return ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][dt.weekday()]

def rfc2822(date_str):
    """2026-05-28 → 'Thu, 28 May 2026 00:00:00 +0800'"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    dt = dt.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    wds = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    wd = wds[dt.weekday()]
    return f"{wd}, {dt.day:02d} {months[dt.month-1]} {dt.year} 00:00:00 +0800"

# ── extract summary from HTML ──

class SummaryExtractor(HTMLParser):
    """Extract text content between the first '本期概要' section and the next <hr>."""
    def __init__(self):
        super().__init__()
        self.in_summary = False
        self.done = False
        self.text_parts = []
        self._tag_stack = []
    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        if tag == "hr" and self.in_summary:
            self.done = True
            return
        if self.in_summary:
            self._tag_stack.append(tag)
    def handle_endtag(self, tag):
        if self.done:
            return
        if tag == "hr" and self.in_summary:
            self.done = True
            return
        if self.in_summary and self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
    def handle_data(self, data):
        if self.done:
            return
        stripped = data.strip()
        if not stripped:
            return
        # Detect "本期概要" heading — any <h3> containing these chars
        if not self.in_summary and ("本期概要" in stripped or "📖" in stripped):
            self.in_summary = True
            # Don't include the heading text itself
            return
        if self.in_summary:
            self.text_parts.append(stripped)

def extract_summary(filepath):
    """Read HTML and extract the 本期概要 section as plain text."""
    if not os.path.exists(filepath):
        return ""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    parser = SummaryExtractor()
    try:
        parser.feed(content)
    except Exception:
        return ""
    text = " ".join(parser.text_parts)
    # Clean: collapse whitespace, limit length
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 300:
        # Try to break at a sentence boundary
        text = text[:297] + "..."
    return text

# ── RSS feed generator ──

def esc(text):
    """XML-escape text."""
    return html_mod.escape(text or "", quote=True)

def generate_feed(reports):
    """Generate RSS 2.0 feed XML."""
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">')
    lines.append('  <channel>')
    lines.append(f'    <title>Web3 日报</title>')
    lines.append(f'    <link>{BASE_URL}/</link>')
    lines.append(f'    <description>每日精选全球 Web3 与宏观财经资讯，自动生成</description>')
    lines.append(f'    <language>zh-cn</language>')
    lines.append(f'    <atom:link href="{BASE_URL}/feed.xml" rel="self" type="application/rss+xml"/>')
    if reports:
        lines.append(f'    <lastBuildDate>{rfc2822(reports[0][1])}</lastBuildDate>')
    for dt, date_str in reports:
        title = f"Web3 日报｜{date_str} {weekday_cn(dt)}"
        url = f"{BASE_URL}/{date_str}.html"
        pub = rfc2822(date_str)
        # Try to extract summary
        filepath = os.path.join(REPO_DIR, f"{date_str}.html")
        summary = extract_summary(filepath)
        desc = esc(summary) if summary else f"Web3 日报 {date_str}"
        lines.append('    <item>')
        lines.append(f'      <title>{esc(title)}</title>')
        lines.append(f'      <link>{esc(url)}</link>')
        lines.append(f'      <guid isPermaLink="true">{esc(url)}</guid>')
        lines.append(f'      <pubDate>{pub}</pubDate>')
        lines.append(f'      <description>{desc}</description>')
        lines.append('    </item>')
    lines.append('  </channel>')
    lines.append('</rss>')
    return "\n".join(lines)

# ── index.html generator ──

def generate_index(reports):
    latest = reports[0][1] if reports else "——"
    lines = []
    lines.append(f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Web3 日报档案馆</title>
<link rel="alternate" type="application/rss+xml" title="Web3 日报" href="{BASE_URL}/feed.xml">
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #faf9f5;
    color: #1a1a1a;
    max-width: 720px;
    margin: 0 auto;
    padding: 40px 24px;
    line-height: 1.6;
  }}
  h1 {{
    font-size: 28px;
    font-weight: 700;
    margin-bottom: 4px;
  }}
  .subtitle {{
    color: #666;
    font-size: 14px;
    margin-bottom: 32px;
  }}
  .latest-badge {{
    display: inline-block;
    background: #a0f9b0;
    color: #1a1a1a;
    font-size: 12px;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 12px;
    margin-left: 8px;
  }}
  .rss-link {{
    display: inline-block;
    margin-left: 12px;
    font-size: 13px;
    color: #f60;
    text-decoration: none;
    font-weight: 500;
  }}
  .rss-link:hover {{
    text-decoration: underline;
  }}
  .report-list {{
    list-style: none;
    padding: 0;
    margin: 0;
  }}
  .report-list li {{
    display: flex;
    align-items: center;
    padding: 14px 16px;
    margin-bottom: 8px;
    background: #fff;
    border-radius: 10px;
    border: 1px solid #e8e6e0;
    transition: box-shadow 0.15s;
  }}
  .report-list li:hover {{
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }}
  .report-list a {{
    text-decoration: none;
    color: #1a1a1a;
    flex: 1;
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .report-date {{
    font-size: 16px;
    font-weight: 600;
    min-width: 100px;
  }}
  .report-weekday {{
    color: #888;
    font-size: 13px;
  }}
  footer {{
    margin-top: 48px;
    padding-top: 20px;
    border-top: 1px solid #e8e6e0;
    font-size: 13px;
    color: #999;
    text-align: center;
  }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #1a1a1a; color: #e0e0e0; }}
    .report-list li {{ background: #252525; border-color: #333; }}
    .report-list a {{ color: #e0e0e0; }}
    .subtitle {{ color: #999; }}
    footer {{ border-top-color: #333; }}
  }}
</style>
</head>
<body>
<h1>📰 Web3 日报</h1>
<p class="subtitle">每日精选全球 Web3 与宏观财经资讯 · 共 {len(reports)} 期
  <a class="rss-link" href="{BASE_URL}/feed.xml" title="订阅 RSS">📡 RSS</a>
</p>

<ul class="report-list">''')
    for dt, date_str in reports:
        wd = weekday_cn(dt)
        tag = '<span class="latest-badge">最新</span>' if date_str == latest else ""
        lines.append(f'''  <li>
    <a href="{date_str}.html">
      <span class="report-date">{date_str}</span>
      <span class="report-weekday">{wd}</span>
      {tag}
    </a>
  </li>''')
    lines.append(f'''</ul>

<footer>
  由 Hermes Agent 自动生成 · <a href="https://github.com/kyonRay/web3-daily" style="color:#666;">GitHub</a>
</footer>
</body>
</html>''')
    return "\n".join(lines)

if __name__ == "__main__":
    reports = get_reports()

    html = generate_index(reports)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ index.html updated — {len(reports)} reports listed")

    feed = generate_feed(reports)
    with open(FEED_PATH, "w", encoding="utf-8") as f:
        f.write(feed)
    print(f"✅ feed.xml updated — {len(reports)} items")

    if reports:
        print(f"   Latest: {reports[0][1]}")
        # Show first summary as sanity check
        summary = extract_summary(os.path.join(REPO_DIR, f"{reports[0][1]}.html"))
        if summary:
            print(f"   Summary: {summary[:80]}...")
