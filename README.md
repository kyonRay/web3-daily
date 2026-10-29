# Web3 日报

每天一篇 Markdown，构建成适合手机和桌面阅读的静态页，由 GitHub Pages 发布在 [kyonray.github.io/web3-daily](https://kyonray.github.io/web3-daily/)。

## 目录

| 路径 | 作用 |
| --- | --- |
| `content/YYYY-MM-DD.md` | 当日源稿，这是要编辑的文件 |
| `src/templates/shell.html` | 页面骨架 |
| `src/assets/site.css` | 样式（浅色 / 深色、手机优先） |
| `scripts/build.py` | 把 Markdown 渲染成静态站 |
| `scripts/html_to_md.py` | 把旧的橘鸦 HTML 迁成 Markdown 的一次性脚本，已经跑完 |
| `index.html`、`YYYY-MM-DD.html`、`feed.xml`、`sitemap.xml`、`assets/` | 构建结果。Pages 从 `main` 的根目录发布，所以这些文件要提交，不要手改 |

根目录的 `.nojekyll` 让 Pages 按原样发布，不会用 Jekyll 去编译 `content/`。

## 加今天的稿

上游文件名类似 `2026-10-29-Web3-Daily.md`。放进仓库时用日期做文件名：

```bash
cp /path/to/2026-10-29-Web3-Daily.md content/2026-10-29.md
python3 -m pip install -r requirements.txt   # 只需一次
python3 scripts/build.py
```

`content/` 里也可以直接放 `2026-10-29-Web3-Daily.md`，构建脚本会认出开头的日期。同一天不要放两个文件。

稿件是普通 Markdown，可选一段 front matter：

```markdown
---
date: 2026-10-29
title: "Web3 日报｜2026-10-29 星期四"
---

## 本期概要

今天的要点。

### 技术动态

正文支持 **加粗**、[链接](https://example.com)、列表和表格。
```

没有 front matter 时，标题用文件名里的日期。`### 本期概要`（或「今日重点」）后面的第一段会变成目录摘要和 RSS 描述。

构建完成后提交 `content/` 里的新稿，以及重新生成的 `index.html`、`feed.xml`、`sitemap.xml` 和对应的 `YYYY-MM-DD.html`。相邻日期的「前一天 / 后一天」链接也会变，那一页需要一起提交。

本机早上的任务可以继续跑仓库里的 `deploy.sh`。它从日记目录复制当天的 `.md`（不再复制 HTML），然后构建并推到 `main`。日记目录默认仍是原来的 Obsidian 路径，可以用环境变量 `WEB3_DAILY_VAULT` 覆盖。

## 本地预览

```bash
python3 scripts/build.py
python3 -m http.server 8000
```

打开 <http://127.0.0.1:8000/> 。日期页是 `http://127.0.0.1:8000/2026-10-29.html`。

`python3 scripts/build.py --check` 会在临时目录重编，并和已提交的页面逐字节比较。拉请求上的 CI 跑的就是这一步。

## 部署

GitHub Pages 当前从 `main` 分支的根目录发布。合并到 `main` 后沿用这个设置即可，不用改成 `/docs` 或 Actions。

线上地址保持不变：

- 目录：`https://kyonray.github.io/web3-daily/`
- 某一天：`https://kyonray.github.io/web3-daily/2026-10-29.html`
- RSS：`https://kyonray.github.io/web3-daily/feed.xml`

RSS 的 `<guid>` 仍是原来的 `YYYY-MM-DD.html` 绝对地址，已有订阅不会因为这次改版被当成新文章。

## 历史稿

仓库里原先的 `YYYY-MM-DD.html` 是橘鸦（mdnice）导出的微信 HTML，没有完整文档结构，样式也全写在行内。这些页面已经抽成 `content/*.md`，再渲染成现在的阅读页。正文、链接和表格都保留了。

`2026-04-21` 的历史导出是空文件，目录里仍留着这一天，页面上说明没有可恢复的正文。
