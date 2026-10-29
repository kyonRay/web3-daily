#!/usr/bin/env python3
"""Convert legacy mdnice / 橘鸦 HTML exports into content Markdown.

The historical pages lived at the repo root as ``YYYY-MM-DD.html``. They are
WeChat-oriented HTML fragments (heavy inline CSS, wrapper ``section``/``span``
tags, no document skeleton). This module walks that HTML and emits Markdown
that ``scripts/build.py`` can render.

Run from the repo root:

    python3 scripts/html_to_md.py
    python3 scripts/html_to_md.py --src . --out content
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parents[1]
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")
JUNK_RE = re.compile(r"^created:\s*20\d{2}-\d{2}-\d{2}", re.I)
BLOCK_TAGS = {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "ul",
    "ol",
    "table",
    "blockquote",
    "hr",
    "pre",
    "div",
    "section",
}
TRANSPARENT = {"div", "section", "span", "font"}


def norm_inline(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text)


def escape_text(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace("*", r"\*")
    text = text.replace("_", r"\_")
    text = text.replace("`", r"\`")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def tighten(text: str) -> str:
    text = re.sub(r"[ ]{2,}(?!\n)", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text


def is_real_email(href: str) -> bool:
    if not href.lower().startswith("mailto:"):
        return False
    addr = href.split(":", 1)[1].split("?")[0]
    if "@" not in addr:
        return False
    domain = addr.rsplit("@", 1)[1]
    # mdnice turned package specs like hardhat-ignition@3.1.2 into mailto links.
    if re.fullmatch(r"[\d.]+", domain):
        return False
    return "." in domain and not domain.startswith(".")


def code_span(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\n", " ")
    fence = "`"
    while fence in text:
        fence += "`"
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def has_block_child(tag: Tag) -> bool:
    for child in tag.children:
        if not isinstance(child, Tag):
            continue
        if child.name in TRANSPARENT:
            if has_block_child(child):
                return True
            continue
        if child.name in BLOCK_TAGS or child.name in {"ul", "ol", "table", "blockquote", "hr", "pre"}:
            return True
        if child.name and child.name[0] == "h" and child.name[1:2].isdigit():
            return True
    return False


class Converter:
    def __init__(self) -> None:
        self.unexpected: set[str] = set()

    def render_link(self, tag: Tag) -> str:
        href = (tag.get("href") or "").strip()
        inner = tighten("".join(self.render_inline(c) for c in tag.children)).strip()
        if href.lower().startswith("mailto:") and not is_real_email(href):
            return inner or escape_text(href.split(":", 1)[1])
        if not href:
            return inner
        href = href.replace(" ", "%20").replace("|", "%7C")
        text = inner or escape_text(href)
        # Labels copied from the old export often include square brackets
        # ("[Bloomberg]"). Escape them so they stay visible instead of
        # becoming another link wrapper.
        text = text.replace("[", r"\[").replace("]", r"\]")
        if href.count(")") != href.count("(") or " " in href:
            href = f"<{href}>"
        return f"[{text}]({href})"

    def render_inline(self, node) -> str:
        if isinstance(node, NavigableString):
            return escape_text(norm_inline(str(node)))
        if not isinstance(node, Tag):
            return ""
        name = node.name
        if name in ("strong", "b"):
            inner = tighten("".join(self.render_inline(c) for c in node.children)).strip()
            return f"**{inner}**" if inner else ""
        if name in ("em", "i"):
            inner = tighten("".join(self.render_inline(c) for c in node.children)).strip()
            return f"*{inner}*" if inner else ""
        if name == "del":
            inner = html.escape(norm_inline(node.get_text()).strip(), quote=False)
            return f"<del>{inner}</del>" if inner else ""
        if name == "code":
            return code_span(node.get_text())
        if name == "a":
            return self.render_link(node)
        if name == "br":
            return "  \n"
        if name in TRANSPARENT or name == "p":
            return "".join(self.render_inline(c) for c in node.children)
        self.unexpected.add(name)
        return "".join(self.render_inline(c) for c in node.children)

    def render_table(self, table: Tag) -> str:
        def cells(tr: Tag) -> list[str]:
            out = []
            for cell in tr.find_all(["th", "td"], recursive=False):
                text = tighten("".join(self.render_inline(c) for c in cell.children))
                text = text.replace("\n", " ").replace("|", r"\|").strip()
                out.append(text or " ")
            return out

        header: list[str] = []
        body: list[list[str]] = []
        thead = table.find("thead", recursive=False)
        if thead:
            rows = thead.find_all("tr", recursive=False)
            if rows:
                header = cells(rows[0])
                for extra in rows[1:]:
                    body.append(cells(extra))
        for child in table.children:
            if not isinstance(child, Tag):
                continue
            if child.name == "tr":
                body.append(cells(child))
            elif child.name == "tbody":
                for tr in child.find_all("tr", recursive=False):
                    body.append(cells(tr))
        if not header and body:
            header = body.pop(0)
        if not header:
            return ""
        width = max([len(header)] + [len(row) for row in body] or [0])
        def pad(row: list[str]) -> list[str]:
            return row + [" "] * (width - len(row))

        header = pad(header)
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(["---"] * width) + " |",
        ]
        for row in body:
            lines.append("| " + " | ".join(pad(row)) + " |")
        return "\n".join(lines)

    def render_list(self, lst: Tag, indent: int = 0) -> str:
        bullet = "-" if lst.name != "ol" else None
        lines: list[str] = []
        index = 1
        pad = "  " * indent
        for li in lst.find_all("li", recursive=False):
            text, nested = self.render_li_parts(li)
            marker = f"{index}." if bullet is None else bullet
            index += 1
            lines.append(f"{pad}{marker} {text}".rstrip())
            if nested:
                lines.append(nested)
        return "\n".join(lines)

    def render_li_parts(self, li: Tag) -> tuple[str, str]:
        inline_bits: list[str] = []
        nested: list[str] = []
        for child in li.children:
            if isinstance(child, NavigableString):
                inline_bits.append(self.render_inline(child))
                continue
            if not isinstance(child, Tag):
                continue
            if child.name in ("ul", "ol"):
                nested.append(self.render_list(child, indent=1))
                continue
            if child.name in TRANSPARENT and has_block_child(child):
                # A wrapper that itself contains a list or other blocks.
                for grand in child.children:
                    if isinstance(grand, Tag) and grand.name in ("ul", "ol"):
                        nested.append(self.render_list(grand, indent=1))
                    else:
                        inline_bits.append(self.render_inline(grand))
                continue
            inline_bits.append(self.render_inline(child))
        text = tighten("".join(inline_bits)).strip()
        text = text.replace("\n", " ")
        return text, "\n".join(nested)

    def render_blockquote(self, tag: Tag) -> str:
        blocks = self.render_children(tag)
        if not blocks:
            inline = tighten("".join(self.render_inline(c) for c in tag.children)).strip()
            blocks = [inline] if inline else []
        quoted: list[str] = []
        for block in blocks:
            for line in block.splitlines() or [""]:
                quoted.append("> " + line if line else ">")
            quoted.append(">")
        while quoted and quoted[-1] == ">":
            quoted.pop()
        return "\n".join(quoted)

    def render_block(self, tag: Tag) -> str:
        name = tag.name
        if name in TRANSPARENT:
            if has_block_child(tag):
                return "\n\n".join(self.render_children(tag))
            text = tighten("".join(self.render_inline(c) for c in tag.children)).strip()
            return text
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(name[1])
            text = tighten("".join(self.render_inline(c) for c in tag.children)).strip()
            text = re.sub(r"\s+", " ", text)
            if not text or JUNK_RE.match(text):
                return ""
            return f"{'#' * level} {text}"
        if name == "p":
            text = tighten("".join(self.render_inline(c) for c in tag.children)).strip()
            if not text or JUNK_RE.match(re.sub(r"\s+", " ", text)):
                return ""
            if re.match(r"\d+\. ", text):
                text = re.sub(r"^(\d+)\. ", r"\1\\. ", text)
            return text
        if name in ("ul", "ol"):
            return self.render_list(tag)
        if name == "table":
            return self.render_table(tag)
        if name == "blockquote":
            return self.render_blockquote(tag)
        if name == "hr":
            return "---"
        if name == "pre":
            code = tag.find("code")
            body = (code.get_text() if code else tag.get_text()).replace("\n", "\n")
            fence = "```"
            return f"{fence}\n{body.rstrip()}\n{fence}"
        self.unexpected.add(name)
        return ""

    def render_children(self, parent: Tag) -> list[str]:
        blocks: list[str] = []
        for child in parent.children:
            if isinstance(child, NavigableString):
                if child.strip():
                    blocks.append(escape_text(norm_inline(str(child)).strip()))
                continue
            if isinstance(child, Tag):
                rendered = self.render_block(child)
                if rendered.strip():
                    blocks.append(rendered.strip())
        return blocks

    def convert_soup(self, soup: BeautifulSoup) -> str:
        root = soup.find("div") or soup.body or soup
        blocks = self.render_children(root)
        # Drop a decorative rule that mdnice sometimes emits before the title.
        while blocks and blocks[0] == "---":
            blocks.pop(0)
        text = "\n\n".join(blocks).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text + "\n"


def first_heading(markdown: str) -> str:
    for line in markdown.splitlines():
        m = re.match(r"^#{1,6}\s+(.+)$", line)
        if m:
            title = re.sub(r"\\([\\*_`])", r"\1", m.group(1))
            title = re.sub(r"\s+", " ", title).strip()
            if title and not JUNK_RE.match(title):
                return title
    return ""


def weekday_cn(date: str) -> str:
    dt = datetime.strptime(date, "%Y-%m-%d")
    return "星期" + "一二三四五六日"[dt.weekday()]


def to_document(date: str, body: str) -> str:
    title = first_heading(body)
    # Early exports used a generic H1 and left the date in a paragraph.
    # Give those a stable, bookmark-friendly title.
    if not title or date not in title:
        title = f"Web3 日报｜{date} {weekday_cn(date)}"
    fm = "---\n" f"date: {date}\n" f"title: {json.dumps(title, ensure_ascii=False)}\n" "---\n\n"
    return fm + body


def convert_file(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    textish = re.sub(r"<[^>]+>", "", raw)
    textish = re.sub(r"\s+", "", textish)
    if len(textish) < 20:
        date = path.stem
        body = (
            "这一期的历史导出是空文件，没有正文可以恢复。"
            "日期仍留在目录里，避免归档出现缺口。\n"
        )
        return to_document(date, body)
    soup = BeautifulSoup(raw, "html.parser")
    conv = Converter()
    body = conv.convert_soup(soup)
    if conv.unexpected:
        print(f"  unexpected tags in {path.name}: {sorted(conv.unexpected)}", file=sys.stderr)
    return to_document(path.stem, body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=ROOT, help="directory of YYYY-MM-DD.html")
    parser.add_argument("--out", type=Path, default=ROOT / "content", help="markdown output directory")
    args = parser.parse_args()
    src = args.src
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in src.iterdir() if DATE_RE.match(p.name))
    if not files:
        print(f"no dated HTML in {src}", file=sys.stderr)
        return 1
    built = []
    for path in files:
        head = path.read_text(encoding="utf-8", errors="replace")[:300].lstrip().lower()
        if head.startswith("<!doctype"):
            built.append(path.name)
    if built:
        print(
            "refusing to convert: these files are already built pages, not legacy exports:\n  "
            + "\n  ".join(built[:8]),
            file=sys.stderr,
        )
        print("content/*.md is the source of truth. Edit that and run scripts/build.py.", file=sys.stderr)
        return 2
    for path in files:
        doc = convert_file(path)
        target = out / f"{path.stem}.md"
        target.write_text(doc, encoding="utf-8")
    print(f"wrote {len(files)} markdown files to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
