#!/usr/bin/env python3
"""Build the Web3 Daily static site from content/*.md.

Writes index.html, dated pages, feed.xml, sitemap.xml, 404.html, and
assets/site.css. GitHub Pages for this repo serves the repository root,
so the default output directory is the repo root.

    python3 scripts/build.py
    python3 scripts/build.py --out dist
    python3 scripts/build.py --check
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

import markdown
from markdown.extensions.toc import slugify_unicode

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
SRC = ROOT / "src"
BASE = "https://kyonray.github.io/web3-daily"
DATE_FILE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-.+)?\.md$")
SUMMARY_KEYS = ("本期概要", "今日重点", "重点速览", "今日摘要")
WEEK_FULL = "一二三四五六日"
EN_WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
EN_MO = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def weekday_cn(d: date) -> str:
    return "星期" + WEEK_FULL[d.weekday()]


def rfc2822(d: date) -> str:
    return f"{EN_WD[d.weekday()]}, {d.day:02d} {EN_MO[d.month - 1]} {d.year} 00:00:00 +0800"


def split_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + 5 :]
    if body.startswith("\n"):
        body = body[1:]
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = json.loads(value)
        meta[key.strip()] = value
    return meta, body


class BlockParser(HTMLParser):
    """Collect heading, paragraph, and list-item text in document order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, str]] = []
        self._stack: list[str] = []
        self._buf: list[list[str]] = []
        self._ignore = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._ignore += 1
            return
        if tag in {"h1", "h2", "h3", "h4", "p", "li"}:
            self._stack.append(tag)
            self._buf.append([])

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignore:
            self._ignore -= 1
            return
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
            text = re.sub(r"\s+", " ", "".join(self._buf.pop())).strip()
            if text:
                kind = "h" if tag.startswith("h") else tag
                self.blocks.append((kind, text))

    def handle_data(self, data: str) -> None:
        if self._ignore or not self._buf:
            return
        self._buf[-1].append(data)


def excerpt_from_html(fragment: str, limit: int = 220) -> str:
    parser = BlockParser()
    parser.feed(fragment)
    chunks: list[str] = []
    capture = False
    for kind, text in parser.blocks:
        if kind == "h":
            if capture:
                break
            if any(key in text for key in SUMMARY_KEYS):
                capture = True
            continue
        if capture and kind in {"p", "li"}:
            chunks.append(text)
            if sum(len(part) for part in chunks) >= limit:
                break
    if not chunks:
        for kind, text in parser.blocks:
            if kind != "p" or len(text) < 40:
                continue
            if text.startswith(("本日报", "本报告", "📰")) or "精选全球" in text[:24]:
                continue
            chunks.append(text)
            break
    if not chunks:
        for kind, text in parser.blocks:
            if kind in {"p", "li"} and len(text) >= 12:
                chunks.append(text)
                break
    text = re.sub(r"\s+", " ", " ".join(chunks)).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for mark in "。！？；":
        idx = cut.rfind(mark)
        if idx >= int(limit * 0.55):
            return cut[: idx + 1]
    return cut.rstrip() + "…"


def flatten_toc(tokens: list[dict]) -> list[dict]:
    out: list[dict] = []
    for token in tokens:
        out.append(token)
        out.extend(flatten_toc(token.get("children") or []))
    return out


def render_markdown(body: str) -> tuple[str, list[dict]]:
    engine = markdown.Markdown(
        extensions=["tables", "fenced_code", "sane_lists", "toc"],
        extension_configs={
            "toc": {
                "slugify": slugify_unicode,
                "toc_depth": 3,
                "marker": "[[[TOC-DISABLED]]]",
                "permalink": False,
            }
        },
        output_format="html",
    )
    rendered = engine.convert(body)
    tokens = list(getattr(engine, "toc_tokens", []) or [])
    return rendered, tokens


