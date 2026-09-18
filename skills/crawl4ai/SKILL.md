---
name: crawl4ai
description: 把網頁抓成 LLM-ready markdown（單頁／深爬多頁／LLM 抽取）。研究外部文件、抓 API docs、收集 RAG 素材、WebFetch 啃不動的 JS 渲染頁時使用。Mike 說「爬」「抓網頁」「crawl」時使用。
---

# /crawl4ai — 網頁轉 LLM-ready markdown

工具本體：[crawl4ai](https://github.com/unclecode/crawl4AI)（2026-08-31 裝，v0.9.2），`uv tool install` 隔離環境（Python 3.12），CLI 在 `~/.local/bin/crwl`（已在 PATH）。真瀏覽器渲染（Patchright chromium），JS 頁面吃得動。

## 與其他工具的分工

| 需求                                              | 用什麼                                                               |
| ------------------------------------------------- | -------------------------------------------------------------------- |
| 單頁快答、有 prompt 要問                          | **WebFetch**（內建，最便宜）                                         |
| JS 渲染頁、要乾淨 markdown 全文、深爬多頁、批次抓 | **本 skill（crwl）**                                                 |
| 對頁面互動（點擊、表單、登入流程、測試）          | **playwright-cli**（唯一依據 /browser-tools） |

## 用法

```bash
# 單頁 → markdown（stdout，可重導向存檔）
crwl <url> -o markdown

# 深爬：BFS 順連結抓多頁（務必設上限）
crwl <url> --deep-crawl bfs --max-pages 10

# LLM 抽取：對頁面問問題（需 LLM key，用前先確認環境有配）
crwl <url> -q "Extract all product prices"
```

Python API（進階場景：自訂 filter、批次、結構化抽取）：

```bash
uv tool run --from crawl4ai python -c "
import asyncio
from crawl4ai import AsyncWebCrawler
async def main():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url='<url>')
        print(result.markdown)
asyncio.run(main())
"
```

## 紀律

- **只讀不寫**：本 skill 是讀取工具，抓公開頁面；不碰需登入態的頁（要登入態的互動走 playwright-cli＋測試帳號 storage state）。
- **深爬必設 `--max-pages`**，不設上限的深爬 = 對人家站台掃射，也炸自己 token。
- 抓下來的 markdown 屬中間產物：存 scratchpad 或 `/tmp`，不進專案 repo；要留存的研究產出走 /research 的落檔規範。
- 大量抓取前想一下 robots／頻率禮貌；同站連抓加延遲。
- 疑難排解：`crawl4ai-doctor`；瀏覽器壞了重跑 `crawl4ai-setup`。升級：`uv tool upgrade crawl4ai`。
