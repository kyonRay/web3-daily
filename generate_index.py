#!/usr/bin/env python3
"""Generate index.html — archives listing for Web3 Daily reports."""
import os, re
from datetime import datetime

REPO_DIR = "/Users/kyonguo/web3-daily"
INDEX_PATH = os.path.join(REPO_DIR, "index.html")

def get_reports():
    """Scan repo for YYYY-MM-DD.html files, return sorted list."""
    reports = []
    pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")
    for f in os.listdir(REPO_DIR):
        m = pattern.match(f)
        if m:
            dt = datetime.strptime(m.group(1), "%Y-%m-%d")
            reports.append((dt, m.group(1)))
    reports.sort(key=lambda x: x[1], reverse=True)
    return reports

def weekday_cn(dt):
    weekdays = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"]
    return weekdays[dt.weekday()]

def generate_index(reports):
    latest = reports[0][1] if reports else "——"
    lines = []

    lines.append(f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Web3 日报档案馆</title>
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
  .report-tag {{
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 8px;
    background: #f0eee6;
    color: #555;
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
    .report-tag {{ background: #333; color: #aaa; }}
    .subtitle {{ color: #999; }}
    footer {{ border-top-color: #333; }}
  }}
</style>
</head>
<body>
<h1>📰 Web3 日报</h1>
<p class="subtitle">每日精选全球 Web3 与宏观财经资讯 · 共 {len(reports)} 期</p>

<ul class="report-list">''')

    for dt, date_str in reports:
        wd = weekday_cn(dt)
        tag = "<span class=\"latest-badge\">最新</span>" if date_str == latest else ""
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
    if reports:
        print(f"   Latest: {reports[0][1]}")