def strip_duplicate_title(fragment: str, title: str) -> str:
    match = re.match(r"\s*<h([12])[^>]*>(.*?)</h\1>", fragment, re.S)
    if not match:
        return fragment
    text = re.sub(r"<[^>]+>", "", match.group(2))
    text = re.sub(r"\s+", "", html.unescape(text))
    if text == re.sub(r"\s+", "", title):
        return fragment[match.end() :].lstrip()
    return fragment


def decorate(fragment: str) -> str:
    fragment = re.sub(
        r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>",
        "",
        fragment,
        flags=re.I | re.S,
    )
    fragment = re.sub(r"\shref=(['\"])\s*javascript:[^'\"]*\1", ' href="#"', fragment, flags=re.I)
    fragment = fragment.replace("<table>", '<div class="table-wrap" tabindex="0"><table>')
    fragment = fragment.replace("</table>", "</table></div>")
    fragment = re.sub(
        r"评分：(\d+(?:\.\d+)?)/10",
        r'<span class="score">评分 \1/10</span>',
        fragment,
    )
    return fragment


def render_toc(tokens: list[dict], fragment: str) -> str:
    items = []
    for token in flatten_toc(tokens):
        anchor = token.get("id") or ""
        name = re.sub(r"<[^>]+>", "", html.unescape(token.get("name") or ""))
        name = re.sub(r"\s+", " ", name).strip()
        level = int(token.get("level") or 2)
        if not anchor or not name or level > 3:
            continue
        # Drop headings removed as a duplicate title, and any id the page
        # does not actually contain.
        if f'id="{anchor}"' not in fragment:
            continue
        items.append((level, anchor, name))
    if len(items) < 3:
        return ""
    top = min(level for level, _, _ in items)
    rows = []
    for level, anchor, name in items:
        klass = "toc-l2" if level == top else "toc-l3"
        rows.append(f'<li class="{klass}"><a href="#{esc(anchor)}">{esc(name)}</a></li>')
    return (
        '<nav class="toc" aria-label="目录">'
        f'<details class="toc-details" id="toc"><summary>目录 · {len(rows)} 节</summary>'
        f"<ol>{''.join(rows)}</ol></details></nav>"
        "<script>if (window.matchMedia(\"(min-width: 900px)\").matches) {"
        'var toc = document.getElementById("toc"); if (toc) toc.open = true;}</script>'
    )


def fill(template: str, mapping: dict[str, str]) -> str:
    for key, value in mapping.items():
        template = template.replace(f"@@{key}@@", value)
    leftover = re.findall(r"@@[A-Z0-9_]+@@", template)
    if leftover:
        raise SystemExit(f"unfilled template tokens: {sorted(set(leftover))}")
    return template


@dataclass
class Issue:
    date: date
    slug: str
    title: str
    body: str
    html: str
    toc: str
    excerpt: str

    @property
    def weekday(self) -> str:
        return weekday_cn(self.date)

    @property
    def short_label(self) -> str:
        return f"{self.date.month}月{self.date.day}日"


def load_issues() -> list[Issue]:
    if not CONTENT.is_dir():
        raise SystemExit(f"missing content directory: {CONTENT}")
    paths = sorted(CONTENT.glob("*.md"))
    if not paths:
        raise SystemExit(f"no markdown in {CONTENT}")
    by_date: dict[str, Issue] = {}
    for path in paths:
        match = DATE_FILE.match(path.name)
        if not match:
            print(f"skip {path.name}: name must start with YYYY-MM-DD", file=sys.stderr)
            continue
        slug = match.group(1)
        if slug in by_date:
            raise SystemExit(f"two files for {slug}: {path.name}")
        meta, body = split_front_matter(path.read_text(encoding="utf-8"))
        day = datetime.strptime(slug, "%Y-%m-%d").date()
        title = str(meta.get("title") or f"Web3 日报｜{slug} {weekday_cn(day)}")
        rendered, tokens = render_markdown(body)
        rendered = strip_duplicate_title(rendered, title)
        rendered = decorate(rendered)
        excerpt = excerpt_from_html(rendered)
        by_date[slug] = Issue(
            date=day,
            slug=slug,
            title=title,
            body=body,
            html=rendered,
            toc=render_toc(tokens, rendered),
            excerpt=excerpt or f"Web3 日报 {slug}",
        )
    issues = sorted(by_date.values(), key=lambda item: item.slug, reverse=True)
    if not issues:
        raise SystemExit("no dated markdown files")
    return issues


def meta_tags(canonical: str, title: str, description: str, kind: str, published: str = "") -> str:
    lines = [
        f'<meta property="og:locale" content="zh_CN">',
        f'<meta property="og:type" content="{esc(kind)}">',
        f'<meta property="og:site_name" content="Web3 日报">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(description)}">',
        f'<meta property="og:url" content="{esc(canonical)}">',
        '<meta name="twitter:card" content="summary">',
    ]
    if published:
        lines.append(f'<meta property="article:published_time" content="{esc(published)}">')
    return "\n".join(lines)


def pager(older: Issue | None, newer: Issue | None) -> str:
    left = (
        f'<a class="pager-prev" href="{older.slug}.html">← {esc(older.short_label)}</a>'
        if older
        else '<span class="pager-gap"></span>'
    )
    right = (
        f'<a class="pager-next" href="{newer.slug}.html">{esc(newer.short_label)} →</a>'
        if newer
        else '<span class="pager-gap"></span>'
    )
    return f'<nav class="pager" aria-label="相邻日报">{left}{right}</nav>'


def page(shell: str, title: str, description: str, canonical: str, meta: str, main: str, extra: str) -> str:
    doc = fill(
        shell,
        {
            "TITLE": esc(title),
            "DESCRIPTION": esc(description),
            "CANONICAL": esc(canonical),
            "META": meta,
            "MAIN": main,
            "EXTRA": extra,
        },
    )
    note = "<!-- Generated by scripts/build.py from content/*.md. Edit the Markdown, then rebuild. -->\n"
    if doc.startswith("<!DOCTYPE html>\n"):
        return "<!DOCTYPE html>\n" + note + doc[len("<!DOCTYPE html>\n") :]
    return note + doc


SEARCH_JS = """
  var input = document.getElementById("q");
  if (input) {
    var items = Array.prototype.slice.call(document.querySelectorAll("[data-day]"));
    var months = Array.prototype.slice.call(document.querySelectorAll("[data-month]"));
    var hero = document.getElementById("hero");
    var status = document.getElementById("search-status");
    var empty = document.getElementById("empty");
    var apply = function () {
      var q = input.value.trim().toLowerCase();
      var n = 0;
      items.forEach(function (el) {
        var hay = (el.getAttribute("data-search") || "").toLowerCase();
        var show = !q || hay.indexOf(q) !== -1;
        el.hidden = !show;
        if (show) n += 1;
      });
      months.forEach(function (month) {
        month.hidden = !month.querySelector("[data-day]:not([hidden])");
      });
      if (hero) hero.hidden = !!q;
      if (empty) empty.hidden = n !== 0;
      if (status) status.textContent = q ? ("找到 " + n + " 期") : "";
    };
    input.addEventListener("input", apply);
  }
"""


def render_index(issues: list[Issue]) -> str:
    latest = issues[0]
    span = f"{issues[-1].slug} 至 {issues[0].slug}"
    hero = f"""
<article class="hero" id="hero">
  <p class="eyebrow"><span class="chip">最新</span> {esc(latest.slug)} · {esc(latest.weekday)}</p>
  <h2><a href="{latest.slug}.html">{esc(latest.title)}</a></h2>
  <p class="hero-excerpt">{esc(latest.excerpt)}</p>
  <a class="read" href="{latest.slug}.html">阅读本期</a>
</article>
"""
    groups: list[str] = []
    current = ""
    bucket: list[str] = []

    def flush() -> None:
        nonlocal bucket, current
        if not current:
            return
        groups.append(
            f'<section class="month" data-month="{esc(current)}">'
            f"<h2>{esc(current)}</h2><ul class=\"days\">{''.join(bucket)}</ul></section>"
        )
        bucket = []

    for index, issue in enumerate(issues):
        month = f"{issue.date.year}年{issue.date.month}月"
        if month != current:
            flush()
            current = month
        chip = '<span class="chip">最新</span>' if index == 0 else ""
        hay = f"{issue.slug} {issue.weekday} {issue.title} {issue.excerpt}"
        bucket.append(
            "<li data-day "
            f'data-search="{esc(hay)}">'
            f'<a class="day" href="{issue.slug}.html">'
            '<span class="day-top">'
            f'<span class="day-date">{esc(issue.slug)}</span>'
            f'<span class="day-wd">{esc(issue.weekday)}</span>'
            f"{chip}</span>"
            f'<span class="excerpt">{esc(issue.excerpt)}</span>'
            "</a></li>"
        )
    flush()
    return f"""
<p class="eyebrow">Web3 Daily</p>
<h1 class="entry-title">Web3 日报</h1>
<p class="lede">每日精选全球 Web3 与宏观财经资讯</p>
<p class="lede lede-meta">共 {len(issues)} 期 · {esc(span)}</p>
{hero}
<label class="search" for="q"><span class="sr-only">搜索日报</span>
<input id="q" type="search" placeholder="搜索日期或摘要" autocomplete="off" enterkeyhint="search">
</label>
<p class="search-status" id="search-status" aria-live="polite"></p>
{''.join(groups)}
<p class="empty" id="empty" hidden>没有匹配的日报。</p>
"""


def render_day(issue: Issue, older: Issue | None, newer: Issue | None) -> str:
    nav = pager(older, newer)
    return f"""
<p class="kicker"><a href="index.html">全部日报</a> · <time datetime="{issue.slug}">{esc(issue.slug)}</time> · {esc(issue.weekday)}</p>
<h1 class="entry-title">{esc(issue.title)}</h1>
{nav}
{issue.toc}
<article class="article">
{issue.html}
</article>
{nav}
"""


def render_404() -> str:
    return """
<p class="eyebrow">404</p>
<h1 class="entry-title">没有这一期</h1>
<p>这个地址不在档案里。回到 <a href="index.html">目录</a> 可以按日期找到已发布的日报。</p>
"""


def render_feed(issues: list[Issue]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "  <channel>",
        "    <title>Web3 日报</title>",
        f"    <link>{BASE}/</link>",
        "    <description>每日精选全球 Web3 与宏观财经资讯</description>",
        "    <language>zh-cn</language>",
        f'    <atom:link href="{BASE}/feed.xml" rel="self" type="application/rss+xml"/>',
        f"    <lastBuildDate>{rfc2822(issues[0].date)}</lastBuildDate>",
    ]
    for issue in issues:
        url = f"{BASE}/{issue.slug}.html"
        title = f"Web3 日报｜{issue.slug} {issue.weekday}"
        lines.extend(
            [
                "    <item>",
                f"      <title>{esc(title)}</title>",
                f"      <link>{esc(url)}</link>",
                f'      <guid isPermaLink="true">{esc(url)}</guid>',
                f"      <pubDate>{rfc2822(issue.date)}</pubDate>",
                f"      <description>{esc(issue.excerpt)}</description>",
                "    </item>",
            ]
        )
    lines.extend(["  </channel>", "</rss>", ""])
    return "\n".join(lines)


def render_sitemap(issues: list[Issue]) -> str:
    rows = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        "  <url>",
        f"    <loc>{BASE}/</loc>",
        f"    <lastmod>{issues[0].slug}</lastmod>",
        "  </url>",
    ]
    for issue in issues:
        rows.extend(
            [
                "  <url>",
                f"    <loc>{BASE}/{issue.slug}.html</loc>",
                f"    <lastmod>{issue.slug}</lastmod>",
                "  </url>",
            ]
        )
    rows.extend(["</urlset>", ""])
    return "\n".join(rows)


def build(out: Path, issues: list[Issue]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    shell = (SRC / "templates" / "shell.html").read_text(encoding="utf-8")
    shutil.copyfile(SRC / "assets" / "site.css", assets / "site.css")

    index_desc = f"每日精选全球 Web3 与宏观财经资讯，共 {len(issues)} 期。最新：{issues[0].slug}。"
    index_html = page(
        shell,
        "Web3 日报",
        index_desc,
        f"{BASE}/",
        meta_tags(f"{BASE}/", "Web3 日报", index_desc, "website"),
        render_index(issues),
        SEARCH_JS,
    )
    (out / "index.html").write_text(index_html, encoding="utf-8")
    missing = page(
        shell,
        "没有这一期 · Web3 日报",
        "这个地址不在 Web3 日报档案里。",
        f"{BASE}/404.html",
        meta_tags(f"{BASE}/404.html", "没有这一期", "这个地址不在 Web3 日报档案里。", "website"),
        render_404(),
        "",
    )
    (out / "404.html").write_text(missing, encoding="utf-8")
    (out / "feed.xml").write_text(render_feed(issues), encoding="utf-8")
    (out / "sitemap.xml").write_text(render_sitemap(issues), encoding="utf-8")

    slugs = set()
    for index, issue in enumerate(issues):
        slugs.add(issue.slug)
        older = issues[index + 1] if index + 1 < len(issues) else None
        newer = issues[index - 1] if index > 0 else None
        published = f"{issue.slug}T00:00:00+08:00"
        doc = page(
            shell,
            f"{issue.title} · Web3 日报" if "日报" not in issue.title else issue.title,
            issue.excerpt,
            f"{BASE}/{issue.slug}.html",
            meta_tags(f"{BASE}/{issue.slug}.html", issue.title, issue.excerpt, "article", published),
            render_day(issue, older, newer),
            "",
        )
        (out / f"{issue.slug}.html").write_text(doc, encoding="utf-8")

    for stale in out.glob("????-??-??.html"):
        if stale.stem not in slugs:
            stale.unlink()

    css = (assets / "site.css").read_text(encoding="utf-8")
    if "word-break: break-all" in css or "word-break:break-all" in css:
        raise SystemExit("site.css still uses word-break: break-all")
    sample = (out / f"{issues[0].slug}.html").read_text(encoding="utf-8")
    for needle in ("<!DOCTYPE html>", 'name="viewport"', "assets/site.css", "<article"):
        if needle not in sample:
            raise SystemExit(f"day page missing {needle}")
    if issues[0].slug not in (out / "feed.xml").read_text(encoding="utf-8"):
        raise SystemExit("feed.xml missing the latest issue")


def check_against_root(issues: list[Issue]) -> int:
    with tempfile.TemporaryDirectory(prefix="web3-daily-") as tmp:
        dest = Path(tmp)
        build(dest, issues)
        diffs: list[str] = []
        produced = [p for p in dest.rglob("*") if p.is_file()]
        for path in produced:
            rel = path.relative_to(dest)
            committed = ROOT / rel
            if not committed.is_file() or committed.read_bytes() != path.read_bytes():
                diffs.append(str(rel))
        for committed in ROOT.glob("????-??-??.html"):
            if not (dest / committed.name).is_file():
                diffs.append(committed.name + " (stale)")
        if diffs:
            print("build is out of date:", file=sys.stderr)
            for name in diffs[:30]:
                print(f"  {name}", file=sys.stderr)
            if len(diffs) > 30:
                print(f"  … {len(diffs) - 30} more", file=sys.stderr)
            print("run: python3 scripts/build.py", file=sys.stderr)
            return 1
    print(f"check ok — {len(issues)} days match the committed site")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT, help="output directory (default: repo root)")
    parser.add_argument("--check", action="store_true", help="rebuild in a temp dir and diff against the repo root")
    args = parser.parse_args()
    issues = load_issues()
    if args.check:
        return check_against_root(issues)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    build(out, issues)
    print(f"built {len(issues)} days → {out}")
    print(f"latest {issues[0].slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
